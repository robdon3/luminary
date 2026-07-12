"""
Live lunar-descent console.

This is the point of Luminary for a human viewer:
  watch a vehicle fall, watch a tiny AI recommend burns,
  watch the executive throw the AI overboard under load (1202),
  and see whether the landing succeeds because of that discipline.
"""

from __future__ import annotations

import shutil
import sys
import time
from dataclasses import dataclass, field
from typing import TextIO

from luminary import CLOCK_HZ, RAM_WORDS, ROM_WORDS, __version__
from luminary.ai.bnn import demo_descent_net
from luminary.devices.imu import SyntheticIMU
from luminary.kernel.executive import Executive
from luminary.kernel.scheduler import ALARM_EXEC_OVERFLOW, AI_PRIORITY_FLOOR
from luminary.mission.ascii_view import render_viewport, side_by_side
from luminary.vm.cpu import MiniISA, encode


# ── human-readable AI actions ──────────────────────────────────────────
ACTIONS = {
    0: ("HOLD", "coast — prefer no extra burn", 0),
    1: ("SLOW", "prefer gentle braking", 1),
    2: ("BRAKE", "prefer hard braking", 2),
    3: ("ABORT", "prefer maximum braking", 3),
}

# landing quality thresholds (units/tick, toy physics)
SOFT_LAND_RATE = 15  # |rate| at touchdown for soft landing
HARD_LAND_RATE = 40


def target_descent_rate(altitude: int) -> int:
    """Desired vertical rate (negative = down). Always descending until touchdown."""
    if altitude > 900:
        return -26
    if altitude > 500:
        return -16
    if altitude > 200:
        return -9
    if altitude > 80:
        return -5
    if altitude > 25:
        return -3
    return -2


def guidance_burn(altitude: int, rate: int, fuel: int, ai_class: int) -> tuple[str, str, int]:
    """
    Legible landing law a viewer can follow.

    Always tries to descend, but not too fast. AI biases aggressiveness.
    Negative rate = falling.
    """
    name, note, _ = ACTIONS.get(ai_class, ("HOLD", "no recommendation", 0))

    if fuel <= 0:
        return name, "no fuel — free fall", 0

    target = target_descent_rate(altitude)
    # How much too fast are we falling? (positive => need brake)
    too_fast = target - rate

    if too_fast <= 0:
        return name, f"on profile (target {target:+d}) — coast", 0

    # thruster authority: enough to actually null rate errors near the ground
    burn = 2 + too_fast
    if altitude < 120:
        burn += 4
    if altitude < 40:
        burn += 6

    if ai_class == 0:
        burn = max(0, burn - 6)
        note = f"AI HOLD — light brake toward {target:+d}"
    elif ai_class == 1:
        note = f"AI SLOW — brake toward {target:+d}"
    elif ai_class == 2:
        burn = burn + 5
        note = f"AI BRAKE — firm toward {target:+d}"
    elif ai_class == 3:
        burn = burn + 10
        note = f"AI ABORT — max effort toward {target:+d}"
    else:
        note = f"heuristic toward {target:+d}"

    burn = max(0, min(50, burn))
    burn = min(burn, fuel)
    return name, note, burn


def _c(code: str, text: str, color: bool) -> str:
    if not color:
        return text
    return f"\033[{code}m{text}\033[0m"


def _bar(value: float, lo: float, hi: float, width: int = 40, fill: str = "█") -> str:
    if hi <= lo:
        return fill * width
    t = max(0.0, min(1.0, (value - lo) / (hi - lo)))
    n = int(round(t * width))
    return fill * n + "·" * (width - n)


def _queue_glyph(priority: int) -> str:
    if priority <= 0:
        return "CTRL"
    if priority == 1:
        return "SENS"
    if priority < AI_PRIORITY_FLOOR:
        return f"P{priority}"
    return "AI· "


@dataclass
class EventLog:
    lines: list[str] = field(default_factory=list)
    max_lines: int = 6

    def push(self, msg: str) -> None:
        self.lines.append(msg)
        if len(self.lines) > self.max_lines:
            self.lines = self.lines[-self.max_lines :]


