import json
from datetime import date, timedelta
from pathlib import Path

import pytest

from hanip.claude_cli import ClaudeError
from hanip.config import Settings
from hanip.content import Post
from hanip.curriculum import Topic, save_curriculum
from hanip.instagram import InstagramError
from hanip.pipeline import Deps, Outcome, approve, run_daily
from hanip.render import RenderResult
from hanip.state import HistoryEntry, Pending, State, load_state, save_state

FIXTURE = Path(__file__).parent / "fixtures" / "post_token.json"
MON = date(2026, 11, 16)  # Monday
TOPICS = [Topic(id=f"t{i}", title_ko=f"주제{i}", keyword_en=f"k{i}", level=1) for i in range(10)]


class Fake:
    """Records calls; each attribute is a Deps-compatible callable."""

    def __init__(self, overflow_times=0, ig_error=None, gen_error=None, publish_error=None, status="PUBLISHED"):
        self.calls = {}
        self.publish_error = publish_error  # raised by publish() but the post still went live
        self.status = status
        self.overflow_times = overflow_times
        self.ig_error = ig_error
        self.gen_error = gen_error
        self.notes = []
        self.published = []

    def _rec(self, name, *a, **k):
        self.calls.setdefault(name, []).append((a, k))

    def deps(self):
        def find_news(topic, **k):
            self._rec("find_news", topic)
            return []

        def generate_post(topic, next_topic, news, *, feedback=None, **k):
            self._rec("generate_post", topic, feedback=feedback)
            if self.gen_error:
                raise self.gen_error
            p = Post.model_validate_json(FIXTURE.read_text())
            p.topic_id = topic.id
            return p

        def render_post(post, *, number, theme, handle, out_dir):
            self._rec("render_post", number=number, theme=theme)
            out_dir.mkdir(parents=True, exist_ok=True)
            paths = []
            for i in range(1, 10):
                p = out_dir / f"slide-{i:02d}.jpg"
                p.write_bytes(b"x")
                paths.append(p)
            n = len(self.calls["render_post"])
            return RenderResult(paths, [2] if n <= self.overflow_times else [])

        def write_preview(paths, caption, out_dir):
            p = out_dir / "preview.html"
            p.write_text(caption)
            return p

        def publish_images(paths, *, number, repo_dir, base_url, **k):
            self._rec("publish_images", number=number)
            return [f"{base_url}/posts/{number:04d}/{p.name}" for p in paths]

        fake = self

        class IG:
            def __init__(self, settings):
                fake._rec("make_instagram", token=settings.ig_access_token)

            def prepare_carousel(self, urls, caption):
                fake._rec("prepare_carousel", urls, caption)
                if fake.ig_error:
                    raise fake.ig_error
                fake.last_caption = caption
                return f"CAR{len(fake.calls['prepare_carousel'])}"

            def publish(self, container_id):
                fake._rec("publish", container_id)
                if fake.publish_error:
                    err, fake.publish_error = fake.publish_error, None
                    if fake.status == "PUBLISHED":
                        fake.published.append(fake.last_caption)
                    raise err
                fake.published.append(fake.last_caption)
                return f"M{len(fake.published)}"

            def container_status(self, container_id):
                fake._rec("container_status", container_id)
                return fake.status

        def refresh_token(token, **k):
            self._rec("refresh_token", token)
            return ("NEWTOKEN", 5184000)

        return Deps(
            find_news=find_news,
            generate_post=generate_post,
            render_post=render_post,
            write_preview=write_preview,
            publish_images=publish_images,
            make_instagram=IG,
            refresh_token=refresh_token,
            notify=lambda t, m: self.notes.append((t, m)),
            open_file=lambda p: self._rec("open_file", p),
        )


@pytest.fixture
def settings(tmp_path):
    save_curriculum(TOPICS, tmp_path / "data" / "curriculum.json")
    return Settings(
        ig_user_id="U", ig_access_token="OLD", image_base_url="https://raw/x", ig_api_version="v23.0",
        repo_dir=tmp_path, var_dir=tmp_path / "var", out_dir=tmp_path / "out",
    )


def put_state(settings, **kw):
    kw.setdefault("token_refreshed_at", MON.isoformat())
    save_state(State(**kw), settings.state_path)


