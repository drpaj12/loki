import unittest

from loki.re.detectors import Candidate, sorted_candidates
from loki.re.detectors.ff_pattern import FfPatternDetector
from loki.re.overlay import Overlay
from tests.re_fixtures import GB, MUX, make_ctx, table_of

AND_NOT = table_of(2, lambda v: v[0] & (1 - v[1]))  # (d, r): d & ~r


def kinds(cands: list[Candidate]) -> list[str]:
    return sorted(c.kind for c in cands)


def en_ff(g: GB, clk: int, en: int, d: int | None = None) -> int:
    """A flip-flop that holds unless ``en``; returns Q."""
    q = g.net()
    g.ff(g.lut(MUX, (q, g.pi() if d is None else d, en)), clk, q=q)
    return q


class FfPatternTest(unittest.TestCase):
    def test_ff_enable_detected(self) -> None:
        g = GB()
        clk, en = g.pi("clk"), g.pi("en")
        q = en_ff(g, clk, en)
        got = FfPatternDetector().propose(make_ctx(g.build([q])))
        self.assertEqual(kinds(got), ["ff_en"])
        self.assertEqual(dict(got[0].params), {"en": en, "active": 1})
        self.assertEqual(got[0].features["en_fn_exact"], "yes")

    def test_ff_srst_detected(self) -> None:
        # d & ~r is symmetric: each of d (active 0) and r (active 1) is a reset reading; the
        # fan-out bin tells them apart (spec 7.3, rst_fanout)
        for count, want in ((1, "1"), (3, "2-3")):
            g = GB()
            clk, r = g.pi("clk"), g.pi("r")
            for _ in range(count):
                g.ff(g.lut(AND_NOT, (g.pi(), r)), clk)
            every = FfPatternDetector().propose(make_ctx(g.build()))
            got = [c for c in every if c.kind == "ff_srst"]
            self.assertEqual(len(got), 2 * count)
            self.assertEqual(len(every) - len(got), 1 if count > 1 else 0)  # the register
            mine = [c for c in got if c.params["rst"] == r]
            self.assertEqual(len(mine), count)
            self.assertEqual(dict(mine[0].params), {"rst": r, "active": 1, "value": 0})
            self.assertEqual({c.features["rst_fanout"] for c in mine}, {want})
            others = [c for c in got if c.params["rst"] != r]
            self.assertEqual({c.features["rst_fanout"] for c in others}, {"1"})

    def test_ff_reset_over_enable(self) -> None:
        g = GB()
        clk, en, r = g.pi("clk"), g.pi("en"), g.pi("r")
        q = g.net()
        inner = g.lut(MUX, (q, g.pi(), en))
        g.ff(g.lut(AND_NOT, (inner, r)), clk, q=q)
        got = FfPatternDetector().propose(make_ctx(g.build([q])))
        self.assertEqual(kinds(got), ["ff_en", "ff_srst"])

    def _bank(self, shared_en: bool) -> tuple[GB, list[int]]:
        g = GB()
        clk, en = g.pi("clk"), g.pi("en")
        qs = [en_ff(g, clk, en if shared_en else g.pi()) for _ in range(4)]
        return g, qs

    def test_register_group(self) -> None:
        g, qs = self._bank(True)
        graph = g.build(qs)
        ov = Overlay()
        first = FfPatternDetector().propose(make_ctx(graph, ov))
        self.assertEqual(kinds(first), ["ff_en"] * 4 + ["register"])
        for c in first:
            ov.add(c, "ff_pattern", 1)
        second = FfPatternDetector().propose(make_ctx(graph, ov))
        reg = [c for c in second if c.kind == "register"][0]
        self.assertEqual(len(reg.children), 4)
        self.assertEqual(reg.features["shared_ctrl"], "en")
        self.assertEqual(reg.features["width"], "3-4")
        self.assertEqual(reg.nets["q"], tuple(sorted(qs)))
        for c in second:
            ov.add(c, "ff_pattern", 2)
        self.assertEqual(len(ov.by_kind("ff_en")), 4)
        (hyp,) = ov.by_kind("register")
        self.assertEqual({h.kind for h in ov.children_of(hyp.id)}, {"ff_en"})

    def test_register_from_bus(self) -> None:
        """Spec 7.3: FFs with one clock whose D cones all read one bus form a register, slices
        ordered as the bus (feature d_from_piece, order_source bus)."""
        g = GB()
        clk = g.pi("clk")
        ds = [g.pi(f"d{i}") for i in range(4)]
        qs = [g.ff(d, clk) for d in ds]
        graph = g.build(qs)
        ov = Overlay()
        # bus bit 0 is the highest D net: the Q order is the reverse of the net id order
        nets = {f"slice{i}": (ds[3 - i],) for i in range(4)}
        ov.add(Candidate("bus", frozenset({900}), nets, {}, {}), "bus", 1)
        got = FfPatternDetector().propose(make_ctx(graph, ov))
        self.assertEqual(kinds(got), ["register"])
        self.assertEqual(got[0].nets["q"], (qs[3], qs[2], qs[1], qs[0]))
        self.assertEqual(got[0].features["d_from_piece"], "yes")
        self.assertEqual(got[0].params["order_source"], "bus")

    def test_no_register_without_shared_control(self) -> None:
        g = GB()
        clk = g.pi("clk")
        for _ in range(4):
            g.ff(g.pi(), clk)
        self.assertEqual(FfPatternDetector().propose(make_ctx(g.build())), [])
        g2, qs = self._bank(False)
        got = FfPatternDetector().propose(make_ctx(g2.build(qs)))
        self.assertEqual(kinds(got), ["ff_en"] * 4)

    def test_candidates_sorted(self) -> None:
        g, qs = self._bank(True)
        got = FfPatternDetector().propose(make_ctx(g.build(qs)))
        self.assertEqual(got, sorted_candidates(got))


if __name__ == "__main__":
    unittest.main()
