# Assembly / rope images

Phase 0 uses the Python mini-ISA encoder (`luminary.vm.cpu.encode`).

Future: a small assembler will emit `.rope` images consumed by `tools/pack_rope.py`.

Constraints:

- Total image ≤ **36,864** words
- Prefer placing AI weight blobs in high rope banks, kernel in low rope
