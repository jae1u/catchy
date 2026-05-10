<div align="center">

# 🪤<br>Catchy

**Ca-ca-catch my flag, baby.**

Autonomous AI agent that plays capture-the-flag challenges.

<sub>[TUI App](./scripts/app.py) &nbsp;·&nbsp; [CLI Runner](./scripts/run.py)</sub>

<br/>
<br/>

<img src="assets/app.png" alt="Catchy TUI — multi-stream agent runner" width="900" />

</div>

## What is this

Catchy plugs an agent into a CTF challenge, runs it inside a sandboxed workspace, and streams every reasoning step, command, and file change to your terminal. Multiple challenge threads can run side-by-side in the TUI, and each thread gets its own workspace, agent model, and event log.

## Quick start

```bash
# 1. Install dependencies — uv handles the workspace + venv
uv sync

# 2. Set your OpenAI API key
export OPENAI_API_KEY=sk-...

# 3. Launch the TUI on a challenge
uv run scripts/app.py challenges/lets-change
```

> **Requires** Python 3.14+, [`uv`](https://docs.astral.sh/uv/), and a running Docker daemon.

Or open the TUI empty and add challenges from the sidebar:

```bash
uv run scripts/app.py
```

For a one-shot, single-challenge run without the UI:

```bash
uv run scripts/run.py challenges/lets-change
```

Use a specific agent configuration:

```bash
uv run scripts/run.py challenges/lets-change --agent-configuration configurations/codex.yaml
uv run scripts/app.py --configurations-dir configurations
```

## Anatomy of a challenge

Challenges are directories with a `challenge.yaml` file and a `source/` folder. The YAML is loaded with OmegaConf, so environment interpolation and other OmegaConf features are available where useful.

```text
challenges/lets-change/
├── challenge.yaml      # id, description, optional webhook
├── source/             # files mounted into the agent's container
└── thread-.../         # one directory per run
    ├── workspace/      # writable scratchpad mounted into the agent container
    └── metadata/       # run metadata and artifacts kept separate from workspace
```

```yaml
# challenge.yaml
id: lets-change
description: "..."

webhook: # optional
  url: "https://discord.com/api/webhooks/..."
  preferred_language: English
```

Every run starts a new thread directory:

```text
challenges/lets-change/thread-20260510-041230-123456/workspace/
challenges/lets-change/thread-20260510-041230-123456/metadata/
```

The CLI prints the generated thread, workspace, and metadata paths before streaming output. In the TUI, add a challenge root, choose an agent, then select **Start thread**. While a thread is active, use the steer message box to queue guidance that will be sent to the agent between stream updates.

## Agent Configuration

Agent configurations live in `configurations/*.yaml`. The `class` field is a fully qualified Python import path; Catchy imports it dynamically, validates the YAML with that module's `Configuration` model, then calls `AgentClass.from_configuration(...)`.

```yaml
# configurations/codex.yaml
id: codex-gpt-5.5
class: catchy.codex.CodexAgent
model:
  provider: openai
  name: gpt-5.5
  api_key: ${oc.env:OPENAI_API_KEY}
```

The old shorthand `class: CodexAgent` still resolves to `catchy.codex.CodexAgent`, but new configs should use the full import path.

## Keyboard

| Key                       | Action                 |
| ------------------------- | ---------------------- |
| <kbd>s</kbd>              | Start selected thread  |
| <kbd>space</kbd>          | Pause / resume         |
| <kbd>r</kbd>              | Refresh the active log |
| <kbd>q</kbd>              | Quit                   |
| <kbd>↑</kbd> <kbd>↓</kbd> | Move between threads   |

## Project layout

```text
catchy/
├── packages/
│   ├── core/         # Challenge, Agent, Webhook protocols & models
│   └── codex/        # CodexAgent — Codex App Server + Docker runtime
├── configurations/   # Agent YAML configurations
├── scripts/
│   ├── app.py        # The TUI shown above
│   └── run.py        # Single-shot CLI runner
├── challenges/       # Challenge YAML, source files, and workspaces
└── assets/           # Screenshots and images
```

## Adding a new agent

The `Agent` protocol is minimal: implement `stream(...)`, add a Pydantic-style `Configuration` model in the same module, and expose `from_configuration(...)` on the agent class. `stream(...)` is an async generator: it yields display text and can receive `str | None` steering messages between yields.

```python
from pathlib import Path
from typing import AsyncGenerator

from pydantic import BaseModel

from catchy.core.agents.protocols import Agent
from catchy.core.challenge.models import Challenge
from catchy.core.webhook.models import Webhook

class Configuration(BaseModel):
    id: str

class MyAgent(Agent):
    key = "my-agent"

    def __init__(self, id: str):
        self.id = id

    @staticmethod
    def from_configuration(configuration: Configuration) -> "MyAgent":
        return MyAgent(id=configuration.id)

    async def stream(
        self,
        challenge: Challenge,
        workspace: Path,
        metadata_directory: Path,
        webhook: Webhook | None = None,
    ) -> AsyncGenerator[str, str | None]:
        steering_message = yield "thinking..."
        if steering_message is not None:
            ...
        ...
```

Drop it under `packages/<name>/`, register it in the workspace, then add a YAML file:

```yaml
id: my-agent
class: catchy.my_agent.MyAgent
```

## Roadmap

- [ ] Additional agents (Claude Code, custom)
- [ ] Exportable run transcripts
- [ ] Per-challenge scoreboard
