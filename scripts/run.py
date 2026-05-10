#!/usr/bin/env python3
import argparse
import asyncio
import importlib
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, cast

from catchy.core.agents.protocols import Agent
from catchy.core.challenge.models import Challenge
from catchy.core.webhook.models import Webhook
from omegaconf import DictConfig, OmegaConf


def _new_thread_root(challenge_root: Path) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    return challenge_root / f"thread-{timestamp}"


def _load_yaml_mapping(config_path: Path) -> dict[str, Any]:
    config = OmegaConf.load(config_path)
    if not isinstance(config, DictConfig):
        raise TypeError(f"configuration must be a mapping: {config_path}")

    raw_data: Any = OmegaConf.to_container(config, resolve=True)
    if not isinstance(raw_data, dict):
        raise TypeError(f"configuration must be a mapping: {config_path}")

    raw_mapping = cast(dict[Any, Any], raw_data)
    return {str(key): value for key, value in raw_mapping.items()}


def _load_challenge(input_directory: Path) -> tuple[Challenge, Webhook | None]:
    config_path = input_directory / "challenge.yaml"
    if not config_path.exists():
        raise FileNotFoundError(f"challenge.yaml not found: {config_path}")

    data = _load_yaml_mapping(config_path)
    challenge = Challenge(
        id=data["id"],
        description=data["description"],
        directory=input_directory / "source",
    )

    webhook_data = data.get("webhook")
    webhook = Webhook(**webhook_data) if webhook_data is not None else None

    return challenge, webhook


def _normalized_agent_data(config: DictConfig, *, resolve: bool) -> dict[str, Any]:
    raw_data: Any = OmegaConf.to_container(config, resolve=resolve)
    if not isinstance(raw_data, dict):
        raise TypeError("agent configuration must be a mapping")

    raw_mapping = cast(dict[Any, Any], raw_data)
    return {str(key): value for key, value in raw_mapping.items()}


def _agent_class_path(data: dict[str, Any], config_path: Path) -> str:
    class_path = data.get("class", "catchy.codex.CodexAgent")
    if class_path == "CodexAgent":
        return "catchy.codex.CodexAgent"
    if not isinstance(class_path, str) or not class_path:
        raise ValueError(f"agent configuration has an invalid class: {config_path}")
    return class_path


def _import_agent_class(class_path: str, config_path: Path) -> type[Any]:
    module_name, separator, attribute_name = class_path.rpartition(".")
    if not separator or not module_name or not attribute_name:
        raise ValueError(
            f"agent class must be a fully qualified import path in {config_path}: "
            f"{class_path!r}"
        )

    module = importlib.import_module(module_name)
    agent_class = getattr(module, attribute_name, None)
    if not isinstance(agent_class, type):
        raise TypeError(f"agent class is not a class in {config_path}: {class_path!r}")
    return agent_class


def _load_agent(config_path: Path) -> Agent:
    config_path = config_path.expanduser().resolve()
    config = OmegaConf.load(config_path)
    if not isinstance(config, DictConfig):
        raise TypeError(f"agent configuration must be a mapping: {config_path}")

    data = _normalized_agent_data(config, resolve=True)
    agent_class = _import_agent_class(_agent_class_path(data, config_path), config_path)
    configuration_class = getattr(
        importlib.import_module(agent_class.__module__),
        "Configuration",
        None,
    )
    if not hasattr(configuration_class, "model_validate"):
        raise TypeError(
            f"agent module must expose a Configuration model with model_validate: "
            f"{agent_class.__module__}"
        )
    configuration_class = cast(Any, configuration_class)

    from_configuration = getattr(agent_class, "from_configuration", None)
    if not callable(from_configuration):
        raise TypeError(
            f"agent class must expose from_configuration: "
            f"{agent_class.__module__}.{agent_class.__name__}"
        )

    agent = from_configuration(configuration_class.model_validate(data))
    if not isinstance(agent, Agent):
        raise TypeError(
            f"from_configuration did not return an Agent for {agent_class.__name__}"
        )
    return agent


async def _run(input_directory: Path, *, agent_configuration: Path) -> None:
    logging.basicConfig(level=logging.INFO)

    input_directory = input_directory.resolve()
    challenge, webhook = _load_challenge(input_directory)
    thread_root = _new_thread_root(input_directory)
    workspace = thread_root / "workspace"
    metadata = thread_root / "metadata"
    workspace.mkdir(exist_ok=True, parents=True)
    metadata.mkdir(exist_ok=True, parents=True)

    agent = _load_agent(agent_configuration)
    print(f"thread: {thread_root}")
    print(f"workspace: {workspace}")
    print(f"metadata: {metadata}")
    print("=" * 80)

    async for delta in agent.stream(
        challenge=challenge,
        workspace=workspace,
        metadata=metadata,
        webhook=webhook,
    ):
        print(delta)
        print("=" * 80)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a Catchy CTF challenge.")
    parser.add_argument(
        "input_directory",
        type=Path,
        help="Path to a challenge root containing challenge.yaml and source/",
    )
    parser.add_argument(
        "--agent-configuration",
        "-a",
        default=Path("configurations/codex.yaml"),
        type=Path,
        help="Path to an agent YAML configuration",
    )
    args = parser.parse_args()

    try:
        asyncio.run(
            _run(
                args.input_directory,
                agent_configuration=args.agent_configuration,
            )
        )
    except KeyError as error:
        print(
            f"missing required configuration or environment key: {error}",
            file=sys.stderr,
        )
        return 1
    except Exception as error:
        print(f"error: {error}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
