"""Mission timer device."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class MissionTimer:
    name: str = "timer"
    channel: int = 2
    irq_priority: int = 0
    ticks: int = 0

    def read(self, reg: int) -> int:
        if reg == 0:
            return self.ticks & 0x7FFF
        if reg == 1:
            return (self.ticks >> 15) & 0x7FFF
        return 0

    def write(self, reg: int, value: int) -> None:
        if reg == 0:
            self.ticks = value

    def advance(self, n: int = 1) -> None:
        self.ticks += n
