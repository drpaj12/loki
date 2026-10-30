import unittest
from collections.abc import Callable, Sequence

from loki.intent import boolmin
from loki.intent.fsm import encoding_of, read_fsm
from loki.intent.groups import sequential_groups
from loki.intent.lower import lower_async_ff
from loki.re.fngraph import Cell
from tests.re_fixtures import GB, table_of
from tests.seq_fixtures import modulo_counter, up_counter
from tests.test_re_fsm import three_state


class BoolMinTest(unittest.TestCase):
    def test_xor_needs_two_products(self) -> None:
        prods = boolmin.products([1, 2], [10, 20])
        self.assertEqual(len(prods), 2)
        self.assertEqual(boolmin.render(prods, {10: "a", 20: "b"}), "a & ~b | ~a & b")

    def test_adjacent_minterms_merge(self) -> None:
        self.assertEqual(boolmin.products([1, 3], [10, 20]), (((10, 1),),))

    def test_constants(self) -> None:
        self.assertEqual(boolmin.products([], [10]), ())
        self.assertEqual(boolmin.render(boolmin.products([0, 1], [10]), {10: "a"}), "always")
        self.assertEqual(boolmin.render((), {}), "never")

    def test_too_many_variables_refused(self) -> None:
        with self.assertRaises(ValueError):
            boolmin.minimise([0], boolmin.MAX_VARS + 1)


class ReadFsmTest(unittest.TestCase):
    def test_three_state_machine(self) -> None:
        g = GB()
        q0, q1, rst, go = three_state(g)
        fsm = read_fsm(g.build(), (q0, q1))
        assert fsm is not None
        self.assertEqual(fsm.states, (0, 1, 2))
        self.assertEqual(fsm.encoding, "binary")
        self.assertEqual(fsm.reset, (rst, 1, 0))
        self.assertEqual(fsm.start, 0)
        self.assertEqual(fsm.controls, (go,))
        moves = {(t.src, t.dst): t.cond for t in fsm.transitions}
        self.assertEqual(moves[(0, 1)], (((go, 1),),))
        self.assertEqual(moves[(0, 0)], (((go, 0),),))
        self.assertEqual(moves[(2, 2)], (((go, 0),),))
        self.assertEqual(moves[(2, 0)], (((go, 1),),))

    def test_no_reset_starts_at_zero(self) -> None:
        g = GB()
        clk, go = g.pi("clk"), g.pi("go")
        q = g.net("s")
        d = g.lut(table_of(2, lambda v: v[0] ^ v[1]), (q, go))
        g.ff(d, clk, q)
        fsm = read_fsm(g.build(), (q,))
        assert fsm is not None
        self.assertIsNone(fsm.reset)
        self.assertEqual(fsm.states, (0, 1))

    def test_too_many_controls_not_claimed(self) -> None:
        g = GB()
        clk = g.pi("clk")
        ins = g.pis_n(15, "i")
        q = g.net("s")
        d = g.lut(table_of(6, lambda v: sum(v) & 1), (q, *ins[:5]))
        d = g.lut(table_of(6, lambda v: sum(v) & 1), (d, *ins[5:10]))
        d = g.lut(table_of(6, lambda v: sum(v) & 1), (d, *ins[10:15]))
        g.ff(d, clk, q)
        self.assertIsNone(read_fsm(g.build(), (q,)))

    def test_encoding(self) -> None:
        self.assertEqual(encoding_of((1, 2, 4), 3), "one-hot")
        self.assertEqual(encoding_of((0, 1, 2, 3), 2), "binary")
        self.assertEqual(encoding_of((1, 2, 6), 3), "coded")


def _load_count(i: int) -> Callable[[Sequence[int]], int]:
    """Bit ``i`` of an up counter with a load port; inputs (load, data, q0..qi)."""

    def fn(v: Sequence[int]) -> int:
        return v[1] if v[0] else v[2 + i] ^ int(all(v[2 : 2 + i]))

    return fn


