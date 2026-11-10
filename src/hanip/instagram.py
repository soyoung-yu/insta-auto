"""Instagram API (Instagram Login flavor): carousel publishing and long-lived token refresh.

Flow: one container per image (is_carousel_item) → carousel container → media_publish.
Each container is polled until status_code is FINISHED before it is used.
"""

from __future__ import annotations

import time

import requests

GRAPH = "https://graph.instagram.com"
POLL_SECONDS = 5
TIMEOUT = 30


class InstagramError(Exception):
    pass


def _check(r: requests.Response) -> dict:
    try:
        data = r.json()
    except ValueError:
        data = {}
    if r.status_code >= 400 or "error" in data:
        msg = (data.get("error") or {}).get("message") or r.text[:300]
        raise InstagramError(f"Instagram API 오류 ({r.status_code}): {msg}")
    return data


class InstagramClient:
    def __init__(self, user_id: str, token: str, *, api_version: str, session: requests.Session | None = None, sleep=time.sleep):
        self.user_id = user_id
        self.token = token
        self.base = f"{GRAPH}/{api_version}"
        self.http = session or requests.Session()
        self.sleep = sleep

    def _post(self, path: str, data: dict) -> dict:
        return _check(self.http.post(f"{self.base}/{path}", data={**data, "access_token": self.token}, timeout=TIMEOUT))

    def create_image_item(self, image_url: str) -> str:
        return self._post(f"{self.user_id}/media", {"image_url": image_url, "is_carousel_item": "true"})["id"]

    def create_carousel(self, children: list[str], caption: str) -> str:
        data = {"media_type": "CAROUSEL", "children": ",".join(children), "caption": caption}
        return self._post(f"{self.user_id}/media", data)["id"]

    def wait_until_ready(self, container_id: str, timeout: int = 300) -> None:
        waited = 0
        while True:
            r = self.http.get(
                f"{self.base}/{container_id}",
                params={"fields": "status_code", "access_token": self.token},
                timeout=TIMEOUT,
            )
            status = _check(r).get("status_code")
            if status == "FINISHED":
                return
            if status in ("ERROR", "EXPIRED"):
                raise InstagramError(f"컨테이너 {container_id} 상태 {status}")
            if waited >= timeout:
                raise InstagramError(f"컨테이너 {container_id} 준비 시간 초과 (상태 {status})")
            self.sleep(POLL_SECONDS)
            waited += POLL_SECONDS

    def publish(self, container_id: str) -> str:
        return self._post(f"{self.user_id}/media_publish", {"creation_id": container_id})["id"]

    def post_carousel(self, image_urls: list[str], caption: str) -> str:
        children = [self.create_image_item(u) for u in image_urls]
        for c in children:
            self.wait_until_ready(c)
        carousel = self.create_carousel(children, caption)
        self.wait_until_ready(carousel)
        return self.publish(carousel)


def refresh_token(token: str, *, session: requests.Session | None = None) -> tuple[str, int]:
    http = session or requests.Session()
    r = http.get(
        f"{GRAPH}/refresh_access_token",
        params={"grant_type": "ig_refresh_token", "access_token": token},
        timeout=TIMEOUT,
    )
    data = _check(r)
    return data["access_token"], int(data.get("expires_in", 0))
