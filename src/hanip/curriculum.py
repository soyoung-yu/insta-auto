"""Ordered list of topics (easy → hard), generated once and stored in data/curriculum.json."""

from __future__ import annotations

import json
from importlib.resources import files
from pathlib import Path

from pydantic import BaseModel, ValidationError

from hanip.claude_cli import ClaudeError, run_claude_json


class Topic(BaseModel):
    id: str
    title_ko: str
    keyword_en: str
    level: int


def load_curriculum(path: Path) -> list[Topic]:
    return [Topic(**t) for t in json.loads(path.read_text())]


def save_curriculum(topics: list[Topic], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps([t.model_dump() for t in topics], ensure_ascii=False, indent=2))


def generate_curriculum(count: int = 60, run=run_claude_json) -> list[Topic]:
    prompt = files("hanip.prompts").joinpath("curriculum.md").read_text().replace("{count}", str(count))
    raw = run(prompt)
    try:
        topics = [Topic(**t) for t in raw]
    except (TypeError, ValidationError) as e:
        raise ClaudeError(f"커리큘럼 형식 오류: {e}") from e
    ids = [t.id for t in topics]
    if len(ids) != len(set(ids)):
        raise ClaudeError("커리큘럼에 중복 id가 있음")
    return topics
