# LUMINARY

**An AI-era operating system constrained to Apollo Guidance Computer Block II hardware.**

> Same bones as the machine that landed humans on the Moon.  
> New brain: purpose-built intelligence that fits in rope memory and 4 KB of core.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-green.svg)](https://www.python.org/)

---

## The experiment

In 1969, the Apollo Guidance Computer (AGC) Block II ran at **2.048 MHz** with **~4 KB RAM** and **~72 KB ROM**, consumed ~70 W, and weighed ~32 kg. It multitasked under hard real-time pressure, interfaced with ~150 devices, and survived priority overloads (the famous **1201/1202** program alarms) during Apollo 11's descent.

**Luminary** asks: *what does an OS look like if we accept those exact ceilings, but design for the age of AI?*

Not a historical replica. A **purpose-built system** that:

1. **Honors the budget** — word length, memory map, cycle model, and scheduling discipline of Block II.
2. **Exploits AI where it pays** — offline model distillation into rope-sized binary nets, host-side co-pilots that never bloat the flight computer, and AI-assisted verification of ultra-dense code.
3. **Rejects the modern default** — no gigabytes of RAM, no thrashing kernels, no "just throw more cloud at it."

The real LM software was also called *Luminary*. We reuse the name as homage, not as a claim of lineage.

---

## Hardware contract (Block II)

| Resource | Spec | Budget in Luminary |
|----------|------|--------------------|
| Clock | 2.048 MHz (1.024 MHz four-phase internal) | Cycle-accurate *relative* timing in the VM |
| Word | 16 bits (15 data + 1 parity) | Enforced on every memory access |
| ROM (fixed / "rope") | 36,864 words ≈ 72 KB | Immutable program + constants + AI weights |
| RAM (erasable) | 2,048 words ≈ 4 KB | Working set only |
| Power / mass / volume | ~55–70 W · ~32 kg · ~1 ft³ | Documented design envelope (not simulated electrically) |
| I/O | ~150 devices | Virtual device bus with priority channels |
| Scheduling | Real-time multitasking + overload handling | Preemptive priority queues; 1202-style load shed |

Full detail: [`docs/HARDWARE.md`](docs/HARDWARE.md) · Architecture: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) · AI design: [`docs/AI_INTEGRATION.md`](docs/AI_INTEGRATION.md)

---

## Quick start

```bash
# clone
git clone https://github.com/robdon3/luminary.git
cd luminary

# run the constrained VM + demo mission profile
python3 -m luminary demo

# run unit tests
python3 -m unittest discover -s tests -v

# inspect memory budget of a built "rope" image
python3 -m luminary budget
```

Requires **Python 3.10+**. No third-party packages for the core VM/kernel.

---

## Repository layout

```
luminary/
├── docs/                 # Hardware contract, architecture, AI strategy
├── src/luminary/
│   ├── vm/               # Block II word machine (registers, memory, cycles)
│   ├── kernel/           # Scheduler, interrupts, memory manager, syscalls
│   ├── ai/               # Rope-sized binary networks + inference
│   └── devices/          # Virtual sensors / thrusters / DSKY-like console
├── asm/                  # Tiny assembly / rope image builders
├── examples/             # Mission-profile demos
├── tests/                # Contract + kernel + AI budget tests
└── tools/                # Host-side helpers (budget, pack, distill stubs)
```

---

## Design principles

1. **Every word counts.** ROM and RAM budgets are first-class. Builds fail if an image exceeds rope or core.
2. **Parity is not optional.** 15+1 words carry parity; the VM can inject and detect faults.
3. **Priority over fairness.** Like the AGC, critical guidance/control beats nice-to-have intelligence.
4. **AI is a passenger, not the pilot bus.** Inference runs as a scheduled job with a hard cycle cap. Overload → shed AI first (a deliberate 1202 philosophy).
5. **Host AI is outside the hull.** LLMs may *author* or *verify* rope images on a development machine. They never ship inside the 72 KB.

---

## Status

**Phase 0 — foundation (this repo):** working VM, kernel skeleton, rope AI micro-inference, demos, tests, hardware docs.

Roadmap sketches live in [`docs/ROADMAP.md`](docs/ROADMAP.md).

---

## Historical note

Specs summarize the publicly documented **AGC Block II** (crewed flights). Values are rounded for systems design; see NASA/MIT documentation and secondary sources for bit-level fidelity. Luminary is an **experimental OS research project**, not flight software and not a cycle-perfect AGC emulator (for that, see projects like *Virtual AGC*).

---

## License

MIT — see [LICENSE](LICENSE).
