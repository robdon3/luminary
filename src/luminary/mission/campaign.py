"""
Earth → Moon launch-to-lander campaign.

You fly it. Luminary runs underneath with Block II budgets.
AI is a passenger: it can advise; on overload (1202) it is shed.

Controls:
  SPACE / w   thrust (hold each tick — press often)
  x           cut thrust intent
  a / d       pitch left / right (ascent efficiency)
  s           stage (when prompted)
  b           commit circularization / LOI when window open
  t           begin TLI when GO
  m           midcourse correction during coast
  ? / h       help line
  q           abort mission
"""

from __future__ import annotations

import shutil
import sys
import time
from dataclasses import dataclass, field
from typing import Optional, TextIO

from luminary import CLOCK_HZ, RAM_WORDS, ROM_WORDS, __version__
from luminary.ai.bnn import demo_descent_net
from luminary.kernel.executive import Executive
from luminary.kernel.scheduler import ALARM_EXEC_OVERFLOW, AI_PRIORITY_FLOOR
from luminary.mission.ascii_view import side_by_side
from luminary.mission.input import drain_keys, poll_key, raw_terminal
from luminary.mission.live import guidance_burn, SOFT_LAND_RATE, HARD_LAND_RATE
from luminary.mission.scenes import render_campaign_scene
from luminary.vm.cpu import MiniISA, encode


def _c(code: str, text: str, color: bool) -> str:
    if not color:
        return text
    return f"\033[{code}m{text}\033[0m"


@dataclass
class Log:
    lines: list[str] = field(default_factory=list)
    max_lines: int = 5

    def push(self, m: str) -> None:
        self.lines.append(m)
        if len(self.lines) > self.max_lines:
            self.lines = self.lines[-self.max_lines :]


