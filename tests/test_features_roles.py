import unittest

from loki.features.graph import make_feature_graph
from loki.features.roles import (
    CLASS_NAMES,
    SignalConfig,
    classify_nets,
    is_forcing,
    is_hold,
    restrict,
)
from tests.features_fixtures import AND2, XOR2, Builder, sync_fg, table_of


def idx(fg_ids: tuple[str, ...], nid: str) -> int:
    return fg_ids.index(nid)


class RolesTest(unittest.TestCase):
    def test_restrict_and_forcing(self) -> None:
        self.assertEqual(restrict(8, 2, 0, 0), 0)
        self.assertEqual(restrict(8, 2, 0, 1), 0b10)
        self.assertTrue(is_forcing(8, 2, 0) and is_forcing(8, 2, 1))
        self.assertFalse(is_forcing(XOR2, 2, 0))
        self.assertFalse(is_forcing(0b10, 1, 0))
        t3 = table_of(3, lambda v: v[0] & v[2])
        self.assertEqual(restrict(t3, 3, 1, 1), AND2)

    def test_is_hold_mux(self) -> None:
        mux = table_of(3, lambda v: v[0] if v[1] else v[2])
        self.assertTrue(is_hold(mux, 3, 1, 2))
        self.assertFalse(is_forcing(mux, 3, 1))
        self.assertFalse(is_hold(mux, 3, 0, 2))
        self.assertFalse(is_hold(mux, 3, 1, 1))

    def test_clock_domains(self) -> None:
        fg = sync_fg(4, clocks=2)
        roles = classify_nets(fg)
        self.assertEqual(roles.clock_domains, 2)
        self.assertEqual([roles.nodes[idx(fg.node_ids, f"ff{i}")].clock_domain for i in range(4)],
                         [1, 2, 1, 2])
        self.assertEqual(roles.nodes[idx(fg.node_ids, "dl0")].clock_domain, 0)
        self.assertEqual(roles.classified["clock"], 2)

    def test_reset_and_enable_found(self) -> None:
        fg = sync_fg(20, reset=True)
        roles = classify_nets(fg)
        self.assertEqual(roles.classified["reset"], 1)
        self.assertEqual(roles.classified["enable"], 0)
        for i in range(20):
            self.assertEqual(roles.nodes[idx(fg.node_ids, f"dl{i}")].has_reset, 1)
            self.assertEqual(roles.nodes[idx(fg.node_ids, f"ff{i}")].has_reset, 1)
            self.assertEqual(roles.nodes[idx(fg.node_ids, f"ff{i}")].enable, 0)
        self.assertEqual(roles.nodes[idx(fg.node_ids, "d0")].has_reset, 0)
        fg = sync_fg(20, enable=True)
        roles = classify_nets(fg)
        self.assertEqual((roles.classified["enable"], roles.classified["reset"]), (1, 0))
        self.assertEqual(roles.nodes[idx(fg.node_ids, "ff3")].enable, 1)
        self.assertEqual(roles.nodes[idx(fg.node_ids, "ff3")].has_reset, 0)

    def test_enable_with_reset_in_one_lut_is_not_found(self) -> None:
        roles = classify_nets(sync_fg(20, reset=True, enable=True))
        self.assertEqual((roles.classified["reset"], roles.classified["enable"]), (1, 0))

    def test_below_min_fanout_is_signal(self) -> None:
        roles = classify_nets(sync_fg(5, reset=True, enable=False))
        self.assertEqual(roles.classified["reset"], 0)
        small = classify_nets(sync_fg(5, reset=True), SignalConfig(min_fanout=4))
        self.assertEqual(small.classified["reset"], 1)

    def test_data_net_not_reset(self) -> None:
        b = Builder()
        x = b.node("x", "pi")
        clk = b.node("clk", "pi")
        for i in range(20):
            d = b.node(f"d{i}", "pi")
            lut = b.lut(f"l{i}", XOR2, [d, x])
            ff = b.node(f"ff{i}", "ff")
            b.edge(lut, ff, "D")
            b.edge(clk, ff, "CLK")
        roles = classify_nets(b.build())
        self.assertEqual((roles.classified["reset"], roles.classified["enable"]), (0, 0))
        self.assertEqual(roles.classified["signal"], 41)

    def test_dominance(self) -> None:
        # 16 of 20 sinks force: exactly 0.8 passes, one fewer fails
        for forcing, expect in ((16, 1), (15, 0)):
            b = Builder()
            x = b.node("x", "pi")
            clk = b.node("clk", "pi")
            for i in range(20):
                d = b.node(f"d{i}", "pi")
                lut = b.lut(f"l{i}", AND2 if i < forcing else XOR2, [d, x])
                ff = b.node(f"ff{i}", "ff")
                b.edge(lut, ff, "D")
                b.edge(clk, ff, "CLK")
            self.assertEqual(classify_nets(b.build()).classified["reset"], expect)

    def test_latch_en_not_clock(self) -> None:
        b = Builder()
        en = b.node("en", "pi")
        d = b.node("d", "pi")
        latch = b.node("lat", "latch")
        b.edge(en, latch, "EN")
        b.edge(d, latch, "D")
        roles = classify_nets(b.build())
        self.assertEqual(roles.classified["clock"], 0)
        self.assertEqual(roles.nodes[latch].clock_domain, 0)

    def test_hard_pins(self) -> None:
        b = Builder()
        clk = b.node("clk", "pi")
        rst = b.node("rst", "pi")
        hard = [b.node(f"h{i}", "hard") for i in range(20)]
        for h in hard:
            b.edge(clk, h, "CLK")
            b.edge(rst, h, "reset")
        roles = classify_nets(b.build())
        self.assertEqual((roles.classified["clock"], roles.classified["reset"]), (1, 1))
        self.assertEqual(roles.nodes[hard[0]].has_reset, 1)

    def test_const_nets_any_fanout(self) -> None:
        b = Builder()
        one = b.node("one", "const", 0, 1)
        a = b.node("a", "pi")
        g = b.lut("g", AND2, [a, one])
        roles = classify_nets(b.build())
        self.assertEqual(roles.classified["const"], 1)
        self.assertEqual(roles.nodes[g].const_inputs, 1)
        self.assertEqual(roles.edge_class[1], "const")

    def test_shape(self) -> None:
        fg = make_feature_graph([], [])
        roles = classify_nets(fg)
        self.assertEqual(tuple(roles.classified), CLASS_NAMES)
        self.assertEqual((roles.nodes, roles.edge_class, roles.clock_domains), ((), (), 0))


if __name__ == "__main__":
    unittest.main()
