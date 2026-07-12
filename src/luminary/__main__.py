"""CLI entry: python -m luminary [demo|budget|test-quick]"""

from __future__ import annotations

import sys

from luminary import RAM_WORDS, ROM_WORDS, CLOCK_HZ, __version__
from luminary.kernel.executive import Executive
from luminary.kernel.memory_map import MemoryMap
from luminary.kernel.scheduler import ALARM_EXEC_OVERFLOW
from luminary.ai.bnn import demo_descent_net
from luminary.devices.imu import SyntheticIMU
from luminary.devices.console import DSKYConsole
from luminary.devices.timer import MissionTimer
from luminary.vm.cpu import MiniISA, encode
from luminary.vm.memory import assert_budgets


def cmd_budget() -> int:
    mmap = MemoryMap()
    mmap.validate()
    net = demo_descent_net()
    rope_ai = net.estimate_rope_words()
    # tiny sample program
    prog = [
        encode(MiniISA.LI, 5),
        encode(MiniISA.STA, 0x10),
        encode(MiniISA.HLT),
    ]
    rope_used = len(prog) + rope_ai + 16  # header margin
    print("LUMINARY budget report")
    print(f"  version:     {__version__}")
    print(f"  clock:       {CLOCK_HZ} Hz (Block II contract)")
    print(f"  ROM (rope):  {rope_used} used / {ROM_WORDS} max words")
    print(f"  RAM (core):  {mmap.total_reserved()} reserved / {RAM_WORDS} max words")
    print(f"  AI net:      {net.n_in}→{net.n_hidden}→{net.n_out} "
          f"({net.weight_bit_count()} weight bits, ~{rope_ai} rope words)")
    print()
    print(mmap.report())
    try:
        assert_budgets(rope_used, mmap.total_reserved())
        print("\nBudget check: PASS")
        return 0
    except Exception as exc:
        print(f"\nBudget check: FAIL — {exc}")
        return 1


def cmd_demo() -> int:
    print("=" * 60)
    print(" LUMINARY — Apollo Block II budgets · AI-era executive")
    print("=" * 60)

    exe = Executive()
    exe.boot()

    imu = SyntheticIMU(altitude=3000, vertical_rate=-60, fuel=800)
    dsky = DSKYConsole()
    timer = MissionTimer()
    exe.devices["imu"] = imu
    exe.devices["dsky"] = dsky
    exe.devices["timer"] = timer

    net = demo_descent_net()
    # tiny rope program at 0, weights after
    prog = [
        encode(MiniISA.LI, 1),
        encode(MiniISA.OUT, 0),  # would talk to dsky if wired
        encode(MiniISA.HLT),
    ]
    exe.rope.load(prog + [0] * 8)
    words = exe.attach_net(net, rope_base=16)

    dsky.display("PROG 00  DESCENT DEMO")
    dsky.display(f"AI ROPE WORDS {words}")

    print("\n[1] Nominal descent with opportunistic AI")
    for t in range(24):
        timer.advance()
        exe.schedule_control()
        exe.schedule_sensor()
        if t % 2 == 0:
            exe.schedule_ai()
        exe.scheduler.run_until_idle(exe, max_jobs=32)
        # apply a crude thruster bias from AI decision if present
        decision = exe.erasable.read(exe.mmap.ai_scratch_base + 16)
        if decision == 2:  # brake class
            imu.write(0, 40)
        elif decision == 1:
            imu.write(0, 10)

    print(f"    {exe.status()}")
    print(f"    altitude={imu.altitude} rate={imu.vertical_rate} fuel={imu.fuel}")
    print(f"    last AI decision class={exe.erasable.read(exe.mmap.ai_scratch_base + 16)}")

    print("\n[2] Executive overload — flood AI jobs (1202 path)")
    exe.flood_ai_jobs(40)
    # keep critical paths
    for _ in range(5):
        exe.schedule_control()
        exe.schedule_sensor()
    exe.scheduler.run_until_idle(exe, max_jobs=200)

    print(f"    {exe.status()}")
    if ALARM_EXEC_OVERFLOW in exe.scheduler.alarms:
        print("    ALARM 1202  EXEC OVERFLOW  (AI shed, control retained)")
    else:
        print("    (overload threshold not crossed — adjust max_depth if needed)")

    print("\n[3] Rope program smoke run")
    assert exe.cpu is not None
    exe.cpu.reset(entry=0)
    exe.cpu.run(max_cycles=100)
    print(f"    CPU halted={exe.cpu.halted} cycles={exe.cpu.cycles} "
          f"sim_time={exe.cpu.simulated_seconds()*1e6:.2f} µs @ {CLOCK_HZ} Hz")

    print("\nDSKY log:")
    for m in dsky.messages:
        print(f"  {m}")

    print("\nDemo complete. Budgets held; AI remained a passenger.")
    return 0


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in {"-h", "--help", "help"}:
        print("usage: python -m luminary [demo|budget|version]")
        return 0
    cmd = argv[0]
    if cmd == "demo":
        return cmd_demo()
    if cmd == "budget":
        return cmd_budget()
    if cmd == "version":
        print(__version__)
        return 0
    print(f"unknown command: {cmd}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
