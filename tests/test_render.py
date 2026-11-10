from pathlib import Path

import pytest
from PIL import Image

import hanip.render as render
from hanip.content import Post
from hanip.render import POSES, build_html, render_post, write_preview

FIXTURE = Path(__file__).parent / "fixtures" / "post_token.json"


@pytest.fixture
def post():
    return Post.model_validate_json(FIXTURE.read_text())


def test_build_html_has_nine_pages_with_series_tag(post):
    pages = build_html(post, number=7, theme="light", handle="@hanip.byte")
    assert len(pages) == 9
    assert "No.07" in pages[1]
    assert "@hanip.byte" in pages[0]
    assert "2 / 9" in pages[1]


def test_series_tag_three_digits(post):
    assert "No.112" in build_html(post, number=112, theme="light", handle="h")[1]


def test_ending_copy_is_fixed(post):
    last = build_html(post, number=1, theme="dark", handle="@hanip.byte")[8]
    assert "오늘의 한입 소화 완료" in last and "♥" in last
    assert "필요할 때 다시 먹으러 와" in last
    assert "컨텍스트 윈도우" in last


def test_theme_colors(post):
    assert "#fff7fa" in build_html(post, number=1, theme="light", handle="h")[1]
    assert "#16121e" in build_html(post, number=2, theme="dark", handle="h")[1]


def test_light_character_is_pink_with_yellow_bobble(post):
    cover = build_html(post, number=1, theme="light", handle="h")[0]
    assert "#ffadc9" in cover and "#ffd166" in cover


def test_dark_character_is_white_with_blue_star(post):
    cover = build_html(post, number=2, theme="dark", handle="h")[0]
    assert "#f7f5fb" in cover and "#5b9dff" in cover


def test_caution_slide_keeps_background_and_uses_yellow_border(post):
    light = build_html(post, number=1, theme="light", handle="h")[7]
    dark = build_html(post, number=2, theme="dark", handle="h")[7]
    assert "#f2b632" in light and "#fff7fa" in light
    assert "#ffd166" in dark and "#16121e" in dark
    assert "알레르기 정보" in light


def test_user_text_is_escaped(post):
    p = post.model_copy(deep=True)
    p.cover.title = "<b>x</b>"
    assert "<b>x</b>" not in build_html(p, number=1, theme="light", handle="h")[0]


def test_filler_pose_inserted_only_where_requested(post):
    pages = build_html(post, number=1, theme="light", handle="h", filler={3: "daze"})
    assert 'data-pose="daze"' in pages[2]
    assert "data-pose=" not in pages[1]


def test_render_outputs_nine_jpegs(post, tmp_path):
    r = render_post(post, number=1, theme="light", handle="@hanip.byte", out_dir=tmp_path)
    assert [p.name for p in r.paths] == [f"slide-{i:02d}.jpg" for i in range(1, 10)]
    for p in r.paths:
        with Image.open(p) as im:
            assert im.size == (1080, 1350) and im.format == "JPEG"
    assert r.overflow == []


def test_overflow_detected(post, tmp_path):
    long = post.model_copy(deep=True)
    long.definition.definition = "아주긴단어" * 12  # bypasses schema limits on purpose
    assert 2 in render_post(long, number=1, theme="light", handle="h", out_dir=tmp_path).overflow


def test_short_slide_gets_filler(post, tmp_path, monkeypatch):
    short = post.model_copy(deep=True)
    short.special.news = []
    short.special.fallback = "요즘 에이전트가 많아져서 중요해"
    seen = {}
    real = render.build_html

    def spy(*a, **k):
        seen.update(k.get("filler") or {})
        return real(*a, **k)

    monkeypatch.setattr(render, "build_html", spy)
    render_post(short, number=1, theme="light", handle="h", out_dir=tmp_path)
    assert 7 in seen
    assert set(seen.values()) <= set(POSES)
    assert 1 not in seen and 9 not in seen


def test_write_preview(post, tmp_path):
    paths = [tmp_path / f"slide-{i:02d}.jpg" for i in range(1, 10)]
    for p in paths:
        p.write_bytes(b"x")
    html = write_preview(paths, "캡션 <b>", tmp_path).read_text()
    assert html.count("<img") == 9 and "캡션 &lt;b&gt;" in html
