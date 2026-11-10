"""Turn a Post into nine 1080×1350 JPEG slides with Playwright (system Google Chrome).

Two passes: the first measures each slide (overflow, how far content reaches),
the second adds a filler character to mid slides whose content ends above half height.
"""

from __future__ import annotations

import html as html_lib
from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path

from jinja2 import Environment, PackageLoader
from playwright.sync_api import Page, sync_playwright

from hanip.characters import POSES, cover_svg, ending_svg, pose_svg
from hanip.content import Post

__all__ = ["POSES", "RenderResult", "build_html", "measure", "render_post", "write_preview"]

WIDTH, HEIGHT = 1080, 1350
HALF = HEIGHT / 2
CHROME_CHANNEL = "chrome"  # bundled Chromium download is blocked on the corporate network
JPEG_QUALITY = 92

THEMES = {
    "light": dict(bg="#fff7fa", dots="#fbeef3", paper="#ffffff", edge="#f0d3df", text="#1b1430",
                  accent="#e8336f", muted="#9a90ad", warn_border="#f2b632"),
    "dark": dict(bg="#16121e", dots="#1d1827", paper="#2a2238", edge="#3a3050", text="#f3eefc",
                 accent="#ff8fb3", muted="#7d7499", warn_border="#ffd166"),
}

_env = Environment(loader=PackageLoader("hanip", "templates"), autoescape=True)
_FONTS = Path(str(files("hanip").joinpath("assets/fonts"))).resolve().as_uri()

MEASURE_JS = """() => {
  const fits = [...document.querySelectorAll('.fit')];
  const overflow = fits.some(e => e.scrollHeight > e.clientHeight + 1 || e.scrollWidth > e.clientWidth + 1);
  const c = document.querySelector('.content');
  let bottom = 0;
  if (c) { for (const ch of c.children) bottom = Math.max(bottom, ch.getBoundingClientRect().bottom); }
  return {overflow: overflow || bottom > %d, content_bottom: c ? bottom : %d};
}""" % (HEIGHT - 70, HEIGHT)


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
    pages = []
    for n in range(1, 10):
        pose = pose_svg(filler[n], theme) if n in filler else None
        align = "top" if (pose or not center) else "center"
        pages.append(tpl.render(n=n, pose=pose, align=align, **common))
    return pages


def measure(page: Page) -> dict:
    return page.evaluate(MEASURE_JS)


def _load(page: Page, html: str, path: Path) -> None:
    path.write_text(html)
    page.goto(path.resolve().as_uri())
    page.evaluate("document.fonts.ready")


def render_post(post: Post, *, number: int, theme: str, handle: str, out_dir: Path) -> RenderResult:
    out_dir.mkdir(parents=True, exist_ok=True)
    html_dir = out_dir / "_html"
    html_dir.mkdir(exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(channel=CHROME_CHANNEL)
        try:
            page = browser.new_page(viewport={"width": WIDTH, "height": HEIGHT}, device_scale_factor=1)
            first = build_html(post, number=number, theme=theme, handle=handle, center=False)
            filler = {}
            for n, html in enumerate(first, start=1):
                _load(page, html, html_dir / f"slide-{n:02d}.html")
                if 2 <= n <= 8 and measure(page)["content_bottom"] < HALF:
                    filler[n] = POSES[(number + n) % len(POSES)]
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


def write_preview(paths: list[Path], caption: str, out_dir: Path) -> Path:
    imgs = "\n".join(f'<img src="{p.name}" alt="{p.name}">' for p in paths)
    doc = f"""<!doctype html><html lang="ko"><head><meta charset="utf-8"><title>미리보기</title>
<style>body{{font-family:-apple-system,sans-serif;background:#eee;margin:24px}}
.grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}}img{{width:100%;display:block}}
pre{{white-space:pre-wrap;background:#fff;padding:16px;font-size:15px}}</style></head>
<body><div class="grid">{imgs}</div><h3>캡션</h3><pre>{html_lib.escape(caption)}</pre></body></html>"""
    out = out_dir / "preview.html"
    out.write_text(doc)
    return out
