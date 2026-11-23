"""Instagram API (Instagram Login flavor): carousel publishing and long-lived token refresh.

Flow: one container per image (is_carousel_item) → carousel container → media_publish.
Each container is polled until status_code is FINISHED before it is used.
"""

from __future__ import annotations

import json
import logging
import time

import requests

GRAPH = "https://graph.instagram.com"  # Instagram-login tokens (refresh endpoint)
DEFAULT_HOST = "graph.facebook.com"  # unified-login system-user tokens
POLL_SECONDS = 15  # every status check counts toward the app rate limit (403 "Application request limit reached")
TIMEOUT = 30
USAGE_WARN_PCT = 75

log = logging.getLogger(__name__)


class InstagramError(Exception):
    pass


def caption_head(caption: str) -> str:
    """First non-empty line of a caption; each episode's hook line is unique."""
    return next((line.strip() for line in caption.splitlines() if line.strip()), "")


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
    def __init__(self, user_id: str, token: str, *, api_version: str, host: str = DEFAULT_HOST, session: requests.Session | None = None, sleep=time.sleep):
        self.user_id = user_id
        self.token = token
        self.base = f"https://{host}/{api_version}"
        self.http = session or requests.Session()
        self.sleep = sleep
        self.calls = 0
        self.peak_usage: dict[str, int] = {}  # highest % seen per metric, from Meta's rate-limit headers

    def _track(self, r: requests.Response) -> requests.Response:
        """Count the call and keep the peak of the usage headers, to see what fills the rate limit."""
        self.calls += 1
        usage: dict[str, int] = {}
        try:
            for k, v in json.loads(r.headers.get("x-app-usage") or "{}").items():
                usage[f"app.{k}"] = int(v)
            for entries in json.loads(r.headers.get("x-business-use-case-usage") or "{}").values():
                for e in entries:
                    for k in ("call_count", "total_cputime", "total_time"):
                        usage[f"{e.get('type', 'buc')}.{k}"] = int(e.get(k, 0))
        except (ValueError, TypeError, AttributeError):
            usage = {}
        for k, v in usage.items():
            self.peak_usage[k] = max(v, self.peak_usage.get(k, 0))
        if r.status_code >= 400 or any(v >= USAGE_WARN_PCT for v in usage.values()):
            log.warning("instagram api call #%d status %s usage %s", self.calls, r.status_code, usage or "(no header)")
        return r

    def usage_summary(self) -> str:
        peak = ", ".join(f"{k} {v}%" for k, v in sorted(self.peak_usage.items())) or "사용량 헤더 없음"
        return f"API 호출 {self.calls}회 · 최고 사용량: {peak}"

    def _post(self, path: str, data: dict) -> dict:
        return _check(self._track(self.http.post(f"{self.base}/{path}", data={**data, "access_token": self.token}, timeout=TIMEOUT)))

    def create_image_item(self, image_url: str) -> str:
        return self._post(f"{self.user_id}/media", {"image_url": image_url, "is_carousel_item": "true"})["id"]

    def create_carousel(self, children: list[str], caption: str) -> str:
        data = {"media_type": "CAROUSEL", "children": ",".join(children), "caption": caption}
        return self._post(f"{self.user_id}/media", data)["id"]

    def container_status(self, container_id: str) -> str:
        r = self.http.get(
            f"{self.base}/{container_id}",
            params={"fields": "status_code", "access_token": self.token},
            timeout=TIMEOUT,
        )
        return _check(self._track(r)).get("status_code", "")

    def wait_until_ready(self, container_id: str, timeout: int = 300) -> None:
        waited = 0
        while True:
            status = self.container_status(container_id)
            if status == "FINISHED":
                return
            if status in ("ERROR", "EXPIRED"):
                raise InstagramError(f"컨테이너 {container_id} 상태 {status}")
            if waited >= timeout:
                raise InstagramError(f"컨테이너 {container_id} 준비 시간 초과 (상태 {status})")
            self.sleep(POLL_SECONDS)
            waited += POLL_SECONDS

    def find_by_caption_head(self, head: str, limit: int = 10) -> str | None:
        """Media id of a recent post whose caption starts with this line: the ground truth for "did it go live"."""
        r = self.http.get(
            f"{self.base}/{self.user_id}/media",
            params={"fields": "id,caption", "limit": limit, "access_token": self.token},
            timeout=TIMEOUT,
        )
        for m in _check(self._track(r)).get("data", []):
            if caption_head(m.get("caption") or "") == caption_head(head):
                return m["id"]
        return None

    def publish(self, container_id: str) -> str:
        return self._post(f"{self.user_id}/media_publish", {"creation_id": container_id})["id"]

    def prepare_carousel(self, image_urls: list[str], caption: str) -> str:
        """Create and wait for all containers; returns the carousel container id (not yet published)."""
        children = [self.create_image_item(u) for u in image_urls]
        for c in children:
            self.wait_until_ready(c)
        carousel = self.create_carousel(children, caption)
        self.wait_until_ready(carousel)
        return carousel

    def post_carousel(self, image_urls: list[str], caption: str) -> str:
        return self.publish(self.prepare_carousel(image_urls, caption))


def refresh_token(token: str, *, session: requests.Session | None = None) -> tuple[str, int]:
    http = session or requests.Session()
    r = http.get(
        f"{GRAPH}/refresh_access_token",
        params={"grant_type": "ig_refresh_token", "access_token": token},
        timeout=TIMEOUT,
    )
    data = _check(r)
    return data["access_token"], int(data.get("expires_in", 0))