@dataclass
class Campaign:
    """Interactive launcher → lander under Luminary constraints."""

    delay: float = 0.18
    color: bool = True
    auto: bool = False  # auto-pilot demo of full stack
    out: TextIO = field(default_factory=lambda: sys.stdout)

    # craft
    phase: str = "PAD"
    tick: int = 0
    alt: int = 0  # km toy / m toy depending on phase
    vel: int = 0
    fuel: int = 2400  # stack fuel
    stage: int = 0  # 0 booster, 1 upper, 2 service, 3 descent
    pitch: int = 0  # -2..2
    thrust_cmd: int = 0
    circularized: bool = False
    tli_go: bool = False
    dv_done: int = 0
    dv_need: int = 0
    coast_progress: int = 0
    # lunar descent
    rate: int = 0
    max_descent_alt: int = 1400
    max_fuel_descent: int = 900
    landed: bool = False
    crashed: bool = False
    action: str = "—"
    action_note: str = ""
    dead: bool = False
    won: bool = False
    message: str = ""
    thrust_hold: bool = False  # sticky burn until cut

    # executive
    exe: Optional[Executive] = None
    log: Log = field(default_factory=Log)
    help_flash: int = 0
    _last_thr: int = 0

    def __post_init__(self) -> None:
        if not sys.stdout.isatty():
            self.color = False

    # ── boot ──────────────────────────────────────────────────────────

    def boot_computer(self) -> None:
        self.exe = Executive()
        self.exe.scheduler.max_depth = 8
        self.exe.boot()
        net = demo_descent_net()
        prog = [encode(MiniISA.LI, 1), encode(MiniISA.HLT)]
        self.exe.rope.load(prog + [0] * 8)
        n = self.exe.attach_net(net, rope_base=16)
        self.log.push(f"Luminary boot — rope AI {n} words / {ROM_WORDS} max.")
        self.log.push("Block II law: CTRL > SENSORS > AI. Overload → 1202 → shed AI.")
        self.log.push("Mission: Earth pad → lunar surface. You fly the burns.")

    # ── input ─────────────────────────────────────────────────────────

    def handle_keys(self, keys: list[str]) -> None:
        for k in keys:
            if k in {"q", "Q", "\x03"}:
                self.dead = True
                self.message = "Mission aborted by crew."
                return
            if k in {"?", "h", "H"}:
                self.help_flash = 12
                continue
            if k in {" ", "w", "W"}:
                self.thrust_cmd = 1
                self.thrust_hold = True
            if k in {"x", "X"}:
                self.thrust_cmd = 0
                self.thrust_hold = False
            if k in {"a", "A", "LEFT"}:
                self.pitch = max(-2, self.pitch - 1)
            if k in {"d", "D", "RIGHT"}:
                self.pitch = min(2, self.pitch + 1)
            if k in {"s", "S"} and self.phase == "ASCENT" and self.stage == 0 and self.alt > 50:
                self.stage = 1
                self.fuel += 400
                self.log.push("STAGE 1 SEP — upper stage live.")
            if k in {"b", "B"}:
                if self.phase == "ORBIT" and not self.circularized:
                    self._circularize()
                elif self.phase == "LOI":
                    self.thrust_cmd = 1
            if k in {"t", "T"} and self.phase == "ORBIT" and self.circularized:
                self.phase = "TLI"
                self.dv_done = 0
                self.dv_need = 90
                self.thrust_cmd = 0
                self.log.push("TLI GO — hold SPACE for trans-lunar injection.")
            if k in {"m", "M"} and self.phase == "COAST":
                self._midcourse()

    def _auto_pilot(self) -> None:
        """Drive a full success path when --auto (spectator)."""
        p = self.phase
        self.thrust_hold = False
        if p == "PAD":
            self.thrust_cmd = 1
            self.thrust_hold = True
        elif p == "ASCENT":
            self.thrust_cmd = 1
            self.thrust_hold = True
            if self.alt > 55 and self.stage == 0:
                self.stage = 1
                self.fuel += 400
            self.pitch = 1 if self.alt > 40 else 0
        elif p == "ORBIT":
            if not self.circularized:
                self._circularize()
            elif self.tick % 3 == 0:
                self.phase = "TLI"
                self.dv_done = 0
                self.dv_need = 90
                self.thrust_hold = True
                self.thrust_cmd = 1
        elif p == "TLI":
            self.thrust_cmd = 1
            self.thrust_hold = True
        elif p == "COAST":
            if self.coast_progress in {40, 70}:
                self._midcourse()
        elif p == "LOI":
            self.thrust_cmd = 1
            self.thrust_hold = True
        elif p == "DESCENT":
            # always assist landing in auto
            self.thrust_cmd = 1
            self.thrust_hold = True

    def _circularize(self) -> None:
        cost = 120
        if self.fuel < cost:
            self.log.push("CIRC failed — fuel low.")
            return
        self.fuel -= cost
        self.vel = 78
        self.alt = max(self.alt, 160)
        self.circularized = True
        self.tli_go = True
        self.log.push("Circularization complete — stable Earth orbit.")
        self.log.push("Press [T] when ready for TLI.")

    def _midcourse(self) -> None:
        cost = 40
        if self.fuel < cost:
            self.log.push("Midcourse skipped — no fuel.")
            return
        self.fuel -= cost
        self.coast_progress = min(100, self.coast_progress + 8)
        self.log.push("Midcourse correction burned.")
        # stress the executive with AI flood occasionally
        if self.exe and self.coast_progress > 50:
            self.exe.flood_ai_jobs(20)
            self.exe.schedule_control()
            self.exe.scheduler.run_until_idle(self.exe, max_jobs=4)
            if ALARM_EXEC_OVERFLOW in self.exe.scheduler.alarms:
                self.log.push("★ 1202 during midcourse — AI shed, nav retained.")

    # ── executive tick ────────────────────────────────────────────────

    def computer_tick(self, ai: bool = True) -> None:
        if not self.exe:
            return
        self.exe.schedule_control()

        def sense(job, ctx: Executive) -> None:
            base = ctx.mmap.device_buf_base
            vals = [
                self.alt & 0x7FFF,
                self.vel & 0x7FFF,
                self.fuel & 0x7FFF,
                self.tick & 0x7FFF,
                1 if self.phase == "DESCENT" else 0,
                1 if self.thrust_cmd else 0,
                abs(self.pitch) & 0x7FFF,
                self.stage & 0x7FFF,
            ]
            for i, v in enumerate(vals):
                ctx.erasable.write(base + i, v)

        self.exe.scheduler.spawn("sensor", priority=1, work=sense, cancellable=False)
        if ai and self.phase in {"ASCENT", "DESCENT", "TLI", "LOI"}:
            self.exe.schedule_ai()
        self.exe.scheduler.run_until_idle(self.exe, max_jobs=12)

    def ai_class(self) -> int:
        if not self.exe or self.exe.ai_inferences < 1:
            return 1
        if ALARM_EXEC_OVERFLOW in self.exe.scheduler.alarms and self.exe.scheduler.shed_count > 0:
            # degraded: ignore net
            return 1
        return self.exe.erasable.read(self.exe.mmap.ai_scratch_base + 16) % 4

    # ── physics by phase ──────────────────────────────────────────────

    def step_physics(self) -> None:
        if self.thrust_hold:
            self.thrust_cmd = 1
        thr = 0
        if self.thrust_cmd and self.fuel > 0:
            if self.phase == "PAD":
                thr = 30
            elif self.phase == "ASCENT":
                thr = 28 + max(0, 2 - abs(self.pitch))
                if self.pitch == 1:
                    thr += 2  # gravity turn sweet spot
            elif self.phase == "TLI":
                thr = 22
            elif self.phase == "LOI":
                thr = 18
            elif self.phase == "DESCENT":
                thr = 25
            else:
                thr = 15
        self.thrust_cmd = 0  # hold flag re-arms next tick

        if self.phase == "PAD":
            if thr > 0:
                self.fuel -= 8
                self.alt = 1
                self.vel = 5
                self.phase = "ASCENT"
                self.log.push("LIFTOFF.")
            return

        if self.phase == "ASCENT":
            # gravity & drag toy
            self.vel += thr // 3
            self.vel = max(0, self.vel - 2)  # gravity
            if self.pitch < 0:
                self.vel = max(0, self.vel - 1)  # inefficient
            self.alt += max(1, self.vel // 4)
            if thr:
                self.fuel -= max(3, thr // 4)
            # staging hint
            if self.stage == 0 and self.alt > 55 and self.tick % 8 == 0:
                self.log.push("Staging window — press [S] to sep booster.")
            # orbit threshold
            if self.alt >= 150 and self.vel >= 55:
                self.phase = "ORBIT"
                self.thrust_cmd = 0
                self.log.push("MECO — insertion. Press [B] to circularize.")
            if self.fuel <= 0 and self.alt < 150:
                self.dead = True
                self.message = "Fuel exhausted on ascent. Vehicle lost."
            if self.alt > 0:
                pass
            # store thrust for view
            self._last_thr = thr
            return

        if self.phase == "ORBIT":
            self._last_thr = 0
            # slow drift if not circularized
            if not self.circularized:
                self.alt = max(80, self.alt - (1 if self.tick % 5 == 0 else 0))
                if self.alt < 90:
                    self.log.push("Orbit decaying — circularize [B] soon!")
                if self.alt < 70:
                    self.dead = True
                    self.message = "Reentered Earth's atmosphere. Mission failed."
            return

        if self.phase == "TLI":
            if thr and self.fuel > 0:
                self.fuel -= 6
                self.dv_done += 6
                self._last_thr = thr
            else:
                self._last_thr = 0
            if self.dv_done >= self.dv_need:
                self.phase = "COAST"
                self.coast_progress = 0
                self.log.push("TLI complete — translunar coast.")
            if self.fuel <= 0 and self.dv_done < self.dv_need:
                self.dead = True
                self.message = "Stranded in Earth orbit — TLI incomplete."
            return

        if self.phase == "COAST":
            self._last_thr = 0
            self.coast_progress += 2
            # computer load spike mid-coast
            if self.coast_progress == 55 and self.exe:
                self.exe.flood_ai_jobs(22)
                self.exe.schedule_control()
                self.exe.scheduler.run_until_idle(self.exe, max_jobs=5)
                if ALARM_EXEC_OVERFLOW in self.exe.scheduler.alarms:
                    self.log.push("★ PROGRAM ALARM 1202 — optics/computer flood. AI shed.")
            if self.coast_progress >= 100:
                self.phase = "LOI"
                self.dv_done = 0
                self.dv_need = 70
                self.log.push("Approaching Moon — LOI burn. Hold [SPACE] or [B].")
            return

        if self.phase == "LOI":
            if thr and self.fuel > 0:
                self.fuel -= 5
                self.dv_done += 5
                self._last_thr = thr
            else:
                self._last_thr = 0
            if self.dv_done >= self.dv_need:
                # convert remaining fuel to descent budget
                self.phase = "DESCENT"
                self.alt = self.max_descent_alt
                self.rate = -48
                self.fuel = min(self.fuel, self.max_fuel_descent)
                if self.fuel < 400:
                    self.fuel = 400  # LM reserves
                self.log.push("LOI complete — powered descent. Fly the lander [SPACE].")
            if self.fuel <= 0 and self.dv_done < self.dv_need:
                self.dead = True
                self.message = "Flyby — LOI failed. Lost to solar orbit."
            return

        if self.phase == "DESCENT":
            # gravity
            self.rate -= 3
            cls = self.ai_class()
            name, note, gburn = guidance_burn(self.alt, self.rate, self.fuel, cls)
            # Pilot enables full guidance authority; does not force climb burns
            if thr > 0:
                burn = gburn
                if gburn == 0 and self.rate < -6:
                    burn = 6  # gentle assist if slightly hot but "on profile"
                self.action = "PILOT"
                self.action_note = f"pilot+AI {name}: {note}"
            else:
                burn = max(0, (gburn * 2) // 3)
                self.action = name
                self.action_note = note + " (SPACE = full authority)"
            if ALARM_EXEC_OVERFLOW in (self.exe.scheduler.alarms if self.exe else []):
                burn = (burn * 2) // 3
                self.action_note = "degraded after 1202 — fly carefully"
            if burn and self.fuel > 0:
                burn = min(burn, self.fuel, 40)
                self.fuel = max(0, self.fuel - max(1, burn // 2))
                self.rate += max(1, (burn * 2) // 3)
                # never climb; keep residual descent until short-final
                if self.alt > 30 and self.rate > -2:
                    self.rate = -2
                elif self.rate > 0:
                    self.rate = 0
            self._last_thr = burn
            self.alt = max(0, self.alt + self.rate)
            if self.alt <= 12 and self.rate >= -SOFT_LAND_RATE - 5:
                contact = abs(self.rate)
                self.alt = 0
                self.landed = True
                self.crashed = contact > HARD_LAND_RATE
                self.phase = "TOUCHDOWN"
                self.rate = -contact
                if self.crashed:
                    self.dead = True
                    self.message = "Hard impact on the Moon."
                elif contact <= SOFT_LAND_RATE:
                    self.won = True
                    self.message = "SOFT LANDING — The Eagle has toys."
                else:
                    self.won = True
                    self.message = "FIRM LANDING — you're on the Moon."
            elif self.alt <= 0:
                self.alt = 0
                self.landed = True
                self.crashed = abs(self.rate) > HARD_LAND_RATE
                self.phase = "TOUCHDOWN"
                self.dead = self.crashed
                self.won = not self.crashed
                self.message = (
                    "Hard impact." if self.crashed else "Landing (rough)."
                )
            return

        self._last_thr = 0

    # ── draw ──────────────────────────────────────────────────────────

    def state_dict(self) -> dict:
        alarm = bool(
            self.exe and ALARM_EXEC_OVERFLOW in self.exe.scheduler.alarms
        )
        return {
            "phase": self.phase,
            "tick": self.tick,
            "alt": self.alt,
            "vel": self.vel,
            "fuel": self.fuel,
            "thrust": self._last_thr,
            "stage": self.stage,
            "circularized": self.circularized,
            "dv_done": self.dv_done,
            "dv_need": self.dv_need,
            "progress": self.coast_progress,
            "midcourse": self.phase == "COAST" and self.tick % 20 < 3,
            "max_alt": 200 if self.phase == "ASCENT" else self.max_descent_alt,
            "rate": self.rate,
            "max_fuel": self.max_fuel_descent if self.phase == "DESCENT" else 2400,
            "action": self.action,
            "landed": self.landed and not self.crashed,
            "crashed": self.crashed,
            "alarm": alarm,
        }

    def panel_lines(self) -> list[str]:
        w = 34
        exe = self.exe
        alarm = bool(exe and ALARM_EXEC_OVERFLOW in exe.scheduler.alarms)

        def row(s: str) -> str:
            s = s[: w - 2]
            return "│ " + s + " " * (w - 2 - len(s)) + "│"

        lines = [
            "┌" + "─" * w + "┐",
            row("LUMINARY  FLIGHT"),
            row(f"PHASE {self.phase}"),
            row(f"t={self.tick}  pitch={self.pitch:+d}"),
            "├" + "─" * w + "┤",
            row(f"ALT  {self.alt:5d}"),
            row(f"VEL  {self.vel:5d}" if self.phase != "DESCENT" else f"RATE {self.rate:+5d}"),
            row(f"FUEL {self.fuel:5d}"),
            row(f"STG  {self.stage}   THR {self._last_thr:3d}"),
            "├" + "─" * w + "┤",
            row("COMPUTER"),
            row(
                f"AI {exe.ai_inferences if exe else 0:3d} shed {exe.scheduler.shed_count if exe else 0:3d}"
            ),
            row("ALARM 1202" if alarm else "alarms none"),
            row(f"rope {(exe.rope.image_size() if exe else 0)}/{ROM_WORDS}"),
            row(f"RAM {RAM_WORDS}w  {CLOCK_HZ//1000}kHz"),
            "├" + "─" * w + "┤",
            row(f"CMD {self.action:6s}"),
            row(self.action_note[:32]),
            "├" + "─" * w + "┤",
            row("CONTROLS"),
            row("SPACE thrust  A/D pitch"),
            row("S stage  B circ/LOI"),
            row("T TLI   M midcourse"),
            row("H help  Q abort"),
            "└" + "─" * w + "┘",
        ]
        if self.help_flash > 0:
            lines.insert(
                -1,
                row("Hold SPACE each beat to burn"),
            )
        if self.color and alarm:
            lines = [
                _c("1;37;41", ln, True) if "1202" in ln else ln for ln in lines
            ]
        return lines

    def draw(self) -> None:
        if self.color:
            self.out.write("\033[2J\033[H")
        view = render_campaign_scene(self.state_dict(), color=self.color)
        panel = self.panel_lines()
        term_w = shutil.get_terminal_size((100, 30)).columns
        self.out.write(
            _c("1;36", "LUMINARY", self.color)
            + f"  LAUNCH → LANDER  v{__version__}  ·  "
            + f"{RAM_WORDS}w RAM · {ROM_WORDS}w rope · AI passenger\n"
        )
        self.out.write(
            _c(
                "2",
                "Earth pad to lunar dust — same computer limits as Apollo Block II\n",
                self.color,
            )
        )
        line = "─" * min(term_w, 92)
        self.out.write(line + "\n")
        if term_w >= 92:
            for r in side_by_side(view, panel):
                self.out.write(r + "\n")
        else:
            for r in view:
                self.out.write(r + "\n")
            for r in panel:
                self.out.write(r + "\n")
        self.out.write(line + "\n")
        self.out.write(_c("1", " MISSION LOG\n", self.color))
        for e in self.log.lines:
            self.out.write(f"  · {e}\n")
        if self.help_flash > 0:
            self.out.write(
                _c(
                    "33",
                    "  SPACE=burn  A/D=pitch  S=stage  B=circularize  T=TLI  M=midcourse  Q=quit\n",
                    self.color,
                )
            )
            self.help_flash -= 1
        self.out.write(line + "\n")
        self.out.flush()

    # ── main loop ─────────────────────────────────────────────────────

    def run(self) -> int:
        self.boot_computer()
        self._last_thr = 0

        use_raw = sys.stdin.isatty() and not self.auto
        with raw_terminal(use_raw):
            while not self.dead and not self.won and self.phase != "TOUCHDOWN":
                keys = drain_keys() if use_raw else []
                if use_raw and self.delay > 0:
                    k = poll_key(min(0.05, self.delay))
                    if k:
                        keys.append(k)
                if self.auto:
                    self._auto_pilot()
                else:
                    self.handle_keys(keys)

                self.computer_tick(ai=True)
                self.step_physics()
                self.tick += 1
                self.draw()

                if self.delay > 0:
                    time.sleep(self.delay)

                if self.tick > 5000:
                    self.dead = True
                    self.message = "Mission clock exceeded."

            if self.phase == "TOUCHDOWN" and not self.dead:
                self.won = not self.crashed
            self.draw()
            if self.delay > 0:
                time.sleep(1.2)

        self.out.write("\n")
        if self.won:
            self.out.write(_c("1;32", f"  MISSION SUCCESS — {self.message}\n", self.color))
            self.out.write("  You flew Earth to Moon on a Block II budget computer.\n")
        else:
            self.out.write(_c("1;31", f"  MISSION FAILED — {self.message or 'incomplete'}\n", self.color))
        self.out.write(
            f"  ticks={self.tick}  fuel_left={self.fuel}  "
            f"AI={self.exe.ai_inferences if self.exe else 0}  "
            f"shed={self.exe.scheduler.shed_count if self.exe else 0}\n"
        )
        self.out.write("  Again:  luminary launch\n")
        self.out.write("  Auto:   luminary launch --auto\n")
        self.out.write("  Descent only: luminary demo\n\n")
        return 0 if self.won else 1


def run_campaign(
    *,
    delay: float = 0.18,
    color: bool = True,
    auto: bool = False,
) -> int:
    return Campaign(delay=delay, color=color, auto=auto).run()
