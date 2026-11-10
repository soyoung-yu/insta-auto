import subprocess
from types import SimpleNamespace

import pytest

from hanip.publish_images import ImageHostError, publish_images


def make_paths(tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    paths = []
    for i in range(1, 10):
        p = src / f"slide-{i:02d}.jpg"
        p.write_bytes(b"jpg")
        paths.append(p)
    return paths


def recording_git(calls, commit_code=0):
    def git(args, **kwargs):
        calls.append(args)
        code = commit_code if "commit" in args else 0
        return subprocess.CompletedProcess(args, code, stdout="nothing to commit" if code else "", stderr="")

    return git


def live_head(url, **kwargs):
    return SimpleNamespace(status_code=200, headers={"content-type": "image/jpeg"})


def test_copies_files_into_post_dir(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    publish_images(make_paths(tmp_path), number=3, repo_dir=repo, base_url="https://x", git=recording_git([]), http_head=live_head, sleep=lambda s: None)
    assert sorted(p.name for p in (repo / "posts" / "0003").iterdir()) == [f"slide-{i:02d}.jpg" for i in range(1, 10)]


def test_commits_only_post_dir_and_pushes(tmp_path):
    calls = []
    publish_images(make_paths(tmp_path), number=3, repo_dir=tmp_path, base_url="https://x", git=recording_git(calls), http_head=live_head, sleep=lambda s: None)
    commit = next(c for c in calls if "commit" in c)
    assert commit[-2:] == ["--", "posts/0003"]
    assert "No.03" in " ".join(commit)
    assert any("push" in c for c in calls)


def test_returns_raw_urls_in_order(tmp_path):
    urls = publish_images(make_paths(tmp_path), number=3, repo_dir=tmp_path, base_url="https://x", git=recording_git([]), http_head=live_head, sleep=lambda s: None)
    assert urls == [f"https://x/posts/0003/slide-{i:02d}.jpg" for i in range(1, 10)]


def test_nothing_to_commit_still_pushes(tmp_path):
    calls = []
    publish_images(make_paths(tmp_path), number=3, repo_dir=tmp_path, base_url="https://x", git=recording_git(calls, commit_code=1), http_head=live_head, sleep=lambda s: None)
    assert any("push" in c for c in calls)


def test_waits_until_urls_are_live(tmp_path):
    codes = iter([404] * 9 + [200] * 9)
    sleeps = []

    def head(url, **kwargs):
        return SimpleNamespace(status_code=next(codes), headers={"content-type": "image/jpeg"})

    urls = publish_images(make_paths(tmp_path), number=3, repo_dir=tmp_path, base_url="https://x", git=recording_git([]), http_head=head, sleep=sleeps.append)
    assert len(urls) == 9 and sleeps


def test_timeout_raises(tmp_path):
    def head(url, **kwargs):
        return SimpleNamespace(status_code=404, headers={})

    with pytest.raises(ImageHostError):
        publish_images(make_paths(tmp_path), number=3, repo_dir=tmp_path, base_url="https://x", git=recording_git([]), http_head=head, sleep=lambda s: None, wait_timeout=30)


def test_push_failure_raises(tmp_path):
    def git(args, **kwargs):
        code = 1 if "push" in args else 0
        return subprocess.CompletedProcess(args, code, stdout="", stderr="denied")

    with pytest.raises(ImageHostError):
        publish_images(make_paths(tmp_path), number=3, repo_dir=tmp_path, base_url="https://x", git=git, http_head=live_head, sleep=lambda s: None)
