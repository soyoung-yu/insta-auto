from pathlib import Path

import pytest
from PIL import Image

import hanip.render as render
from hanip.content import Post
from hanip.render import POSES, SLIDES, build_html, render_post, write_preview

FIXTURE = Path(__file__).parent / "fixtures" / "post_token.json"


@pytest.fixture
def post():
    return Post.model_validate_json(FIXTURE.read_text())


def bodies(post, **kw):
    kw.setdefault("number", 1)
    kw.setdefault("theme", "light")
    kw.setdefault("handle", "h")
    return [p.split("</style>")[1] for p in build_html(post, **kw)]


def test_ten_slides():
    assert SLIDES == 10


def test_build_html_has_ten_pages_with_series_tag_and_page_numbers(post):
    pages = build_html(post, number=7, theme="light", handle="@hanip.byte")
    assert len(pages) == 10
    assert "No.07" in pages[1] and "2 / 10" in pages[1] and "10 / 10" in pages[9]
    assert "@hanip.byte" in pages[0]


def test_series_tag_three_digits(post):
    assert "No.112" in build_html(post, number=112, theme="light", handle="h")[1]


def test_ending_copy_is_fixed(post):
    last = bodies(post, theme="dark")[9]
    assert "오늘의 한입 소화 완료" in last and "♥" in last
    assert "필요할 때 다시 먹으러 와" in last
    assert "프론트엔드" in last


def test_theme_colors(post):
    assert "#fff7fa" in build_html(post, number=1, theme="light", handle="h")[1]
    assert "#16121e" in build_html(post, number=2, theme="dark", handle="h")[1]


def test_light_character_is_pink_with_yellow_bobble(post):
    cover = build_html(post, number=1, theme="light", handle="h")[0]
    assert "#ffadc9" in cover and "#ffd166" in cover


def test_dark_character_is_white_with_blue_star(post):
    cover = build_html(post, number=2, theme="dark", handle="h")[0]
    assert "#f7f5fb" in cover and "#5b9dff" in cover


def test_highlighter_question_titles_in_order(post):
    pages = bodies(post)
    titles = ["그래서 뭔데?", "뭐가 달라?", "헷갈리지 마!", "어디서 봤더라?", "어떻게 돌아가?",
              "언제 알아야 해?", "요즘 어디에 쓰여?", "이건 조심!", "오늘 먹은 것"]
    for page, title in zip(pages[1:], titles):
        assert f'<h2 class="hl">{title}</h2>' in page, title


def test_no_receipt_metaphor_words(post):
    pages = bodies(post)
    for word in ("한입 요약", "합계", "A 세트", "B 세트", "TODAY'S", "MENU", "ORDER OPTION", "KITCHEN", "알레르기", "메인 메뉴", "특선"):
        assert not any(word in p for p in pages), word


def test_paper_edges_first_paper_straight_top_last_straight_bottom(post):
    pages = bodies(post)
    assert 'class="paper' not in pages[0]
    assert 'class="paper edge-bottom' in pages[1]
    for n in range(3, 10):
        assert 'class="paper edge-both' in pages[n - 1], n
    assert 'class="paper edge-top' in pages[9]


def test_definition_breaks_line_after_comma_and_colors_the_two_concepts(post):
    page = bodies(post)[1]
    assert "요청하면 <span class=\"ca\">클라이언트</span>,<br>" in page
    assert "<span class=\"cb\">서버</span>" in page


def test_compare_is_a_table_with_colored_heads_and_shared_labels(post):
    page = bodies(post)[2]
    assert '<th class="ca">클라이언트</th>' in page and '<th class="cb">서버</th>' in page
    assert page.count('<td class="k">') == 3
    assert "같은 컴퓨터도 역할 따라 바뀌어" in page


def test_confusion_shows_wrong_then_right(post):
    page = bodies(post)[3]
    assert page.index("서버 = 큰 컴퓨터") < page.index("그 컴퓨터는 호스트")
    assert page.count('class="myth"') == 2


def test_examples_show_who_asks_whom_for_what(post):
    page = bodies(post)[4]
    assert page.count('class="rel"') == 4
    first = page.index("웹 브라우저")
    assert first < page.index("페이지 요청") < page.index("웹 서버")
    assert '<span class="src">웹 브라우저</span>' in page and '<span class="dst">웹 서버</span>' in page


def test_example_without_target_is_a_plain_card(post):
    p = post.model_copy(deep=True)
    p.menu.items[0].dst = None
    page = bodies(p)[4]
    assert page.count('class="rel"') == 3 and page.count('class="solo"') == 1


def test_situations_are_bubbles(post):
    assert bodies(post)[6].count('class="bubble') == 3


def test_flow_nodes_colored_by_actor(post):
    page = bodies(post)[5]
    assert page.count('class="node na"') == 2 and page.count('class="node nb"') == 2
    assert page.count('class="node no"') == 1
    assert page.count('class="arrow"') == 4


def test_usage_news_shows_why(post):
    page = bodies(post)[7]
    assert "에이전트가 도구 서버를 부르는 구조" in page


def test_caution_cards_keep_background_and_yellow_border(post):
    light = build_html(post, number=1, theme="light", handle="h")[8]
    dark = build_html(post, number=2, theme="dark", handle="h")[8]
    assert "#f2b632" in light and "#fff7fa" in light
    assert "#ffd166" in dark and "#16121e" in dark
    assert light.split("</style>")[1].count('class="warn"') == 3


def test_user_text_is_escaped(post):
    p = post.model_copy(deep=True)
    p.cover.title = "<b>x</b>"
    p.definition.definition = "<i>a</i>, b"
    pages = bodies(p)
    assert "<b>x</b>" not in pages[0] and "<i>a</i>" not in pages[1]


def test_filler_pose_inserted_only_where_requested(post):
    pages = bodies(post, filler={3: "daze"})
    assert 'data-pose="daze"' in pages[2]
    assert "data-pose=" not in pages[1]


def test_render_outputs_ten_jpegs(post, tmp_path):
    r = render_post(post, number=1, theme="light", handle="@hanip.byte", out_dir=tmp_path)
    assert [p.name for p in r.paths] == [f"slide-{i:02d}.jpg" for i in range(1, 11)]
    for p in r.paths:
        with Image.open(p) as im:
            assert im.size == (1080, 1350) and im.format == "JPEG"
    assert r.overflow == []


def test_long_cover_title_shrinks_instead_of_overflowing(post, tmp_path):
    p = post.model_copy(deep=True)
    p.cover.title = "오브젝트 스토리지(S3)가 뭐야?"  # 20 chars, schema maximum
    assert 1 not in render_post(p, number=1, theme="light", handle="h", out_dir=tmp_path).overflow


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
    assert 8 in seen
    assert set(seen.values()) <= set(POSES)
    assert 1 not in seen and 10 not in seen


def test_write_preview(tmp_path):
    paths = [tmp_path / f"slide-{i:02d}.jpg" for i in range(1, 11)]
    for p in paths:
        p.write_bytes(b"x")
    html = write_preview(paths, "캡션 <b>", tmp_path).read_text()
    assert html.count("<img") == 10 and "캡션 &lt;b&gt;" in html


def test_caution_paper_class_does_not_collide_with_warning_cards(post):
    page = bodies(post)[8]
    assert 'class="paper edge-both caution"' in page
