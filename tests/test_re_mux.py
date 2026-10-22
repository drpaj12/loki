import unittest
from collections.abc import Sequence
from dataclasses import replace

from loki.re.detectors import Candidate
from loki.re.detectors.bus import BusDetector
from loki.re.detectors.mux import MuxDetector, mux_class
from loki.re.overlay import Overlay
from tests.re_fixtures import GB, MUX, make_ctx, table_of


def of_kind(cands: list[Candidate], kind: str) -> list[Candidate]:
    return [c for c in cands if c.kind == kind]


def mux4_fn(v: Sequence[int]) -> int:
    """Inputs ``(d0, d1, d2, d3, s0, s1)``."""
    return v[v[4] + 2 * v[5]]


def tree4(g: GB, s0: int, s1: int) -> tuple[int, list[int], int]:
    """Two 2:1 mux LUTs (select ``s0``) feeding a third (select ``s1``)."""
    d = g.pis_n(4, "d")
    lo = g.lut(MUX, (d[0], d[1], s0))
    hi = g.lut(MUX, (d[2], d[3], s0))
    return g.lut(MUX, (lo, hi, s1)), d, lo


def commit_all(ov: Overlay, cands: list[Candidate], rnd: int = 1) -> None:
    for c in cands:
        ov.add(c, "mux", rnd)


class MuxBitTest(unittest.TestCase):
    def test_mux_bit_from_lut3(self) -> None:
        g = GB()
        a, b, s = g.pi("a"), g.pi("b"), g.pi("s")
        y = g.lut(MUX, (a, b, s))
        got = of_kind(MuxDetector().propose(make_ctx(g.build((y,)))), "mux_bit")
        self.assertEqual(len(got), 1)
        c = got[0]
        self.assertEqual(c.nets, {"S": (s,), "D": (a, b), "Y": (y,)})
        assert c.claim is not None
        self.assertEqual(c.claim.op, "muxn")
        self.assertEqual(dict(c.claim.params)["N"], 2)

    def test_mux4_in_one_lut6(self) -> None:
        g = GB()
        d = g.pis_n(4, "d")
        s0, s1 = g.pi("s0"), g.pi("s1")
        y = g.lut(table_of(6, mux4_fn), (*d, s0, s1))
        got = of_kind(MuxDetector().propose(make_ctx(g.build((y,)))), "mux_bit")
        self.assertEqual(len(got), 1)
        c = got[0]
        self.assertEqual(c.nets["S"], (s0, s1))
        self.assertEqual(c.nets["D"], tuple(d))
        assert c.claim is not None
        self.assertEqual(dict(c.claim.params), {"N": 4, "S_WIDTH": 2})

    def test_mux_bit_npn_class(self) -> None:
        g = GB()
        a, b, s = g.pi(), g.pi(), g.pi()
        g.pos.append(g.lut(MUX, (a, b, s)))
        d = g.pis_n(4, "d")
        g.pos.append(g.lut(table_of(6, mux4_fn), (*d, g.pi(), g.pi())))
        merged = table_of(4, lambda v: (v[1] if v[2] else v[0]) & v[3])
        g.pos.append(g.lut(merged, (g.pi(), g.pi(), g.pi(), g.pi())))
        got = MuxDetector().propose(make_ctx(g.build()))
        self.assertEqual(
            sorted(c.features["npn_class"] for c in got), ["mux2", "mux4"]
        )
        self.assertEqual(mux_class(merged, 4), "other")
        # features off: no class feature
        off = MuxDetector().propose(make_ctx(g.build(), features=False))
        self.assertTrue(all("npn_class" not in c.features for c in off))


class TreeTest(unittest.TestCase):
    def test_tree_composition(self) -> None:
        g = GB()
        s0, s1 = g.pi("s0"), g.pi("s1")
        y, d, _ = tree4(g, s0, s1)
        graph = g.build((y,))
        ov = Overlay()
        commit_all(ov, of_kind(MuxDetector().propose(make_ctx(graph)), "mux_bit"))
        got = of_kind(MuxDetector().propose(make_ctx(graph, ov)), "mux_tree")
        self.assertEqual(len(got), 1)
        c = got[0]
        self.assertEqual((c.params["N"], c.params["S_WIDTH"]), (4, 2))
        self.assertEqual(c.nets["S"], (s0, s1))
        self.assertEqual(c.nets["D"], tuple(d))
        self.assertEqual(len(c.cells), 3)
        self.assertEqual(len(c.children), 3)
        assert c.claim is not None
        self.assertEqual(c.claim.op, "muxn")

    def test_tree_not_composed_when_shared(self) -> None:
        g = GB()
        s0, s1 = g.pi("s0"), g.pi("s1")
        y, _, lo = tree4(g, s0, s1)
        extra = g.lut(table_of(2, lambda v: v[0] & v[1]), (lo, g.pi("x")))
        got = MuxDetector().propose(make_ctx(g.build((y, extra))))
        self.assertEqual(of_kind(got, "mux_tree"), [])
        self.assertEqual(len(of_kind(got, "mux_bit")), 3)

    def test_tree_not_composed_with_different_selects(self) -> None:
        g = GB()
        d = g.pis_n(4, "d")
        lo = g.lut(MUX, (d[0], d[1], g.pi("sa")))
        hi = g.lut(MUX, (d[2], d[3], g.pi("sb")))
        y = g.lut(MUX, (lo, hi, g.pi("s1")))
        got = MuxDetector().propose(make_ctx(g.build((y,))))
        self.assertEqual(of_kind(got, "mux_tree"), [])


def mux_bank(g: GB, k: int, s: int) -> list[int]:
    outs = []
    for i in range(k):
        outs.append(g.lut(MUX, (g.pi(f"a{i}"), g.pi(f"b{i}"), s)))
    return outs