def state(settings):
    return load_state(settings.state_path)


def test_weekend_skips(settings):
    f = Fake()
    assert run_daily(settings, today=date(2026, 11, 14), deps=f.deps()) == Outcome.SKIPPED_WEEKEND
    assert "generate_post" not in f.calls


def test_first_run_waits_for_approval_with_light_theme(settings):
    put_state(settings)
    f = Fake()
    assert run_daily(settings, today=MON, deps=f.deps()) == Outcome.PENDING_APPROVAL
    s = state(settings)
    assert s.pending.number == 1 and s.pending.theme == "light" and s.pending.topic_id == "t0"
    assert s.pending.date == MON.isoformat()
    assert "publish_images" not in f.calls
    assert f.calls["open_file"] and f.notes


def test_pending_today_is_not_regenerated(settings):
    put_state(settings)
    f = Fake()
    run_daily(settings, today=MON, deps=f.deps())
    assert run_daily(settings, today=MON, deps=f.deps()) == Outcome.PENDING_APPROVAL
    assert len(f.calls["generate_post"]) == 1


def test_stale_pending_regenerates_same_topic(settings):
    put_state(settings, pending=Pending((MON - timedelta(days=1)).isoformat(), "t0", 1, "light", "out/0001"))
    f = Fake()
    assert run_daily(settings, today=MON, deps=f.deps()) == Outcome.PENDING_APPROVAL
    s = state(settings)
    assert s.pending.date == MON.isoformat() and s.pending.topic_id == "t0"


def test_approve_publishes_and_advances(settings):
    put_state(settings)
    f = Fake()
    run_daily(settings, today=MON, deps=f.deps())
    assert approve(settings, today=MON, deps=f.deps()) == Outcome.PUBLISHED
    s = state(settings)
    assert (s.published_count, s.curriculum_index, s.pending) == (1, 1, None)
    assert s.history[0] == HistoryEntry(1, MON.isoformat(), "t0", "light", "M1")
    assert "#오늘의한입" in f.published[0]


def test_approve_without_pending_today(settings):
    put_state(settings, pending=Pending((MON - timedelta(days=1)).isoformat(), "t0", 1, "light", "out/0001"))
    f = Fake()
    assert approve(settings, today=MON, deps=f.deps()) == Outcome.NOTHING_TO_APPROVE
    assert "publish_images" not in f.calls


def test_sixth_post_publishes_without_approval(settings):
    put_state(settings, published_count=5, curriculum_index=5)
    f = Fake()
    assert run_daily(settings, today=MON, deps=f.deps()) == Outcome.PUBLISHED
    assert f.calls["render_post"][0][1]["theme"] == "dark"
    assert state(settings).published_count == 6


def test_second_run_same_day_does_nothing(settings):
    put_state(settings, published_count=5, curriculum_index=5)
    f = Fake()
    run_daily(settings, today=MON, deps=f.deps())
    assert run_daily(settings, today=MON, deps=f.deps()) == Outcome.ALREADY_POSTED
    assert len(f.published) == 1


def test_overflow_retries_then_fails(settings):
    put_state(settings, published_count=5, curriculum_index=5)
    f = Fake(overflow_times=3)
    assert run_daily(settings, today=MON, deps=f.deps()) == Outcome.FAILED
    assert len(f.calls["generate_post"]) == 3
    assert "2장" in f.calls["generate_post"][1][1]["feedback"]
    assert state(settings).published_count == 5 and f.notes


def test_overflow_once_then_succeeds(settings):
    put_state(settings, published_count=5, curriculum_index=5)
    f = Fake(overflow_times=1)
    assert run_daily(settings, today=MON, deps=f.deps()) == Outcome.PUBLISHED


def test_claude_error_fails_without_state_change(settings):
    put_state(settings)
    f = Fake(gen_error=ClaudeError("x"))
    assert run_daily(settings, today=MON, deps=f.deps()) == Outcome.FAILED
    assert state(settings).pending is None


def test_publish_failure_keeps_state(settings):
    put_state(settings, published_count=5, curriculum_index=5)
    f = Fake(ig_error=InstagramError("boom"))
    assert run_daily(settings, today=MON, deps=f.deps()) == Outcome.FAILED
    s = state(settings)
    assert (s.published_count, s.curriculum_index) == (5, 5) and f.notes


