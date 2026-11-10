"""Schema for the 9-slide post and its generation through `claude -p`.

Length limits (characters) keep text inside the receipt layout; rendering
also measures overflow as a second check.
"""

from __future__ import annotations

import json
from importlib.resources import files
from typing import Annotated, Any

from pydantic import BaseModel, Field, ValidationError, model_validator

from hanip.claude_cli import ClaudeError, run_claude_json
from hanip.curriculum import Topic


def _limited(n: int):
    return Annotated[str, Field(min_length=1, max_length=n)]


Str6 = _limited(6)
Str8 = _limited(8)
Str10 = _limited(10)
Str12 = _limited(12)
Str14 = _limited(14)
Str18 = _limited(18)
Str24 = _limited(24)
Str600 = _limited(600)


class Row(BaseModel):
    label: Str8
    value: Str14


class Cover(BaseModel):
    title: Str12
    subtitle: Str18


class Definition(BaseModel):
    definition: Str24
    rows: Annotated[list[Row], Field(min_length=3, max_length=3)]
    summary: Str14


class SetReceipt(BaseModel):
    name: Str6
    caption: Str8
    rows: Annotated[list[Row], Field(min_length=2, max_length=3)]
    total: Str10


class Compare(BaseModel):
    a: SetReceipt
    b: SetReceipt
    conclusion: Str18


class Menu(BaseModel):
    items: Annotated[list[Row], Field(min_length=3, max_length=4)]
    summary: Str14


class Check(BaseModel):
    text: Str14
    checked: bool


class Options(BaseModel):
    checks: Annotated[list[Check], Field(min_length=3, max_length=4)]
    summary: Str14


class Steps(BaseModel):
    steps: Annotated[list[Str12], Field(min_length=3, max_length=5)]
    summary: Str14


class SpecialNews(BaseModel):
    title: Str24
    source: Str12
    summary: Str24


class Special(BaseModel):
    news: Annotated[list[SpecialNews], Field(max_length=3)]
    fallback: Annotated[str, Field(max_length=40)] | None = None

    @model_validator(mode="after")
    def _need_fallback(self):
        if not self.news and not self.fallback:
            raise ValueError("news가 비어 있으면 fallback이 필요함")
        return self


class Caution(BaseModel):
    items: Annotated[list[Row], Field(min_length=3, max_length=3)]
    summary: Str14


class Total(BaseModel):
    points: Annotated[list[Str14], Field(min_length=3, max_length=3)]
    next_topic: Annotated[str, Field(max_length=14)] | None = None


class Post(BaseModel):
    topic_id: str
    cover: Cover
    definition: Definition
    compare: Compare
    menu: Menu
    options: Options
    steps: Steps
    special: Special
    caution: Caution
    total: Total
    caption: Str600
    hashtags: Annotated[list[str], Field(min_length=5, max_length=10)]


def build_prompt(topic: Topic, next_topic: Topic | None, news: list[Any], feedback: str | None) -> str:
    template = files("hanip.prompts").joinpath("post.md").read_text()
    news_json = json.dumps(
        [{"title": n.title, "source": n.source, "url": n.url, "snippet": n.summary} for n in news],
        ensure_ascii=False,
        indent=1,
    )
    return (
        template.replace("{topic_id}", topic.id)
        .replace("{topic_title}", topic.title_ko)
        .replace("{topic_keyword}", topic.keyword_en)
        .replace("{next_topic}", next_topic.title_ko if next_topic else "없음 (null로 둘 것)")
        .replace("{news}", news_json if news else "[] (관련 소식 없음 → news는 빈 배열, fallback 작성)")
        .replace("{feedback}", feedback or "없음")
    )


def generate_post(
    topic: Topic,
    next_topic: Topic | None,
    news: list[Any],
    *,
    feedback: str | None = None,
    run=run_claude_json,
) -> Post:
    try:
        return Post.model_validate(run(build_prompt(topic, next_topic, news, feedback)))
    except ClaudeError as e:
        problem = f"이전 답을 JSON으로 읽을 수 없었어. 설명 없이 JSON 객체 하나만 출력해. ({e})"
    except ValidationError as e:
        problem = f"이전 답의 형식 오류(꼭 고칠 것):\n{e}"
    retry_feedback = "\n".join(filter(None, [feedback, problem]))
    raw = run(build_prompt(topic, next_topic, news, retry_feedback))
    try:
        return Post.model_validate(raw)
    except ValidationError as e:
        raise ClaudeError(f"문구 형식 오류가 반복됨: {e}") from e
