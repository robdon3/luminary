import unittest

from luminary.vm.cpu import CPU, MiniISA, encode
from luminary.vm.memory import ErasableMemory, RopeMemory


class TestCPU(unittest.TestCase):
    def test_add_program(self):
        # LI 7; STA 0x20; LI 3; ADD 0x20; STA 0x21; HLT
        prog = [
            encode(MiniISA.LI, 7),
            encode(MiniISA.STA, 0x20),
            encode(MiniISA.LI, 3),
            encode(MiniISA.ADD, 0x20),
            encode(MiniISA.STA, 0x21),
            encode(MiniISA.HLT),
        ]
        rope = RopeMemory(prog)
        erasable = ErasableMemory()
        cpu = CPU(erasable=erasable, rope=rope)
        cpu.run()
        self.assertTrue(cpu.halted)
        self.assertEqual(erasable.read(0x21), 10)


if __name__ == "__main__":
    unittest.main()
