#!/usr/bin/env python3
"""Standalone descent demo (same as `python -m luminary demo`)."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from luminary.__main__ import cmd_demo

if __name__ == "__main__":
    raise SystemExit(cmd_demo())
