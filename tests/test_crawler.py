from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import requests

from hanip.crawler import NewsItem, fetch_geeknews, fetch_hn, find_news
from hanip.curriculum import Topic

FIX = Path(__file__).parent / "fixtures"
TOPIC = Topic(id="token", title_ko="토큰", keyword_en="token", level=1)


def resp(text=None, json_data=None):
    return SimpleNamespace(
        text=text, content=(text or "").encode(), json=lambda: json_data, raise_for_status=lambda: None
    )


def gn_get(url, **k):
    return resp(text=(FIX / "geeknews.xml").read_text())


def hn_get(url, **k):
    import json

    return resp(json_data=json.loads((FIX / "hn.json").read_text()))


def test_geeknews_filters_by_keyword_or_korean_title():
    items = fetch_geeknews("token", title_ko="토큰", http_get=gn_get)
    assert [i.url for i in items] == ["https://news.hada.io/topic?id=1", "https://news.hada.io/topic?id=3"]
    assert all(i.source == "GeekNews" for i in items)


def test_hn_uses_since_window_and_falls_back_to_item_url():
    seen = []

    def get(url, **k):
        seen.append((url, k.get("params")))
        return hn_get(url)

    now = datetime(2026, 11, 10, tzinfo=timezone.utc)
    items = fetch_hn("token", since_days=30, now=now, http_get=get)
    params = seen[0][1]
    assert params["query"] == "token"
    assert params["numericFilters"] == f"created_at_i>{int(now.timestamp()) - 30 * 86400}"
    assert items[1].url == "https://news.ycombinator.com/item?id=12"
    assert all(i.source == "Hacker News" for i in items)


def test_find_news_dedupes_and_limits():
    def get(url, **k):
        return gn_get(url) if "hada" in url else hn_get(url)

    items = find_news(TOPIC, limit=3, http_get=get)
    urls = [i.url for i in items]
    assert len(urls) == 3 and len(set(urls)) == 3
    assert urls[:2] == ["https://news.hada.io/topic?id=1", "https://news.hada.io/topic?id=3"]


def test_find_news_survives_source_error():
    def boom(*a, **k):
        raise requests.ConnectionError("down")

    assert find_news(TOPIC, http_get=boom) == []


def test_newsitem_fields():
    assert NewsItem("t", "s", "u", "x").summary == "x"
