"""Minimal ISA CPU with cycle accounting at Block II clock scale."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum
from typing import Callable, Optional

from luminary import CLOCK_HZ
from luminary.vm.memory import ErasableMemory, MemoryFault, RopeMemory
from luminary.vm.word import from_signed15, to_signed15


class MiniISA(IntEnum):
    NOP = 0x0
    HLT = 0x1
    LDA = 0x2
    STA = 0x3
    ADD = 0x4
    SUB = 0x5
    JMP = 0x6
    JZ = 0x7
    JN = 0x8
    OUT = 0x9
    IN = 0xA
    SYS = 0xB
    LI = 0xC
    AND = 0xD
    OR = 0xE
    XOR = 0xF


# Rough relative cycle costs (not cycle-perfect AGC)
OP_CYCLES = {
    MiniISA.NOP: 1,
    MiniISA.HLT: 1,
    MiniISA.LDA: 2,
    MiniISA.STA: 2,
    MiniISA.ADD: 2,
    MiniISA.SUB: 2,
    MiniISA.JMP: 1,
    MiniISA.JZ: 1,
    MiniISA.JN: 1,
    MiniISA.OUT: 3,
    MiniISA.IN: 3,
    MiniISA.SYS: 4,
    MiniISA.LI: 1,
    MiniISA.AND: 2,
    MiniISA.OR: 2,
    MiniISA.XOR: 2,
}


def encode(op: MiniISA | int, payload: int = 0) -> int:
    """Encode op + 11-bit payload into 15-bit data field."""
    return ((int(op) & 0xF) << 11) | (payload & 0x7FF)


def decode(data15: int) -> tuple[int, int]:
    op = (data15 >> 11) & 0xF
    payload = data15 & 0x7FF
    return op, payload


@dataclass
class CPU:
    """
    Registers + fetch/execute loop.

    Address space for LDA/STA/etc.:
      0x000–0x7FF  → erasable (wrapped mod RAM capacity for safety in demos)
      with rope fetch for PC when running pure rope programs
    """

    erasable: ErasableMemory
    rope: RopeMemory
    A: int = 0
    L: int = 0
    Q: int = 0
    Z: int = 0  # program counter (rope address by default)
    cycles: int = 0
    halted: bool = False
    # device and syscall hooks
    out_handler: Optional[Callable[[int, int], None]] = None
    in_handler: Optional[Callable[[int], int]] = None
    sys_handler: Optional[Callable[[int, "CPU"], int]] = None
    # fetch from rope (programs) by default
    fetch_from_rope: bool = True
    trace: list[str] = field(default_factory=list)
    enable_trace: bool = False

    def reset(self, entry: int = 0) -> None:
        self.A = self.L = self.Q = 0
        self.Z = entry & 0x7FFF
        self.cycles = 0
        self.halted = False
        self.trace.clear()

    def mem_read(self, addr: int) -> int:
        addr &= 0x7FF
        if addr < self.erasable.CAPACITY:
            return self.erasable.read(addr)
        raise MemoryFault(f"data address {addr} unmapped")

    def mem_write(self, addr: int, value: int) -> None:
        addr &= 0x7FF
        if addr < self.erasable.CAPACITY:
            self.erasable.write(addr, value & 0x7FFF)
            return
        raise MemoryFault(f"data address {addr} unmapped")

    def fetch(self) -> int:
        if self.fetch_from_rope:
            return self.rope.read(self.Z)
        return self.mem_read(self.Z)

    def step(self) -> int:
        if self.halted:
            return 0
        data = self.fetch()
        op, payload = decode(data)
        cost = OP_CYCLES.get(MiniISA(op), 1) if op in MiniISA._value2member_map_ else 1

        if self.enable_trace:
            self.trace.append(f"Z={self.Z:04X} op={op:X} p={payload:03X} A={self.A:04X}")

        if op == MiniISA.NOP:
            self.Z += 1
        elif op == MiniISA.HLT:
            self.halted = True
        elif op == MiniISA.LDA:
            self.A = self.mem_read(payload)
            self.Z += 1
        elif op == MiniISA.STA:
            self.mem_write(payload, self.A)
            self.Z += 1
        elif op == MiniISA.ADD:
            s = to_signed15(self.A) + to_signed15(self.mem_read(payload))
            self.A = from_signed15(s)
            self.Z += 1
        elif op == MiniISA.SUB:
            s = to_signed15(self.A) - to_signed15(self.mem_read(payload))
            self.A = from_signed15(s)
            self.Z += 1
        elif op == MiniISA.JMP:
            self.Z = payload
        elif op == MiniISA.JZ:
            self.Z = payload if self.A == 0 else self.Z + 1
        elif op == MiniISA.JN:
            self.Z = payload if to_signed15(self.A) < 0 else self.Z + 1
        elif op == MiniISA.OUT:
            if self.out_handler:
                self.out_handler(payload, self.A)
            self.Z += 1
        elif op == MiniISA.IN:
            self.A = self.in_handler(payload) if self.in_handler else 0
            self.A &= 0x7FFF
            self.Z += 1
        elif op == MiniISA.SYS:
            if self.sys_handler:
                self.A = self.sys_handler(payload, self) & 0x7FFF
            self.Z += 1
        elif op == MiniISA.LI:
            # 11-bit payload; treat low 7 as signed immediate for convenience
            imm = payload & 0x7F
            if imm & 0x40:
                imm -= 0x80
            self.A = from_signed15(imm)
            self.Z += 1
        elif op == MiniISA.AND:
            self.A = (self.A & self.mem_read(payload)) & 0x7FFF
            self.Z += 1
        elif op == MiniISA.OR:
            self.A = (self.A | self.mem_read(payload)) & 0x7FFF
            self.Z += 1
        elif op == MiniISA.XOR:
            self.A = (self.A ^ self.mem_read(payload)) & 0x7FFF
            self.Z += 1
        else:
            # illegal → halt with alarm path left to kernel
            self.halted = True
            cost = 1

        self.cycles += cost
        return cost

    def run(self, max_cycles: int = 100_000) -> int:
        start = self.cycles
        while not self.halted and (self.cycles - start) < max_cycles:
            self.step()
        return self.cycles - start

    def simulated_seconds(self) -> float:
        return self.cycles / float(CLOCK_HZ)
