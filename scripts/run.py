#!/usr/bin/env python3
import argparse
import asyncio
import logging
import shutil
import sys
import tomllib
from pathlib import Path
from typing import Any, cast

from catchy.codex import CodexAgent, Configuration
from catchy.core.challenge.models import Challenge
from catchy.core.webhook.models import Webhook
from omegaconf import DictConfig, OmegaConf


def _load_challenge(input_directory: Path) -> tuple[Challenge, Webhook | None]:
    config_path = input_directory / "challenge.toml"
    if not config_path.exists():
        raise FileNotFoundError(f"challenge.toml not found: {config_path}")

    with config_path.open("rb") as file:
        data: dict[str, Any] = tomllib.load(file)

    challenge = Challenge(
        id=data["id"],
        description=data["description"],
        directory=input_directory / "source",
    )

    webhook_data = data.get("webhook")
    webhook = Webhook(**webhook_data) if webhook_data is not None else None

    return challenge, webhook


def _reset_workspace(workspace: Path) -> None:
    if not workspace.exists():
        return

    answer = input(f"Delete existing workspace at {workspace}? [y/N] ").strip().lower()
    if answer not in {"y", "yes"}:
        raise RuntimeError("workspace reset cancelled")

    shutil.rmtree(workspace)


def _normalized_agent_data(config: DictConfig, *, resolve: bool) -> dict[str, Any]:
    raw_data: Any = OmegaConf.to_container(config, resolve=resolve)
    if not isinstance(raw_data, dict):
        raise TypeError("agent configuration must be a mapping")

    raw_mapping = cast(dict[Any, Any], raw_data)
    return {str(key): value for key, value in raw_mapping.items()}


def _load_agent(config_path: Path) -> CodexAgent:
    config_path = config_path.expanduser().resolve()
    config = OmegaConf.load(config_path)
    if not isinstance(config, DictConfig):
        raise TypeError(f"agent configuration must be a mapping: {config_path}")

    data = _normalized_agent_data(config, resolve=True)
    class_name = data.get("class", "CodexAgent")
    if class_name != "CodexAgent":
        raise ValueError(f"unsupported agent class {class_name!r} in {config_path}")

    configuration = Configuration.model_validate(data)
    return CodexAgent.from_configuration(configuration)


async def _run(
    input_directory: Path, *, reset_workspace: bool, agent_configuration: Path
) -> None:
    logging.basicConfig(level=logging.INFO)

    input_directory = input_directory.resolve()
    challenge, webhook = _load_challenge(input_directory)
    workspace = input_directory / "workspace"
    if reset_workspace:
        _reset_workspace(workspace)
    workspace.mkdir(exist_ok=True, parents=True)

    agent = _load_agent(agent_configuration)

    async for delta in agent.stream(
        challenge=challenge,
        workspace=workspace,
        webhook=webhook,
    ):
        print(delta)
        print("=" * 80)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a Catchy CTF challenge.")
    parser.add_argument(
        "input_directory",
        type=Path,
        help="Path to a challenge root containing challenge.toml and source/",
    )
    parser.add_argument(
        "--reset-workspace",
        action="store_true",
        help="Delete workspace if previous trial exists before running",
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
                reset_workspace=args.reset_workspace,
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
