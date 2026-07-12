"""
ASCII viewport for Luminary.

Design constraint (in spirit of Block II / era dreams):
  Fixed character framebuffer — no sprites beyond glyphs, no GPU.
  Width/height are small on purpose: a display an AGC-era engineer
  might *imagine* if they had a glass TTY, not a 4K monitor.

  VIEW_W × VIEW_H character cells. Stars are a deterministic hash of
  coordinates (not random RAM). Exhaust is a 2-frame flicker.
"""

from __future__ import annotations

from typing import Sequence

# Hard "display ROM" budget — the whole scene is this many cells
VIEW_W = 52
VIEW_H = 16
# surface occupies bottom rows
SURFACE_ROWS = 3


def _star_at(x: int, y: int, tick: int) -> str:
    """Sparse stars; a few twinkle by tick (no float, pure int hash)."""
    h = (x * 73 + y * 191 + (tick // 3) * 17) & 0xFFFF
    if h % 47 == 0:
        return "*" if (h + tick) % 5 else "+"
    if h % 89 == 0:
        return "."
    return " "


def _lander_sprite(thrust: int, rate: int, landed: bool, crashed: bool, frame: int) -> list[str]:
    """Return 5 rows × variable width lander art (pure ASCII)."""
    if crashed:
        return [
            r"  \ /  ",
            r"   X   ",
            r"  / \  ",
            r" # # # ",
            r"#######",
        ]
    if landed:
        return [
            r"   ^   ",
            r"  /|\  ",
            r" /_|_\ ",
            r"  / \  ",
            r"=======",
        ]

    body = [
        r"   ^   ",
        r"  /|\  ",
        r" /_|_\ ",
        r"  / \  ",
    ]
    if thrust <= 0:
        body.append(r"       ")
        return body

    # Flame size by thrust; flicker by frame
    if thrust < 12:
        flame = r"   *   " if frame % 2 == 0 else r"   +   "
    elif thrust < 28:
        flame = r"  ^*^  " if frame % 2 == 0 else r"  *v*  "
    else:
        flame = r" ^*#*^ " if frame % 2 == 0 else r" *v#v* "
    body.append(flame)

    # falling hard: slight lean via spaces (still mono)
    if rate < -40:
        body = [" " + row[:-1] if row else row for row in body]
    return body


def _surface_row(y_from_bottom: int, width: int, tick: int, dust: bool) -> str:
    """Moon surface with shallow craters."""
    chars = []
    for x in range(width):
        h = (x * 13 + y_from_bottom * 7) % 11
        if y_from_bottom == 0:
            ch = "=" if h > 2 else "-"
        elif y_from_bottom == 1:
            if h == 0:
                ch = "("
            elif h == 1:
                ch = ")"
            elif h == 5:
                ch = "o"
            else:
                ch = "."
        else:
            ch = ":" if h % 3 == 0 else "."
        if dust and y_from_bottom >= 1 and (x + tick) % 4 == 0:
            ch = "~"
        chars.append(ch)
    return "".join(chars)


def _alt_to_row(altitude: int, max_alt: int, sky_rows: int) -> int:
    """Map altitude to sky row (0 = top). Low altitude near surface."""
    if sky_rows <= 1:
        return 0
    if max_alt <= 0:
        return sky_rows - 1
    t = max(0.0, min(1.0, 1.0 - (altitude / max_alt)))
    # lander sits above surface; use sky_rows - lander height
    return int(round(t * (sky_rows - 1)))


def render_viewport(
    *,
    altitude: int,
    max_alt: int,
    rate: int,
    fuel: int,
    max_fuel: int,
    thrust: int,
    tick: int,
    alarm: bool,
    phase: str,
    action_name: str,
    landed: bool = False,
    crashed: bool = False,
    color: bool = True,
) -> list[str]:
    """
    Build VIEW_H lines of width VIEW_W for the lunar scene.
    Returns list of strings (no trailing newline).
    """
    w, h = VIEW_W, VIEW_H
    sky_h = h - SURFACE_ROWS
    grid = [[" "] * w for _ in range(h)]

    # stars
    for y in range(sky_h):
        for x in range(w):
            grid[y][x] = _star_at(x, y, tick)

    # Earth / horizon hint far away (tiny)
    if altitude > max_alt * 0.55:
        ex, ey = w - 6, 1
        if 0 <= ey < sky_h and 0 <= ex < w - 2:
            grid[ey][ex] = "o"
            grid[ey][ex + 1] = "."

    # surface
    dust = thrust > 8 and altitude < 200
    for i in range(SURFACE_ROWS):
        row = _surface_row(SURFACE_ROWS - 1 - i, w, tick, dust)
        for x, ch in enumerate(row):
            grid[sky_h + i][x] = ch

    # lander placement
    sprite = _lander_sprite(thrust, rate, landed, crashed, tick)
    sw = max(len(r) for r in sprite)
    sh = len(sprite)
    # horizontal: slight drift from tick for life (still deterministic)
    lx = (w - sw) // 2 + ((tick // 5) % 5) - 2
    lx = max(0, min(w - sw, lx))
    if landed or crashed:
        ly = sky_h - sh + 1
        ly = max(0, min(sky_h - 1, ly))
    else:
        ly = _alt_to_row(altitude, max_alt, max(1, sky_h - sh + 1))
        ly = max(0, min(sky_h - sh, ly))

    for dy, row in enumerate(sprite):
        yy = ly + dy
        if yy >= h:
            continue
        # last lander rows may overpaint top of surface when landing
        for dx, ch in enumerate(row):
            xx = lx + dx
            if 0 <= xx < w and 0 <= yy < h and ch != " ":
                grid[yy][xx] = ch

    # left altitude ruler (marks)
    for y in range(sky_h):
        if y % 4 == 0:
            grid[y][0] = "|"

    # compose lines with border labels
    lines: list[str] = []
    title = f" VIEWPORT {w}x{h} CHAR  ·  ERA-DREAM DISPLAY  ·  t={tick}"
    if alarm:
        title = " !! 1202 EXEC OVERFLOW — AI SHED — FLY THE VEHICLE !! "

    top = "╔" + "═" * w + "╗"
    bot = "╚" + "═" * w + "╝"
    lines.append(top)

    for y, row in enumerate(grid):
        body = "".join(row)
        # phase-colored border mark via plain prefix (color applied outside if needed)
        lines.append("║" + body + "║")

    lines.append(bot)

    # HUD strip under view (still ASCII, fixed width)
    fuel_cells = 12
    if max_fuel > 0:
        fn = int(round((fuel / max_fuel) * fuel_cells))
    else:
        fn = 0
    fuel_bar = "#" * fn + "-" * (fuel_cells - fn)
    fall = max(0, -rate)
    danger = "!" * min(8, fall // 8) if rate < -5 else "."

    hud1 = f"ALT {altitude:5d}  RATE {rate:+4d}  FUEL[{fuel_bar}]  THR {thrust:2d}"
    hud2 = f"ACT {action_name:6s} FALL {danger:8s} {phase[:22]}"
    # pad / trim to border width
    def _fit(s: str) -> str:
        s = s[:w]
        return s + " " * (w - len(s))

    lines.append("║" + _fit(hud1) + "║")
    lines.append("║" + _fit(hud2) + "║")
    lines.append("╚" + "═" * w + "╝")

    if color:
        lines = _colorize_viewport(lines, alarm=alarm, thrust=thrust, crashed=crashed, landed=landed)

    return lines


def _colorize_viewport(
    lines: list[str],
    *,
    alarm: bool,
    thrust: int,
    crashed: bool,
    landed: bool,
) -> list[str]:
    """Light ANSI pass — still character graphics, not a framebuffer API."""
    out: list[str] = []
    for i, line in enumerate(lines):
        if i == 0 and alarm:
            out.append(f"\033[1;37;41m{line}\033[0m")
            continue
        if crashed and i > 0:
            out.append(f"\033[31m{line}\033[0m")
            continue
        if landed and not crashed and i > 0:
            out.append(f"\033[32m{line}\033[0m")
            continue
        # flame-ish: highlight * # in lower sky — cheap full-line dim for thrust
        if thrust > 0 and 3 < i < VIEW_H:
            out.append(f"\033[33m{line}\033[0m")
        else:
            out.append(f"\033[36m{line}\033[0m" if i <= 1 else line)
    return out


def side_by_side(left: Sequence[str], right: Sequence[str], gap: str = "  ") -> list[str]:
    """Pad and join two column blocks."""
    # strip ANSI for width measure
    def vis_len(s: str) -> int:
        raw = s
        while "\033[" in raw:
            a = raw.index("\033[")
            b = raw.find("m", a)
            if b < 0:
                break
            raw = raw[:a] + raw[b + 1 :]
        return len(raw)

    n = max(len(left), len(right))
    lw = max((vis_len(x) for x in left), default=0)
    rw = max((vis_len(x) for x in right), default=0)
    rows = []
    for i in range(n):
        l = left[i] if i < len(left) else ""
        r = right[i] if i < len(right) else ""
        lpad = l + " " * max(0, lw - vis_len(l))
        rpad = r + " " * max(0, rw - vis_len(r))
        rows.append(lpad + gap + rpad)
    return rows
