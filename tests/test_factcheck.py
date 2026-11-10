from pathlib import Path

import pytest

from hanip.claude_cli import ClaudeError
from hanip.content import Post
from hanip.crawler import NewsItem
from hanip.curriculum import Topic
from hanip.factcheck import CheckResult, check_post

FIXTURE = Path(__file__).parent / "fixtures" / "post_token.json"
TOPIC = Topic(id="client-server", title_ko="클라이언트와 서버", keyword_en="client server", level=1)
NEWS = [
    NewsItem("Agent API server released", "Hacker News", "https://a", "an API server for agents"),
    NewsItem("LLM running in the browser", "GeekNews", "https://b", "no server needed"),
]


def post():
    return Post.model_validate_json(FIXTURE.read_text())


def test_clean_post_passes_and_checker_sees_post_and_cited_news():
    seen = {}

    def run(p):
        seen["p"] = p
        return {"issues": []}

    r = check_post(TOPIC, post(), NEWS, run=run)
    assert r == CheckResult(ok=True, issues=[])
    assert "클라이언트와 서버" in seen["p"] and "Agent API server released" in seen["p"] and "https://a" in seen["p"]


def test_news_must_point_at_a_crawled_item():
    p = post()
    p.special.news[1].ref = 7
    r = check_post(TOPIC, p, NEWS, run=lambda _: {"issues": []})
    assert not r.ok and r.issues[0].field == "special.news.1.ref"


def test_news_source_is_taken_from_the_crawled_item():
    p = post()
    p.special.news[0].source = "해커뉴스"
    check_post(TOPIC, p, NEWS, run=lambda _: {"issues": []})
    assert p.special.news[0].source == "Hacker News"


def test_checker_issues_are_reported():
    run = lambda _: {"issues": [{"field": "compare.b.rows.0.value", "problem": "서버는 원격만이 아님", "fix": "다른 컴퓨터"}]}
    r = check_post(TOPIC, post(), NEWS, run=run)
    assert not r.ok and r.issues[0].problem == "서버는 원격만이 아님" and r.issues[0].fix == "다른 컴퓨터"


def test_feedback_text_lists_each_issue():
    run = lambda _: {"issues": [{"field": "definition.definition", "problem": "틀림", "fix": "고친 문장"}]}
    text = check_post(TOPIC, post(), NEWS, run=run).feedback()
    assert "definition.definition" in text and "틀림" in text and "고친 문장" in text


def test_checker_failure_is_not_a_pass():
    def boom(p):
        raise ClaudeError("down")

    with pytest.raises(ClaudeError):
        check_post(TOPIC, post(), NEWS, run=boom)


def test_malformed_checker_answer_is_an_error():
    with pytest.raises(ClaudeError):
        check_post(TOPIC, post(), NEWS, run=lambda _: ["nope"])


def test_checker_prompt_flags_only_wrong_explanations_not_simplifications():
    seen = {}

    def run(p):
        seen["p"] = p
        return {"issues": []}

    check_post(TOPIC, post(), NEWS, run=run)
    p = seen["p"]
    assert "틀린 설명만" in p
    assert "대표적인 경우" in p and "주로" in p  # typical-case simplifications are fine; no hedging fixes
    assert "오해를 부르게" not in p
