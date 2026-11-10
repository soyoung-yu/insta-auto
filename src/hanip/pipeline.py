"""Daily run and approval: weekend/duplicate guards, token refresh, generate → render → (approve) → publish.

State only advances after a successful publish, so any failure retries the same topic next run.
"""

from __future__ import annotations

import dataclasses
import json
import logging
from dataclasses import dataclass
from datetime import date
from enum import StrEnum
from pathlib import Path
from typing import Any, Callable

from hanip import crawler, render
from hanip import instagram as ig
from hanip import notify as notify_mod
from hanip.claude_cli import ClaudeError
from hanip.config import Settings
from hanip.content import Post, generate_post
from hanip.curriculum import load_curriculum
from hanip.publish_images import publish_images
from hanip.state import (
    HistoryEntry,
    Inflight,
    Pending,
    State,
    already_published_on,
    load_state,
    needs_approval,
    next_number,
    save_state,
    theme_for,
)

log = logging.getLogger(__name__)

TOKEN_REFRESH_DAYS = 50
MAX_GENERATIONS = 3  # first try + 2 retries on overflow
APP = "오늘의 한입"


class Outcome(StrEnum):
    SKIPPED_WEEKEND = "skipped_weekend"
    ALREADY_POSTED = "already_posted"
    PENDING_APPROVAL = "pending_approval"
    PUBLISHED = "published"
    FAILED = "failed"
    CURRICULUM_EXHAUSTED = "curriculum_exhausted"
    NOTHING_TO_APPROVE = "nothing_to_approve"


def _make_instagram(settings: Settings):
    return ig.InstagramClient(settings.ig_user_id, settings.ig_access_token, api_version=settings.ig_api_version)


@dataclass
class Deps:
    find_news: Callable[..., Any] = crawler.find_news
    generate_post: Callable[..., Any] = generate_post
    render_post: Callable[..., Any] = render.render_post
    write_preview: Callable[..., Any] = render.write_preview
    publish_images: Callable[..., Any] = publish_images
    make_instagram: Callable[[Settings], Any] = _make_instagram
    refresh_token: Callable[..., Any] = ig.refresh_token
    notify: Callable[[str, str], None] = notify_mod.notify
    open_file: Callable[[Path], None] = notify_mod.open_file


def full_caption(post: Post) -> str:
    return f"{post.caption}\n\n{' '.join(post.hashtags)}"


def _maybe_refresh_token(settings: Settings, state: State, today: date, deps: Deps) -> Settings:
    last = date.fromisoformat(state.token_refreshed_at) if state.token_refreshed_at else None
    if last and (today - last).days < TOKEN_REFRESH_DAYS:
        return settings
    try:
        token, expires_in = deps.refresh_token(settings.ig_access_token)
    except Exception as e:  # noqa: BLE001 - an old token may still work; don't block the post
        log.warning("token refresh failed: %s", e)
        deps.notify(APP, f"토큰 갱신 실패: {e}")
        return settings
    settings.token_path.parent.mkdir(parents=True, exist_ok=True)
    settings.token_path.write_text(
        json.dumps({"access_token": token, "expires_in": expires_in, "refreshed_at": today.isoformat()})
    )
    settings.token_path.chmod(0o600)
    state.token_refreshed_at = today.isoformat()
    save_state(state, settings.state_path)
    return dataclasses.replace(settings, ig_access_token=token)


def _generate_and_render(settings, topic, next_topic, number, theme, out_dir, deps) -> tuple[Post, list[Path]]:
    news = deps.find_news(topic)
    feedback = None
    for _ in range(MAX_GENERATIONS):
        post = deps.generate_post(topic, next_topic, news, feedback=feedback)
        result = deps.render_post(post, number=number, theme=theme, handle=settings.account_handle, out_dir=out_dir)
        if not result.overflow:
            (out_dir / "post.json").write_text(post.model_dump_json(indent=2))
            return post, result.paths
        slides = ", ".join(str(n) for n in result.overflow)
        feedback = f"{slides}장 글자가 넘쳐서 잘렸어. 그 장의 문구를 더 짧게 써."
        log.info("overflow on slides %s, regenerating", slides)
    raise ClaudeError(f"글자 넘침이 계속됨 ({feedback})")


def _record(state: State, settings: Settings, *, number: int, day: str, topic_id: str, theme: str, media_id: str) -> None:
    state.published_count += 1
    state.curriculum_index += 1
    state.history.append(HistoryEntry(number, day, topic_id, theme, media_id))
    if state.pending and state.pending.number == number:
        state.pending = None
    state.inflight = None
    save_state(state, settings.state_path)


