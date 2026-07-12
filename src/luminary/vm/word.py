"""15 data bits + 1 odd-parity bit — the Block II word contract."""

from __future__ import annotations

from dataclasses import dataclass


DATA_MASK = 0x7FFF  # 15 bits
SIGN_BIT = 0x4000  # bit 14 of data field (two's complement sign)


class ParityError(Exception):
    """Raised when a stored word fails odd-parity check."""


def _parity_bit(data15: int) -> int:
    """Odd parity over the 15 data bits. Returns 0 or 1."""
    data15 &= DATA_MASK
    ones = bin(data15).count("1")
    # odd parity: total ones including parity bit is odd
    return 0 if (ones % 2 == 1) else 1


def data_to_word(data15: int) -> int:
    """Pack 15-bit data into a 16-bit word with odd parity in bit 15."""
    data15 &= DATA_MASK
    p = _parity_bit(data15)
    return data15 | (p << 15)


def word_to_data(word16: int, *, check_parity: bool = True) -> int:
    """Extract 15-bit data; optionally verify odd parity."""
    word16 &= 0xFFFF
    data = word16 & DATA_MASK
    stored_p = (word16 >> 15) & 1
    if check_parity and stored_p != _parity_bit(data):
        raise ParityError(f"parity fault on word 0x{word16:04X}")
    return data


def to_signed15(data15: int) -> int:
    """Interpret 15-bit field as two's complement signed integer."""
    data15 &= DATA_MASK
    if data15 & SIGN_BIT:
        return data15 - 0x8000
    return data15


def from_signed15(value: int) -> int:
    """Clamp/wrap Python int into 15-bit two's complement field."""
    # wrap like hardware
    return value & DATA_MASK


@dataclass(frozen=True, slots=True)
class Word:
    """Immutable view of a parity-protected word."""

    raw: int

    @classmethod
    def from_data(cls, data15: int) -> "Word":
        return cls(data_to_word(data15))

    @classmethod
    def from_signed(cls, value: int) -> "Word":
        return cls(data_to_word(from_signed15(value)))

    def data(self, *, check_parity: bool = True) -> int:
        return word_to_data(self.raw, check_parity=check_parity)

    def signed(self, *, check_parity: bool = True) -> int:
        return to_signed15(self.data(check_parity=check_parity))

    def with_flipped_parity(self) -> "Word":
        """Inject a parity fault (for testing)."""
        return Word(self.raw ^ 0x8000)
