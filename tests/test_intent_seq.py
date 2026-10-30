import unittest

from loki.intent.modes import mode_table
from loki.intent.seq import name_order, sequential_claims
from tests.re_fixtures import GB, table_of
from tests.seq_fixtures import down_counter, lfsr, modulo_counter, shift_register, up_counter
from tests.test_re_fsm import three_state


class CounterTest(unittest.TestCase):
    def test_binary_counter_with_reset(self) -> None:
        g = GB()
        clk, rst = g.pi("clk"), g.pi("rst")
        up_counter(g, clk, 4, rst=rst)
        (claim,) = sequential_claims(g.build())
        self.assertEqual(claim.kind, "counter")
        self.assertEqual(claim.params["width"], 4)
        self.assertEqual(claim.params["dir"], "up")
        self.assertEqual(claim.params["modulus"], 0)
        self.assertEqual(claim.nets["rst"], (rst,))
        self.assertEqual(claim.params["rst_value"], 0)
        self.assertTrue(claim.exact)

    def test_decade_counter_low_bit_is_a_feeder(self) -> None:
        g = GB()
        q = modulo_counter(g, g.pi("clk"), 4, 9, 0)
        (claim,) = sequential_claims(g.build())
        self.assertEqual(claim.kind, "counter")
        self.assertEqual((claim.params["width"], claim.params["modulus"], claim.params["wrap"]),
                         (4, 10, 0))
        self.assertEqual(claim.q, tuple(q))

    def test_down_counter_and_wrap_value(self) -> None:
        g = GB()
        down_counter(g, g.pi("clk"), 3)
        (claim,) = sequential_claims(g.build())
        self.assertEqual((claim.kind, claim.params["dir"]), ("counter", "down"))
        g = GB()
        modulo_counter(g, g.pi("clk"), 4, 10, 1)
        (claim,) = sequential_claims(g.build())
        self.assertEqual((claim.params["modulus"], claim.params["wrap"]), (11, 1))

    def test_shift_register_and_lfsr(self) -> None:
        g = GB()
        x = g.pi("x")
        shift_register(g, g.pi("clk"), 4, x)
        (claim,) = sequential_claims(g.build())
        self.assertEqual(claim.kind, "shift_reg")
        self.assertEqual(claim.nets["x"], (x,))
        g = GB()
        lfsr(g, g.pi("clk"), 5, (4, 2))
        (claim,) = sequential_claims(g.build())
        self.assertEqual(claim.kind, "lfsr")


class FragmentTest(unittest.TestCase):
    def test_group_steered_by_an_unclaimed_flip_flop_is_not_claimed(self) -> None:
        g = GB()
        clk = g.pi("clk")
        stray = g.ff(g.pi("d"), clk)
        up_counter(g, clk, 3, en=stray)
        self.assertEqual(sequential_claims(g.build()), [])

    def test_group_steered_by_a_claimed_group_is_claimed_after_it(self) -> None:
        g = GB()
        clk, rst = g.pi("clk"), g.pi("rst")
        low = up_counter(g, clk, 2, rst=rst)
        up_counter(g, clk, 2, en=low[1])
        claims = sequential_claims(g.build())
        self.assertEqual(sorted(c.kind for c in claims), ["counter", "counter"])


class ModesTest(unittest.TestCase):
    def test_shift_with_load_and_enable(self) -> None:
        g = GB()
        clk, load, ena = g.pi("clk"), g.pi("load"), g.pi("ena")
        data = g.pis_n(3, "d")
        qs = [g.net(f"q{i}") for i in range(3)]
        for i in range(3):
            left = qs[i + 1] if i + 1 < 3 else g.const(0)
            d = g.lut(table_of(5, lambda v: v[2] if v[0] else (v[3] if v[1] else v[4])),
                      (load, ena, data[i], left, qs[i]))
            g.ff(d, clk, qs[i])
        mt = mode_table(g.build(), tuple(qs))
        assert mt is not None
        self.assertEqual(mt.kind, "shift_reg")
        by = {m.label: m for m in mt.modes}
        self.assertEqual(by["load-const"].data, tuple(data))
        self.assertEqual(set(by), {"hold", "load-const", "shift-r"})

    def test_unrecognised_group_has_no_mode_table(self) -> None:
        g = GB()
        q0, q1, _rst, _go = three_state(g)
        self.assertIsNone(mode_table(g.build(), (q0, q1)))


class OrderTest(unittest.TestCase):
    def test_indexed_names_give_lsb_first(self) -> None:
        g = GB()
        clk = g.pi("clk")
        a, b = g.net("q[1]"), g.net("q[0]")
        g.ff(b, clk, a)
        g.ff(a, clk, b)
        graph = g.build()
        order = name_order(graph, frozenset(graph.cells))
        self.assertEqual([graph.names[graph.cells[c].outs[0]] for c in order], ["q[0]", "q[1]"])

    def test_other_names_give_cell_order(self) -> None:
        g = GB()
        clk = g.pi("clk")
        a, b = g.net("a"), g.net("b")
        g.ff(b, clk, a)
        g.ff(a, clk, b)
        graph = g.build()
        self.assertEqual(name_order(graph, frozenset(graph.cells)), tuple(sorted(graph.cells)))


class FsmClaimTest(unittest.TestCase):
    def test_three_state_machine_is_an_fsm_claim(self) -> None:
        g = GB()
        three_state(g)
        (claim,) = sequential_claims(g.build())
        self.assertEqual(claim.kind, "fsm")
        assert claim.fsm is not None
        self.assertEqual(claim.params["states"], 3)
        self.assertEqual(len(claim.fsm.transitions), 6)

    def test_enabled_register_bit_is_not_an_fsm(self) -> None:
        g = GB()
        clk, en, d = g.pi("clk"), g.pi("en"), g.pi("d")
        q = g.net("q")
        g.ff(g.lut(table_of(3, lambda v: v[1] if v[0] else v[2]), (en, d, q)), clk, q)
        self.assertEqual(sequential_claims(g.build()), [])


if __name__ == "__main__":
    unittest.main()
