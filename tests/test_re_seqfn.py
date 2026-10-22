import random
import unittest

from loki.re.detectors import Candidate
from loki.re.detectors.seqfn import SeqfnDetector
from loki.re.provers import TruthTableProver
from loki.re.seqtable import classify, reachable, transition_table
from tests.re_fixtures import GB, make_ctx, table_of
from tests.seq_fixtures import (
    down_counter,
    lfsr,
    modulo_counter,
    shift_register,
    up_counter,
)


def propose(g: GB, kind: str | None = None) -> list[Candidate]:
    got = SeqfnDetector().propose(make_ctx(g.build()))
    return [c for c in got if kind is None or c.kind == kind]


def proves(g: GB, c: Candidate) -> bool:
    assert c.claim is not None
    verdict = TruthTableProver().prove(g.build(), c.claim, random.Random(1))
    return verdict.verdict == "equivalent"


class CounterTest(unittest.TestCase):
    def test_up_counter_with_enable(self) -> None:
        g = GB()
        clk, en = g.pi("clk"), g.pi("en")
        qs = up_counter(g, clk, 4, en=en)
        got = propose(g)
        self.assertEqual({c.kind for c in got}, {"counter"})
        main = [c for c in got if c.claim and c.claim.op == "counter"]
        alt = [c for c in got if c.claim and c.claim.op == "counter_en"]
        self.assertEqual(len(main), 1)
        self.assertEqual(len(alt), 1)
        p = main[0].params
        got_p = (p["dir"], p["modulus"], p["width"], p["en"], p["rst"])
        self.assertEqual(got_p, ("up", 0, 4, en, 0))
        self.assertEqual(main[0].nets["Q"], tuple(qs))
        self.assertEqual(main[0].features["table"], "exact")
        self.assertEqual(main[0].features["counter_terms"], "1-2")
        self.assertTrue(proves(g, main[0]))
        self.assertTrue(proves(g, alt[0]))
        assert alt[0].claim is not None
        self.assertEqual(dict(alt[0].claim.inputs)["B"], (en,))

    def test_counter_with_enable_and_reset(self) -> None:
        g = GB()
        clk, en, rst = g.pi("clk"), g.pi("en"), g.pi("rst")
        up_counter(g, clk, 3, en=en, rst=rst)
        got = propose(g)
        self.assertEqual(len(got), 1)
        p = got[0].params
        self.assertEqual((p["en"], p["rst"], p["rst_value"]), (en, rst, 0))
        self.assertEqual(got[0].features["counter_terms"], "3+")
        self.assertTrue(proves(g, got[0]))

    def test_free_running_counter(self) -> None:
        g = GB()
        up_counter(g, g.pi("clk"), 3)
        got = propose(g)
        self.assertEqual(len(got), 1)
        self.assertEqual((got[0].params["en"], got[0].params["rst"]), (0, 0))
        self.assertTrue(proves(g, got[0]))

    def test_modulo_10_counter(self) -> None:
        g = GB()
        modulo_counter(g, g.pi("clk"), 4, last=9, wrap=0)
        got = propose(g)
        self.assertEqual(len(got), 1)
        self.assertEqual((got[0].params["dir"], got[0].params["modulus"]), ("up", 10))
        self.assertEqual(got[0].params["wrap"], 0)
        self.assertTrue(proves(g, got[0]))

    def test_modulo_counter_wrapping_to_one(self) -> None:
        g = GB()
        modulo_counter(g, g.pi("clk"), 4, last=10, wrap=1)
        got = propose(g)
        self.assertEqual(len(got), 1)
        self.assertEqual((got[0].params["modulus"], got[0].params["wrap"]), (11, 1))
        self.assertTrue(proves(g, got[0]))

    def test_down_counter(self) -> None:
        g = GB()
        down_counter(g, g.pi("clk"), 4)
        got = propose(g)
        self.assertEqual(len(got), 1)
        self.assertEqual((got[0].params["dir"], got[0].params["modulus"]), ("down", 0))
        self.assertTrue(proves(g, got[0]))

    def test_bit_order_from_toggle_frequency(self) -> None:
        # every next-state bit reads every state bit, so there is no chain: the order comes
        # from how often each bit toggles
        g = GB()
        qs = modulo_counter(g, g.pi("clk"), 4, last=9, wrap=0)
        got = propose(g)
        self.assertEqual(got[0].nets["Q"], tuple(qs))

    def test_sampled_table_when_wide(self) -> None:
        g = GB()
        clk = g.pi("clk")
        k = 20
        qs = [g.net() for _ in range(k)]
        g.ff(g.lut(0b01, (qs[0],)), clk, qs[0])
        carry = qs[0]
        for i in range(1, k):
            g.ff(g.lut(0b0110, (qs[i], carry)), clk, qs[i])
            carry = g.lut(0b1000, (carry, qs[i]))
        got = propose(g)
        self.assertEqual(len(got), 1)
        self.assertEqual(got[0].kind, "counter")
        self.assertEqual(got[0].features["table"], "sampled")
        t = transition_table(g.build(), qs, random.Random(1))
        self.assertFalse(t.exact)
        self.assertLessEqual(len(t.rows), 4096)

    def test_no_counter_in_plain_register(self) -> None:
        g = GB()
        clk = g.pi("clk")
        for _ in range(4):
            g.ff(g.pi(), clk)
        self.assertEqual(propose(g), [])


class ShiftLfsrTest(unittest.TestCase):
    def test_shift_register_4(self) -> None:
        g = GB()
        x = g.pi("x")
        qs = shift_register(g, g.pi("clk"), 4, x)
        got = propose(g)
        self.assertEqual([c.kind for c in got], ["shift_reg"])
        c = got[0]
        self.assertEqual((c.params["width"], c.params["dir"], c.params["x"]), (4, "l", x))
        self.assertEqual(c.nets["X"], (x,))
        self.assertEqual(c.nets["Q"], tuple(qs))
        self.assertTrue(proves(g, c))

    def test_shift_register_with_enable(self) -> None:
        g = GB()
        clk, x, en = g.pi("clk"), g.pi("x"), g.pi("en")
        qs = [g.net() for _ in range(3)]
        for i in range(3):
            src = x if i == 0 else qs[i - 1]
            g.ff(g.lut(table_of(3, lambda v: v[0] if v[2] else v[1]), (src, qs[i], en)), clk, qs[i])
        got = propose(g)
        self.assertEqual([c.kind for c in got], ["shift_reg"])
        self.assertEqual((got[0].params["x"], got[0].params["en"]), (x, en))
        self.assertTrue(proves(g, got[0]))

    def test_lfsr_taps(self) -> None:
        g = GB()
        lfsr(g, g.pi("clk"), 5, (2, 4))
        got = propose(g)
        self.assertEqual([c.kind for c in got], ["lfsr"])
        self.assertEqual(got[0].params["taps"], 0b10100)
        self.assertEqual(got[0].params["width"], 5)
        self.assertTrue(proves(g, got[0]))

    def test_classify_labels(self) -> None:
        g = GB()
        qs = up_counter(g, g.pi("clk"), 3, en=g.pi("en"))
        t = transition_table(g.build(), qs, random.Random(1))
        self.assertEqual(classify(t), {0: "hold", 1: "inc"})
        states, edges = reachable(t, 0)
        self.assertEqual(states, list(range(8)))
        self.assertEqual(len(edges), 16)


if __name__ == "__main__":
    unittest.main()
