"""Recent news for slide 7 from GeekNews (RSS) and Hacker News (Algolia search).

find_news never raises: a broken source is skipped so the daily post still goes out.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone

import feedparser
import requests

from hanip.claude_cli import ClaudeError, run_claude_json
from hanip.curriculum import Topic

log = logging.getLogger(__name__)

GEEKNEWS_RSS = "https://news.hada.io/rss/news"
HN_SEARCH = "https://hn.algolia.com/api/v1/search_by_date"
TIMEOUT = 15


@dataclass
class NewsItem:
    title: str
    source: str
    url: str
    summary: str


def fetch_geeknews(keyword: str, *, title_ko: str | None = None, http_get=requests.get) -> list[NewsItem]:
    r = http_get(GEEKNEWS_RSS, timeout=TIMEOUT)
    r.raise_for_status()
    feed = feedparser.parse(r.content)
    needles = [keyword.lower()] + ([title_ko.lower()] if title_ko else [])
    items = []
    for e in feed.entries:
        summary = e.get("summary", "")
        haystack = f"{e.get('title', '')} {summary}".lower()
        if any(n in haystack for n in needles):
            items.append(NewsItem(e.get("title", ""), "GeekNews", e.get("link", ""), summary[:300]))
    return items


def fetch_hn(
    keyword: str, *, since_days: int = 30, now: datetime | None = None, http_get=requests.get
) -> list[NewsItem]:
    now = now or datetime.now(timezone.utc)
    since = int(now.timestamp()) - since_days * 86400
    params = {"query": keyword, "tags": "story", "numericFilters": f"created_at_i>{since}"}
    r = http_get(HN_SEARCH, params=params, timeout=TIMEOUT)
    r.raise_for_status()
    items = []
    for h in r.json().get("hits", []):
        url = h.get("url") or f"https://news.ycombinator.com/item?id={h['objectID']}"
        items.append(NewsItem(h.get("title") or "", "Hacker News", url, (h.get("story_text") or "")[:300]))
    return items


USAGE_PROMPT = """너는 기술 뉴스 검색 도우미야. 개념 "{title}"({keyword})이 **요즘 실제 제품·서비스·오픈소스에서 쓰인 사례**를
Hacker News에서 찾으려고 해. 개념 설명 글이 아니라 "이 개념을 써서 만든 것/바꾼 것" 소식이 걸리도록 짧은 영어 검색어 3개를 만들어.
각 검색어는 2~5 단어. JSON 문자열 배열만 출력."""


def suggest_usage_queries(topic: Topic, *, run=run_claude_json) -> list[str]:
    """Search queries aimed at real-world uses of the concept; falls back to the plain keyword."""
    try:
        raw = run(USAGE_PROMPT.format(title=topic.title_ko, keyword=topic.keyword_en))
        queries = [q.strip() for q in raw if isinstance(q, str) and 0 < len(q.strip()) <= 60]
    except (ClaudeError, TypeError) as e:
        log.warning("usage query generation failed: %s", e)
        queries = []
    return queries[:3] or [topic.keyword_en]


def find_news(topic: Topic, limit: int = 3, *, queries: list[str] | None = None, http_get=requests.get) -> list[NewsItem]:
    collected: list[NewsItem] = []
    sources = [lambda: fetch_geeknews(topic.keyword_en, title_ko=topic.title_ko, http_get=http_get)]
    sources += [lambda q=q: fetch_hn(q, http_get=http_get) for q in (queries or [topic.keyword_en])]
    for fetch in sources:
        try:
            collected.extend(fetch())
        except Exception as e:  # noqa: BLE001 - any source failure must not stop the post
            log.warning("news source failed: %s", e)
    seen: set[str] = set()
    out = []
    for item in collected:
        if item.url in seen or not item.title:
            continue
        seen.add(item.url)
        out.append(item)
        if len(out) == limit:
            break
    return out