class MemoryPatternTest(unittest.TestCase):
    def test_word_bit_with_address_decode_is_hold_load(self) -> None:
        g = GB()
        clk, we, wa, wd = g.pi("clk"), g.pi("we"), g.pi("wa"), g.pi("wd")
        q = g.net("q")
        d = g.lut(table_of(4, lambda v: v[2] if v[0] and v[1] else v[3]), (we, wa, wd, q))
        g.ff(d, clk, q)
        fsm = read_fsm(g.build(), (q,))
        assert fsm is not None
        self.assertEqual(fsm.memory, "hold-load")

    def test_toggle_is_not_hold_load(self) -> None:
        g = GB()
        clk, go = g.pi("clk"), g.pi("go")
        q = g.net("s")
        g.ff(g.lut(table_of(2, lambda v: v[0] ^ v[1]), (q, go)), clk, q)
        fsm = read_fsm(g.build(), (q,))
        assert fsm is not None
        self.assertEqual(fsm.memory, "")

    def test_counter_with_load_port_is_free_load(self) -> None:
        g = GB()
        clk, load = g.pi("clk"), g.pi("load")
        data = g.pis_n(3, "d")
        qs = [g.net(f"q{i}") for i in range(3)]
        for i in range(3):
            ins = (load, data[i], *qs[: i + 1])

            g.ff(g.lut(table_of(len(ins), _load_count(i)), ins), clk, qs[i])
        fsm = read_fsm(g.build(), tuple(qs))
        assert fsm is not None
        self.assertEqual(fsm.memory, "free-load")

    def test_state_machines_are_not_memory(self) -> None:
        g = GB()
        q0, q1, _, _ = three_state(g)
        fsm = read_fsm(g.build(), (q0, q1))
        assert fsm is not None
        self.assertEqual(fsm.memory, "")


class GroupsTest(unittest.TestCase):
    def test_counter_with_reset_has_a_feeder(self) -> None:
        g = GB()
        clk, rst = g.pi("clk"), g.pi("rst")
        q = up_counter(g, clk, 4, rst=rst)
        groups = sequential_groups(g.build())
        self.assertEqual(len(groups[0].ffs), 4)
        self.assertTrue(groups[0].is_loop)
        self.assertEqual(len(groups[0].loop) + len(groups[0].feeders), 4)
        self.assertEqual(len(q), 4)

    def test_feeder_reading_an_input_is_not_a_state_bit(self) -> None:
        g = GB()
        clk, go = g.pi("clk"), g.pi("go")
        qs = modulo_counter(g, clk, 2, 3, 0)
        reg = g.ff(go, clk)
        groups = sequential_groups(g.build())
        self.assertEqual(len(groups[0].ffs), 2)
        self.assertNotIn(g.cell_of(reg), groups[0].ffs)
        self.assertEqual(len(qs), 2)


class LowerTest(unittest.TestCase):
    def test_dffsr_becomes_a_flip_flop_with_dominant_reset(self) -> None:
        g = GB()
        clk, d, s, r = g.pi("clk"), g.pi("d"), g.pi("s"), g.pi("r")
        q = g.net("q")
        g._cell += 1
        cid = g._cell
        g.cells[cid] = Cell(cid, "ff0", "hard", "DFFSR", (clk, d, s, r, q), (), 0, 0, 0, cid, {},
                            ("C", "D", "S", "R", "Q"))
        low, asyn = lower_async_ff(g.build())
        self.assertEqual(asyn, {q: (s, r)})
        self.assertEqual(low.cells[cid].kind, "ff")
        self.assertEqual(low.driver[q], cid)
        lut = low.cells[low.driver[low.cells[cid].ins[0]]]
        for x in range(8):
            dd, ss, rr = x & 1, (x >> 1) & 1, (x >> 2) & 1
            self.assertEqual((lut.table >> x) & 1, 0 if rr else (1 if ss else dd))

    def test_graph_without_dffsr_is_returned_unchanged(self) -> None:
        g = GB()
        g.ff(g.pi("d"), g.pi("clk"))
        graph = g.build()
        self.assertIs(lower_async_ff(graph)[0], graph)


if __name__ == "__main__":
    unittest.main()
