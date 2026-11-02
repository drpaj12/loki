"""Tests of the Q-L8a orders, subclasses and tables (no Odin III needed).

Run from this directory: ``python -m unittest test_ql8a``.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import numpy as np
import q8a_env as env
import q8a_eval as qe
import q8a_grow as qg

qn = env.mod("q6_net")

# a0 -> r0 -> a1 -> r1 chain, cell L reads r1 and drives a0; S1 and S2 read the shared net sel
BLIF = """.model t
.inputs a b clk
.outputs q
.names a L a0
11 1
.latch a0 r0 re clk 0
.names r0 a1
1 1
.latch a1 r1 re clk 0
.names r1 L
1 1
.names r0 sel S1
11 1
.names r1 sel S2
11 1
.names b sel
1 1
.names r1 q
1 1
.end
"""


def graph(text: str) -> Any:
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "n.blif"
        p.write_text(text, encoding="utf-8")
        return qn.Graph.read(p)


def cell_of(g: Any, net: str) -> int:
    return int(g.b.producer[net])


class OrderTest(unittest.TestCase):
    def setUp(self) -> None:
        self.g = graph(BLIF)
        self.r0, self.r1 = cell_of(self.g, "r0"), cell_of(self.g, "r1")

    def grower(self, order: str) -> Any:
        return qg.OrderedGrower(self.g, None, None, "O-gate", order)

    def block(self, cells: set[int]) -> Any:
        return SimpleNamespace(cells=set(cells), cand={}, touches=set())

    def test_closing_cell_has_top_tier(self) -> None:
        gr = self.grower("OB")
        b = self.block({self.r0, self.r1})
        touched, readers = gr.block_nets(b)
        closer = cell_of(self.g, "a1")  # reads r0 and drives r1: sits on a path between block cells
        other = cell_of(self.g, "L")  # only reads r1
        self.assertEqual(gr.key(b, closer, 0.0, touched, readers)[0], 2)
        self.assertLess(gr.key(b, other, 0.0, touched, readers)[0], 2)

    def test_sibling_added_only_by_ob(self) -> None:
        b = self.block({self.r0})
        s1 = cell_of(self.g, "S1")
        s2 = cell_of(self.g, "S2")
        near = set(self.grower("OA").free_frontier(b))
        wide = set(self.grower("OB").free_frontier(b))
        self.assertTrue(near <= wide)
        self.assertIn(s1, near)  # reads r0 directly
        self.assertNotIn(s2, near)

    def test_cone_prefers_drivers(self) -> None:
        gr = self.grower("OC")
        b = self.block({self.r1})
        touched, readers = gr.block_nets(b)
        a1 = cell_of(self.g, "a1")  # drives r1
        out = cell_of(self.g, "q")  # only reads r1
        self.assertGreater(gr.key(b, a1, 0.0, touched, readers)[0],
                           gr.key(b, out, 9.0, touched, readers)[0])

    def test_e74_uses_base_propose(self) -> None:
        gr = self.grower("E74")
        b = self.block({self.r0})
        b.cand = {5: 0.5, 3: 1.5}
        self.assertEqual(gr.propose(b), 3)

    def test_propose_none_when_nothing_live(self) -> None:
        gr = self.grower("OA")
        b = self.block({self.r0})
        self.assertIsNone(gr.propose(b))


def unit(inter: list[list[int]], size: list[int], ntrue: int) -> Any:
    blocks = []
    for it, sz in zip(inter, size, strict=True):
        inter_a = np.array([it], dtype=float)
        s = np.array(sz, dtype=float) if isinstance(sz, list) else np.array([sz], dtype=float)
        blocks.append(SimpleNamespace(
            inter=inter_a, size=s, ntrue=np.array([float(ntrue)]),
            coverage=inter_a / ntrue))
    return SimpleNamespace(blocks=blocks)


class SubclassTest(unittest.TestCase):
    def test_bloated(self) -> None:
        u = unit([[5, 9]], [[5, 40]], 10)  # covers 0.9 at size 40: Jaccard 9/41 < 0.5
        self.assertEqual(qe.order_subclass(u, 0), "BLOATED")

    def test_split(self) -> None:
        u = unit([[3, 5], [2, 4]], [[3, 5], [2, 4]], 10)  # 5 + 4 = 9 >= 8, no block alone
        self.assertEqual(qe.order_subclass(u, 0), "SPLIT")

    def test_underreach(self) -> None:
        u = unit([[3, 4]], [[3, 4]], 10)
        self.assertEqual(qe.order_subclass(u, 0), "UNDERREACH")


class PathsTest(unittest.TestCase):
    def test_paths_dir(self) -> None:
        self.assertEqual(env.paths_dir("OA", "TEST").name, "TEST")
        self.assertIn("paths_OA", str(env.paths_dir("OA", "VALIDATION")))
        self.assertEqual(env.paths_dir("E74", "TEST"), env.q7env.paths_dir("TEST"))


if __name__ == "__main__":
    unittest.main()
