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


def test_special_may_be_empty_then_the_slide_is_dropped():
    assert Special(news=[]).news == []


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


def test_generate_post_gives_up_after_three_invalid():
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


def test_generate_post_retries_once_on_non_json_answer():
    calls = []

    def run(p):
        calls.append(p)
        if len(calls) == 1:
            raise ClaudeError("답변이 JSON이 아님")
        return good()

    assert generate_post(TOPIC, None, [], run=run).topic_id == "client-server"
    assert "JSON" in calls[1]


def test_schema_has_no_summary_or_total_fields():
    from hanip.content import Caution, Definition, Menu, Options, SetReceipt, Steps
    for model in (Definition, Menu, Options, Steps, Caution):
        assert "summary" not in model.model_fields, model.__name__
    assert "total" not in SetReceipt.model_fields


def test_retry_feedback_names_field_length_and_limit_and_allows_two_retries():
    long_row = {"label": "서버", "value": "요청을 받아 처리하는 컴퓨터"}  # 15 chars, limit 14
    bad = good()
    bad["definition"]["rows"][1] = long_row
    calls = []

    def run(p):
        calls.append(p)
        return bad if len(calls) < 3 else good()

    generate_post(TOPIC, None, [], run=run)
    assert len(calls) == 3
    assert "definition.rows.1.value" in calls[1] and "15자" in calls[1] and "14자" in calls[1]


def test_ten_slide_schema_parts():
    from hanip.content import Confusion, SpecialNews, Step

    with pytest.raises(ValidationError):
        Step(text="요청", who="client")  # must be a / b / other
    with pytest.raises(ValidationError):
        Confusion(items=[{"wrong": "x", "right": "y"}])  # at least 2 myths
    assert SpecialNews(ref=0, title="t", source="HN", why="에이전트가 서버를 부름").why
    p = Post.model_validate_json(FIXTURE.read_text())
    assert p.options.situations[0] == "에러가 어디서 났는지 볼 때"
    assert p.cover.title == "클라이언트와 서버가 뭐야?"  # full term, no abbreviation


def test_review_notes_are_included_in_the_prompt():
    seen = {}

    def run(p):
        seen["p"] = p
        return good()

    generate_post(TOPIC, None, [], notes="- 표지 제목은 줄이지 마", run=run)
    assert "표지 제목은 줄이지 마" in seen["p"]
