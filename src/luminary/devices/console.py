"""DSKY-like console — verb/noun style messages for demos."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class DSKYConsole:
    name: str = "dsky"
    channel: int = 0
    irq_priority: int = 3
    messages: list[str] = field(default_factory=list)
    verb: int = 0
    noun: int = 0

    def read(self, reg: int) -> int:
        if reg == 0:
            return self.verb
        if reg == 1:
            return self.noun
        return 0

    def write(self, reg: int, value: int) -> None:
        if reg == 0:
            self.verb = value
        elif reg == 1:
            self.noun = value
        elif reg == 2:
            self.messages.append(f"V{self.verb:02d} N{self.noun:02d} = {value}")

    def display(self, text: str) -> None:
        self.messages.append(text)
