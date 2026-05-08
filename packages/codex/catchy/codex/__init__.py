import json
import logging
from contextlib import contextmanager
from pathlib import Path
from typing import AsyncIterator

from catchy.core.agents.protocols import Agent
from catchy.core.challenge.models import Challenge
from catchy.core.webhook.models import Webhook
from codex_app_server import (
    AppServerConfig,
    AsyncCodex,
    TextInput,
)
from codex_app_server.generated.v2_all import (
    AgentMessageDeltaNotification,
    CommandExecutionOutputDeltaNotification,
    FileChangeOutputDeltaNotification,
    ItemCompletedNotification,
    ItemStartedNotification,
    McpToolCallProgressNotification,
    PlanDeltaNotification,
    ReasoningSummaryPartAddedNotification,
    ReasoningSummaryTextDeltaNotification,
    TerminalInteractionNotification,
)
from codex_app_server.models import JsonObject
from docker import DockerClient

_LOGGER = logging.getLogger(__name__)


class CodexAgent(Agent):
    key: str = "codex"
    _dockerfile = Path(__file__).parent / "Dockerfile"

    def __init__(
        self,
        api_key: str,
        docker_client: DockerClient | None = None,
        model: str = "gpt-5.4",
        config: JsonObject = {},
    ):
        if docker_client is None:
            docker_client = DockerClient.from_env()

        self._docker_client = docker_client
        self._model = model
        self._config = config
        self._api_key = api_key
        self._id = f"agent-{self.key}-{model}-{hash(json.dumps(config, sort_keys=True)) % 10000:05d}"

        _LOGGER.info(f"({self._id}) Building Docker image from {self._dockerfile}...")
        self._docker_image, _ = self._docker_client.images.build(
            path=str(self._dockerfile.parent), dockerfile=self._dockerfile.name
        )
        _LOGGER.info(f"({self._id}) Docker image built: {self._docker_image.id}")

    async def stream(
        self, challenge: Challenge, workspace: Path, webhook: Webhook | None = None
    ) -> AsyncIterator[str]:
        if not workspace.exists():
            raise ValueError(f"workspace does not exist: {workspace}")
        if not workspace.is_dir():
            raise ValueError(f"workspace is not a directory: {workspace}")

        with self._docker_container(
            challenge=challenge, workspace=workspace
        ) as container:
            async with AsyncCodex(
                config=AppServerConfig(
                    launch_args_override=(  # pyright: ignore[reportArgumentType]
                        "docker",
                        "exec",
                        "-i",
                        container.id,
                        "codex",
                        "app-server",
                        "--listen",
                        "stdio://",
                    )
                )
            ) as codex:
                threads = (await codex.thread_list()).data

                match threads:
                    case [thread]:
                        _LOGGER.info(
                            f"({self._id})({challenge.id}) Resuming existing thread: {thread.id}"
                        )
                        thread = await codex.thread_resume(thread.id)
                    case []:
                        _LOGGER.info(
                            f"({self._id})({challenge.id}) Starting new thread"
                        )
                        thread = await codex.thread_start(
                            model=self._model, config=self._config
                        )
                    case _:
                        raise RuntimeError(
                            f"Expected at most one thread, but found {len(threads)}"
                        )

                prompt = f"""You are the best at solving CTF challenges.
Solve the challenge in /challenge and explain.

<challenge-description>{challenge.description}</challenge-description>"""

                if webhook is not None:
                    prompt += f"""When you have any findings or trial and errors to share, send them to the webhook at {webhook.url}. Prefer to send messages in {webhook.preferred_language or "English"}."""

                turn = await thread.turn(TextInput(prompt))

                item_message = ""

                async for event in turn.stream():
                    match event.payload:
                        case ItemStartedNotification():
                            item_message = ""
                        case ItemCompletedNotification():
                            if item_message.strip():
                                yield item_message
                            item_message = ""
                        case (
                            AgentMessageDeltaNotification()
                            | PlanDeltaNotification()
                            | ReasoningSummaryTextDeltaNotification()
                            | CommandExecutionOutputDeltaNotification()
                            | FileChangeOutputDeltaNotification()
                        ):
                            item_message += event.payload.delta
                        case ReasoningSummaryPartAddedNotification():
                            _LOGGER.info(
                                f"({self._id})({challenge.id}) Reasoning summary part added: {event.payload}"
                            )
                        case TerminalInteractionNotification():
                            _LOGGER.info(
                                f"({self._id})({challenge.id}) Terminal interaction: {event.payload}"
                            )
                        case McpToolCallProgressNotification():
                            _LOGGER.info(
                                f"({self._id})({challenge.id}) MCP tool call progress: {event.payload}"
                            )
                        case _:
                            # TODO: raise an error
                            ...

    @contextmanager
    def _docker_container(self, challenge: Challenge, workspace: Path):
        assert workspace.is_dir()

        container = self._docker_client.containers.run(
            self._docker_image,
            detach=True,
            stdin_open=True,
            # Codex uses bubblewrap for its Linux sandbox; Docker's default confinement blocks the user/mount namespace setup bwrap needs.
            cap_add=["SYS_ADMIN"],
            security_opt=["seccomp=unconfined", "apparmor=unconfined"],
            volumes={
                str(challenge.directory): {"bind": "/challenge", "mode": "ro"},
                str(workspace): {"bind": "/workspace", "mode": "rw"},
            },
        )

        _LOGGER.info(f"({self._id}) Started Docker container: {container.id}")

        result = container.exec_run(
            cmd=[
                "sh",
                "-c",
                f"mkdir -p /workspace/.codex && echo '{
                    json.dumps({'auth_mode': 'apikey', 'OPENAI_API_KEY': self._api_key})
                }' > /workspace/.codex/auth.json",
            ]
        )
        if result.exit_code != 0:
            logs = container.logs().decode()
            container.remove(force=True)
            raise RuntimeError(f"Failed to set up container auth file: {logs}")

        try:
            yield container
        finally:
            _LOGGER.info(
                f"({self._id}) Stopping and removing Docker container: {container.id}"
            )
            container.remove(force=True)
            _LOGGER.info(f"({self._id}) Docker container removed: {container.id}")
