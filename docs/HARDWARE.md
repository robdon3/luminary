# Hardware contract — Apollo Block II envelope

Luminary treats the following as **hard law**. The virtual machine and image builder enforce the numeric budgets. Physical power/mass/size are design documentation only (no electrical model yet).

## Processor

| Parameter | Value | Notes |
|-----------|-------|-------|
| Clock | 2.048 MHz | Master clock reference |
| Internal timing | 1.024 MHz four-phase | Modeled as discrete machine cycles |
| Word length | 16 bits | 15 data bits + 1 odd-parity bit |
| Data range | −16384 … +16383 | 15-bit two's complement (parity separate) |
| Logic fabric (historical) | ~2,800–4,000 ICs | Mostly dual 3-input NOR (Fairchild); not simulated gate-level |

### Architectural registers (Luminary VM)

Simplified Block-II-inspired set (not a gate-accurate AGC replica):

| Name | Width | Role |
|------|-------|------|
| `A` | 15+1 | Accumulator |
| `L` | 15+1 | Lower product / aux |
| `Q` | 15+1 | Remainder / link |
| `Z` | 12-bit effective | Program counter (word address into unified map) |
| `BB` | bank bits | ROM bank select for rope window |
| `EB` | bank bits | Erasable bank select |
| `TIME1`/`TIME2` | counters | Mission timers (scaled) |
| Priority interrupt mask | 15-bit | Per-level enable |

## Memory

### ROM — fixed memory ("core rope")

| Parameter | Value |
|-----------|-------|
| Capacity | **36,864 words** |
| Approx. bytes | 36,864 × 15 bits ≈ **69 KB** usable data (often cited ~72 KB with packaging) |
| Mutability | **Read-only** at runtime |
| Contents | Kernel, device drivers, constants, **AI weight tables**, mission programs |
| Historical note | Hand-woven ferrite "rope"; 1s/0s encoded by wire path through/around cores |

In Luminary, rope is a packed immutable image built offline. Host tools may use AI to *generate* or *verify* the image; the flight image itself is static bits.

### RAM — erasable core memory

| Parameter | Value |
|-----------|-------|
| Capacity | **2,048 words** |
| Approx. bytes | 2,048 × 15 bits ≈ **3.8 KB** (~4 KB cited) |
| Mutability | Read/write |
| Contents | Stacks, task control blocks, sensor buffers, AI activation scratch |

### Default memory map (word addresses)

```
0x0000 – 0x00FF   Zero page / unswitched erasable (256 words)
0x0100 – 0x02FF   Switched erasable window (into 2K total)
0x0300 – 0x07FF   Fixed-fixed / low rope window (implementation-defined)
0x0800 – 0x0FFF   Rope bank window (banked into 36K rope)
…                 Higher logical banks via BB
```

Exact banking is implemented in `luminary.vm.memory`. The **invariant** is total erasable ≤ 2048 and total fixed ≤ 36864 words.

## Power, mass, volume (design envelope)

| Parameter | Block II (approx.) |
|-----------|--------------------|
| Power | 55–70 W |
| Mass | ~32 kg (70 lb) |
| Volume | ~1 cubic foot |

These constrain *future* porting targets (FPGA soft-core, microcontroller demos). The software VM does not model watts.

## I/O and devices

Historical AGC talked to on the order of **~150** interfaces (IMU, optics/sextant, thrusters, DSKY, telemetry, etc.).

Luminary exposes a **virtual device bus**:

- Priority interrupt lines (high = guidance/control, low = AI / telemetry cosmetics)
- Memory-mapped or channel-style device registers
- Pluggable backends: `console` (DSKY-like), `imu_stub`, `thruster_stub`, `timer`

## Real-time behavior

- Preemptive **priority scheduling**
- Overload path inspired by **program alarms 1201/1202**: when the executive cannot service the job queue in time, drop or defer lowest-priority work and signal `ALARM_EXEC_OVERFLOW`
- AI inference is **never** higher priority than hard control loops unless explicitly promoted for an experiment (default: AI is shed first)

## What we deliberately do *not* claim

- Cycle-perfect AGC instruction timing
- Bit-identical rope encoding or yaYUL/assembly compatibility
- Flight certification of any kind

For historical fidelity of the real AGC, see Virtual AGC and MIT/NASA primary sources. Luminary is a **constrained OS laboratory** using Block II *budgets* as law.
