#!/usr/bin/env python3
"""Pack a list of 15-bit data words into a .rope text image and check budgets."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from luminary import ROM_WORDS
from luminary.vm.memory import assert_budgets
from luminary.vm.word import data_to_word


def main() -> int:
    p = argparse.ArgumentParser(description="Pack rope image")
    p.add_argument("-o", "--output", type=Path, default=Path("image.rope"))
    p.add_argument(
        "words",
        nargs="*",
        type=lambda s: int(s, 0),
        help="15-bit data words (hex with 0x ok)",
    )
    args = p.parse_args()
    data = list(args.words)
    assert_budgets(len(data), 0)
    packed = [data_to_word(w) for w in data]
    lines = [f"{w:04X}" for w in packed]
    args.output.write_text("\n".join(lines) + ("\n" if lines else ""))
    print(f"wrote {len(packed)} words to {args.output} (max {ROM_WORDS})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
