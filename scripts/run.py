#!/usr/bin/env python3
import argparse
import asyncio
import logging
import os
import shutil
import sys
import tomllib
from pathlib import Path
from typing import Any

from catchy.codex import CodexAgent
from catchy.core.challenge.models import Challenge
from catchy.core.webhook.models import Webhook


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


async def _run(input_directory: Path, *, reset_workspace: bool) -> None:
    logging.basicConfig(level=logging.INFO)

    input_directory = input_directory.resolve()
    challenge, webhook = _load_challenge(input_directory)
    workspace = input_directory / "workspace"
    if reset_workspace:
        _reset_workspace(workspace)
    workspace.mkdir(exist_ok=True, parents=True)

    agent = CodexAgent(api_key=os.environ["OPENAI_API_KEY"])

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
    args = parser.parse_args()

    try:
        asyncio.run(_run(args.input_directory, reset_workspace=args.reset_workspace))
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