class WordTest(unittest.TestCase):
    def test_word_mux_from_bus(self) -> None:
        g = GB()
        s = g.pi("s")
        outs = mux_bank(g, 4, s)
        graph = g.build(tuple(outs))
        ov = Overlay()
        commit_all(ov, of_kind(MuxDetector().propose(make_ctx(graph)), "mux_bit"))
        buses = BusDetector().propose(make_ctx(graph))
        self.assertEqual(len(buses), 1)
        bus = ov.add(buses[0], "bus", 1)
        got = of_kind(MuxDetector().propose(make_ctx(graph, ov)), "mux")
        self.assertEqual(len(got), 1)
        c = got[0]
        self.assertEqual(c.params["WIDTH"], 4)
        self.assertEqual(c.nets["S"], (s,))
        self.assertEqual(c.nets["Y"], tuple(outs))
        assert c.claim is not None
        self.assertEqual(c.claim.op, "mux2")
        self.assertEqual(dict(c.claim.inputs)["S"], (s,))
        self.assertEqual(dict(c.claim.inputs)["A"], c.nets["A"])
        self.assertEqual(len(c.children), 4)
        self.assertEqual(c.features["sel_shared"], "yes")
        self.assertEqual(c.features["width"], "3-4")
        self.assertEqual(c.features["wl_depth"], bus.features["wl_depth"])

    def test_word_muxn_from_bus_of_trees(self) -> None:
        g = GB()
        s0, s1 = g.pi("s0"), g.pi("s1")
        outs = [tree4(g, s0, s1)[0] for _ in range(2)]
        graph = g.build(tuple(outs))
        ov = Overlay()
        det = MuxDetector()
        commit_all(ov, det.propose(make_ctx(graph)))
        bus = Candidate(
            "bus", frozenset(graph.cells), {"slice0": (outs[0],), "slice1": (outs[1],)},
            {"k": 2, "order_source": "net_id"}, {"wl_depth": "4"},
        )
        ov.add(bus, "bus", 1)
        got = of_kind(det.propose(make_ctx(graph, ov)), "mux")
        self.assertEqual(len(got), 1)
        c = got[0]
        assert c.claim is not None
        self.assertEqual(c.claim.op, "muxn")
        self.assertEqual(c.params["N"], 4)
        self.assertEqual(c.nets["S"], (s0, s1))
        self.assertEqual(len(c.children), 2)

    def test_word_mux_copies_wl_depth(self) -> None:
        g = GB()
        s = g.pi("s")
        outs = mux_bank(g, 3, s)
        graph = g.build(tuple(outs))
        ov = Overlay()
        commit_all(ov, of_kind(MuxDetector().propose(make_ctx(graph)), "mux_bit"))
        bus = Candidate(
            "bus", frozenset(graph.cells), {f"slice{i}": (o,) for i, o in enumerate(outs)},
            {"k": 3, "order_source": "net_id"}, {"wl_depth": "2-3"},
        )
        ov.add(bus, "bus", 1)
        got = of_kind(MuxDetector().propose(make_ctx(graph, ov)), "mux")
        self.assertEqual([c.features["wl_depth"] for c in got], ["2-3"])

    def test_no_word_without_shared_select(self) -> None:
        g = GB()
        outs = [g.lut(MUX, (g.pi(), g.pi(), g.pi())) for _ in range(3)]
        graph = g.build(tuple(outs))
        ov = Overlay()
        commit_all(ov, of_kind(MuxDetector().propose(make_ctx(graph)), "mux_bit"))
        bus = Candidate(
            "bus", frozenset(graph.cells), {f"slice{i}": (o,) for i, o in enumerate(outs)},
            {"k": 3, "order_source": "net_id"}, {"wl_depth": "0"},
        )
        ov.add(bus, "bus", 1)
        self.assertEqual(of_kind(MuxDetector().propose(make_ctx(graph, ov)), "mux"), [])

    def test_lone_mux_bit_word_from_round_2(self) -> None:
        """L1 spec 15 pin 3: a lone 2:1 mux LUT (no bus) becomes a WIDTH 1 word in round 2."""
        g = GB()
        a, b, s = g.pi("a"), g.pi("b"), g.pi("s")
        y = g.lut(MUX, (a, b, s))
        graph = g.build((y,))
        ov = Overlay()
        det = MuxDetector()
        commit_all(ov, of_kind(det.propose(make_ctx(graph)), "mux_bit"))
        self.assertEqual(of_kind(det.propose(make_ctx(graph, ov)), "mux"), [])
        got = of_kind(det.propose(replace(make_ctx(graph, ov), round=2)), "mux")
        self.assertEqual(len(got), 1)
        c = got[0]
        self.assertEqual(c.params["WIDTH"], 1)
        self.assertEqual(
            (c.nets["A"], c.nets["B"], c.nets["S"], c.nets["Y"]), ((a,), (b,), (s,), (y,)))
        assert c.claim is not None
        self.assertEqual(c.claim.op, "mux2")
        self.assertEqual(len(c.children), 1)

    def test_bus_slice_gets_no_lone_word(self) -> None:
        g = GB()
        s = g.pi("s")
        outs = mux_bank(g, 3, s)
        graph = g.build(tuple(outs))
        ov = Overlay()
        det = MuxDetector()
        commit_all(ov, of_kind(det.propose(make_ctx(graph)), "mux_bit"))
        for c in BusDetector().propose(make_ctx(graph)):
            ov.add(c, "bus", 1)
        got = of_kind(det.propose(replace(make_ctx(graph, ov), round=2)), "mux")
        self.assertEqual([c.params["WIDTH"] for c in got], [3])


if __name__ == "__main__":
    unittest.main()
