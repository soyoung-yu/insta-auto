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
    assert "⚠ 주의" in light


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


def test_compare_receipts_never_exceed_frame(post, tmp_path):
    # real No.01 copy that pushed the right receipt off-screen (assignment bypasses schema limits)
    wide = post.model_copy(deep=True)
    copy = {"a": [("시작", "맨 꼭대기(/)부터"), ("예시", "/home/me/a.csv")],
            "b": [("시작", "지금 폴더부터"), ("특징", "위치 따라 달라져")]}
    for side, rows in copy.items():
        for row, (label, value) in zip(getattr(wide.compare, side).rows, rows):
            row.label, row.value = label, value
    r = render_post(wide, number=1, theme="light", handle="h", out_dir=tmp_path)
    # either it fits inside 1080px or the slide is reported as overflowing (→ regenerated shorter)
    if 3 not in r.overflow:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            b = p.chromium.launch(channel="chrome")
            pg = b.new_page(viewport={"width": 1080, "height": 1350})
            pg.goto((tmp_path / "_html" / "slide-03.html").resolve().as_uri())
            right = pg.evaluate("Math.max(...[...document.querySelectorAll('.two .paper')].map(e => e.getBoundingClientRect().right))")
            b.close()
        assert right <= 1080 - 90 + 1


def test_no_receipt_metaphor_words(post):
    pages = build_html(post, number=1, theme="light", handle="h")
    for word in ("한입 요약", "합계", "A 세트", "B 세트", "TODAY'S BITE", "MENU", "ORDER OPTION", "KITCHEN ORDER", "알레르기"):
        assert not any(word in p for p in pages), word


def test_plain_section_titles(post):
    pages = build_html(post, number=1, theme="light", handle="h")
    titles = ["정의", "비교", "예시", "언제 알아야 해", "동작 순서", "요즘 소식", "주의할 점", "요약"]
    for page, title in zip(pages[1:], titles):
        assert f'<div class="shop">{title}</div>' in page, title


def test_compare_uses_concept_names(post):
    page = build_html(post, number=1, theme="light", handle="h")[2]
    assert ">영어<" in page and ">한글<" in page


def test_paper_edges_mid_pages_torn_both_ends_last_page_torn_top_only(post):
    pages = [p.split("</style>")[1] for p in build_html(post, number=1, theme="light", handle="h")]
    assert "class=\"paper" not in pages[0]
    for n in range(2, 9):
        assert 'class="paper edge-both' in pages[n - 1], n
        assert "edge-top" not in pages[n - 1], n
    assert 'class="paper edge-top' in pages[8] and "edge-both" not in pages[8]
