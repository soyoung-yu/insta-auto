"""Turn a Post into nine 1080×1350 JPEG slides with Playwright (system Google Chrome).

Two passes: the first measures each slide (overflow, how far content reaches),
the second adds a filler character to mid slides whose content ends above half height.
"""

from __future__ import annotations

import html as html_lib
import re
from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path

from jinja2 import Environment, PackageLoader
from markupsafe import Markup, escape
from playwright.sync_api import Page, sync_playwright

from hanip.characters import POSES, cover_svg, ending_svg, pose_svg
from hanip.content import Post

__all__ = ["POSES", "SLIDES", "RenderResult", "build_html", "measure", "render_post", "write_preview"]

WIDTH, HEIGHT = 1080, 1350
HALF = HEIGHT / 2
CHROME_CHANNEL = "chrome"  # bundled Chromium download is blocked on the corporate network
JPEG_QUALITY = 92

SLIDES = 10

THEMES = {
    "light": dict(bg="#fff7fa", dots="#fbeef3", paper="#ffffff", edge="#f0d3df", text="#1b1430",
                  accent="#e8336f", muted="#9a90ad", warn_border="#f2b632", marker="#ffd166", bubble="#fff1f6",
                  a_bg="#ffd6e4", a_fg="#b8124d", b_bg="#fff1c2", b_fg="#8a6200", o_bg="#eee9f6", o_fg="#5b4f7a"),
    "dark": dict(bg="#16121e", dots="#1d1827", paper="#2a2238", edge="#3a3050", text="#f3eefc",
                 accent="#ff8fb3", muted="#7d7499", warn_border="#ffd166", marker="#8a6a1c", bubble="#3a2f4d",
                 a_bg="#5a2340", a_fg="#ffc2d8", b_bg="#4a3c14", b_fg="#ffd98a", o_bg="#322a44", o_fg="#c9bfe6"),
}

_env = Environment(loader=PackageLoader("hanip", "templates"), autoescape=True)
_FONTS = Path(str(files("hanip").joinpath("assets/fonts"))).resolve().as_uri()

MEASURE_JS = """() => {
  const fits = [...document.querySelectorAll('.fit')];
  const overflow = fits.some(e => e.scrollHeight > e.clientHeight + 1 || e.scrollWidth > e.clientWidth + 1);
  const c = document.querySelector('.content');
  let bottom = 0, right = 0;
  if (c) {
    for (const el of c.querySelectorAll('*')) {
      const r = el.getBoundingClientRect();
      right = Math.max(right, r.right);
    }
    for (const ch of c.children) bottom = Math.max(bottom, ch.getBoundingClientRect().bottom);
  }
  return {overflow: overflow || bottom > %d || right > %d, content_bottom: c ? bottom : %d};
}""" % (HEIGHT - 70, WIDTH - 89, HEIGHT)


FIT_JS = """() => {
  for (const el of document.querySelectorAll('[data-autofit]')) {
    const min = parseFloat(el.dataset.autofit);
    let size = parseFloat(getComputedStyle(el).fontSize);
    while ((el.scrollHeight > el.clientHeight + 1 || el.scrollWidth > el.clientWidth + 1) && size > min) {
      size -= 2;
      el.style.fontSize = size + 'px';
    }
  }
}"""


def concept_markup(text: str | None, a: str, b: str) -> Markup:
    """Escape text, color the two compared concept names, and break the line after each comma."""
    if not text:
        return Markup("")
    out = str(escape(text))
    names = sorted({(a, "ca"), (b, "cb")}, key=lambda x: -len(x[0]))
    pattern = "|".join(re.escape(str(escape(n))) for n, _ in names if n)
    if pattern:
        cls = {str(escape(n)): c for n, c in names}
        out = re.sub(pattern, lambda m: f'<span class="{cls[m.group(0)]}">{m.group(0)}</span>', out)
    out = re.sub(r",\s*", ",<br>", out)
    return Markup(out)