def _publish(settings: Settings, state: State, *, number: int, topic_id: str, theme: str, out_dir: Path, today: date, deps: Deps) -> Outcome:
    try:
        post = Post.model_validate_json((out_dir / "post.json").read_text())
        paths = [out_dir / f"slide-{i:02d}.jpg" for i in range(1, 10)]
        urls = deps.publish_images(paths, number=number, repo_dir=settings.repo_dir, base_url=settings.image_base_url)
        client = deps.make_instagram(settings)
        container = client.prepare_carousel(urls, full_caption(post))
    except Exception as e:  # noqa: BLE001 - nothing is public yet; keep state for a retry
        log.exception("publish preparation failed")
        deps.notify(APP, f"No.{number:02d} 게시 실패: {e}")
        return Outcome.FAILED
    # Remember the container before publishing: if media_publish succeeds but the response is lost,
    # the next run checks this container instead of posting the same episode again.
    state.inflight = Inflight(number, topic_id, theme, today.isoformat(), container)
    save_state(state, settings.state_path)
    try:
        media_id = client.publish(container)
    except Exception as e:  # noqa: BLE001
        log.exception("media_publish failed")
        deps.notify(APP, f"No.{number:02d} 게시 결과를 알 수 없어요. 다음 실행에서 확인합니다: {e}")
        return Outcome.FAILED
    _record(state, settings, number=number, day=today.isoformat(), topic_id=topic_id, theme=theme, media_id=media_id)
    deps.notify(APP, f"No.{number:02d} 게시 완료")
    return Outcome.PUBLISHED


def _resolve_inflight(settings: Settings, state: State, today: date, deps: Deps) -> Outcome | None:
    """Settle a publish whose outcome was unknown. Returns an Outcome to stop, or None to continue."""
    inf = state.inflight
    if not inf:
        return None
    try:
        client = deps.make_instagram(settings)
        status = client.container_status(inf.container_id)
        if status == "PUBLISHED":
            _record(state, settings, number=inf.number, day=inf.date, topic_id=inf.topic_id, theme=inf.theme,
                    media_id=f"container:{inf.container_id}")
            deps.notify(APP, f"No.{inf.number:02d}은 이미 게시돼 있었어요. 기록만 정리했어요.")
            return None
        if status == "FINISHED":
            media_id = client.publish(inf.container_id)
            _record(state, settings, number=inf.number, day=today.isoformat(), topic_id=inf.topic_id, theme=inf.theme,
                    media_id=media_id)
            deps.notify(APP, f"No.{inf.number:02d} 게시 완료")
            return Outcome.PUBLISHED
    except Exception as e:  # noqa: BLE001 - unknown outcome: never risk a duplicate post
        log.exception("in-flight check failed")
        deps.notify(APP, f"No.{inf.number:02d} 게시 여부를 확인하지 못했어요: {e}")
        return Outcome.FAILED
    log.info("in-flight container %s is %s; dropping it", inf.container_id, status)
    state.inflight = None
    save_state(state, settings.state_path)
    return None


def run_daily(settings: Settings, *, today: date, deps: Deps | None = None) -> Outcome:
    deps = deps or Deps()
    if today.weekday() >= 5:
        return Outcome.SKIPPED_WEEKEND
    state = load_state(settings.state_path)
    day = today.isoformat()
    settings = _maybe_refresh_token(settings, state, today, deps)
    resolved = _resolve_inflight(settings, state, today, deps)
    if resolved:
        return resolved
    if already_published_on(state, day):
        return Outcome.ALREADY_POSTED
    if state.pending and state.pending.date == day:
        deps.open_file(Path(state.pending.dir) / "preview.html")
        return Outcome.PENDING_APPROVAL

    topics = load_curriculum(settings.curriculum_path)
    if state.curriculum_index >= len(topics):
        deps.notify(APP, "커리큘럼을 모두 소진했어요. python -m hanip curriculum --force 로 새로 만들어 주세요.")
        return Outcome.CURRICULUM_EXHAUSTED
    topic = topics[state.curriculum_index]
    next_topic = topics[state.curriculum_index + 1] if state.curriculum_index + 1 < len(topics) else None

    number = next_number(state)
    theme = theme_for(number)
    out_dir = settings.out_dir / f"{number:04d}"
    try:
        post, paths = _generate_and_render(settings, topic, next_topic, number, theme, out_dir, deps)
    except Exception as e:  # noqa: BLE001 - generation/render failure must not post anything
        log.exception("generation failed")
        deps.notify(APP, f"No.{number:02d} 생성 실패: {e}")
        return Outcome.FAILED

    if needs_approval(number):
        preview = deps.write_preview(paths, full_caption(post), out_dir)
        state.pending = Pending(day, topic.id, number, theme, str(out_dir))
        save_state(state, settings.state_path)
        deps.open_file(preview)
        deps.notify(APP, f"No.{number:02d} 미리보기를 확인하고 승인해 주세요: python -m hanip approve")
        return Outcome.PENDING_APPROVAL

    return _publish(settings, state, number=number, topic_id=topic.id, theme=theme, out_dir=out_dir, today=today, deps=deps)


def approve(settings: Settings, *, today: date, deps: Deps | None = None) -> Outcome:
    deps = deps or Deps()
    state = load_state(settings.state_path)
    resolved = _resolve_inflight(settings, state, today, deps)
    if resolved:
        return resolved
    p = state.pending
    if not p or p.date != today.isoformat():
        return Outcome.NOTHING_TO_APPROVE
    return _publish(settings, state, number=p.number, topic_id=p.topic_id, theme=p.theme, out_dir=Path(p.dir), today=today, deps=deps)
