import unittest

from loki.re.fngraph import Cell, FnGraph
from loki.re.sim import SUPPORT_MAX, Support, cone, simulate, topo_order

XOR2, AND2, XOR3 = 0b0110, 0b1000, 0b10010110


def lut(cid: int, ins: tuple[int, ...], out: int, table: int) -> Cell:
    return Cell(cid, "", "lut", "$sop", ins, (out,), table, len(ins), 0, cid, {})


def graph_of(cells: list[Cell], pis: tuple[int, ...], pos: tuple[int, ...]) -> FnGraph:
    by_id = {c.id: c for c in cells}
    driver = {n: c.id for c in cells for n in c.outs}
    readers: dict[int, list[tuple[int, int]]] = {}
    for c in cells:
        for pin, n in enumerate(c.ins):
            readers.setdefault(n, []).append((c.id, pin))
    return FnGraph(by_id, driver, {n: tuple(r) for n, r in readers.items()}, {}, pis, pos,
                   {}, "")


def add2() -> FnGraph:
    # nets: a0=1 a1=2 b0=3 b1=4 y0=5 c0=6 y1=7
    cells = [
        lut(9, (1, 3), 5, XOR2),
        lut(10, (1, 3), 6, AND2),
        lut(11, (2, 4, 6), 7, XOR3),
    ]
    return graph_of(cells, (1, 2, 3, 4), (5, 7))


class SimTest(unittest.TestCase):
    def test_simulate_bit_parallel(self) -> None:
        g = add2()
        a, b = [], []
        for x in range(4):
            for y in range(4):
                a.append(x)
                b.append(y)
        n = len(a)
        vec = {net: sum(((v >> bit) & 1) << k for k, v in enumerate(src))
               for net, src, bit in ((1, a, 0), (2, a, 1), (3, b, 0), (4, b, 1))}
        out = simulate(g, [11, 9, 10], vec, n)
        for k in range(n):
            got = ((out[5] >> k) & 1) | (((out[7] >> k) & 1) << 1)
            self.assertEqual(got, (a[k] + b[k]) & 3)

    def test_missing_input_reads_zero(self) -> None:
        out = simulate(add2(), [10], {1: 0b11}, 2)
        self.assertEqual(out[6], 0)

    def test_topo_order(self) -> None:
        self.assertEqual(topo_order(add2(), [11, 10, 9]), [9, 10, 11])

    def test_support_of_add2(self) -> None:
        s = Support(add2())
        self.assertEqual(s.of(7), frozenset({1, 2, 3, 4}))
        self.assertEqual(s.of(5), frozenset({1, 3}))
        self.assertEqual(s.of(1), frozenset({1}))
        self.assertEqual(s.loops_cut, 0)

    def test_support_with_loop(self) -> None:
        # cell 1: net 3 = AND(net 1, net 4); cell 2: net 4 = XOR(net 3, net 2); a loop
        g = graph_of([lut(1, (1, 4), 3, AND2), lut(2, (3, 2), 4, XOR2)], (1, 2), (4,))
        s = Support(g)
        self.assertEqual(s.loops_cut, 1)
        self.assertEqual(s.of(4), frozenset({1, 2}))
        self.assertEqual(s.of(3), frozenset({1}))  # cut at cell 1, the lowest id

    def test_support_self_loop(self) -> None:
        g = graph_of([lut(1, (1, 2), 2, AND2)], (1,), (2,))
        s = Support(g)
        self.assertEqual(s.loops_cut, 1)
        self.assertEqual(s.of(2), frozenset({1}))

    def test_support_cap(self) -> None:
        n = SUPPORT_MAX + 1
        pis = tuple(range(1, n + 1))
        cells, cur = [], pis[0]
        for i, p in enumerate(pis[1:]):
            out = 100 + i
            cells.append(lut(50 + i, (cur, p), out, XOR2))
            cur = out
        g = graph_of(cells, pis, (cur,))
        self.assertIsNone(Support(g).of(cur))
        ok = graph_of(cells[: SUPPORT_MAX - 1], pis, (cur,))
        self.assertEqual(len(Support(ok).of(100 + SUPPORT_MAX - 2) or ()), SUPPORT_MAX)

    def test_extra_sources(self) -> None:
        s = Support(add2(), frozenset({6}))
        self.assertEqual(s.of(7), frozenset({2, 4, 6}))

    def test_cone_side_inputs(self) -> None:
        g = add2()
        cells, side = cone(g, frozenset({1, 3}), [5], frozenset())
        self.assertEqual((cells, side), ((9,), frozenset()))
        cells, side = cone(g, frozenset({6}), [7], frozenset())
        self.assertEqual((cells, side), ((11,), frozenset({2, 4})))
        cells, side = cone(g, frozenset({2, 4, 6}), [7], frozenset())
        self.assertEqual((cells, side), ((11,), frozenset()))

    def test_cone_stop(self) -> None:
        cells, side = cone(add2(), frozenset({2, 4}), [7], frozenset({6}))
        self.assertEqual((cells, side), ((11,), frozenset({6})))


if __name__ == "__main__":
    unittest.main()
