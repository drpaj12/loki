"""Tests of the Q-L8b anchor classes and tables (no Odin III needed).

Run from this directory: ``python -m unittest test_ql8b``.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from typing import Any

import q8b_anchors as qa
import q8b_env as env

qn = env.mod("q6_net")


def bank_blif(n: int, fan: int) -> str:
    """n flip-flops q_i <= x_i & en & qe & q_(i-1) & q_(i+1), qe an outside flip-flop; en is read
    by n gates and fan extra gates."""
    xs = " ".join(f"x{i}" for i in range(n))
    out = [".model t", f".inputs clk en {xs}", ".outputs z", ".latch x0 qe re clk 0"]
    for i in range(n):
        out += [f".names x{i} en qe q{(i - 1) % n} q{(i + 1) % n} d{i}", "11111 1",
                f".latch d{i} q{i} re clk 0"]
    for k in range(fan):
        out += [f".names en e{k}", "1 1"]
    out += [".names c0", "1", ".names q0 c0 z", "11 1", ".end"]
    return "\n".join(out) + "\n"


OPEN_LOOP = """.model t
.inputs clk a
.outputs z
.names a de
1 1
.latch de e re clk 0
.names q1 q2 e d0
111 1
.names q0 e d1
11 1
.names q0 e d2
11 1
.latch d0 q0 re clk 0
.latch d1 q1 re clk 0
.latch d2 q2 re clk 0
.names q0 z
1 1
.end
"""


def graph(text: str) -> Any:
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "n.blif"
        p.write_text(text, encoding="utf-8")
        return qn.Graph.read(p)


class AnchorTest(unittest.TestCase):
    def test_bank_groups_flip_flops_sharing_a_global_net(self) -> None:
        g = graph(bank_blif(8, 8))
        old = qn.anchors(g)
        extra = qa.extra_anchors(g, old, ("bank",))
        banks = [a for a in extra if a.kind == "bank"]
        self.assertEqual(len(banks), 1)
        self.assertEqual(len(banks[0].cells), 8)
        self.assertTrue(all(g.b.latch[i] for i in banks[0].cells))

    def test_no_bank_below_threshold(self) -> None:
        g = graph(bank_blif(7, 9))
        self.assertEqual(qa.extra_anchors(g, qn.anchors(g), ("bank",)), [])

    def test_no_bank_without_a_global_net(self) -> None:
        g = graph(bank_blif(8, 0))  # en is read by 8 cells only: not global
        self.assertEqual(qa.extra_anchors(g, qn.anchors(g), ("bank",)), [])

    def test_const_anchor_is_one_anchor_of_constants(self) -> None:
        g = graph(bank_blif(8, 8))
        const = [a for a in qa.extra_anchors(g, qn.anchors(g), ("const",)) if a.kind == "const"]
        self.assertEqual(len(const), 1)
        self.assertEqual([g.b.ins[i] for i in const[0].cells], [[]])

    def test_loop_takes_open_feedback_loop(self) -> None:
        g = graph(OPEN_LOOP)
        old = qn.anchors(g)
        loops = [a for a in qa.extra_anchors(g, old, ("loop",)) if a.kind == "loop"]
        self.assertEqual(len(loops), 1)
        self.assertEqual(len(loops[0].cells), 3)
        self.assertEqual([a.kind for a in old], ["register"])  # the outside flip-flop e

    def test_new_anchor_never_takes_an_old_cell(self) -> None:
        g = graph(bank_blif(8, 8))
        old = qn.anchors(g)
        taken = {i for a in old for i in a.cells}
        for a in qa.extra_anchors(g, old, qa.CLASSES):
            self.assertFalse(a.cells & taken)

    def test_no_class_no_extra(self) -> None:
        g = graph(bank_blif(8, 8))
        self.assertEqual(qa.extra_anchors(g, qn.anchors(g), ()), [])


class PathsTest(unittest.TestCase):
    def test_paths_dir(self) -> None:
        self.assertEqual(env.paths_dir("OLD", "TEST"), env.q7env.paths_dir("TEST"))
        self.assertIn("paths_bank+loop", str(env.paths_dir("bank+loop", "VALIDATION")))


if __name__ == "__main__":
    unittest.main()
