"""Erasable (2K) and rope (36K) memory with parity enforcement."""

from __future__ import annotations

from typing import Iterable, Sequence

from luminary import RAM_WORDS, ROM_WORDS
from luminary.vm.word import ParityError, Word, data_to_word, word_to_data


class MemoryFault(Exception):
    """Invalid address, write to rope, or parity failure."""


class ErasableMemory:
    """RAM: 2,048 words of parity-protected core."""

    CAPACITY = RAM_WORDS

    def __init__(self) -> None:
        self._cells = [data_to_word(0) for _ in range(self.CAPACITY)]
        self.read_count = 0
        self.write_count = 0
        self.parity_faults = 0

    def read(self, addr: int, *, check_parity: bool = True) -> int:
        self._check_addr(addr)
        self.read_count += 1
        try:
            return word_to_data(self._cells[addr], check_parity=check_parity)
        except ParityError as exc:
            self.parity_faults += 1
            raise MemoryFault(str(exc)) from exc

    def write(self, addr: int, data15: int) -> None:
        self._check_addr(addr)
        self.write_count += 1
        self._cells[addr] = data_to_word(data15)

    def read_word(self, addr: int) -> Word:
        self._check_addr(addr)
        return Word(self._cells[addr])

    def inject_parity_fault(self, addr: int) -> None:
        self._check_addr(addr)
        self._cells[addr] ^= 0x8000

    def used_nonzero(self) -> int:
        return sum(1 for c in self._cells if (c & 0x7FFF) != 0)

    def _check_addr(self, addr: int) -> None:
        if not 0 <= addr < self.CAPACITY:
            raise MemoryFault(
                f"erasable address {addr} out of range [0, {self.CAPACITY})"
            )


class RopeMemory:
    """ROM: 36,864 words of immutable 'core rope'."""

    CAPACITY = ROM_WORDS

    def __init__(self, image: Sequence[int] | None = None) -> None:
        self._cells = [data_to_word(0) for _ in range(self.CAPACITY)]
        self.read_count = 0
        self.parity_faults = 0
        if image is not None:
            self.load(image)

    def load(self, image: Sequence[int], *, already_packed: bool = False) -> None:
        """Load data words (15-bit) or pre-packed 16-bit words into rope."""
        if len(image) > self.CAPACITY:
            raise MemoryFault(
                f"rope image has {len(image)} words; max is {self.CAPACITY}"
            )
        for i, w in enumerate(image):
            if already_packed:
                self._cells[i] = w & 0xFFFF
            else:
                self._cells[i] = data_to_word(w)
        # remainder stays zero (NOP / empty)

    def load_from_bytes_words(self, words: Iterable[int]) -> int:
        """Load iterable of 15-bit data words; return count written."""
        buf = list(words)
        self.load(buf, already_packed=False)
        return len(buf)

    def read(self, addr: int, *, check_parity: bool = True) -> int:
        self._check_addr(addr)
        self.read_count += 1
        try:
            return word_to_data(self._cells[addr], check_parity=check_parity)
        except ParityError as exc:
            self.parity_faults += 1
            raise MemoryFault(str(exc)) from exc

    def write(self, addr: int, data15: int) -> None:
        raise MemoryFault(f"write to rope ROM at {addr} forbidden")

    def image_size(self) -> int:
        """Highest address+1 with non-zero data (for budget reports)."""
        last = 0
        for i, c in enumerate(self._cells):
            if (c & 0x7FFF) != 0:
                last = i + 1
        return last

    def as_data_list(self, n: int | None = None) -> list[int]:
        n = n if n is not None else self.CAPACITY
        return [word_to_data(self._cells[i], check_parity=False) for i in range(n)]

    def _check_addr(self, addr: int) -> None:
        if not 0 <= addr < self.CAPACITY:
            raise MemoryFault(
                f"rope address {addr} out of range [0, {self.CAPACITY})"
            )


def assert_budgets(rope_used: int, erasable_reserved: int) -> None:
    """Host-side budget gate — fail builds that exceed Block II."""
    if rope_used > ROM_WORDS:
        raise MemoryFault(f"rope budget exceeded: {rope_used} > {ROM_WORDS}")
    if erasable_reserved > RAM_WORDS:
        raise MemoryFault(
            f"erasable budget exceeded: {erasable_reserved} > {RAM_WORDS}"
        )
