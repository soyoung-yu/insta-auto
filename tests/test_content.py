import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from hanip.claude_cli import ClaudeError
from hanip.content import Post, Row, Special, generate_post
from hanip.curriculum import Topic

FIXTURE = Path(__file__).parent / "fixtures" / "post_token.json"
TOPIC = Topic(id="token", title_ko="토큰", keyword_en="token", level=1)
NEXT = Topic(id="context-window", title_ko="컨텍스트 윈도우", keyword_en="context window", level=1)
NEWS = SimpleNamespace(title="Token costs explained", source="Hacker News", url="https://x", summary="raw")


def good():
    return json.loads(FIXTURE.read_text())


def test_fixture_is_valid():
    Post.model_validate_json(FIXTURE.read_text())


def test_row_value_too_long_rejected():
    with pytest.raises(ValidationError):
        Row(label="단위", value="가" * 15)


def test_special_requires_fallback_when_no_news():
    with pytest.raises(ValidationError):
        Special(news=[], fallback=None)


def test_hashtag_count_bounds():
    with pytest.raises(ValidationError):
        Post.model_validate({**good(), "hashtags": ["#a"]})


def test_generate_post_retries_once_on_validation_error():
    bad = {**good(), "cover": {"title": "가" * 30, "subtitle": "x"}}
    calls = []

    def run(p):
        calls.append(p)
        return bad if len(calls) == 1 else good()

    post = generate_post(TOPIC, None, [], run=run)
    assert post.cover.title == good()["cover"]["title"]
    assert len(calls) == 2 and "cover" in calls[1]


def test_generate_post_gives_up_after_second_invalid():
    bad = {**good(), "cover": {"title": "가" * 30, "subtitle": "x"}}
    with pytest.raises(ClaudeError):
        generate_post(TOPIC, None, [], run=lambda p: bad)


def test_prompt_includes_news_next_topic_and_feedback():
    seen = {}

    def run(p):
        seen["p"] = p
        return good()

    generate_post(TOPIC, NEXT, [NEWS], feedback="2장 글자가 넘쳐", run=run)
    assert NEWS.title in seen["p"]
    assert NEXT.title_ko in seen["p"]
    assert "2장 글자가 넘쳐" in seen["p"]
    assert TOPIC.title_ko in seen["p"]
