"""
Rope-sized binary neural network.

Weights are ±1 (stored as 0/1). Inference is XNOR-popcount style integer math —
no floats, fits the AGC integer heritage and tiny erasable scratch.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import random
from typing import Sequence


def _popcount(x: int) -> int:
    return bin(x & 0xFFFFFFFF).count("1")


def _bits_to_words(bits: Sequence[int]) -> list[int]:
    """Pack bits MSB-first into 15-bit data words."""
    words: list[int] = []
    acc = 0
    n = 0
    for b in bits:
        acc = (acc << 1) | (1 if b else 0)
        n += 1
        if n == 15:
            words.append(acc & 0x7FFF)
            acc = 0
            n = 0
    if n:
        acc <<= 15 - n
        words.append(acc & 0x7FFF)
    return words


def _xnor_popcount_score(input_bits: Sequence[int], weight_bits: Sequence[int]) -> int:
    """
    Agreement count between inputs and weights (both 0/1 meaning ±1).
    Higher = more aligned. Lengths must match.
    """
    assert len(input_bits) == len(weight_bits)
    # pack into ints for speed on host
    score = 0
    for i, w in zip(input_bits, weight_bits):
        # XNOR: equal bits agree
        score += 1 if (i == w) else 0
    # center around 0: 2*agreements - n
    return 2 * score - len(input_bits)


@dataclass
class BinaryNet:
    """Fully-connected binary net: n_in → n_hidden → n_out."""

    n_in: int
    n_hidden: int
    n_out: int
    # weight bits: layer1[h][i], layer2[o][h]
    w1: list[list[int]] = field(default_factory=list)
    w2: list[list[int]] = field(default_factory=list)
    rope_base: int = 0
    rope_words: int = 0

    def __post_init__(self) -> None:
        if not self.w1:
            self.w1 = [
                [0 for _ in range(self.n_in)] for _ in range(self.n_hidden)
            ]
        if not self.w2:
            self.w2 = [
                [0 for _ in range(self.n_hidden)] for _ in range(self.n_out)
            ]

    @classmethod
    def random(
        cls,
        n_in: int,
        n_hidden: int,
        n_out: int,
        *,
        seed: int = 11,
    ) -> "BinaryNet":
        rng = random.Random(seed)
        w1 = [[rng.randint(0, 1) for _ in range(n_in)] for _ in range(n_hidden)]
        w2 = [[rng.randint(0, 1) for _ in range(n_hidden)] for _ in range(n_out)]
        return cls(n_in=n_in, n_hidden=n_hidden, n_out=n_out, w1=w1, w2=w2)

    def forward(self, x_bits: Sequence[int]) -> list[int]:
        if len(x_bits) != self.n_in:
            raise ValueError(f"expected {self.n_in} inputs, got {len(x_bits)}")
        # hidden activations as bits via threshold 0 on signed score
        h_bits: list[int] = []
        for h in range(self.n_hidden):
            s = _xnor_popcount_score(x_bits, self.w1[h])
            h_bits.append(1 if s >= 0 else 0)
        scores: list[int] = []
        for o in range(self.n_out):
            scores.append(_xnor_popcount_score(h_bits, self.w2[o]))
        return scores

    def predict(self, x_bits: Sequence[int]) -> int:
        scores = self.forward(x_bits)
        return max(range(len(scores)), key=lambda i: scores[i])

    def weight_bit_count(self) -> int:
        return self.n_hidden * self.n_in + self.n_out * self.n_hidden

    def estimate_rope_words(self) -> int:
        # header: 3 words (n_in, n_hidden, n_out) + packed weights
        bits = self.weight_bit_count()
        packed = (bits + 14) // 15
        return 3 + packed


def pack_weights_to_words(net: BinaryNet) -> list[int]:
    """Serialize net into rope data words (15-bit each, no parity yet)."""
    header = [net.n_in & 0x7FFF, net.n_hidden & 0x7FFF, net.n_out & 0x7FFF]
    bits: list[int] = []
    for row in net.w1:
        bits.extend(row)
    for row in net.w2:
        bits.extend(row)
    return header + _bits_to_words(bits)


def demo_descent_net() -> BinaryNet:
    """
    Hand-ish small net for the descent demo.

    Inputs (8 bits derived from sensor words): rough features.
    Outputs (4 classes): 0=hold, 1=slow_descent, 2=brake, 3=abort_rec
    """
    # Prefer a deterministic handcrafted-ish random seed so demos are stable
    net = BinaryNet.random(8, 16, 4, seed=1969)
    return net