@dataclass
class RenderResult:
    paths: list[Path]
    overflow: list[int]


def build_html(
    post: Post,
    *,
    number: int,
    theme: str,
    handle: str,
    filler: dict[int, str] | None = None,
    center: bool = True,
) -> list[str]:
    filler = filler or {}
    tpl = _env.get_template("slides.html.j2")
    common = dict(
        post=post,
        c=THEMES[theme],
        tag=f"No.{number:02d}",
        handle=handle,
        fonts=_FONTS,
        cover_svg=cover_svg(theme),
        ending_svg=ending_svg(theme),
    )
    a, b = post.compare.a.name, post.compare.b.name
    common["concepts"] = lambda text: concept_markup(text, a, b)
    kinds = slide_kinds(post)
    common["total_slides"] = len(kinds)
    pages = []
    for pos, n in enumerate(kinds, start=1):
        pose = pose_svg(filler[n], theme) if n in filler else None
        align = "top" if (pose or not center) else "center"
        pages.append(tpl.render(n=n, pos=pos, pose=pose, align=align, **common))
    return pages


USAGE_SLIDE = 8


def slide_kinds(post: Post) -> list[int]:
    """Template slide kinds in order; the usage-news slide only appears when news was found."""
    return [n for n in range(1, SLIDES + 1) if n != USAGE_SLIDE or post.special.news]


def measure(page: Page) -> dict:
    return page.evaluate(MEASURE_JS)


def _load(page: Page, html: str, path: Path) -> None:
    path.write_text(html)
    page.goto(path.resolve().as_uri())
    page.evaluate("document.fonts.ready")
    page.evaluate(FIT_JS)


def render_post(post: Post, *, number: int, theme: str, handle: str, out_dir: Path) -> RenderResult:
    out_dir.mkdir(parents=True, exist_ok=True)
    html_dir = out_dir / "_html"
    html_dir.mkdir(exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(channel=CHROME_CHANNEL)
        try:
            page = browser.new_page(viewport={"width": WIDTH, "height": HEIGHT}, device_scale_factor=1)
            kinds = slide_kinds(post)
            first = build_html(post, number=number, theme=theme, handle=handle, center=False)
            filler = {}
            for pos, (kind, html) in enumerate(zip(kinds, first), start=1):
                _load(page, html, html_dir / f"slide-{pos:02d}.html")
                if 2 <= kind <= SLIDES - 1 and measure(page)["content_bottom"] < HALF:
                    filler[kind] = POSES[(number + pos) % len(POSES)]
            final = build_html(post, number=number, theme=theme, handle=handle, filler=filler)
            paths, overflow = [], []
            for n, html in enumerate(final, start=1):
                _load(page, html, html_dir / f"slide-{n:02d}.html")
                if measure(page)["overflow"]:
                    overflow.append(n)
                path = out_dir / f"slide-{n:02d}.jpg"
                page.screenshot(path=str(path), type="jpeg", quality=JPEG_QUALITY)
                paths.append(path)
        finally:
            browser.close()
    return RenderResult(paths=paths, overflow=overflow)


def write_preview(paths: list[Path], caption: str, out_dir: Path, report: str = "") -> Path:
    imgs = "\n".join(f'<img src="{p.name}" alt="{p.name}">' for p in paths)
    doc = f"""<!doctype html><html lang="ko"><head><meta charset="utf-8"><title>미리보기</title>
<style>body{{font-family:-apple-system,sans-serif;background:#eee;margin:24px}}
.grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}}img{{width:100%;display:block}}
pre{{white-space:pre-wrap;background:#fff;padding:16px;font-size:15px}}</style></head>
<body><div class="grid">{imgs}</div><h3>캡션</h3><pre>{html_lib.escape(caption)}</pre>
<h3>사실 확인</h3><pre>{html_lib.escape(report or "(기록 없음)")}</pre></body></html>"""
    out = out_dir / "preview.html"
    out.write_text(doc)
    return out
