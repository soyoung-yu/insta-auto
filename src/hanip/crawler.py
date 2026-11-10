"""Recent news for slide 7 from GeekNews (RSS) and Hacker News (Algolia search).

find_news never raises: a broken source is skipped so the daily post still goes out.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone

import feedparser
import requests

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


def find_news(topic: Topic, limit: int = 3, *, http_get=requests.get) -> list[NewsItem]:
    collected: list[NewsItem] = []
    sources = [
        lambda: fetch_geeknews(topic.keyword_en, title_ko=topic.title_ko, http_get=http_get),
        lambda: fetch_hn(topic.keyword_en, http_get=http_get),
    ]
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
