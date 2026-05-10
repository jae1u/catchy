#!/usr/bin/env python3
import argparse
import asyncio
import importlib
import logging
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, cast

from catchy.core.agents.protocols import Agent
from catchy.core.challenge.models import Challenge
from catchy.core.webhook.models import Webhook
from omegaconf import DictConfig, OmegaConf
from rich.markdown import Markdown
from rich.panel import Panel
from rich.text import Text
from textual import on
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import (
    Button,
    Footer,
    Header,
    Input,
    Label,
    ListItem,
    ListView,
    RichLog,
    Select,
    Static,
)

# GitHub / Vercel-inspired monochrome palette
PALETTE = {
    "bg": "#0a0a0a",
    "panel": "#0d0d0d",
    "elevated": "#161616",
    "border": "#262626",
    "border_hi": "#3a3a3a",
    "text": "#ededed",
    "text_muted": "#8b8b8b",
    "text_dim": "#525252",
    "accent": "#ededed",
    "blue": "#3b82f6",
    "green": "#3fb950",
    "yellow": "#d29922",
    "orange": "#f0883e",
    "red": "#f85149",
}

STATUS_STYLES: dict[str, tuple[str, str]] = {
    "queued": ("○", PALETTE["text_dim"]),
    "preparing": ("◐", PALETTE["yellow"]),
    "running": ("●", PALETTE["green"]),
    "paused": ("⏸", PALETTE["orange"]),
    "completed": ("✓", PALETTE["blue"]),
    "failed": ("✗", PALETTE["red"]),
}


def _new_thread_root(challenge_root: Path) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    return challenge_root / f"thread-{timestamp}"


@dataclass
class StreamEvent:
    kind: str
    text: str
    timestamp: datetime = field(default_factory=datetime.now)


def _new_events() -> list["StreamEvent"]:
    return []


@dataclass(frozen=True)
class AgentDefinition:
    id: str
    path: Path
    class_name: str
    model_name: str


@dataclass
class StreamState:
    root: Path
    challenge: Challenge
    webhook: Webhook | None
    thread_root: Path | None = None
    workspace: Path | None = None
    status: str = "queued"
    events: list[StreamEvent] = field(default_factory=_new_events)
    started: bool = False
    agent_id: str = ""
    pause_gate: asyncio.Event = field(default_factory=asyncio.Event)


