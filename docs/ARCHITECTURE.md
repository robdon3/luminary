# Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Host development machine                 │
│  (optional LLMs, distillers, verifiers — never in rope)      │
└───────────────────────────┬─────────────────────────────────┘
                            │ builds rope image (.rope)
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                     Luminary Virtual Machine                 │
│  15+1 words · 2K erasable · 36K rope · cycle accounting      │
├─────────────────────────────────────────────────────────────┤
│  Kernel executive                                            │
│  · priority job queue  · interrupt dispatch  · memory mgr    │
│  · alarm / load-shed (1202-class)  · device channels         │
├──────────────┬──────────────────────┬───────────────────────┤
│  Control     │  Sensing / I/O       │  AI passenger          │
│  loops       │  device drivers      │  binary net inference  │
│  (P0–P2)     │  (P1–P4)             │  (P5–P7, shed first)   │
└──────────────┴──────────────────────┴───────────────────────┘
```

## Layers

### 1. VM (`luminary.vm`)

- **Word**: 15 data bits + odd parity
- **ErasableMemory**: 2048 words, parity-checked R/W
- **RopeMemory**: 36864 words, read-only
- **CPU**: registers, fetch/decode of a *tiny* instruction set sufficient for demos (not full AGC ISA)
- **Clock**: advances machine cycles; optional real-time throttle vs host wall clock

### 2. Kernel (`luminary.kernel`)

- **Scheduler**: multi-level priority queues; each job has `priority`, `deadline_cycles`, `work_fn`
- **Interrupts**: timer tick, device IRQs, software traps
- **Alarms**: `ALARM_EXEC_OVERFLOW` when backlog exceeds threshold (1202 spirit)
- **Memory manager**: static partitions + tiny bump allocator in erasable; no general heap fragmentation games
- **Syscalls**: `yield`, `spawn`, `sleep_cycles`, `read_device`, `write_device`, `ai_infer`, `raise_alarm`

### 3. AI passenger (`luminary.ai`)

- Weights live in **rope** (immutable)
- Activations live in a **fixed erasable scratch** window
- Inference is a **bounded job**: max ops per invocation; excess → partial result or skip
- On executive overflow, AI jobs are cancelled first

### 4. Devices (`luminary.devices`)

- Abstract `Device` with channel id, IRQ priority, read/write
- Demo set: `DSKYConsole`, `MissionTimer`, `SyntheticIMU`, `ThrusterBank`

## Instruction set (Luminary mini-ISA)

Enough to write rope programs without pulling a full AGC toolchain:

| Op | Mnemonic | Effect |
|----|----------|--------|
| 0x0 | `NOP` | — |
| 0x1 | `HLT` | Halt |
| 0x2 | `LDA addr` | A ← mem |
| 0x3 | `STA addr` | mem ← A |
| 0x4 | `ADD addr` | A ← A + mem |
| 0x5 | `SUB addr` | A ← A − mem |
| 0x6 | `JMP addr` | PC ← addr |
| 0x7 | `JZ addr` | if A==0 PC ← addr |
| 0x8 | `JN addr` | if A<0 PC ← addr |
| 0x9 | `OUT port` | write A to device |
| 0xA | `IN port` | A ← device |
| 0xB | `SYS n` | syscall |
| 0xC | `LI imm` | A ← immediate (7-bit signed in low field) |
| 0xD | `AND addr` | A ← A & mem |
| 0xE | `OR addr` | A ← A \| mem |
| 0xF | `XOR addr` | A ← A ^ mem |

Encoding: 16-bit word = `[parity | op:4 | payload:11]` with payload as address or immediate (addresses use 11 bits for low window; banking for full rope via kernel helpers).

## Build pipeline

```
sources / weight tables
        │
        ▼
  tools/pack_rope.py   ──►  image.rope  (≤ 36864 words)
        │
        ▼
  budget check (fail if over)
        │
        ▼
  VM load + kernel boot
```

## Failure philosophy

| Condition | Response |
|-----------|----------|
| Parity error on read | Trap → alarm; optional scrub/retry |
| Erasable exhaustion | Fail allocation; never silent OOM into neighbors |
| Job queue overload | Drop P≥5 (AI/telemetry), raise 1202-class alarm |
| Rope image too large | **Host build failure** — never boot partial |

## Relationship to real AGC software

Names (`Luminary`, rope, 1202) are **intentional cultural anchors**. Implementation is a clean-room constrained OS for research and education, not a rehost of Colossus/Luminary flight code.
