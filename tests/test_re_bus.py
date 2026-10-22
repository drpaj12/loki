import unittest

from loki.re.detectors import Candidate
from loki.re.detectors.bus import BusDetector
from loki.re.overlay import Overlay
from tests.re_fixtures import GB, MUX, make_ctx, table_of


def mux_bank(count: int, order: list[int] | None = None) -> tuple[GB, int, list[int]]:
    """``count`` mux LUTs sharing select ``s``; LUTs are created in ``order`` (default reversed)."""
    g = GB()
    s = g.pi("s")
    data = [(g.pi(f"a{i}"), g.pi(f"b{i}")) for i in range(count)]
    outs = [0] * count
    for i in order if order is not None else list(reversed(range(count))):
        outs[i] = g.lut(MUX, (data[i][0], data[i][1], s))
    g.pos.extend(outs)
    return g, s, outs


class BusTest(unittest.TestCase):
    def test_bus_k_slices_shared_select(self) -> None:
        g, s, outs = mux_bank(4)
        graph = g.build()
        got = BusDetector().propose(make_ctx(graph))
        self.assertEqual(len(got), 1)
        c = got[0]
        self.assertEqual(c.kind, "bus")
        self.assertEqual(c.features["k"], "3-4")
        self.assertEqual(c.features["ctrl_fanout_exact"], "yes")
        self.assertEqual(c.params["order_source"], "net_id")
        self.assertEqual([c.nets[f"slice{i}"] for i in range(4)], [(o,) for o in outs])
        self.assertEqual(c.nets["ctrl"], (s,))

    def test_bus_rejects_overlapping_data(self) -> None:
        g = GB()
        s, d = g.pi("s"), g.pi("d")
        for i in range(4):
            g.lut(MUX, (d if i < 2 else g.pi(f"a{i}"), g.pi(f"b{i}"), s))
        got = BusDetector().propose(make_ctx(g.build()))
        # the controls of the four muxes are {s} only and their data overlap: no 4-slice bus; the
        # two muxes that also share d form a bus of their own with controls {s, d}
        self.assertEqual([(c.params["k"], c.nets["ctrl"]) for c in got], [(2, (s, d))])

    def test_bus_ctrl_fanout_not_exact(self) -> None:
        g, s, outs = mux_bank(3)
        extra = g.lut(table_of(2, lambda v: v[0] & v[1]), (s, g.pi("x")))
        g.pos.append(extra)
        got = BusDetector().propose(make_ctx(g.build()))
        self.assertEqual([c.features["ctrl_fanout_exact"] for c in got], ["no"])

    def _permuted(self) -> GB:
        g = GB()
        s = g.pi("s")
        swapped = table_of(3, lambda v: v[2] if v[0] else v[1])  # (s, a, b)
        for i in range(4):
            a, b = g.pi(f"a{i}"), g.pi(f"b{i}")
            g.pos.append(g.lut(MUX, (a, b, s)) if i % 2 == 0 else g.lut(swapped, (s, a, b)))
        return g

    def test_bus_groups_by_colour_class(self) -> None:
        g = self._permuted()
        got = BusDetector().propose(make_ctx(g.build()))
        self.assertEqual(len(got), 1)
        self.assertEqual(got[0].features["k"], "3-4")
        self.assertIn(got[0].features["wl_depth"], ("0", "1", "2-3", "4"))

    def test_bus_without_features_uses_npn_sig(self) -> None:
        g = self._permuted()
        got = BusDetector().propose(make_ctx(g.build(), features=False))
        self.assertEqual(len(got), 1)
        self.assertEqual(got[0].features["wl_depth"], "n/a")

    def test_bus_wl_depth_bins(self) -> None:
        # slice 0 reads a through `n` buffers, slice 1 through `n + 1`: the colours agree up
        # to round n (depth n); equal chains agree at every round (4)
        for n, other, want in ((0, 1, "0"), (1, 2, "1"), (2, 3, "2-3"), (3, 4, "2-3"),
                               (2, 2, "4")):
            g = GB()
            s = g.pi("s")
            for length in (n, other):
                a = g.pi()
                for _ in range(length):
                    a = g.lut(0b10, (a,))
                g.pos.append(g.lut(MUX, (a, g.pi(), s)))
            got = BusDetector().propose(make_ctx(g.build()))
            self.assertEqual(len(got), 1, (n, other))
            self.assertEqual(got[0].features["wl_depth"], want, (n, other))

    def test_bus_data_from_bus(self) -> None:
        g, s, outs = mux_bank(2)
        t = g.pi("t")
        for o in outs:
            g.pos.append(g.lut(MUX, (o, g.pi(), t)))
        graph = g.build()
        first = BusDetector().propose(make_ctx(graph))
        self.assertEqual([c.features["data_from_bus"] for c in first], ["none", "none"])
        ov = Overlay()
        for c in first:
            ov.add(c, "bus", 1)
        again = BusDetector().propose(make_ctx(graph, overlay=ov))
        by_ctrl = {c.nets["ctrl"]: c.features["data_from_bus"] for c in again}
        self.assertEqual(by_ctrl[(t,)], "some")
        self.assertEqual(by_ctrl[(s,)], "none")

    def test_bus_chain_order(self) -> None:
        g, s, outs = mux_bank(2)
        ov = Overlay()
        ov.add(Candidate("adder", frozenset({1}), {"Y": (outs[1], outs[0])}, {}, {}), "arith", 1)
        got = BusDetector().propose(make_ctx(g.build(), overlay=ov))
        self.assertEqual(got[0].params["order_source"], "chain")
        self.assertEqual([got[0].nets["slice0"], got[0].nets["slice1"]],
                         [(outs[1],), (outs[0],)])


if __name__ == "__main__":
    unittest.main()