class CatchyApp(App[None]):
    CSS = """
    /* ── Base ────────────────────────────────── */

    Screen {
        background: #0a0a0a;
        color: #ededed;
    }

    Header {
        background: #0a0a0a;
        color: #ededed;
        text-style: bold;
        border-bottom: hkey #262626;
    }

    Footer {
        background: #0a0a0a;
        color: #8b8b8b;
        border-top: hkey #262626;
    }

    Footer > .footer--key {
        background: #0a0a0a;
        color: #ededed;
        text-style: bold;
    }

    Footer > .footer--description {
        background: #0a0a0a;
        color: #8b8b8b;
    }

    #main {
        height: 1fr;
    }

    /* ── Sidebar ─────────────────────────────── */

    #sidebar {
        width: 40;
        min-width: 32;
        background: #0a0a0a;
        border-right: vkey #262626;
    }

    #compose-row {
        height: auto;
        padding: 2 2 1 2;
    }

    #compose-row Label {
        color: #8b8b8b;
        text-style: none;
        padding-bottom: 1;
    }

    #challenge-input {
        margin-bottom: 1;
        background: #0a0a0a;
        color: #ededed;
        border: tall #262626;
    }

    #challenge-input:focus {
        border: tall #ededed;
    }

    #add-challenge {
        width: 100%;
        height: 3;
        margin-bottom: 0;
        background: #ededed;
        color: #0a0a0a;
        border: none;
        text-style: bold;
    }

    #add-challenge:hover {
        background: #ffffff;
        color: #0a0a0a;
    }

    #add-challenge:focus {
        text-style: bold;
        background: #ffffff;
    }

    #streams-section {
        height: 1fr;
    }

    #streams-header {
        padding: 1 2 1 2;
        color: #8b8b8b;
        text-style: none;
        border-top: hkey #262626;
    }

    #streams {
        height: 1fr;
        padding: 0;
        background: #0a0a0a;
        scrollbar-gutter: stable;
        border: none;
    }

    #streams > ListItem {
        height: 3;
        padding: 0 2;
        background: #0a0a0a;
        border-left: blank;
    }

    #streams > ListItem:hover {
        background: #161616;
    }

    #streams > ListItem.--highlight {
        background: #161616;
        border-left: thick #ededed;
        padding-left: 1;
    }

    #streams > ListItem.--highlight:hover {
        background: #1a1a1a;
    }

    #controls-section {
        height: auto;
        padding: 1 2 1 2;
        background: #0a0a0a;
        border-top: hkey #262626;
    }

    #controls {
        height: 3;
        margin-bottom: 1;
    }

    #controls Button {
        width: 1fr;
        margin-right: 1;
        background: #0a0a0a;
        color: #ededed;
        border: tall #262626;
    }

    #controls Button:last-of-type {
        margin-right: 0;
    }

    #controls Button:hover {
        background: #161616;
        border: tall #3a3a3a;
    }

    #controls Button:focus {
        border: tall #ededed;
    }

    #controls Button:disabled {
        color: #525252;
        border: tall #1a1a1a;
        background: #0a0a0a;
    }

    #run-selected {
        color: #3fb950;
    }

    #run-selected:hover {
        border: tall #3fb950;
    }

    #pause-selected {
        color: #f0883e;
    }

    #pause-selected:hover {
        border: tall #f0883e;
    }

    #settings-block {
        height: auto;
        margin-bottom: 1;
    }

    .settings-label {
        color: #8b8b8b;
        padding: 0 0 1 0;
    }

    #agent-select {
        color: #ededed;
        margin-bottom: 1;
        height: auto;
    }

    #agent-select > SelectCurrent {
        background: #0a0a0a;
        color: #ededed;
        border: tall #262626;
        height: 3;
        padding: 0 1;
    }

    #agent-select > SelectCurrent Static#label {
        color: #ededed;
    }

    #agent-select:focus > SelectCurrent {
        border: tall #ededed;
    }

    #agent-select:disabled > SelectCurrent {
        color: #525252;
        border: tall #1a1a1a;
    }

    #agent-select > SelectOverlay {
        background: #161616;
        border: tall #3a3a3a;
        max-height: 8;
    }

    /* ── Content ─────────────────────────────── */

    #content {
        width: 1fr;
        background: #0a0a0a;
    }

    #stream-header {
        height: 5;
        padding: 1 3;
        background: #0a0a0a;
        border-bottom: hkey #262626;
    }

    #stream-id-row {
        height: 1;
    }

    #stream-id {
        text-style: bold;
        color: #ededed;
        width: 1fr;
    }

    #stream-status-pill {
        text-style: bold;
        width: auto;
    }

    #stream-path {
        color: #8b8b8b;
        height: 1;
        margin-top: 1;
    }

    #stream-log {
        height: 1fr;
        padding: 1 3;
        background: #0a0a0a;
        scrollbar-color: #262626;
        scrollbar-color-hover: #3a3a3a;
        scrollbar-color-active: #525252;
        scrollbar-background: #0a0a0a;
    }
    """

    BINDINGS = [
        ("q", "quit", "Quit"),
        ("ctrl+c", "quit", "Quit"),
        ("s", "start_selected", "Start thread"),
        ("space", "toggle_pause", "Pause"),
        ("r", "refresh_active", "Refresh"),
    ]

    def __init__(
        self, states: list[StreamState], *, agent_definitions: list[AgentDefinition]
    ) -> None:
        super().__init__()
        self._states = states
        self._agent_definitions = {
            definition.id: definition for definition in agent_definitions
        }
        self._default_agent_id = agent_definitions[0].id
        self._pending_agent_id = self._default_agent_id
        for state in self._states:
            state.agent_id = state.agent_id or self._default_agent_id
        self._active_index = 0
        self._labels: list[Label] = []
        self._agents: dict[str, Agent] = {}
        self._agent_lock = asyncio.Lock()

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Horizontal(id="main"):
            with Vertical(id="sidebar"):
                with Vertical(id="compose-row"):
                    yield Label("Challenge root")
                    yield Input(
                        placeholder="path/to/challenge",
                        id="challenge-input",
                    )
                    yield Button("Add challenge  →", id="add-challenge")
                    with Vertical(id="settings-block"):
                        yield Label("Agent", classes="settings-label")
                        yield Select[str](
                            self._agent_options(),
                            value=self._default_agent_id,
                            allow_blank=False,
                            id="agent-select",
                        )

                with Vertical(id="streams-section"):
                    yield Static("Threads", id="streams-header")
                    self._labels = [
                        Label(self._sidebar_text(state), id=f"stream-label-{index}")
                        for index, state in enumerate(self._states)
                    ]
                    yield ListView(
                        *[
                            ListItem(label, id=f"stream-{index}")
                            for index, label in enumerate(self._labels)
                        ],
                        id="streams",
                    )

                with Vertical(id="controls-section"):
                    with Horizontal(id="controls"):
                        yield Button("▶  Start thread", id="run-selected")
                        yield Button("⏸  Pause", id="pause-selected")

            with Vertical(id="content"):
                with Vertical(id="stream-header"):
                    with Horizontal(id="stream-id-row"):
                        yield Static("", id="stream-id")
                        yield Static("", id="stream-status-pill")
                    yield Static("", id="stream-path")
                yield RichLog(
                    id="stream-log",
                    wrap=True,
                    markup=True,
                    highlight=True,
                    auto_scroll=True,
                )
        yield Footer()

    async def on_mount(self) -> None:
        self.title = "🪤  Catchy"
        self.sub_title = "Ca-ca-catch My Flag!"
        if self._states:
            self._select_stream(0)
        else:
            self._render_empty_state()

    @on(ListView.Selected, "#streams")
    def on_stream_selected(self, event: ListView.Selected) -> None:
        if event.item.id is None:
            return
        self._select_stream(int(event.item.id.removeprefix("stream-")))

    @on(Input.Submitted, "#challenge-input")
    async def on_challenge_submitted(self, event: Input.Submitted) -> None:
        await self._add_challenge(event.value)

    @on(Button.Pressed, "#add-challenge")
    async def on_add_pressed(self) -> None:
        await self._add_challenge(self.query_one("#challenge-input", Input).value)

    @on(Button.Pressed, "#run-selected")
    def on_run_selected_pressed(self) -> None:
        self.action_start_selected()

    @on(Button.Pressed, "#pause-selected")
    def on_pause_selected_pressed(self) -> None:
        self.action_toggle_pause()

    @on(Select.Changed, "#agent-select")
    def on_agent_changed(self, event: Select.Changed) -> None:
        if event.value == Select.NULL:
            return

        self._pending_agent_id = str(event.value)
        if not self._states:
            return

        state = self._states[self._active_index]
        if state.started:
            return
        state.agent_id = self._pending_agent_id

    def action_start_selected(self) -> None:
        if not self._states:
            self._append_event(None, "error", "add a challenge first")
            return

        state = self._states[self._active_index]
        if state.started:
            self._append_event(self._active_index, "status", "thread already started")
            return

        state.thread_root = _new_thread_root(state.root)
        state.workspace = state.thread_root / "workspace"
        state.started = True
        state.pause_gate.set()
        self._render_active_stream()
        self._sync_controls()
        self.run_worker(
            self._run_stream(index=self._active_index),
            name=f"catchy-thread-{self._active_index}",
            group="catchy-threads",
        )

    def action_toggle_pause(self) -> None:
        if not self._states:
            self._append_event(None, "error", "add a challenge first")
            return

        state = self._states[self._active_index]
        if not state.started or state.status in {"queued", "completed", "failed"}:
            self._append_event(self._active_index, "status", "thread is not running")
            return

        if state.pause_gate.is_set():
            state.pause_gate.clear()
            self._set_status(self._active_index, "paused")
            self._append_event(self._active_index, "status", "paused")
        else:
            state.pause_gate.set()
            self._set_status(self._active_index, "running")
            self._append_event(self._active_index, "status", "resumed")

    def action_refresh_active(self) -> None:
        self._render_active_stream()

    async def _run_stream(self, *, index: int) -> None:
        state = self._states[index]
        try:
            self._set_status(index, "preparing")
            agent = await self._get_agent(state.agent_id)
            self._append_event(
                index, "status", f"agent: {self._agent_label_by_id(state.agent_id)}"
            )
            if state.thread_root is None or state.workspace is None:
                state.thread_root = _new_thread_root(state.root)
                state.workspace = state.thread_root / "workspace"
            thread_root = state.thread_root
            workspace = state.workspace
            workspace.mkdir(exist_ok=True, parents=True)

            self._set_status(index, "running")
            self._append_event(index, "status", f"thread: {thread_root}")
            self._append_event(index, "status", f"workspace: {workspace}")
            stream = agent.stream(
                challenge=state.challenge,
                workspace=workspace,
                webhook=state.webhook,
            ).__aiter__()
            while True:
                await state.pause_gate.wait()
                try:
                    delta = await stream.__anext__()
                except StopAsyncIteration:
                    break
                self._append_event(index, "delta", delta)

            self._set_status(index, "completed")
            self._append_event(index, "status", "completed")
        except Exception as error:
            self._set_status(index, "failed")
            self._append_event(index, "error", str(error))

    async def _get_agent(self, agent_id: str) -> Agent:
        async with self._agent_lock:
            agent = self._agents.get(agent_id)
            if agent is None:
                definition = self._agent_definitions[agent_id]
                self._append_event(
                    None,
                    "status",
                    f"preparing {self._agent_label(definition)}",
                )
                agent = await asyncio.to_thread(_load_agent, definition.path)
                self._agents[agent_id] = agent
            return agent

    async def _add_challenge(self, raw_path: str) -> None:
        raw_path = raw_path.strip()
        if not raw_path:
            self._append_event(None, "error", "enter a challenge root path first")
            return

        try:
            state = _load_state(Path(raw_path))
        except Exception as error:
            self._append_event(None, "error", str(error))
            return

        state.agent_id = self._pending_agent_id
        index = len(self._states)
        self._states.append(state)
        label = Label(self._sidebar_text(state), id=f"stream-label-{index}")
        self._labels.append(label)
        await self.query_one("#streams", ListView).append(
            ListItem(label, id=f"stream-{index}")
        )
        self.query_one("#challenge-input", Input).value = ""
        self._select_stream(index)
        self._append_event(index, "status", f"added {state.root}")

    def _select_stream(self, index: int) -> None:
        if not self._states:
            self._render_empty_state()
            return
        self._active_index = index
        streams = self.query_one("#streams", ListView)
        streams.index = index
        self._render_active_stream()
        self._sync_controls()

    def _render_active_stream(self) -> None:
        if not self._states:
            self._render_empty_state()
            return
        state = self._states[self._active_index]

        muted = PALETTE["text_muted"]
        dim = PALETTE["text_dim"]
        thread_name = (
            state.thread_root.name if state.thread_root is not None else "new thread"
        )
        self.query_one("#stream-id", Static).update(
            f"{state.challenge.id} / {thread_name}"
        )
        self.query_one("#stream-status-pill", Static).update(
            self._status_pill(state.status)
        )
        self.query_one("#stream-path", Static).update(
            f"[{dim}]↳[/]  [{muted}]{state.root}[/]   "
            f"[{dim}]·[/]  [{muted}]{thread_name}[/]   "
            f"[{dim}]·[/]  [{muted}]{self._agent_label_by_id(state.agent_id)}[/]"
        )

        log = self.query_one("#stream-log", RichLog)
        log.clear()
        for event in state.events:
            self._write_event(log, event)

    def _append_event(self, index: int | None, kind: str, text: str) -> None:
        event = StreamEvent(kind=kind, text=text)

        if not self._states:
            self._write_event(self.query_one("#stream-log", RichLog), event)
            return

        if index is None:
            for state in self._states:
                state.events.append(event)
            self._render_active_stream()
            return

        self._states[index].events.append(event)
        if index == self._active_index:
            self._write_event(self.query_one("#stream-log", RichLog), event)
        self._labels[index].update(self._sidebar_text(self._states[index]))

    def _set_status(self, index: int, status: str) -> None:
        self._states[index].status = status
        self._labels[index].update(self._sidebar_text(self._states[index]))
        if index == self._active_index:
            self.query_one("#stream-status-pill", Static).update(
                self._status_pill(status)
            )
            self._sync_controls()

    def _write_event(self, log: RichLog, event: StreamEvent) -> None:
        timestamp = event.timestamp.strftime("%H:%M:%S")
        ts = PALETTE["text_dim"]
        muted = PALETTE["text_muted"]
        border = PALETTE["border"]
        red = PALETTE["red"]
        match event.kind:
            case "delta":
                log.write(
                    Panel(
                        Markdown(event.text),
                        border_style=border,
                        title=f"[{ts}]{timestamp}[/]",
                        title_align="right",
                        padding=(0, 1),
                    )
                )
            case "error":
                log.write(
                    Text.from_markup(
                        f"[{ts}]{timestamp}[/]  [bold {red}]✗[/]  [{red}]{event.text}[/]"
                    )
                )
            case _:
                log.write(
                    Text.from_markup(
                        f"[{ts}]{timestamp}[/]  [{muted}]▸  {event.text}[/]"
                    )
                )

    def _sidebar_text(self, state: StreamState) -> str:
        glyph, color = STATUS_STYLES.get(state.status, ("·", PALETTE["text"]))
        event_count = len(state.events)
        suffix = f"{state.status} · {event_count} evt" if event_count else state.status
        text_color = PALETTE["text"]
        muted = PALETTE["text_muted"]
        return (
            f"[{color}]{glyph}[/]  [bold {text_color}]{state.challenge.id}[/]\n"
            f"   [{muted}]{suffix}[/]"
        )

    def _status_pill(self, status: str) -> str:
        glyph, color = STATUS_STYLES.get(status, ("·", PALETTE["text"]))
        return f"[{color}]{glyph}  {status.upper()}[/]"

    def _render_empty_state(self) -> None:
        text = PALETTE["text"]
        muted = PALETTE["text_muted"]
        dim = PALETTE["text_dim"]
        border = PALETTE["border"]

        self.query_one("#stream-id", Static).update(f"[{muted}]No thread selected[/]")
        self.query_one("#stream-status-pill", Static).update(f"[{dim}]○  EMPTY[/]")
        self.query_one("#stream-path", Static).update("")

        log = self.query_one("#stream-log", RichLog)
        log.clear()
        log.write(
            Panel(
                Text.from_markup(
                    f"[bold {text}]Get started[/]\n"
                    f"[{muted}]Start autonomous CTF threads with Catchy.[/]\n\n"
                    f"[{dim}]1[/]   [{text}]Enter a challenge root[/]\n"
                    f"     [{muted}]e.g.[/] [{text}]challenges/lets-change[/]\n\n"
                    f"[{dim}]2[/]   [{text}]Press[/] [bold {text}]Enter[/] [{text}]or click[/] [bold {text}]Add challenge[/]\n\n"
                    f"[{dim}]3[/]   [{text}]Choose an agent, then hit[/] [bold {text}]Start thread[/]\n\n"
                    f"[{dim}]────────────────────────────────[/]\n\n"
                    f"[{muted}]Shortcuts[/]   "
                    f"[bold {text}]s[/] [{muted}]start thread[/]   "
                    f"[bold {text}]space[/] [{muted}]pause[/]   "
                    f"[bold {text}]r[/] [{muted}]refresh[/]   "
                    f"[bold {text}]q[/] [{muted}]quit[/]"
                ),
                border_style=border,
                title=f"[{muted}]🪤 catchy[/]",
                title_align="left",
                padding=(1, 2),
            )
        )
        self._sync_controls()

    def _sync_controls(self) -> None:
        run_button = self.query_one("#run-selected", Button)
        pause_button = self.query_one("#pause-selected", Button)
        agent_select = cast(Select[str], self.query_one("#agent-select", Select))

        if not self._states:
            run_button.disabled = True
            pause_button.disabled = True
            agent_select.disabled = False
            if agent_select.value != self._pending_agent_id:
                agent_select.value = self._pending_agent_id
            pause_button.label = "⏸  Pause"
            return

        state = self._states[self._active_index]
        state.agent_id = state.agent_id or self._pending_agent_id
        run_button.disabled = state.started
        agent_select.disabled = state.started
        if agent_select.value != state.agent_id:
            agent_select.value = state.agent_id
        pause_button.disabled = not state.started or state.status in {
            "queued",
            "completed",
            "failed",
        }
        pause_button.label = "▶  Resume" if state.status == "paused" else "⏸  Pause"

    def _agent_label(self, definition: AgentDefinition) -> str:
        return f"{definition.id} · {definition.model_name}"

    def _agent_label_by_id(self, agent_id: str) -> str:
        definition = self._agent_definitions.get(agent_id)
        if definition is None:
            return agent_id
        return self._agent_label(definition)

    def _agent_options(self) -> list[tuple[str, str]]:
        return [
            (self._agent_label(definition), definition.id)
            for definition in self._agent_definitions.values()
        ]


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


