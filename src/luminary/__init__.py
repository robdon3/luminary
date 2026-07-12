"""Luminary — AI-era OS under Apollo Guidance Computer Block II budgets."""

__version__ = "0.1.0"

# Block II hardware contract (words, not bytes)
ROM_WORDS = 36_864
RAM_WORDS = 2_048
CLOCK_HZ = 2_048_000
DATA_BITS = 15
WORD_BITS = 16  # 15 data + 1 parity

__all__ = [
    "__version__",
    "ROM_WORDS",
    "RAM_WORDS",
    "CLOCK_HZ",
    "DATA_BITS",
    "WORD_BITS",
]
