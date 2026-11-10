"""Fact check a generated post before it is rendered or published.

Two layers:
1. Code: every news item must cite (ref) an item we actually crawled; its source is copied from that item.
2. A separate `claude -p` call reviews each claim and reports factual errors (no web search: plan A).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from importlib.resources import files
from typing import Any

from hanip.claude_cli import ClaudeError, run_claude_json
from hanip.content import Post
from hanip.curriculum import Topic


@dataclass
class Issue:
    field: str
    problem: str
    fix: str = ""


@dataclass
class CheckResult:
    ok: bool
    issues: list[Issue] = field(default_factory=list)

    def feedback(self) -> str:
        lines = [f"- {i.field}: {i.problem}" + (f" → 제안: {i.fix}" if i.fix else "") for i in self.issues]
        return "사실 확인에서 나온 문제(꼭 고칠 것):\n" + "\n".join(lines)

    def report(self) -> str:
        return "사실 확인: 통과" if self.ok else self.feedback()


def _ground_news(post: Post, news: list[Any]) -> list[Issue]:
    issues = []
    for i, item in enumerate(post.special.news):
        if not 0 <= item.ref < len(news):
            issues.append(Issue(f"special.news.{i}.ref", "크롤링한 소식 목록에 없는 번호야. 지어낸 소식은 넣지 마"))
            continue
        item.source = news[item.ref].source
    return issues


def check_post(topic: Topic, post: Post, news: list[Any], *, run=run_claude_json) -> CheckResult:
    issues = _ground_news(post, news)
    cited = [
        {"ref": n.ref, "title": news[n.ref].title, "url": news[n.ref].url, "snippet": news[n.ref].summary, "why_in_post": n.why}
        for n in post.special.news
        if 0 <= n.ref < len(news)
    ]
    prompt = (
        files("hanip.prompts").joinpath("factcheck.md").read_text()
        .replace("{topic}", topic.title_ko)
        .replace("{post}", post.model_dump_json(indent=1))
        .replace("{news}", json.dumps(cited, ensure_ascii=False, indent=1))
    )
    raw = run(prompt)
    if not isinstance(raw, dict) or not isinstance(raw.get("issues"), list):
        raise ClaudeError(f"사실 확인 답변 형식 오류: {str(raw)[:200]}")
    for it in raw["issues"]:
        if isinstance(it, dict) and it.get("problem"):
            issues.append(Issue(str(it.get("field", "")), str(it["problem"]), str(it.get("fix", ""))))
    return CheckResult(ok=not issues, issues=issues)