def _load_agent_definition(config_path: Path) -> AgentDefinition:
    config = OmegaConf.load(config_path)
    if not isinstance(config, DictConfig):
        raise TypeError(f"agent configuration must be a mapping: {config_path}")

    data = _normalized_agent_data(config, resolve=False)
    agent_id = data.get("id")
    if not isinstance(agent_id, str) or not agent_id:
        raise ValueError(f"agent configuration is missing an id: {config_path}")

    class_name = _agent_class_path(data, config_path)

    model = data.get("model")
    model_name = ""
    if isinstance(model, dict):
        model = cast(dict[str, Any], model)
        raw_model_name = model.get("name")
        if isinstance(raw_model_name, str):
            model_name = raw_model_name

    return AgentDefinition(
        id=agent_id,
        path=config_path,
        class_name=class_name,
        model_name=model_name or "unknown model",
    )


def _load_agent_definitions(configurations_dir: Path) -> list[AgentDefinition]:
    root = configurations_dir.expanduser().resolve()
    if not root.exists():
        raise FileNotFoundError(f"configurations directory not found: {root}")
    if not root.is_dir():
        raise NotADirectoryError(f"configurations path is not a directory: {root}")

    config_paths = sorted([*root.glob("*.yaml"), *root.glob("*.yml")])
    definitions = [_load_agent_definition(path) for path in config_paths]
    if not definitions:
        raise RuntimeError(f"no agent configuration files found in {root}")

    seen: set[str] = set()
    for definition in definitions:
        if definition.id in seen:
            raise RuntimeError(f"duplicate agent id in configurations: {definition.id}")
        seen.add(definition.id)
    return definitions


def _load_agent(config_path: Path) -> Agent:
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


def _load_state(input_directory: Path) -> StreamState:
    root = input_directory.expanduser().resolve()
    challenge, webhook = _load_challenge(root)
    return StreamState(
        root=root,
        challenge=challenge,
        webhook=webhook,
    )


def _load_states(input_directories: list[Path]) -> list[StreamState]:
    return [_load_state(input_directory) for input_directory in input_directories]


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Catchy CTF threads in a TUI.")
    parser.add_argument(
        "input_directories",
        nargs="*",
        type=Path,
        help="Optional initial challenge roots containing challenge.yaml and source/",
    )
    parser.add_argument(
        "--configurations-dir",
        default=Path("configurations"),
        type=Path,
        help="Directory containing agent YAML configurations",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)

    try:
        agent_definitions = _load_agent_definitions(args.configurations_dir)
        states = _load_states(args.input_directories)
        CatchyApp(states, agent_definitions=agent_definitions).run()
    except Exception as error:
        print(f"error: {error}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
