import re

import pytest
import responses
from responses import matchers

from hanip.instagram import InstagramClient, InstagramError, refresh_token

BASE = "https://graph.facebook.com/v23.0"  # system-user token (unified login) works only here
URLS = [f"https://x/slide-{i:02d}.jpg" for i in range(1, 10)]


def client(sleeps=None):
    return InstagramClient("U1", "TOK", api_version="v23.0", sleep=(sleeps.append if sleeps is not None else lambda s: None))


def add_status(cid, *codes):
    for code in codes:
        responses.get(f"{BASE}/{cid}", json={"status_code": code, "id": cid})


@responses.activate
def test_post_carousel_happy_path():
    for i in range(9):
        responses.post(f"{BASE}/U1/media", json={"id": f"C{i}"}, match=[matchers.urlencoded_params_matcher({"image_url": URLS[i], "is_carousel_item": "true", "access_token": "TOK"})])
    for i in range(9):
        add_status(f"C{i}", "FINISHED")
    responses.post(
        f"{BASE}/U1/media",
        json={"id": "CAR"},
        match=[matchers.urlencoded_params_matcher({"media_type": "CAROUSEL", "children": ",".join(f"C{i}" for i in range(9)), "caption": "hello", "access_token": "TOK"})],
    )
    add_status("CAR", "FINISHED")
    responses.post(f"{BASE}/U1/media_publish", json={"id": "MEDIA1"}, match=[matchers.urlencoded_params_matcher({"creation_id": "CAR", "access_token": "TOK"})])
    assert client().post_carousel(URLS, "hello") == "MEDIA1"


@responses.activate
def test_waits_through_in_progress():
    add_status("C1", "IN_PROGRESS", "IN_PROGRESS", "FINISHED")
    sleeps = []
    client(sleeps).wait_until_ready("C1")
    assert len(sleeps) == 2


@responses.activate
def test_error_status_raises():
    add_status("C1", "ERROR")
    with pytest.raises(InstagramError):
        client().wait_until_ready("C1")


@responses.activate
def test_carousel_error_does_not_publish():
    responses.post(f"{BASE}/U1/media", json={"id": "C"})
    responses.get(re.compile(f"{BASE}/C.*"), json={"status_code": "ERROR"})
    with pytest.raises(InstagramError):
        client().post_carousel(URLS[:2], "x")
    assert not any("media_publish" in c.request.url for c in responses.calls)


@responses.activate
def test_wait_times_out():
    responses.get(f"{BASE}/C1", json={"status_code": "IN_PROGRESS"})
    with pytest.raises(InstagramError):
        client().wait_until_ready("C1", timeout=10)


@responses.activate
def test_api_error_message_surfaces():
    responses.post(f"{BASE}/U1/media", status=400, json={"error": {"message": "Invalid token"}})
    with pytest.raises(InstagramError, match="Invalid token"):
        client().create_image_item(URLS[0])


@responses.activate
def test_refresh_token():
    responses.get(
        "https://graph.instagram.com/refresh_access_token",
        json={"access_token": "NEW", "token_type": "bearer", "expires_in": 5184000},
        match=[matchers.query_param_matcher({"grant_type": "ig_refresh_token", "access_token": "OLD"})],
    )
    assert refresh_token("OLD") == ("NEW", 5184000)


@responses.activate
def test_container_status():
    add_status("CAR", "PUBLISHED")
    assert client().container_status("CAR") == "PUBLISHED"


@responses.activate
def test_find_by_caption_head_matches_first_line():
    responses.get(f"{BASE}/U1/media", json={"data": [
        {"id": "M2", "caption": "다른 글\n\n본문"},
        {"id": "M1", "caption": "로그인은 한 번 했는데?\n\n1. 쿠키는"},
        {"id": "M0"},  # caption-less media must not break matching
    ]})
    assert client().find_by_caption_head("로그인은 한 번 했는데?") == "M1"
    assert client().find_by_caption_head("없는 글") is None


@responses.activate
def test_find_by_caption_head_raises_on_api_error():
    responses.get(f"{BASE}/U1/media", status=403, json={"error": {"message": "Application request limit reached"}})
    with pytest.raises(InstagramError):
        client().find_by_caption_head("x")


@responses.activate
def test_usage_headers_are_tracked_as_peak_and_call_count():
    responses.get(f"{BASE}/C1", json={"status_code": "IN_PROGRESS"}, headers={
        "x-app-usage": '{"call_count":40,"total_cputime":5,"total_time":7}'})
    responses.get(f"{BASE}/C1", json={"status_code": "FINISHED"}, headers={
        "x-business-use-case-usage": '{"123":[{"type":"instagram","call_count":82,"total_cputime":3,"total_time":9,"estimated_time_to_regain_access":0}]}'})
    c = client()
    c.wait_until_ready("C1")
    assert c.calls == 2
    assert c.peak_usage == {"app.call_count": 40, "app.total_cputime": 5, "app.total_time": 7,
                            "instagram.call_count": 82, "instagram.total_cputime": 3, "instagram.total_time": 9}
    assert "API 호출 2회" in c.usage_summary() and "instagram.call_count 82%" in c.usage_summary()


@responses.activate
def test_bad_usage_header_is_ignored():
    responses.get(f"{BASE}/C1", json={"status_code": "FINISHED"}, headers={"x-app-usage": "not json"})
    c = client()
    c.wait_until_ready("C1")
    assert c.calls == 1 and c.peak_usage == {}
