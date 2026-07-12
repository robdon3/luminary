import unittest

from luminary import RAM_WORDS, ROM_WORDS
from luminary.vm.memory import ErasableMemory, MemoryFault, RopeMemory, assert_budgets


class TestMemory(unittest.TestCase):
    def test_erasable_capacity(self):
        m = ErasableMemory()
        self.assertEqual(m.CAPACITY, RAM_WORDS)
        m.write(0, 42)
        self.assertEqual(m.read(0), 42)
        with self.assertRaises(MemoryFault):
            m.read(RAM_WORDS)

    def test_rope_readonly_and_budget(self):
        r = RopeMemory([1, 2, 3])
        self.assertEqual(r.read(0), 1)
        with self.assertRaises(MemoryFault):
            r.write(0, 9)
        with self.assertRaises(MemoryFault):
            RopeMemory([0] * (ROM_WORDS + 1))

    def test_parity_inject(self):
        m = ErasableMemory()
        m.write(5, 0x55)
        m.inject_parity_fault(5)
        with self.assertRaises(MemoryFault):
            m.read(5)

    def test_assert_budgets(self):
        assert_budgets(100, 2048)
        with self.assertRaises(MemoryFault):
            assert_budgets(ROM_WORDS + 1, 10)


if __name__ == "__main__":
    unittest.main()
