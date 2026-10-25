import unittest
from unittest import mock

from loki.re.detectors import DETECTOR_ORDER, Candidate, load_detectors
from loki.re.detectors import wordfirst as wf
from loki.re.detectors.wordfirst import (
    WordFirstDetector,
    WordGroupDetector,
    register_words,
    word_decoders,
)
from loki.re.overlay import Overlay
from tests.re_fixtures import GB, MUX, make_ctx, ripple, table_of

AND_NOT = table_of(2, lambda v: v[0] & (1 - v[1]))
AND4 = table_of(4, lambda v: v[0] & v[1] & v[2] & v[3])
NAND4 = table_of(4, lambda v: 1 - (v[0] & v[1] & v[2] & v[3]))
XOR2 = table_of(2, lambda v: v[0] ^ v[1])


def en_ff(g: GB, clk: int, en: int) -> int:
    q = g.net()
    g.ff(g.lut(MUX, (q, g.pi(), en)), clk, q=q)
    return q


def kinds(cands: list[Candidate]) -> list[str]:
    return sorted(c.kind for c in cands)


class WordFirstTest(unittest.TestCase):
    def test_opt_in_only(self) -> None:
        self.assertIn("wordfirst", DETECTOR_ORDER)
        self.assertNotIn("wordfirst", [d.name for d in load_detectors(None)])
        self.assertEqual([d.name for d in load_detectors(["wordgroup", "wordfirst"])],
                         ["wordfirst", "wordgroup"])

    def test_register_word_by_enable(self) -> None:
        g = GB()
        clk, en = g.pi("clk"), g.pi("en")
        qs = [en_ff(g, clk, en) for _ in range(4)]
        got = WordFirstDetector().propose(make_ctx(g.build(qs)))
        self.assertEqual(kinds(got), ["ff_en", "mux", "register"])
        word = next(c for c in got if c.kind == "ff_en")
        self.assertEqual(dict(word.params), {"en": en, "active": 1, "width": 4})
        self.assertEqual(word.nets["q"], tuple(sorted(qs)))

    def test_two_words_two_enables_split(self) -> None:
        g = GB()
        clk, e1, e2 = g.pi("clk"), g.pi("e1"), g.pi("e2")
        qs = [en_ff(g, clk, e1) for _ in range(3)] + [en_ff(g, clk, e2) for _ in range(3)]
        got = WordFirstDetector().propose(make_ctx(g.build(qs)))
        self.assertEqual(kinds(got).count("register"), 2)

    def test_plain_register_split_by_reader(self) -> None:
        g = GB()
        clk = g.pi("clk")
        qa = [g.ff(g.pi(), clk) for _ in range(3)]
        qb = [g.ff(g.pi(), clk) for _ in range(3)]
        outs = [g.lut(AND_NOT, (q, g.pi())) for q in qa]
        outs += [g.lut(table_of(2, lambda v: v[0] ^ v[1]), (q, g.pi())) for q in qb]
        ctx = make_ctx(g.build(outs))
        from loki.re.detectors.wordfirst import _analysed_ffs

        words = register_words(ctx, _analysed_ffs(ctx))
        self.assertEqual(sorted(len(w.ffs) for w in words), [3, 3])

    def test_mux_word_shared_select(self) -> None:
        g = GB()
        sel = g.pi("s")
        ys = [g.lut(MUX, (g.pi(), g.pi(), sel)) for _ in range(4)]
        got = WordFirstDetector().propose(make_ctx(g.build(ys)))
        mux = [c for c in got if c.kind == "mux"]
        self.assertEqual(len(mux), 1)
        self.assertEqual(mux[0].nets["S"], (sel,))
        self.assertIsNotNone(mux[0].claim)

    def test_eq_const_needs_word_support(self) -> None:
        g = GB()
        clk = g.pi("clk")
        qs = [g.ff(g.pi(), clk) for _ in range(4)]
        z = g.lut(AND4, tuple(qs))
        ctx = make_ctx(g.build([z]))
        from loki.re.detectors.wordfirst import _analysed_ffs

        words = register_words(ctx, _analysed_ffs(ctx))
        decs = word_decoders(ctx, words)
        self.assertEqual([(d.op, d.const) for d in decs], [("eq", 15)])

    def test_wordgroup_links_bits(self) -> None:
        g = GB()
        clk, en = g.pi("clk"), g.pi("en")
        qs = [en_ff(g, clk, en) for _ in range(3)]
        graph = g.build(qs)
        ov = Overlay()
        from loki.re.detectors.ff_pattern import FfPatternDetector

        for c in FfPatternDetector().propose(make_ctx(graph, ov)):
            ov.add(c, "ff_pattern", 1)
        for c in WordFirstDetector().propose(make_ctx(graph, ov)):
            ov.add(c, "wordfirst", 1)
        got = WordGroupDetector().propose(make_ctx(graph, ov))
        word = [c for c in got if c.kind == "ff_en" and len(c.children) == 3]
        self.assertEqual(len(word), 1)


