"""Cube monster SVGs (cover, ending, 4 filler poses) for light and dark themes.

Geometry is copied from the approved mockups in
docs/superpowers/specs/2026-11-10-insta-auto-mockups/.
"""

from __future__ import annotations

from markupsafe import Markup

CHAR_THEMES = {
    "light": dict(body="#ffadc9", leg="#e57fa6", ant="#1b1430", bobble="rect", ink="#1b1430", mouth="#1b1430", fx="#e8a3bd"),
    "dark": dict(body="#f7f5fb", leg="#d6d0e4", ant="#f7f5fb", bobble="star", ink="#0b0f20", mouth="#0b0f20", fx="#6d6488"),
}

STAR = "200,36 203.8,46.7 214.3,47.4 206.2,54 208.8,64.1 200,58.5 191.2,64.1 193.8,54 185.7,47.4 196.2,46.7"


def _bobble(t: dict) -> str:
    if t["bobble"] == "rect":
        return f'<rect x="190" y="46" width="20" height="16" fill="#ffd166" stroke="{t["ink"]}" stroke-width="5"/>'
    return f'<polygon points="{STAR}" fill="#5b9dff" stroke="{t["ink"]}" stroke-width="4" stroke-linejoin="round"/>'


def _antenna(t: dict, tilt: float = 0) -> str:
    return (
        f'<g transform="rotate({tilt} 200 90)"><line x1="200" y1="90" x2="200" y2="60" '
        f'stroke="{t["ant"]}" stroke-width="6"/>{_bobble(t)}</g>'
    )


def _leg(t: dict, x: float, y: float, h: float = 32, transform: str = "") -> str:
    tr = f' transform="{transform}"' if transform else ""
    return (
        f'<rect{tr} x="{x}" y="{y}" width="40" height="{h}" fill="{t["leg"]}" '
        f'stroke="{t["ink"]}" stroke-width="7"/>'
    )


def cover_svg(theme: str) -> Markup:
    """Open-mouth cube (slide 1). Mouth area in viewBox units: x 90..310, y 150..375. No tongue."""
    t = CHAR_THEMES[theme]
    i = t["ink"]
    return Markup(
        f'<svg class="char-cover" viewBox="40 30 320 410" xmlns="http://www.w3.org/2000/svg">'
        f'<rect x="130" y="398" width="40" height="34" fill="{t["leg"]}" stroke="{i}" stroke-width="6"/>'
        f'<rect x="230" y="398" width="40" height="34" fill="{t["leg"]}" stroke="{i}" stroke-width="6"/>'
        f'<rect x="70" y="90" width="260" height="315" rx="14" fill="{t["body"]}" stroke="{i}" stroke-width="7"/>'
        f"{_antenna(t)}"
        f'<rect x="140" y="112" width="18" height="24" fill="{i}"/>'
        f'<rect x="242" y="112" width="18" height="24" fill="{i}"/>'
        f'<rect x="90" y="150" width="220" height="225" rx="10" fill="{t["mouth"]}"/>'
        f'<rect x="112" y="150" width="20" height="18" fill="#fff"/>'
        f'<rect x="268" y="150" width="20" height="18" fill="#fff"/>'
        f"</svg>"
    )


def _closed_body(t: dict, *, legs: str, eyes: str | None = None, tilt: float = 0, paper: bool = False) -> str:
    i = t["ink"]
    eyes = eyes or (
        f'<rect x="140" y="108" width="18" height="24" fill="{i}"/>'
        f'<rect x="242" y="108" width="18" height="24" fill="{i}"/>'
    )
    doc = (
        '<g transform="rotate(14 200 200)">'
        f'<rect x="172" y="164" width="56" height="48" fill="#fff" stroke="{i}" stroke-width="5"/>'
        '<line x1="182" y1="178" x2="218" y2="178" stroke="#ff5d8f" stroke-width="5"/>'
        '<line x1="182" y1="190" x2="208" y2="190" stroke="#b9c2e8" stroke-width="5"/></g>'
        if paper
        else ""
    )
    return (
        f"{legs}"
        f'<rect x="70" y="90" width="260" height="180" rx="14" fill="{t["body"]}" stroke="{i}" stroke-width="7"/>'
        f"{_antenna(t, tilt)}{eyes}"
        f'<line x1="100" y1="150" x2="300" y2="150" stroke="{i}" stroke-width="7" stroke-linecap="round"/>'
        f'<rect x="120" y="153" width="20" height="18" fill="#fff" stroke="{i}" stroke-width="4"/>'
        f'<rect x="260" y="153" width="20" height="18" fill="#fff" stroke="{i}" stroke-width="4"/>'
        f"{doc}"
        f'<path d="M138 192 h124 v34 q0 28 -28 28 h-68 q-28 0 -28 -28 z" fill="#ffd166" '
        f'stroke="{i}" stroke-width="6" stroke-linejoin="round"/>'
    )


