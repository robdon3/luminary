"""Static erasable layout — every word reserved in advance."""

from __future__ import annotations

from dataclasses import dataclass

from luminary import RAM_WORDS


# Fixed partitions (word addresses)
ZERO_PAGE = 0x0000
ZERO_PAGE_WORDS = 64

# Kernel TCBs / queues
KERNEL_BASE = 0x0040
KERNEL_WORDS = 128

# Sensor / device buffers
DEVICE_BUF_BASE = 0x00C0
DEVICE_BUF_WORDS = 64

# AI activation scratch (shed-safe; not critical path)
AI_SCRATCH_BASE = 0x0100
AI_SCRATCH_WORDS = 32

# General working set / stacks
WORK_BASE = 0x0120
WORK_WORDS = RAM_WORDS - WORK_BASE


@dataclass(frozen=True)
class MemoryMap:
    """Describes erasable layout; used by budget tools and kernel."""

    zero_page: int = ZERO_PAGE
    zero_page_words: int = ZERO_PAGE_WORDS
    kernel_base: int = KERNEL_BASE
    kernel_words: int = KERNEL_WORDS
    device_buf_base: int = DEVICE_BUF_BASE
    device_buf_words: int = DEVICE_BUF_WORDS
    ai_scratch_base: int = AI_SCRATCH_BASE
    ai_scratch_words: int = AI_SCRATCH_WORDS
    work_base: int = WORK_BASE
    work_words: int = WORK_WORDS

    def total_reserved(self) -> int:
        return (
            self.zero_page_words
            + self.kernel_words
            + self.device_buf_words
            + self.ai_scratch_words
            + self.work_words
        )

    def validate(self) -> None:
        total = self.total_reserved()
        # partitions are contiguous by construction; assert end == RAM
        end = self.work_base + self.work_words
        if end != RAM_WORDS:
            raise ValueError(f"memory map end {end} != RAM_WORDS {RAM_WORDS}")
        if total != RAM_WORDS:
            raise ValueError(f"memory map total {total} != {RAM_WORDS}")

    def report(self) -> str:
        lines = [
            "Erasable memory map (words):",
            f"  zero page     @ 0x{self.zero_page:04X}  {self.zero_page_words:4d} words",
            f"  kernel        @ 0x{self.kernel_base:04X}  {self.kernel_words:4d} words",
            f"  device buf    @ 0x{self.device_buf_base:04X}  {self.device_buf_words:4d} words",
            f"  AI scratch    @ 0x{self.ai_scratch_base:04X}  {self.ai_scratch_words:4d} words",
            f"  work/stack    @ 0x{self.work_base:04X}  {self.work_words:4d} words",
            f"  TOTAL                    {RAM_WORDS:4d} / {RAM_WORDS} (Block II)",
        ]
        return "\n".join(lines)
