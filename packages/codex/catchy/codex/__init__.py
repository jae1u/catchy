import json
from contextlib import contextmanager
from pathlib import Path

from catchy.core.agents.protocols import Agent
from catchy.core.challenge.models import Challenge
from codex_app_server import (
    AppServerConfig,
    AsyncCodex,
    TextInput,
)
from codex_app_server.models import JsonObject
from docker import DockerClient


class CodexAgent(Agent):
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
        self._docker_image, _ = self._docker_client.images.build(
            path=str(self._dockerfile.parent), dockerfile=self._dockerfile.name
        )

    async def stream(self, challenge: Challenge):
        with self._docker_container() as container:
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
                thread = await codex.thread_start(
                    model=self._model, config=self._config
                )
                turn = await thread.turn(TextInput(challenge.description))

                async for event in turn.stream():
                    match event.method:
                        case "item/agentMessage/delta":
                            delta: str | None = getattr(event.payload, "delta", None)
                            if delta is not None:
                                yield delta
                        case "turn/started":
                            ...
                        case "turn/completed":
                            ...
                        case _:
                            ...

    @contextmanager
    def _docker_container(self):
        container = self._docker_client.containers.run(
            self._docker_image,
            detach=True,
            stdin_open=True,
            # TODO: provide workspace directory
            # volumes={
            #     repo_path: {"bind": "/challenge", "mode": "ro"},
            #     codex_home: {"bind": "/root/.codex", "mode": "rw"},
            # },
            environment={"CODEX_HOME": "/.codex"},
        )

        result = container.exec_run(
            cmd=[
                "sh",
                "-c",
                f"mkdir -p /.codex && echo '{
                    json.dumps({'auth_mode': 'apikey', 'OPENAI_API_KEY': self._api_key})
                }' > /.codex/auth.json",
            ]
        )
        if result.exit_code != 0:
            logs = container.logs().decode()
            container.remove(force=True)
            raise RuntimeError(f"Failed to set up container auth file: {logs}")

        try:
            yield container
        finally:
            container.remove(force=True)