def test_token_refreshed_after_50_days(settings):
    put_state(settings, published_count=5, curriculum_index=5, token_refreshed_at=(MON - timedelta(days=51)).isoformat())
    f = Fake()
    run_daily(settings, today=MON, deps=f.deps())
    assert f.calls["refresh_token"][0][0] == ("OLD",)
    assert json.loads(settings.token_path.read_text())["access_token"] == "NEWTOKEN"
    assert f.calls["make_instagram"][0][1]["token"] == "NEWTOKEN"
    assert state(settings).token_refreshed_at == MON.isoformat()


def test_token_not_refreshed_when_recent(settings):
    put_state(settings, published_count=5, curriculum_index=5, token_refreshed_at=(MON - timedelta(days=10)).isoformat())
    f = Fake()
    run_daily(settings, today=MON, deps=f.deps())
    assert "refresh_token" not in f.calls


def test_curriculum_exhausted(settings):
    put_state(settings, published_count=10, curriculum_index=10)
    f = Fake()
    assert run_daily(settings, today=MON, deps=f.deps()) == Outcome.CURRICULUM_EXHAUSTED
    assert f.notes


def test_missed_day_posts_only_next_topic(settings):
    put_state(settings, published_count=6, curriculum_index=6,
              history=[HistoryEntry(6, (MON - timedelta(days=3)).isoformat(), "t5", "dark", "M0")])
    f = Fake()
    assert run_daily(settings, today=MON, deps=f.deps()) == Outcome.PUBLISHED
    assert len(f.published) == 1 and state(settings).curriculum_index == 7


def test_next_topic_passed_for_preview_of_next_episode(settings):
    put_state(settings)
    f = Fake()
    run_daily(settings, today=MON, deps=f.deps())
    assert f.calls["generate_post"][0][0][0].id == "t0"


def test_publish_that_went_live_despite_error_is_not_reposted(settings):
    put_state(settings, published_count=5, curriculum_index=5)
    f = Fake(publish_error=InstagramError("timeout"), status="PUBLISHED")
    assert run_daily(settings, today=MON, deps=f.deps()) == Outcome.FAILED
    assert state(settings).inflight.number == 6
    tue = MON + timedelta(days=1)
    assert run_daily(settings, today=tue, deps=f.deps()) == Outcome.PUBLISHED
    s = state(settings)
    assert [h.number for h in s.history] == [6, 7]
    assert s.history[0].date == MON.isoformat()
    assert (s.published_count, s.curriculum_index, s.inflight) == (7, 7, None)
    assert len(f.published) == 2  # No.6 once, No.7 once


def test_inflight_published_today_stops_same_day_rerun(settings):
    put_state(settings, published_count=5, curriculum_index=5)
    f = Fake(publish_error=InstagramError("timeout"), status="PUBLISHED")
    run_daily(settings, today=MON, deps=f.deps())
    assert run_daily(settings, today=MON, deps=f.deps()) == Outcome.ALREADY_POSTED
    assert len(f.published) == 1


def test_finished_container_is_published_on_next_run_without_regenerating(settings):
    put_state(settings, published_count=5, curriculum_index=5)
    f = Fake(publish_error=InstagramError("5xx"), status="FINISHED")
    run_daily(settings, today=MON, deps=f.deps())
    gens = len(f.calls["generate_post"])
    assert run_daily(settings, today=MON, deps=f.deps()) == Outcome.PUBLISHED
    assert len(f.calls["generate_post"]) == gens
    assert f.calls["publish"][-1][0] == ("CAR1",)
    assert len(f.published) == 1 and state(settings).published_count == 6


def test_expired_inflight_is_dropped_and_same_topic_regenerated(settings):
    put_state(settings, published_count=5, curriculum_index=5)
    f = Fake(publish_error=InstagramError("5xx"), status="EXPIRED")
    run_daily(settings, today=MON, deps=f.deps())
    tue = MON + timedelta(days=1)
    assert run_daily(settings, today=tue, deps=f.deps()) == Outcome.PUBLISHED
    s = state(settings)
    assert s.history[0].topic_id == "t5" and s.inflight is None
