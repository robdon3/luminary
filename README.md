# Luminary

An experimental operating system, in Python, held to the public memory budget of the Apollo Guidance Computer Block II: about 2.048 MHz, 2,048 words of RAM (~4 KB), and 36,864 words of ROM (~72 KB). The question is what an OS looks like under those ceilings if a small AI model is allowed on board as a passenger, not as the pilot.

This is not flight software and not a cycle-perfect AGC emulator. The real lunar-module program was also called Luminary; the name is homage, not a claim of lineage.

## What it is

A virtual machine, a priority kernel, a rope-sized binary network, a handful of virtual devices, and a terminal campaign that flies from an Earth pad to a lunar landing. Host-side language models are described as authors of rope images. They are not inside the 72 KB.

## Problem

Modern stacks hide cost. Luminary keeps that cost in the machine: odd-parity words, a fixed memory map, a rope image rejected when it exceeds `ROM_WORDS`, and a scheduler that sheds AI jobs first when the executive overloads (alarm 1202).

## Approach

```text
Host (docs, tests, optional image packing)
        │  rope image stays inside ROM_WORDS
        ▼
Luminary VM          15 data bits + odd parity, 2K erasable, 36K rope
  Kernel             priority jobs, 1202-class load shed
    ├─ control loops
    ├─ devices: console, timer, IMU
    └─ AI passenger   binary net in rope, activations in a fixed RAM window
```

The CPU is a small demo instruction set (load/store, add/sub, bitwise logic, jumps, immediate, device in/out, syscall, and halt). It is not the full AGC instruction set. Detail is in [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md), [docs/HARDWARE.md](docs/HARDWARE.md), and [docs/AI_INTEGRATION.md](docs/AI_INTEGRATION.md).

## Run

Python 3.10+. No third-party packages for the VM.

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e .
luminary launch          # you fly: pad → landing
luminary launch --auto   # autopilot
luminary demo            # descent only
luminary budget          # rope and RAM check
```

`luminary` with no arguments also starts the launch campaign. Controls: `SPACE`/`W` thrust (sticky, `X` cuts), `A`/`D` pitch, `S` stage, `B` circularize or assist lunar orbit insertion, `T` trans-lunar injection, `M` midcourse, `H` help, `Q` quit.

Tests are standard-library `unittest` (pytest is not a package dependency):

```bash
python -m unittest discover -s tests
```

## Tech

Python 3.10+, setuptools. Standard library only at runtime. MIT license.
