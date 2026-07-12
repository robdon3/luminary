"""
Multi-phase ASCII scenes for Earth → Moon campaign.

Same display budget spirit: fixed character grid, no GPU.
"""

from __future__ import annotations

from luminary.mission.ascii_view import (
    VIEW_H,
    VIEW_W,
    _star_at,
    render_viewport,
    side_by_side,
)


def _blank() -> list[list[str]]:
    return [[" "] * VIEW_W for _ in range(VIEW_H)]


def _put(grid: list[list[str]], x: int, y: int, ch: str) -> None:
    if 0 <= y < VIEW_H and 0 <= x < VIEW_W and ch:
        grid[y][x] = ch[0]


def _blit(grid: list[list[str]], x: int, y: int, rows: list[str]) -> None:
    for dy, row in enumerate(rows):
        for dx, ch in enumerate(row):
            if ch != " ":
                _put(grid, x + dx, y + dy, ch)


def _stars(grid: list[list[str]], tick: int, y0: int = 0, y1: int | None = None) -> None:
    y1 = VIEW_H if y1 is None else y1
    for y in range(y0, y1):
        for x in range(VIEW_W):
            ch = _star_at(x, y, tick)
            if ch != " ":
                grid[y][x] = ch


def _border(lines: list[str], title: str, color: bool, alarm: bool) -> list[str]:
    w = VIEW_W
    top = "╔" + "═" * w + "╗"
    bot = "╚" + "═" * w + "╝"
    out = [top]
    for row in lines:
        body = (row + " " * w)[:w]
        out.append("║" + body + "║")
    out.append(bot)
    # HUD title line inside bottom caption area
    cap = (title + " " * w)[:w]
    out.append("║" + cap + "║")
    out.append(bot)
    if not color:
        return out
    painted = []
    for i, ln in enumerate(out):
        if alarm and i == 0:
            painted.append(f"\033[1;37;41m{ln}\033[0m")
        elif i == 0 or i == len(out) - 1 or i == len(out) - 3:
            painted.append(f"\033[36m{ln}\033[0m")
        else:
            painted.append(ln)
    return painted


def _grid_to_rows(grid: list[list[str]]) -> list[str]:
    return ["".join(r) for r in grid]


# ── scene renderers ────────────────────────────────────────────────────


