import itertools
import random
import unittest

from loki.re.fnfacts import MuxFact, cofactor, facts, npn_sig


def table_of(width: int, fn: object) -> int:
    assert callable(fn)
    out = 0
    for x in range(1 << width):
        bits = [(x >> i) & 1 for i in range(width)]
        out |= (int(fn(*bits)) & 1) << x
    return out


def permute(table: int, width: int, perm: tuple[int, ...], neg_out: bool) -> int:
    out = 0
    for x in range(1 << width):
        y = sum(((x >> i) & 1) << perm[i] for i in range(width))
        out |= (((table >> y) & 1) ^ int(neg_out)) << x
    return out


class FactsTest(unittest.TestCase):
    def test_facts_xor_xnor(self) -> None:
        self.assertEqual(facts(0b0110, 2).parity, 1)
        self.assertEqual(facts(0b1001, 2).parity, -1)
        self.assertEqual(facts(0b1000, 2).parity, 0)

    def test_facts_and_or(self) -> None:
        f = facts(0b1000, 2)
        self.assertTrue(f.and_like and not f.or_like)
        self.assertEqual((f.ones, f.support), (1, (0, 1)))
        g = facts(0b1110, 2)
        self.assertTrue(g.or_like and not g.and_like)
        self.assertFalse(facts(0b0110, 2).and_like)

    def test_facts_mux2(self) -> None:
        t = table_of(3, lambda a, b, s: b if s else a)
        self.assertEqual(facts(t, 3).mux, MuxFact((2,), (0, 1)))
        self.assertIsNone(facts(0b1000, 2).mux)

    def test_facts_mux4_lut6(self) -> None:
        t = table_of(6, lambda d0, d1, d2, d3, s0, s1: (d0, d1, d2, d3)[s0 + 2 * s1])
        self.assertEqual(facts(t, 6).mux, MuxFact((4, 5), (0, 1, 2, 3)))

    def test_facts_maj3_negated(self) -> None:
        maj = table_of(3, lambda a, b, c: a + b + c >= 2)
        inv1 = table_of(3, lambda a, b, c: a + (1 - b) + c >= 2)
        self.assertTrue(facts(maj, 3).maj3)
        self.assertTrue(facts(inv1, 3).maj3)
        self.assertTrue(facts(maj ^ 0xFF, 3).maj3)
        self.assertFalse(facts(table_of(3, lambda a, b, c: a ^ b ^ c), 3).maj3)

    def test_support_drops_dummy_input(self) -> None:
        t = table_of(3, lambda a, b, c: a & c)  # b is a dummy input
        f = facts(t, 3)
        self.assertEqual(f.support, (0, 2))
        self.assertTrue(f.and_like)

    def test_npn_sig_invariant(self) -> None:
        t = table_of(3, lambda a, b, c: (a & b) | c)
        base = npn_sig(t, 3)
        for perm in itertools.permutations(range(3)):
            for neg in (False, True):
                self.assertEqual(npn_sig(permute(t, 3, perm, neg), 3), base)
        inv_in = table_of(3, lambda a, b, c: ((1 - a) & b) | c)
        self.assertEqual(npn_sig(inv_in, 3), base)
        self.assertNotEqual(npn_sig(0b1000, 2), npn_sig(0b0110, 2))

    def test_npn_sig_random_invariance(self) -> None:
        rng = random.Random("l1-npn")
        for _ in range(30):
            t = rng.getrandbits(16)
            perm = tuple(rng.sample(range(4), 4))
            self.assertEqual(npn_sig(permute(t, 4, perm, True), 4), npn_sig(t, 4))

    def test_cofactor(self) -> None:
        t = table_of(2, lambda a, b: a & b)
        self.assertEqual(cofactor(t, 2, 0, 1), table_of(2, lambda a, b: b))
        self.assertEqual(cofactor(t, 2, 0, 0), 0)
        self.assertEqual(cofactor(t, 2, 1, 1), table_of(2, lambda a, b: a))


if __name__ == "__main__":
    unittest.main()
