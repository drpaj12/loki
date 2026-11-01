"""Tests of the Q-L4 classification rule and the block helpers (no Odin III run needed)."""

from __future__ import annotations

import math
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import blocks as bl  # noqa: E402
import classify as cl  # noqa: E402

BLIF = """.model t
.inputs a b clk
.outputs q2
.names a b n1
11 1
.cname c_and
.latch n1 q1 re clk 0
.cname c_ff1
.names q1 n2
0 1
.cname c_inv
.latch n2 q2 re clk 0
.cname c_ff2
.end
"""


def facts(**kw: float | int | bool) -> cl.MissFacts:
    base: dict[str, float | int | bool] = {
        "jaccard": 0.9, "coverage": 0.95, "true_ff": 4, "has_entry": True, "t_dist": 0.1,
        "t_wrong": 0.3, "q90": 0.2}
    base.update(kw)
    return cl.MissFacts(**base)  # type: ignore[arg-type]


class RuleTests(unittest.TestCase):
    def test_order(self) -> None:
        self.assertEqual(cl.classify(facts(true_ff=0)), "absent")
        self.assertEqual(cl.classify(facts(has_entry=False, jaccard=0.0)),
                         "missing pattern (width)")
        self.assertEqual(cl.classify(facts(jaccard=0.4)), "partition miss")
        self.assertEqual(cl.classify(facts(coverage=0.7)), "partition miss")
        self.assertEqual(cl.classify(facts()), "threshold miss")
        self.assertEqual(cl.classify(facts(t_dist=0.5)), "structure miss")

    def test_boundaries(self) -> None:
        self.assertEqual(cl.classify(facts(jaccard=0.5, coverage=0.8)), "threshold miss")
        self.assertEqual(cl.classify(facts(t_dist=0.2)), "threshold miss")
        self.assertEqual(cl.classify(facts(t_dist=math.nan)), "structure miss")
        self.assertEqual(cl.classify(facts(q90=math.nan)), "structure miss")

    def test_rank_flag(self) -> None:
        self.assertTrue(cl.rank_flag(facts(t_wrong=0.05)))
        self.assertFalse(cl.rank_flag(facts()))
        self.assertFalse(cl.rank_flag(facts(t_wrong=math.nan)))

    def test_percentile(self) -> None:
        self.assertAlmostEqual(cl.percentile([0.0, 1.0, 2.0, 3.0, 4.0], 0.9), 3.6)
        self.assertTrue(math.isnan(cl.percentile([], 0.9)))
        self.assertEqual(cl.percentile([math.nan, 2.0], 0.5), 2.0)


class BlockTests(unittest.TestCase):
    def setUp(self) -> None:
        self.dir = tempfile.TemporaryDirectory()
        self.path = Path(self.dir.name) / "n.blif"
        self.path.write_text(BLIF, encoding="utf-8")
        self.b = bl.Blif.read(self.path)

    def tearDown(self) -> None:
        self.dir.cleanup()

    def test_parse(self) -> None:
        self.assertEqual(self.b.n, 4)
        self.assertEqual(self.b.cname, ["c_and", "c_ff1", "c_inv", "c_ff2"])
        self.assertEqual([self.b.latch[i] for i in range(4)], [False, True, False, True])
        self.assertEqual(self.b.n_latches({0, 1, 2, 3}), 2)

    def test_unbounded_cone_crosses_flip_flops(self) -> None:
        self.assertEqual(bl.unbounded_block(self.b, ["q2"]), {0, 1, 2, 3})
        self.assertEqual(bl.unbounded_block(self.b, ["q1"]), {0, 1})

    def test_jaccard(self) -> None:
        self.assertEqual(bl.jaccard({1, 2, 3}, {2, 3, 4, 5}), (0.4, 0.5))
        self.assertEqual(bl.jaccard({1}, set()), (0.0, 0.0))

    def test_block_nodes(self) -> None:
        outs, pis = bl.block_nodes(self.b, {0, 1})
        self.assertEqual(outs, ["n1", "q1"])
        self.assertEqual(pis, ["a", "b"])  # the latch clock is a global net, not a data input

    def test_part_blocks_by_label_and_line(self) -> None:
        labels = Path(self.dir.name) / "labels.csv"
        labels.write_text(
            "node_id,kind,module_path,hdl_line\n"
            "c_and,gate,top/u0,5\nc_ff1,gate,top/*,12\nc_inv,gate,top,30\nc_ff2,gate,top/u1,40\n"
            "p,pi,top,1\n", encoding="utf-8")
        parts, by_line = bl.part_blocks(self.b, labels, {0: (1, 20), 1: (21, 50)})
        self.assertEqual(parts, {0: {0, 1}, 1: {2, 3}})
        self.assertEqual(by_line, {0: 1, 1: 1})


if __name__ == "__main__":
    unittest.main()