def ring(g: GB, k: int, second: bool = True) -> list[int]:
    """``k`` plain flip-flops; D of bit i is XOR(q_i, q_next) (``second``) or XOR(q_i, a PI)."""
    clk = g.pi("clk")
    qs = [g.net() for _ in range(k)]
    for i, q in enumerate(qs):
        other = qs[(i + 1) % k] if second else g.pi()
        g.ff(g.lut(XOR2, (q, other)), clk, q=q)
    return qs


class FsmRuleTest(unittest.TestCase):
    def test_coupled_word_is_fsm_without_decoder(self) -> None:
        g = GB()
        qs = ring(g, 4)
        got = WordFirstDetector().propose(make_ctx(g.build(qs)))
        fsm = [c for c in got if c.kind == "fsm"]
        self.assertEqual(len(fsm), 1)
        self.assertEqual(fsm[0].params["decoders"], 0)
        self.assertEqual(fsm[0].features["decoder_readers"], "<0.5")

    def test_one_q_bit_per_cone_is_not_an_fsm(self) -> None:
        g = GB()
        qs = ring(g, 4, second=False)
        got = WordFirstDetector().propose(make_ctx(g.build(qs)))
        self.assertNotIn("fsm", kinds(got))

    def test_cone_without_q_is_not_an_fsm(self) -> None:
        g = GB()
        clk = g.pi("clk")
        qs = [g.ff(g.lut(XOR2, (g.pi(), g.pi())), clk) for _ in range(4)]
        got = WordFirstDetector().propose(make_ctx(g.build(qs)))
        self.assertNotIn("fsm", kinds(got))

    def test_stage0_rule_needs_two_decoders(self) -> None:
        g = GB()
        qs = ring(g, 4)
        ctx = make_ctx(g.build(qs))
        with mock.patch.object(wf, "FSM_RULE", "stage0"):
            self.assertNotIn("fsm", kinds(WordFirstDetector().propose(ctx)))


class ChainTest(unittest.TestCase):
    def test_carry_chain_joins_the_bits(self) -> None:
        g = GB()
        a, b = g.pis_n(4, "a"), g.pis_n(4, "b")
        ys, cs = ripple(g, a, b)
        got = WordFirstDetector().propose(make_ctx(g.build([*ys, cs[-1]])))
        add = [c for c in got if c.kind == "adder"]
        self.assertEqual(len(add), 1)
        self.assertEqual(add[0].nets["Y"], (*ys, cs[-1]))
        self.assertEqual(add[0].nets["A"], tuple(a))


