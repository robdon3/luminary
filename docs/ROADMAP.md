# Roadmap

## Phase 0 — Foundation (current)

- [x] Hardware contract documentation
- [x] 15+1 word VM, rope + erasable
- [x] Priority scheduler + 1202-class overflow alarm
- [x] Rope-sized binary net inference
- [x] Demo mission profile + tests
- [x] Public GitHub project

## Phase 1 — Density

- [ ] Assembler + rope linker with bank maps
- [ ] Stricter cycle accounting per ISA op
- [ ] Property tests: never exceed 2048 / 36864
- [ ] DSKY-like TUI over the console device

## Phase 2 — Fidelity experiments

- [ ] Optional mode closer to published AGC interrupt priorities
- [ ] Fault injection (parity flips, delayed IRQs)
- [ ] Telemetry recorder for "descent" replays

## Phase 3 — AI research hooks

- [ ] Host distiller: train small BNN → pack rope
- [ ] Auto budget report in CI
- [ ] Compare BNN vs pure heuristics under identical overload

## Phase 4 — Silicon path (optional)

- [ ] soft-core on FPGA with real timing
- [ ] Power/thermal notes vs 55–70 W historical envelope
- [ ] Physical "1 cubic foot" demo build notes

Contributions should preserve the hard budgets. Features that need more RAM belong on the **host**, not in erasable core.
