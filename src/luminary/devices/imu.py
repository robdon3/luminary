"""Synthetic IMU / altitude source for descent demos."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class SyntheticIMU:
    name: str = "imu"
    channel: int = 1
    irq_priority: int = 1
    # mission state
    altitude: int = 5000  # arbitrary units
    vertical_rate: int = -50  # negative = descending
    fuel: int = 1000
    tick: int = 0

    def read(self, reg: int) -> int:
        if reg == 0:
            return self.altitude & 0x7FFF
        if reg == 1:
            return self.vertical_rate & 0x7FFF
        if reg == 2:
            return self.fuel & 0x7FFF
        if reg == 3:
            return self.tick & 0x7FFF
        return 0

    def write(self, reg: int, value: int) -> None:
        # reg 0 = thruster command magnitude (demo)
        if reg == 0:
            thrust = value & 0xFF
            self.vertical_rate += thrust // 8
            self.fuel = max(0, self.fuel - thrust // 4)

    def sample(self) -> list[int]:
        """Advance physics one tick; return feature words for erasable."""
        self.tick += 1
        self.altitude = max(0, self.altitude + self.vertical_rate)
        # pack features as 15-bit words (also used to derive AI bits)
        return [
            self.altitude & 0x7FFF,
            self.vertical_rate & 0x7FFF,
            self.fuel & 0x7FFF,
            self.tick & 0x7FFF,
            (1 if self.altitude < 500 else 0),
            (1 if self.vertical_rate < -80 else 0),
            (1 if self.fuel < 200 else 0),
            (self.altitude ^ self.fuel) & 0x7FFF,
        ]
