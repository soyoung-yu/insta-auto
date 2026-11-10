"""Put slide JPEGs in posts/NNNN/ of this (public) repo, push, and wait until raw URLs serve them."""

from __future__ import annotations

import shutil
import subprocess
import time
from pathlib import Path

import requests

POLL_SECONDS = 10


class ImageHostError(Exception):
    pass


def _git(git, repo_dir: Path, *args: str, check: bool = True):
    proc = git(["git", *args], cwd=repo_dir, capture_output=True, text=True)
    if check and proc.returncode != 0:
        raise ImageHostError(f"git {' '.join(args)} 실패: {proc.stderr.strip()[-300:]}")
    return proc


def publish_images(
    paths: list[Path],
    *,
    number: int,
    repo_dir: Path,
    base_url: str,
    git=subprocess.run,
    http_head=requests.head,
    sleep=time.sleep,
    wait_timeout: int = 300,
) -> list[str]:
    rel = f"posts/{number:04d}"
    dest = repo_dir / rel
    dest.mkdir(parents=True, exist_ok=True)
    for p in paths:
        shutil.copyfile(p, dest / p.name)

    _git(git, repo_dir, "add", rel)
    # exit code 1 here means "nothing to commit" (images already committed by an earlier attempt)
    _git(git, repo_dir, "commit", "-m", f"post: No.{number:02d}", "--", rel, check=False)
    _git(git, repo_dir, "push", "origin", "HEAD")

    urls = [f"{base_url.rstrip('/')}/{rel}/{p.name}" for p in paths]
    waited = 0
    pending = list(urls)
    while True:
        pending = [u for u in pending if not _is_live(http_head, u)]
        if not pending:
            return urls
        if waited >= wait_timeout:
            raise ImageHostError(f"이미지 주소가 열리지 않음: {pending[0]}")
        sleep(POLL_SECONDS)
        waited += POLL_SECONDS


def _is_live(http_head, url: str) -> bool:
    try:
        r = http_head(url, allow_redirects=True, timeout=15)
    except requests.RequestException:
        return False
    return r.status_code == 200 and r.headers.get("content-type", "").startswith("image/jpeg")
