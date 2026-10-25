import unittest

from loki.re.detectors import DETECTOR_ORDER, Candidate, load_detectors
from loki.re.detectors.wordfirst import (
    WordFirstDetector,
    WordGroupDetector,
    register_words,
    word_decoders,
)
from loki.re.overlay import Overlay
from tests.re_fixtures import GB, MUX, make_ctx, table_of

AND_NOT = table_of(2, lambda v: v[0] & (1 - v[1]))
AND4 = table_of(4, lambda v: v[0] & v[1] & v[2] & v[3])


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


if __name__ == "__main__":
    unittest.main()
