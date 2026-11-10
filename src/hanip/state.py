"""Posting progress: episode number, curriculum position, pending approval, history."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Literal

APPROVAL_RUNS = 5


@dataclass
class HistoryEntry:
    number: int
    date: str
    topic_id: str
    theme: str
    media_id: str


@dataclass
class Pending:
    date: str
    topic_id: str
    number: int
    theme: str
    dir: str


@dataclass
class Inflight:
    """A carousel container about to be published; kept until the outcome is known."""

    number: int
    topic_id: str
    theme: str
    date: str
    container_id: str


@dataclass
class State:
    published_count: int = 0
    curriculum_index: int = 0
    history: list[HistoryEntry] = field(default_factory=list)
    pending: Pending | None = None
    token_refreshed_at: str | None = None
    inflight: Inflight | None = None


def load_state(path: Path) -> State:
    if not path.exists():
        return State()
    raw = json.loads(path.read_text())
    return State(
        published_count=raw.get("published_count", 0),
        curriculum_index=raw.get("curriculum_index", 0),
        history=[HistoryEntry(**h) for h in raw.get("history", [])],
        pending=Pending(**raw["pending"]) if raw.get("pending") else None,
        token_refreshed_at=raw.get("token_refreshed_at"),
        inflight=Inflight(**raw["inflight"]) if raw.get("inflight") else None,
    )


def save_state(state: State, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(asdict(state), ensure_ascii=False, indent=2))
    os.replace(tmp, path)


def next_number(state: State) -> int:
    return state.published_count + 1


def theme_for(number: int) -> Literal["light", "dark"]:
    return "light" if number % 2 == 1 else "dark"


def needs_approval(number: int) -> bool:
    return number <= APPROVAL_RUNS


def already_published_on(state: State, day: str) -> bool:
    return any(h.date == day for h in state.history)
