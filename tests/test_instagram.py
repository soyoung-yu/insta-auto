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