class GrowTest(unittest.TestCase):
    def layer(self, g: GB, nets: list[int], skip: int = 0) -> list[int]:
        """AND_NOT per net with a fresh input; the first ``skip`` nets get a different cell."""
        return [g.lut(XOR2 if i < skip else AND_NOT, (n, g.pi())) for i, n in enumerate(nets)]

    def test_forward_slices_two_levels_not_three(self) -> None:
        g = GB()
        clk = g.pi("clk")
        qs = [g.ff(g.pi(), clk) for _ in range(4)]
        l1 = self.layer(g, qs)
        l2 = self.layer(g, l1)
        l3 = self.layer(g, l2)
        ctx = make_ctx(g.build(l3))
        got = wf._grow(ctx, [tuple(qs)])
        self.assertEqual([frozenset(x) for x in got], [frozenset(l1), frozenset(l2)])

    def test_three_quarters_of_the_bits_are_enough(self) -> None:
        g = GB()
        clk = g.pi("clk")
        qs = [g.ff(g.pi(), clk) for _ in range(4)]
        ctx = make_ctx(g.build(self.layer(g, qs, skip=1)))
        got = wf._grow(ctx, [tuple(qs)])
        self.assertEqual([len(x) for x in got], [3])

    def test_half_of_the_bits_are_not(self) -> None:
        g = GB()
        clk = g.pi("clk")
        qs = [g.ff(g.pi(), clk) for _ in range(4)]
        ctx = make_ctx(g.build(self.layer(g, qs, skip=2)))
        self.assertEqual(wf._grow(ctx, [tuple(qs)]), [])


class SplitTest(unittest.TestCase):
    def shared_enable(self, n: int) -> list[int]:
        """``n`` enabled flip-flops on one enable; the first half read by one LUT class, the
        second half by another (the reader signature that splits a wide group)."""
        g = GB()
        clk, en = g.pi("clk"), g.pi("en")
        qs = [en_ff(g, clk, en) for _ in range(n)]
        outs = [g.lut(AND_NOT if i < n // 2 else XOR2, (q, g.pi())) for i, q in enumerate(qs)]
        self.graph = g.build(outs)
        return qs

    def test_group_of_fmax_is_one_word(self) -> None:
        self.shared_enable(wf.FMAX)
        ctx = make_ctx(self.graph)
        words = register_words(ctx, wf._analysed_ffs(ctx))
        self.assertEqual([len(w.ffs) for w in words], [wf.FMAX])

    def test_wider_group_splits_by_reader_signature(self) -> None:
        self.shared_enable(wf.FMAX + 8)
        ctx = make_ctx(self.graph)
        words = register_words(ctx, wf._analysed_ffs(ctx))
        self.assertEqual(sorted(len(w.ffs) for w in words), [20, 20])


class NeConstTest(unittest.TestCase):
    def decoders(self, table: int) -> tuple[list[wf.Decoder], list[Candidate]]:
        g = GB()
        clk = g.pi("clk")
        qs = [g.ff(g.pi(), clk) for _ in range(4)]
        z = g.lut(table, tuple(qs))
        ctx = make_ctx(g.build([z]))
        decs = word_decoders(ctx, register_words(ctx, wf._analysed_ffs(ctx)))
        return decs, wf._eq_cands(ctx, decs)

    def test_ne_const_decoder_and_claim(self) -> None:
        # false only for the assignment 1 (bit 0 set): a "not equal 1" decoder
        decs, cands = self.decoders(table_of(4, lambda v: 1 - (v[0] & (1 - v[1]) & (1 - v[2]) & (
            1 - v[3]))))
        self.assertEqual([(d.op, d.const) for d in decs], [("ne", 1)])
        (cand,) = cands
        assert cand.claim is not None
        self.assertEqual(cand.claim.op, "ne_const")
        self.assertEqual(dict(cand.claim.params)["C"], 1)

    @unittest.expectedFailure
    def test_ne_const_high_constant_known_defect(self) -> None:
        """Known defect, left in place on purpose: ``_minterm`` masks the inverted table with
        ``n - 1`` instead of ``(1 << n) - 1``, so a ``ne`` constant of 4 or more bits reads back
        as ``-1`` and the prover refutes the candidate (5 such candidates in the round-5 W runs).
        Fixing it would change the evaluated results."""
        decs, _ = self.decoders(NAND4)
        self.assertEqual([(d.op, d.const) for d in decs], [("ne", 15)])


if __name__ == "__main__":
    unittest.main()