@dataclass
class LiveMission:
    """Interactive, watchable descent under Block II discipline."""

    delay: float = 0.35  # seconds between frames
    color: bool = True
    out: TextIO = field(default_factory=lambda: sys.stdout)
    start_alt: int = 1400
    start_rate: int = -48  # fast fall — without burns you crash
    start_fuel: int = 1100
    gravity: int = 3  # each physics tick accelerates downward
    # outcome flags for viewport art
    _landed_view: bool = False
    _crashed_view: bool = False

    def __post_init__(self) -> None:
        if not sys.stdout.isatty():
            self.color = False

    def _write(self, s: str = "") -> None:
        self.out.write(s + "\n")
        self.out.flush()

    def _clear(self) -> None:
        if self.color:
            self.out.write("\033[2J\033[H")
            self.out.flush()

    def _sleep(self) -> None:
        if self.delay > 0:
            time.sleep(self.delay)

    def _telemetry_panel(
        self,
        *,
        phase: str,
        imu: SyntheticIMU,
        exe: Executive,
        action_name: str,
        action_note: str,
        thrust: int,
        alarm: bool,
        jobs_this_tick: list[str],
        title_extra: str,
    ) -> list[str]:
        """Right-hand text instruments — same data as before, denser for dual view."""
        alt_bar = _bar(imu.altitude, 0, self.start_alt, width=18)
        fuel_bar = _bar(imu.fuel, 0, self.start_fuel, width=18)
        fall = max(0, -imu.vertical_rate)
        rate_bar = _bar(fall, 0, 80, width=18, fill="v")
        rope_used = exe.rope.image_size()
        rope_pct = 100.0 * rope_used / ROM_WORDS

        dec = ACTIONS.get(
            exe.erasable.read(exe.mmap.ai_scratch_base + 16) if exe.ai_inferences else -1,
            ("—", "no recommendation yet", 0),
        )

        w = 34
        def box_row(s: str) -> str:
            s = s[: w - 2]
            return "│ " + s + " " * (w - 2 - len(s)) + "│"

        lines = [
            "┌" + "─" * w + "┐",
            box_row("DSKY / TELEMETRY"),
            box_row(f"PHASE {phase[:24]}"),
            box_row((title_extra or "")[:32]),
            "├" + "─" * w + "┤",
            box_row(f"ALT   {imu.altitude:5d}  m"),
            box_row(f"RATE  {imu.vertical_rate:+5d}  m/t"),
            box_row(f"FUEL  {imu.fuel:5d}  kg"),
            box_row(f"BURN  {thrust:5d}  thruster"),
            box_row(f"ALT  [{alt_bar}]"),
            box_row(f"FALL [{rate_bar}]"),
            box_row(f"FUEL [{fuel_bar}]"),
            "├" + "─" * w + "┤",
            box_row("EXECUTIVE"),
            box_row(f"queue {exe.scheduler.pending():3d}  shed {exe.scheduler.shed_count:3d}"),
            box_row(f"AI ok {exe.ai_inferences:3d}  skip {exe.ai_skipped:2d}"),
            box_row(f"ctrl ticks {exe.control_ticks:4d}"),
            box_row(
                "ALARM 1202 ACTIVE" if alarm else "alarms: none"
            ),
            "├" + "─" * w + "┤",
            box_row(f"CMD  {action_name:6s}"),
            box_row(action_note[:32]),
            box_row(f"NET  {dec[0]:6s} {dec[1][:18]}"),
            box_row("JOBS " + " ".join(
                # strip ANSI for job tags length
                j.replace("\033[32m", "")
                .replace("\033[36m", "")
                .replace("\033[35m", "")
                .replace("\033[31m", "")
                .replace("\033[0m", "")
                for j in jobs_this_tick
            )[:28]),
            "├" + "─" * w + "┤",
            box_row(f"rope {rope_used}/{ROM_WORDS} ({rope_pct:.2f}%)"),
            box_row(f"erasable {RAM_WORDS} words HARD"),
            box_row(f"clock {CLOCK_HZ // 1000} kHz contract"),
            "└" + "─" * w + "┘",
        ]
        if self.color:
            painted = []
            for ln in lines:
                if "ALARM 1202 ACTIVE" in ln:
                    painted.append(_c("1;37;41", ln, True))
                elif ln.startswith("┌") or ln.startswith("├") or ln.startswith("└"):
                    painted.append(_c("1;36", ln, True))
                else:
                    painted.append(ln)
            return painted
        return lines

    def _frame(
        self,
        *,
        phase: str,
        imu: SyntheticIMU,
        exe: Executive,
        events: EventLog,
        action_name: str,
        action_note: str,
        thrust: int,
        alarm: bool,
        jobs_this_tick: list[str],
        title_extra: str = "",
    ) -> None:
        cols = min(shutil.get_terminal_size((100, 30)).columns, 100)
        line = "─" * min(cols, 90)

        view = render_viewport(
            altitude=imu.altitude,
            max_alt=self.start_alt,
            rate=imu.vertical_rate,
            fuel=imu.fuel,
            max_fuel=self.start_fuel,
            thrust=thrust,
            tick=imu.tick,
            alarm=alarm,
            phase=phase,
            action_name=action_name,
            landed=self._landed_view,
            crashed=self._crashed_view,
            color=self.color,
        )
        panel = self._telemetry_panel(
            phase=phase,
            imu=imu,
            exe=exe,
            action_name=action_name,
            action_note=action_note,
            thrust=thrust,
            alarm=alarm,
            jobs_this_tick=jobs_this_tick,
            title_extra=title_extra,
        )

        # If terminal is narrow, stack; else side-by-side game + instruments
        term_w = shutil.get_terminal_size((100, 30)).columns
        self._clear()
        self._write(
            _c("1;36", "LUMINARY", self.color)
            + f"  v{__version__}  ·  the game Apollo could only dream of  ·  "
            + f"{CLOCK_HZ // 1000} kHz / {RAM_WORDS}w RAM / {ROM_WORDS}w rope"
        )
        self._write(
            _c(
                "2",
                "ASCII viewport (fixed char grid) + live telemetry  ·  AI passenger under Block II law",
                self.color,
            )
        )
        self._write(line)

        if term_w >= 92:
            for row in side_by_side(view, panel, gap="  "):
                self._write(row)
        else:
            for row in view:
                self._write(row)
            self._write("")
            for row in panel:
                self._write(row)

        self._write(line)
        self._write(_c("1", " MISSION LOG", self.color))
        for ev in events.lines:
            self._write(f"  · {ev}")
        self._write(line)
        self._write(
            _c(
                "2",
                " Ctrl+C abort  ·  both panels update every tick  ·  52×16 char display budget",
                self.color,
            )
        )

    def run(self) -> int:
        events = EventLog()
        exe = Executive()
        # small queue so overload is obvious to a human watching
        exe.scheduler.max_depth = 8

        imu = SyntheticIMU(
            altitude=self.start_alt,
            vertical_rate=self.start_rate,
            fuel=self.start_fuel,
        )
        # Don't auto-integrate rate into alt inside sample twice — we drive physics here.
        # We'll call a dedicated physics step.

        exe.boot()
        exe.devices["imu"] = imu

        net = demo_descent_net()
        prog = [
            encode(MiniISA.LI, 1),
            encode(MiniISA.OUT, 0),
            encode(MiniISA.HLT),
        ]
        exe.rope.load(prog + [0] * 8)
        ai_words = exe.attach_net(net, rope_base=16)

        events.push("Cold boot — Block II budgets locked (2K erasable / 36K rope).")
        events.push(f"AI passenger loaded into rope: {ai_words} words of binary weights.")
        events.push("Priority law: CTRL > SENSORS > AI. On overload, AI dies first.")
        self._frame(
            phase="0  BOOT",
            imu=imu,
            exe=exe,
            events=events,
            action_name="—",
            action_note="",
            thrust=0,
            alarm=False,
            jobs_this_tick=["BOOT"],
            title_extra="loading rope image…",
        )
        self._sleep()
        time.sleep(max(0.6, self.delay))

        # ── ACT 1: powered descent with AI ─────────────────────────────
        events.push("PDI — powered descent. AI may recommend burns; control applies them.")
        landed = False
        crashed = False
        soft = False

        # Phase 1: AI allowed to help (no flood)
        for t in range(1, 22):
            jobs: list[str] = []
            imu.vertical_rate -= self.gravity

            before_ai = exe.ai_inferences

            exe.schedule_control()
            jobs.append(_c("32", "CTRL", self.color))

            def sense(job, ctx: Executive) -> None:
                base = ctx.mmap.device_buf_base
                feats = [
                    imu.altitude & 0x7FFF,
                    imu.vertical_rate & 0x7FFF,
                    imu.fuel & 0x7FFF,
                    t & 0x7FFF,
                    1 if imu.altitude < 400 else 0,
                    1 if imu.vertical_rate < -40 else 0,
                    1 if imu.fuel < 200 else 0,
                    (imu.altitude ^ imu.fuel) & 0x7FFF,
                ]
                for i, v in enumerate(feats):
                    ctx.erasable.write(base + i, v)

            exe.scheduler.spawn("sensor", priority=1, work=sense, cancellable=False)
            jobs.append(_c("36", "SENS", self.color))

            # every tick: one AI recommendation
            exe.schedule_ai()
            jobs.append(_c("35", "AI", self.color))

            exe.scheduler.run_until_idle(exe, max_jobs=64)

            action_name, action_note, thrust = "—", "waiting for net…", 0
            cls = 1
            if exe.ai_inferences > before_ai:
                cls = exe.erasable.read(exe.mmap.ai_scratch_base + 16)
            action_name, action_note, thrust = guidance_burn(
                imu.altitude, imu.vertical_rate, imu.fuel, cls
            )
            if thrust:
                imu.fuel = max(0, imu.fuel - max(1, thrust // 2))
                imu.vertical_rate += max(1, (thrust * 2) // 3)
                if imu.vertical_rate > 1:
                    imu.vertical_rate = 1

            imu.altitude = max(0, imu.altitude + imu.vertical_rate)
            imu.tick = t
            events.push(
                f"t+{t:02d}  {action_name}: {action_note}  "
                f"burn {thrust}  rate {imu.vertical_rate:+d}  alt {imu.altitude}"
            )

            self._frame(
                phase="1  POWERED DESCENT",
                imu=imu,
                exe=exe,
                events=events,
                action_name=action_name,
                action_note=action_note,
                thrust=thrust,
                alarm=False,
                jobs_this_tick=jobs,
                title_extra=f"tick {t}/21 — AI is allowed to help",
            )
            self._sleep()

            if imu.altitude <= 0:
                imu.altitude = 0
                landed = True
                soft = abs(imu.vertical_rate) <= SOFT_LAND_RATE
                crashed = abs(imu.vertical_rate) > HARD_LAND_RATE
                break

        # ── ACT 2: deliberate overload ─────────────────────────────────
        if not landed:
            events.push(
                _c(
                    "33",
                    "COMPUTER FLOOD — too many AI jobs for the tiny executive.",
                    self.color,
                )
            )
            events.push("Apollo move: raise 1202, shed AI, keep control flying.")

            for t in range(22, 30):
                jobs = []
                imu.vertical_rate -= self.gravity

                before_shed = exe.scheduler.shed_count
                before_ai = exe.ai_inferences

                # Overfill the job queue with AI (must exceed max_depth)
                exe.flood_ai_jobs(24)
                exe.schedule_control()
                jobs.append(_c("32", "CTRL", self.color))

                def sense(job, ctx: Executive) -> None:
                    base = ctx.mmap.device_buf_base
                    for i, v in enumerate(
                        [
                            imu.altitude & 0x7FFF,
                            imu.vertical_rate & 0x7FFF,
                            imu.fuel & 0x7FFF,
                            t & 0x7FFF,
                            1,
                            1,
                            0,
                            0,
                        ]
                    ):
                        ctx.erasable.write(base + i, v)

                exe.scheduler.spawn("sensor", priority=1, work=sense, cancellable=False)
                jobs.append(_c("36", "SENS", self.color))
                jobs.append(_c("31", "AI×24 FLOOD", self.color))

                # run only a few jobs so backlog + shed stay visible
                exe.scheduler.run_until_idle(exe, max_jobs=6)

                shed_delta = exe.scheduler.shed_count - before_shed
                # Under flood: do NOT trust AI class — weaker fixed backup only
                action_name, action_note, thrust = (
                    "—",
                    "AI SHED — control-only weak brake",
                    0,
                )
                if exe.ai_inferences > before_ai and shed_delta == 0:
                    cls = exe.erasable.read(exe.mmap.ai_scratch_base + 16)
                    action_name, action_note, thrust = guidance_burn(
                        imu.altitude, imu.vertical_rate, imu.fuel, cls
                    )
                    events.push(f"t+{t:02d}  AI slipped through before shed → {action_name}")
                else:
                    # Degraded: still brake on profile, but weaker (no AI assist)
                    _, _, thrust = guidance_burn(
                        imu.altitude, imu.vertical_rate, imu.fuel, ai_class=1
                    )
                    thrust = max(0, (thrust * 2) // 3)  # ~2/3 authority
                    action_name = "SAFE"
                    action_note = "degraded mode after 1202"

                if thrust and imu.fuel > 0:
                    thrust = min(thrust, imu.fuel)
                    imu.fuel = max(0, imu.fuel - max(1, thrust // 2))
                    imu.vertical_rate += max(1, (thrust * 2) // 3)
                    if imu.vertical_rate > 1:
                        imu.vertical_rate = 1

                imu.altitude = max(0, imu.altitude + imu.vertical_rate)
                imu.tick = t
                alarm = ALARM_EXEC_OVERFLOW in exe.scheduler.alarms

                if shed_delta:
                    events.push(
                        _c(
                            "31",
                            f"t+{t:02d}  ★ 1202  shed×{shed_delta} AI  "
                            f"(total {exe.scheduler.shed_count})  ·  {action_note}  "
                            f"burn {thrust}  rate {imu.vertical_rate:+d}  alt {imu.altitude}",
                            self.color,
                        )
                    )
                else:
                    events.push(
                        f"t+{t:02d}  {action_note}  burn {thrust}  "
                        f"rate {imu.vertical_rate:+d}  alt {imu.altitude}"
                    )

                self._frame(
                    phase="2  OVERLOAD / 1202",
                    imu=imu,
                    exe=exe,
                    events=events,
                    action_name=action_name,
                    action_note=action_note,
                    thrust=thrust,
                    alarm=alarm,
                    jobs_this_tick=jobs,
                    title_extra="AI passenger jettisoned — control retained",
                )
                self._sleep()

                if imu.altitude <= 0:
                    imu.altitude = 0
                    landed = True
                    soft = abs(imu.vertical_rate) <= SOFT_LAND_RATE
                    crashed = abs(imu.vertical_rate) > HARD_LAND_RATE
                    break

        # ── ACT 3: recovery (Apollo kept flying after 1202) ───────────
        if not landed:
            events.push(
                _c(
                    "33",
                    "Flood cleared. AI stays offline; control finishes the landing alone.",
                    self.color,
                )
            )
            t = 40
            while not landed and t < 280:
                jobs = [_c("32", "CTRL", self.color), _c("36", "SENS", self.color)]
                imu.vertical_rate -= self.gravity

                exe.schedule_control()

                def sense(job, ctx: Executive) -> None:
                    base = ctx.mmap.device_buf_base
                    ctx.erasable.write(base, imu.altitude & 0x7FFF)
                    ctx.erasable.write(base + 1, imu.vertical_rate & 0x7FFF)

                exe.scheduler.spawn("sensor", priority=1, work=sense, cancellable=False)
                exe.scheduler.run_until_idle(exe, max_jobs=16)

                # Full control authority; AI remains offline (the point of recovery)
                action_name, action_note, thrust = guidance_burn(
                    imu.altitude, imu.vertical_rate, imu.fuel, ai_class=2
                )
                action_name = "CTRL"
                action_note = "recovery — AI offline, control finishes the job"
                if thrust and imu.fuel > 0:
                    thrust = min(thrust, imu.fuel)
                    imu.fuel = max(0, imu.fuel - max(1, thrust // 2))
                    imu.vertical_rate += max(1, (thrust * 3) // 4)
                    if imu.vertical_rate > 1:
                        imu.vertical_rate = 1

                imu.altitude = max(0, imu.altitude + imu.vertical_rate)
                imu.tick = t
                events.push(
                    f"t+{t:02d}  RECOVERY  burn {thrust}  "
                    f"rate {imu.vertical_rate:+d}  alt {imu.altitude}  fuel {imu.fuel}"
                )

                self._frame(
                    phase="3  RECOVERY",
                    imu=imu,
                    exe=exe,
                    events=events,
                    action_name=action_name,
                    action_note=action_note,
                    thrust=thrust,
                    alarm=ALARM_EXEC_OVERFLOW in exe.scheduler.alarms,
                    jobs_this_tick=jobs,
                    title_extra="same computer, no AI passenger",
                )
                self._sleep()

                # Commit the landing once we're in the pad zone at a sane rate
                if imu.altitude <= 12 and imu.vertical_rate <= 2:
                    contact = min(abs(imu.vertical_rate), HARD_LAND_RATE)
                    imu.altitude = 0
                    imu.vertical_rate = -contact if imu.vertical_rate < 0 else imu.vertical_rate
                    landed = True
                    soft = abs(imu.vertical_rate) <= SOFT_LAND_RATE
                    crashed = abs(imu.vertical_rate) > HARD_LAND_RATE
                    break
                if imu.altitude <= 0:
                    imu.altitude = 0
                    landed = True
                    soft = abs(imu.vertical_rate) <= SOFT_LAND_RATE
                    crashed = abs(imu.vertical_rate) > HARD_LAND_RATE
                    break
                if imu.fuel <= 0 and imu.vertical_rate < -HARD_LAND_RATE:
                    break
                t += 1

        if not landed:
            while imu.altitude > 0:
                imu.vertical_rate -= self.gravity
                imu.altitude = max(0, imu.altitude + imu.vertical_rate)
            landed = True
            soft = abs(imu.vertical_rate) <= SOFT_LAND_RATE
            crashed = abs(imu.vertical_rate) > HARD_LAND_RATE

        if crashed:
            outcome = "HARD IMPACT — rate too high at touchdown"
            outcome_color = "1;31"
            events.push(_c(outcome_color, outcome, self.color))
        elif soft:
            outcome = "SOFT LANDING — contact rate within limits"
            outcome_color = "1;32"
            events.push(_c(outcome_color, outcome, self.color))
        else:
            outcome = "FIRM LANDING — survived, not pretty"
            outcome_color = "1;33"
            events.push(_c(outcome_color, outcome, self.color))

        self._landed_view = True
        self._crashed_view = bool(crashed)
        imu.altitude = 0

        events.push(
            f"Final rate {imu.vertical_rate:+d}  fuel left {imu.fuel}  "
            f"AI inferences {exe.ai_inferences}  shed {exe.scheduler.shed_count}"
        )
        events.push(
            "What you watched: a computer with Apollo-sized memory "
            "used AI when it could, and discarded it when it had to."
        )

        self._frame(
            phase="4  TOUCHDOWN",
            imu=imu,
            exe=exe,
            events=events,
            action_name="LAND" if not crashed else "CRASH",
            action_note=outcome,
            thrust=0,
            alarm=ALARM_EXEC_OVERFLOW in exe.scheduler.alarms,
            jobs_this_tick=["DONE"],
            title_extra=outcome,
        )
        # Hold the final tableau so the ASCII landing/crash is readable
        if self.delay > 0:
            time.sleep(max(1.2, self.delay * 3))

        self._write("")
        self._write(_c("1", "  WHY THIS MATTERS", self.color))
        self._write("  · Left: fixed 52×16 char viewport — the game they could only dream of in 1969.")
        self._write("  · Right: DSKY-style telemetry from the same constrained executive.")
        self._write("  · When flooded: alarm 1202, shed AI, keep flying — you saw it in both panels.")
        self._write("  · That discipline is the product. The lander is how it feels.")
        self._write("")
        self._write("  Run again:  luminary demo")
        self._write("  Faster:     luminary demo --fast")
        self._write("  Instant:    luminary demo --no-delay")
        self._write("")
        return 0 if not crashed else 1


def run_live_mission(
    *,
    delay: float = 0.35,
    color: bool = True,
) -> int:
    return LiveMission(delay=delay, color=color).run()
