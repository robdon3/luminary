"""Virtual device bus — stand-in for ~150 AGC interfaces."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict


class Device(ABC):
    name: str
    channel: int
    irq_priority: int = 4

    @abstractmethod
    def read(self, reg: int) -> int:
        ...

    @abstractmethod
    def write(self, reg: int, value: int) -> None:
        ...


@dataclass
class DeviceBus:
    devices: Dict[int, Device] = field(default_factory=dict)
    by_name: Dict[str, Device] = field(default_factory=dict)

    def attach(self, dev: Device) -> None:
        self.devices[dev.channel] = dev
        self.by_name[dev.name] = dev

    def read(self, channel: int, reg: int = 0) -> int:
        dev = self.devices.get(channel)
        if dev is None:
            return 0
        return dev.read(reg) & 0x7FFF

    def write(self, channel: int, value: int, reg: int = 0) -> None:
        dev = self.devices.get(channel)
        if dev is None:
            return
        dev.write(reg, value & 0x7FFF)