def ending_svg(theme: str) -> Markup:
    """Flat closed-mouth cube with a document tilted 14° right in its flat pouch (slide 9)."""
    t = CHAR_THEMES[theme]
    legs = _leg(t, 130, 262) + _leg(t, 230, 262)
    return Markup(
        f'<svg class="char-ending" viewBox="60 40 280 260" xmlns="http://www.w3.org/2000/svg">'
        f"{_closed_body(t, legs=legs, paper=True)}</svg>"
    )


def _waddle(t: dict) -> str:
    legs = _leg(t, 130, 262) + _leg(t, 232, 258, 28, "rotate(-28 272 262)")
    fx = t["fx"]
    marks = (
        f'<path d="M40 150 q-18 20 0 40 M22 140 q-26 30 0 60" stroke="{fx}" stroke-width="6" fill="none" stroke-linecap="round"/>'
        f'<path d="M360 150 q18 20 0 40 M378 140 q26 30 0 60" stroke="{fx}" stroke-width="6" fill="none" stroke-linecap="round"/>'
    )
    return marks + f'<g transform="rotate(-9 200 290)">{_closed_body(t, legs=legs, tilt=-14)}</g>'


def _rolling(t: dict) -> str:
    legs = _leg(t, 130, 262) + _leg(t, 230, 262)
    fx = t["fx"]
    marks = (
        f'<path d="M20 230 h70 M10 260 h60 M30 200 h50" stroke="{fx}" stroke-width="7" stroke-linecap="round"/>'
        f'<circle cx="95" cy="320" r="14" fill="{fx}" opacity=".5"/><circle cx="70" cy="326" r="9" fill="{fx}" opacity=".4"/>'
    )
    eyes = f'<path d="M140 110 l18 12 l-18 12 M260 110 l-18 12 l18 12" stroke="{t["ink"]}" stroke-width="7" fill="none"/>'
    return marks + f'<g transform="translate(30 -25) rotate(35 200 190)">{_closed_body(t, legs=legs, eyes=eyes, tilt=-20)}</g>'


def _butterfly(t: dict) -> str:
    i, fx = t["ink"], t["fx"]
    legs = _leg(t, 118, 258, 30) + _leg(t, 240, 262)
    fly = (
        '<g transform="translate(340 55)">'
        f'<path d="M0 0 q-24 -26 -30 0 q-4 18 30 4 z" fill="#ff8fb3" stroke="{i}" stroke-width="3"/>'
        f'<path d="M0 0 q24 -26 30 0 q4 18 -30 4 z" fill="#ffd166" stroke="{i}" stroke-width="3"/>'
        f'<line x1="0" y1="-8" x2="0" y2="10" stroke="{i}" stroke-width="4"/></g>'
        f'<path d="M250 40 q30 -30 60 0" stroke="{fx}" stroke-width="4" stroke-dasharray="6 8" fill="none"/>'
    )
    eyes = f'<rect x="150" y="104" width="18" height="24" fill="{i}"/><rect x="252" y="104" width="18" height="24" fill="{i}"/>'
    speed = f'<path d="M30 200 h40 M20 230 h40" stroke="{fx}" stroke-width="6" stroke-linecap="round"/>'
    return speed + fly + (
        f'<g transform="translate(-10 30) scale(.88) rotate(8 200 290)">{_closed_body(t, legs=legs, eyes=eyes, tilt=18)}</g>'
    )


def _daze(t: dict) -> str:
    i, fx = t["ink"], t["fx"]
    legs = _leg(t, 130, 262) + _leg(t, 230, 262)
    eyes = f'<rect x="140" y="112" width="18" height="10" fill="{i}"/><rect x="242" y="112" width="18" height="10" fill="{i}"/>'
    bubble = (
        f'<circle cx="330" cy="70" r="7" fill="none" stroke="{fx}" stroke-width="4"/>'
        f'<circle cx="350" cy="44" r="10" fill="none" stroke="{fx}" stroke-width="4"/>'
        f'<circle cx="355" cy="14" r="4" fill="{fx}"/><circle cx="370" cy="14" r="4" fill="{fx}"/><circle cx="385" cy="14" r="4" fill="{fx}"/>'
    )
    return bubble + f'<g transform="translate(0 10)">{_closed_body(t, legs=legs, eyes=eyes)}</g>'


_POSE_FUNCS = {"waddle": _waddle, "rolling": _rolling, "butterfly": _butterfly, "daze": _daze}
POSES = tuple(_POSE_FUNCS)


def pose_svg(name: str, theme: str) -> Markup:
    t = CHAR_THEMES[theme]
    return Markup(
        f'<svg class="char-pose" data-pose="{name}" viewBox="-30 0 460 330" xmlns="http://www.w3.org/2000/svg">'
        f"{_POSE_FUNCS[name](t)}</svg>"
    )
