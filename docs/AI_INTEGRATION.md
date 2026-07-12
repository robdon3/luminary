# AI integration under Apollo budgets

The point of Luminary is not "run ChatGPT on the Moon." It is to force a clean separation:

| Where AI lives | What it may do | Budget |
|----------------|----------------|--------|
| **Host (dev/ops)** | Author code, distill models, verify proofs, generate tests | Unlimited modern hardware |
| **Rope (flight image)** | Immutable weights + tiny inference code | Share of 36,864 words |
| **Erasable (runtime)** | Activations, scores, decisions | Share of 2,048 words |
| **Scheduler** | Run inference as low-priority real-time job | Hard cycle cap; shed first |

## Principles

1. **Distill, don't download.** Large models train on the ground. Deployed artifact is a binary network, LUT, or decision table that fits rope.
2. **Intelligence is interruptible.** Incomplete inference beats a missed thruster deadline.
3. **Parity covers weights.** Rope words are parity-protected; corrupted intelligence is a fault, not "creative output."
4. **No ambient agents.** No network-dependent LLM calls from inside the VM. If a co-pilot exists, it is a *host* process talking *to* the sim, not code running under the 4 KB ceiling.

## Rope-sized model: binary neural net (BNN)

Default onboard model:

- Inputs: 8–16 quantized sensor features (e.g. rates, altitudes, flags)
- Hidden: 1–2 layers of binary units (XNOR-popcount style)
- Output: class scores or a small control recommendation enum
- Weights: packed bits in rope (±1 stored as 0/1)
- Activations: bitsets in erasable scratch (~a few words)

### Why binary nets?

| Property | Benefit under Block II |
|----------|-------------------------|
| 1-bit weights | Thousands of parameters per rope word group |
| XNOR + popcount | Fits mini-ISA / tight Python loops with tiny cycle cost |
| No float | Matches integer AGC heritage |
| Deterministic | Certifiable behavior for experiments |

## Example budget sketch (demo model)

| Item | Words (approx.) |
|------|-----------------|
| Kernel executive | 800–2000 |
| Device stubs | 200–400 |
| BNN weights (8→32→4) | ~20–40 |
| Inference routine | ~50–100 |
| Mission demo logic | 100–300 |
| **Total demo rope** | **≪ 36K** (leaves room for real experiments) |

Erasable scratch for AI: **16–64 words** reserved in the memory map (`AI_SCRATCH_BASE`).

## Host-side AI (outside the hull)

Allowed and encouraged:

- Generate assembly / rope packing scripts
- Search for smaller equivalent nets (NAS under word budget)
- Formal or fuzz verification of the scheduler under overload
- Natural-language "mission brief" → structured job table (compile step only)

Forbidden inside the flight image:

- Tokenizer + transformer weights
- Dynamic code download
- Unbounded heap for attention caches

## Overload policy (AI and 1202)

When the executive detects overload:

1. Cancel jobs with priority ≥ `AI_PRIORITY_FLOOR` (default 5)
2. Raise `ALARM_EXEC_OVERFLOW` (mnemonic nod to 1201/1202)
3. Keep P0–P2 control and sensing paths alive
4. Optionally re-queue a *cheap* heuristic fallback instead of the net

This is the core "AI age meets AGC discipline" thesis: **smart when quiet, ruthless when busy.**

## Future directions

- Quantized int4 tables if BNN is too weak for a research task
- Rope compression of LUTs (shared banks)
- Dual-string comparison: two tiny models vote; disagreement → safe mode
- FPGA port measuring real power toward the 55–70 W envelope
