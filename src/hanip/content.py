"""Schema for the 9-slide post and its generation through `claude -p`.

Length limits (characters) keep text inside the receipt layout; rendering
also measures overflow as a second check.
"""

from __future__ import annotations

import json
from importlib.resources import files
from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field, ValidationError, model_validator

from hanip.claude_cli import ClaudeError, run_claude_json
from hanip.curriculum import Topic


def _limited(n: int):
    return Annotated[str, Field(min_length=1, max_length=n)]


Str4 = _limited(4)
Str6 = _limited(6)
Str8 = _limited(8)
Str10 = _limited(10)
Str12 = _limited(12)
Str14 = _limited(14)
Str18 = _limited(18)
Str24 = _limited(24)
Str600 = _limited(600)
Str20 = _limited(20)
Str28 = _limited(28)
Str30 = _limited(30)


class Row(BaseModel):
    label: Str8
    value: Str14


class Cover(BaseModel):
    title: Str20  # full term, never abbreviated; the renderer shrinks the font to fit
    subtitle: Str24


class Definition(BaseModel):
    definition: Str30  # rendered with a line break after each comma
    rows: Annotated[list[Row], Field(min_length=3, max_length=3)]


class CompareRow(BaseModel):
    label: Str4
    value: Str8


class SetReceipt(BaseModel):
    """One side of the comparison, named after the compared thing itself (e.g. 클라이언트)."""

    name: Str8
    caption: Str12
    rows: Annotated[list[CompareRow], Field(min_length=2, max_length=3)]


class Compare(BaseModel):
    a: SetReceipt
    b: SetReceipt
    conclusion: Str20


class Myth(BaseModel):
    wrong: Str20
    right: Str28


class Confusion(BaseModel):
    items: Annotated[list[Myth], Field(min_length=2, max_length=3)]


class Example(BaseModel):
    """A real-world case drawn as [src] —action→ [dst]; dst is None when there is no counterpart."""

    name: Str10
    src: Str10
    action: Str8
    dst: Annotated[str, Field(min_length=1, max_length=10)] | None = None


class Menu(BaseModel):
    items: Annotated[list[Example], Field(min_length=3, max_length=4)]


class Options(BaseModel):
    situations: Annotated[list[Str18], Field(min_length=3, max_length=4)]


class Step(BaseModel):
    text: Str14
    who: Literal["a", "b", "other"]  # a/b = compare.a/b (colored), other = neither


class Steps(BaseModel):
    steps: Annotated[list[Step], Field(min_length=3, max_length=5)]


class SpecialNews(BaseModel):
    title: Str24
    source: Str12
    why: Str28  # how this item uses today's concept


class Special(BaseModel):
    news: Annotated[list[SpecialNews], Field(max_length=3)]
    fallback: Annotated[str, Field(max_length=40)] | None = None

    @model_validator(mode="after")
    def _need_fallback(self):
        if not self.news and not self.fallback:
            raise ValueError("news가 비어 있으면 fallback이 필요함")
        return self


class Warn(BaseModel):
    title: Str14
    reason: Str20


class Caution(BaseModel):
    items: Annotated[list[Warn], Field(min_length=3, max_length=3)]


class Total(BaseModel):
    points: Annotated[list[Str14], Field(min_length=3, max_length=3)]
    next_topic: Annotated[str, Field(max_length=14)] | None = None


class Post(BaseModel):
    topic_id: str
    cover: Cover
    definition: Definition
    compare: Compare
    confusion: Confusion
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


MAX_ATTEMPTS = 3  # first try + 2 retries with specific feedback


def _describe(e: ValidationError) -> str:
    lines = []
    for err in e.errors():
        loc = ".".join(str(x) for x in err["loc"])
        value = err.get("input")
        limit = (err.get("ctx") or {}).get("max_length")
        if err["type"] == "string_too_long" and isinstance(value, str):
            lines.append(f"- {loc}: '{value}' 는 {len(value)}자. 최대 {limit}자 → 더 짧은 말로 바꿔")
        else:
            lines.append(f"- {loc}: {err['msg']}")
    return "이전 답의 형식 오류(꼭 고칠 것, 글자 수는 공백 포함):\n" + "\n".join(lines)


def generate_post(
    topic: Topic,
    next_topic: Topic | None,
    news: list[Any],
    *,
    feedback: str | None = None,
    run=run_claude_json,
) -> Post:
    problem = None
    for _ in range(MAX_ATTEMPTS):
        prompt_feedback = "\n".join(filter(None, [feedback, problem])) or None
        try:
            return Post.model_validate(run(build_prompt(topic, next_topic, news, prompt_feedback)))
        except ClaudeError as e:
            problem = f"이전 답을 JSON으로 읽을 수 없었어. 설명 없이 JSON 객체 하나만 출력해. ({e})"
        except ValidationError as e:
            problem = _describe(e)
    raise ClaudeError(f"문구 형식 오류가 반복됨:\n{problem}")
