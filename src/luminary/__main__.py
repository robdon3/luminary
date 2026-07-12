"""CLI: luminary launch | demo | budget | version"""

from __future__ import annotations

import sys

from luminary import RAM_WORDS, ROM_WORDS, CLOCK_HZ, __version__
from luminary.kernel.memory_map import MemoryMap
from luminary.ai.bnn import demo_descent_net
from luminary.vm.cpu import MiniISA, encode
from luminary.vm.memory import assert_budgets


def _parse_pace(argv: list[str]) -> tuple[float, bool]:
    delay = 0.40
    color = True
    if "--fast" in argv:
        delay = 0.12
    if "--no-delay" in argv or "--instant" in argv:
        delay = 0.0
    if "--slow" in argv:
        delay = 0.75
    if "--no-color" in argv:
        color = False
    return delay, color


def cmd_budget() -> int:
    mmap = MemoryMap()
    mmap.validate()
    net = demo_descent_net()
    rope_ai = net.estimate_rope_words()
    prog = [
        encode(MiniISA.LI, 5),
        encode(MiniISA.STA, 0x10),
        encode(MiniISA.HLT),
    ]
    rope_used = len(prog) + rope_ai + 16
    print("LUMINARY budget report")
    print(f"  version:     {__version__}")
    print(f"  clock:       {CLOCK_HZ} Hz (Block II contract)")
    print(f"  ROM (rope):  {rope_used} used / {ROM_WORDS} max words")
    print(f"  RAM (core):  {mmap.total_reserved()} reserved / {RAM_WORDS} max words")
    print(
        f"  AI net:      {net.n_in}→{net.n_hidden}→{net.n_out} "
        f"({net.weight_bit_count()} weight bits, ~{rope_ai} rope words)"
    )
    print()
    print(mmap.report())
    try:
        assert_budgets(rope_used, mmap.total_reserved())
        print("\nBudget check: PASS")
        return 0
    except Exception as exc:
        print(f"\nBudget check: FAIL — {exc}")
        return 1


def cmd_demo(argv: list[str]) -> int:
    delay, color = _parse_pace(argv)
    if "--fast" not in argv and "--slow" not in argv and "--no-delay" not in argv:
        delay = 0.40
    from luminary.mission.live import run_live_mission

    return run_live_mission(delay=delay, color=color)


def cmd_launch(argv: list[str]) -> int:
    """Interactive Earth → Moon campaign."""
    delay = 0.16
    color = True
    auto = "--auto" in argv
    if "--fast" in argv:
        delay = 0.08
    if "--slow" in argv:
        delay = 0.35
    if "--no-delay" in argv or "--instant" in argv:
        delay = 0.0
    if "--no-color" in argv:
        color = False
    # auto defaults a bit snappier
    if auto and "--slow" not in argv and "--fast" not in argv and "--no-delay" not in argv:
        delay = 0.05

    from luminary.mission.campaign import run_campaign

    return run_campaign(delay=delay, color=color, auto=auto)


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv:
        print(
            "luminary — Apollo Block II budget OS\n"
            "  luminary launch     Earth → Moon (you fly)\n"
            "  luminary launch --auto\n"
            "  luminary demo       descent-only watch mode\n"
            "  luminary --help\n"
        )
        return cmd_launch([])

    cmd = argv[0]
    if cmd in {"-h", "--help", "help"}:
        print(
            """luminary — AI-era OS under Apollo Block II budgets

LAUNCH → LANDER (interactive)
  luminary launch           fly Earth pad → lunar surface
  luminary launch --auto    full mission autopilot (watch)
  luminary launch --fast
  luminary launch --slow

  Controls:
    SPACE / W   thrust (sticky — X to cut)
    A / D       pitch (ascent)
    S           stage sep
    B           circularize (orbit) / assist LOI
    T           start TLI burn
    M           midcourse correction (coast)
    H / ?       help
    Q           abort

DESCENT ONLY
  luminary demo             watch powered descent + 1202
  luminary demo --fast

SYSTEM
  luminary budget           memory contract
  luminary version

Same computer the whole way: ~4 KB RAM, ~72 KB rope, AI as passenger.
"""
        )
        return 0
    if cmd in {"launch", "play", "mission", "fly"}:
        return cmd_launch(argv[1:])
    if cmd == "demo":
        return cmd_demo(argv[1:])
    if cmd == "budget":
        return cmd_budget()
    if cmd == "version":
        print(__version__)
        return 0
    if cmd.startswith("-"):
        # flags alone → launch
        return cmd_launch(argv)
    print(f"unknown command: {cmd}", file=sys.stderr)
    print("try: luminary launch   or   luminary --help", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
