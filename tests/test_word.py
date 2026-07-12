import unittest

from luminary.vm.word import (
    ParityError,
    Word,
    data_to_word,
    from_signed15,
    to_signed15,
    word_to_data,
)


class TestWord(unittest.TestCase):
    def test_parity_roundtrip(self):
        for v in (0, 1, 0x7FFF, 0x1234, 0x4000):
            w = data_to_word(v)
            self.assertEqual(word_to_data(w), v & 0x7FFF)

    def test_parity_fault(self):
        w = data_to_word(0x00FF)
        bad = w ^ 0x8000
        with self.assertRaises(ParityError):
            word_to_data(bad, check_parity=True)

    def test_signed(self):
        self.assertEqual(to_signed15(from_signed15(-3)), -3)
        self.assertEqual(to_signed15(from_signed15(100)), 100)
        self.assertEqual(Word.from_signed(-1).signed(), -1)


if __name__ == "__main__":
    unittest.main()