def scene_pad(*, tick: int, thrusting: bool, color: bool, alarm: bool) -> list[str]:
    g = _blank()
    # sky
    for y in range(10):
        for x in range(VIEW_W):
            g[y][x] = _star_at(x, y, tick) if y < 6 else " "
    # earth horizon band
    for x in range(VIEW_W):
        g[10][x] = "~" if (x + tick // 2) % 5 else "-"
        g[11][x] = "#"
        g[12][x] = "#"
        g[13][x] = "="
        g[14][x] = "="
        g[15][x] = "="
    # tower
    for y in range(4, 13):
        _put(g, 18, y, "|")
        _put(g, 19, y, "|")
    _blit(g, 16, 3, ["[=]"])
    # rocket on pad
    rocket = [
        "  /\\  ",
        " |##| ",
        " |##| ",
        " |##| ",
        "/_||_\\",
    ]
    _blit(g, 22, 8, rocket)
    if thrusting:
        flame = "  ^^  " if tick % 2 == 0 else "  **  "
        _blit(g, 22, 13, [flame])
        # dust
        for x in range(20, 32):
            if (x + tick) % 3 == 0:
                _put(g, x, 14, "*")
    title = f" PAD  KENNEDY-CLASS  t={tick}  [SPACE] IGNITE"
    return _border(_grid_to_rows(g), title, color, alarm)


def scene_ascent(
    *,
    alt: int,
    max_alt: int,
    vel: int,
    thrust: int,
    tick: int,
    color: bool,
    alarm: bool,
    stage: int,
) -> list[str]:
    g = _blank()
    _stars(g, tick, 0, 12)
    # atmosphere gradient as density of ':' near bottom when low
    atmo = max(0, 8 - alt // 20)
    for y in range(VIEW_H - atmo, VIEW_H):
        for x in range(VIEW_W):
            if g[y][x] == " ":
                g[y][x] = ":" if (x + y) % 4 == 0 else "."
    # ground only very low
    if alt < 40:
        for x in range(VIEW_W):
            g[VIEW_H - 1][x] = "#"
            g[VIEW_H - 2][x] = "="

    # rocket position by altitude (bottom → top as we climb… inverted: high alt = high on screen)
    # pad at bottom of sky
    sky = 12
    t = max(0.0, min(1.0, alt / max(1, max_alt)))
    y = int((1.0 - t) * (sky - 6))
    y = max(0, min(sky - 6, y))
    x = 24 + (tick // 4) % 3 - 1

    if stage <= 0:
        body = ["  /\\  ", " |S1| ", " |##| ", "/_||_\\"]
    else:
        body = ["  /\\  ", " |S2| ", " |**| ", "  ||  "]
    _blit(g, x, y, body)
    if thrust > 0:
        fl = "  ##  " if tick % 2 == 0 else "  **  "
        _blit(g, x, y + 4, [fl])
        if thrust > 20:
            _blit(g, x, y + 5, ["  vv  "])

    # Earth curve low
    if alt < 120:
        for x2 in range(VIEW_W):
            _put(g, x2, VIEW_H - 1, "e" if x2 % 7 == 0 else "~")

    title = f" ASCENT  alt={alt}  vel={vel}  stg={stage}  thr={thrust}"
    return _border(_grid_to_rows(g), title, color, alarm)


def scene_orbit(
    *,
    alt: int,
    vel: int,
    tick: int,
    color: bool,
    alarm: bool,
    circularized: bool,
) -> list[str]:
    g = _blank()
    _stars(g, tick)
    # Earth disk bottom-left
    earth = [
        "   .--.   ",
        "  (####)  ",
        " (######) ",
        "  (####)  ",
        "   '--'   ",
    ]
    _blit(g, 2, 9, earth)
    # craft on orbital path
    ox = 20 + (tick % 28)
    oy = 4 + (tick // 7) % 3
    _blit(g, ox, oy, ["[>]", " | "])
    path = "orbit LOCKED" if circularized else "ellipse — need circ burn"
    title = f" EARTH ORBIT  alt={alt}  vel={vel}  {path}"
    return _border(_grid_to_rows(g), title, color, alarm)


def scene_tli(
    *,
    tick: int,
    thrusting: bool,
    dv_done: int,
    dv_need: int,
    color: bool,
    alarm: bool,
) -> list[str]:
    g = _blank()
    _stars(g, tick)
    _blit(g, 2, 11, ["  .--.  ", " (####) ", "  '--'  "])
    _blit(g, 40, 2, [" (·) ", "moon"])
    # transfer arc dots
    for i in range(12):
        _put(g, 12 + i * 2, 9 - i // 3, ".")
    craft_x = 14 + min(20, (dv_done * 20) // max(1, dv_need))
    _blit(g, craft_x, 7, ["{>}"])
    if thrusting:
        _blit(g, craft_x - 3, 7, ["###"] if tick % 2 == 0 else ["***"])
    title = f" TLI BURN  Δv {dv_done}/{dv_need}  hold [SPACE]"
    return _border(_grid_to_rows(g), title, color, alarm)


def scene_coast(
    *,
    tick: int,
    progress: int,  # 0..100
    color: bool,
    alarm: bool,
    midcourse: bool,
) -> list[str]:
    g = _blank()
    _stars(g, tick)
    # Earth left, Moon right
    _blit(g, 1, 10, [".--.", "(##)", "`--'"])
    _blit(g, 44, 3, ["(.)", " M "])
    # path
    for i in range(1, 40):
        _put(g, 6 + i, 8 - (i // 10), "-" if i % 2 == 0 else ".")
    cx = 6 + (progress * 38) // 100
    cy = 8 - (progress // 25)
    _blit(g, cx, cy, ["<*>"])
    if midcourse:
        _blit(g, cx - 2, cy, ["~"])
    title = f" TRANSLUNAR COAST  {progress}%  to Moon"
    return _border(_grid_to_rows(g), title, color, alarm)


def scene_loi(
    *,
    tick: int,
    thrusting: bool,
    dv_done: int,
    dv_need: int,
    color: bool,
    alarm: bool,
) -> list[str]:
    g = _blank()
    _stars(g, tick)
    # Moon large
    moon = [
        "    .----.    ",
        "  .'  o   '.  ",
        " /   o   o  \\ ",
        "|  o    o    |",
        " \\   o    o / ",
        "  '.  o   .'  ",
        "    '----'    ",
    ]
    _blit(g, 18, 4, moon)
    ox = 10 + (tick % 8)
    _blit(g, ox, 2, ["[LM]"])
    if thrusting:
        _blit(g, ox - 3, 2, ["##"] if tick % 2 else ["**"])
    title = f" LOI — LUNAR ORBIT INSERTION  Δv {dv_done}/{dv_need}"
    return _border(_grid_to_rows(g), title, color, alarm)


def scene_descent_wrapper(
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
    landed: bool,
    crashed: bool,
    color: bool,
) -> list[str]:
    """Reuse the lunar descent viewport."""
    return render_viewport(
        altitude=altitude,
        max_alt=max_alt,
        rate=rate,
        fuel=fuel,
        max_fuel=max_fuel,
        thrust=thrust,
        tick=tick,
        alarm=alarm,
        phase=phase,
        action_name=action_name,
        landed=landed,
        crashed=crashed,
        color=color,
    )


def render_campaign_scene(state: dict, color: bool = True) -> list[str]:
    """Dispatch on state['phase']."""
    phase = state["phase"]
    alarm = state.get("alarm", False)
    tick = state.get("tick", 0)

    if phase == "PAD":
        return scene_pad(
            tick=tick,
            thrusting=state.get("thrust", 0) > 0,
            color=color,
            alarm=alarm,
        )
    if phase == "ASCENT":
        return scene_ascent(
            alt=state["alt"],
            max_alt=state.get("max_alt", 200),
            vel=state["vel"],
            thrust=state.get("thrust", 0),
            tick=tick,
            color=color,
            alarm=alarm,
            stage=state.get("stage", 0),
        )
    if phase == "ORBIT":
        return scene_orbit(
            alt=state["alt"],
            vel=state["vel"],
            tick=tick,
            color=color,
            alarm=alarm,
            circularized=state.get("circularized", False),
        )
    if phase == "TLI":
        return scene_tli(
            tick=tick,
            thrusting=state.get("thrust", 0) > 0,
            dv_done=state.get("dv_done", 0),
            dv_need=state.get("dv_need", 100),
            color=color,
            alarm=alarm,
        )
    if phase == "COAST":
        return scene_coast(
            tick=tick,
            progress=state.get("progress", 0),
            color=color,
            alarm=alarm,
            midcourse=state.get("midcourse", False),
        )
    if phase == "LOI":
        return scene_loi(
            tick=tick,
            thrusting=state.get("thrust", 0) > 0,
            dv_done=state.get("dv_done", 0),
            dv_need=state.get("dv_need", 80),
            color=color,
            alarm=alarm,
        )
    if phase in {"DESCENT", "LANDING", "TOUCHDOWN"}:
        return scene_descent_wrapper(
            altitude=state.get("alt", 0),
            max_alt=state.get("max_alt", 1400),
            rate=state.get("rate", 0),
            fuel=state.get("fuel", 0),
            max_fuel=state.get("max_fuel", 1100),
            thrust=state.get("thrust", 0),
            tick=tick,
            alarm=alarm,
            phase=phase,
            action_name=state.get("action", "—"),
            landed=state.get("landed", False),
            crashed=state.get("crashed", False),
            color=color,
        )
    # fallback
    g = _blank()
    _stars(g, tick)
    return _border(_grid_to_rows(g), f" {phase}", color, alarm)
