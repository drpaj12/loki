"""Unit tests of the census labeller and BLIF reach (run: python -m unittest in this folder)."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from typing import Any

import blifgraph
import labels_rtl


def words(types: list[str], edges: list[tuple[int, int]], fsm: tuple[int, ...] = ()) -> Any:
    return {"words": [{"id": i, "type": t, "fsm": i in fsm, "const_ports": ["B"]}
                      for i, t in enumerate(types)],
            "edges": [{"src": a, "dst": b} for a, b in edges]}


class LabelTests(unittest.TestCase):
    def test_counter_and_timer(self) -> None:
        w = words(["$dff", "$add", "$eq", "$mux"], [(0, 1), (1, 3), (3, 0), (0, 2), (2, 3)])
        out = labels_rtl.label_design(w, "")
        self.assertEqual((out["counter"], out["timer"], out["glue"]), (1, 1, 0))

    def test_accumulator_is_not_counter(self) -> None:
        w = words(["$dff", "$add"], [(0, 1), (1, 0)])
        w["words"][1]["const_ports"] = []
        self.assertEqual(labels_rtl.label_design(w, "")["counter"], 0)

    def test_fsm_not_counter(self) -> None:
        w = words(["$dff", "$add", "$mux"], [(0, 1), (1, 2), (2, 0)], fsm=(0,))
        out = labels_rtl.label_design(w, "")
        self.assertEqual((out["fsm"], out["counter"]), (1, 0))

    def test_glue_and_register(self) -> None:
        self.assertEqual(labels_rtl.label_design(words(["$and"], []), "")["glue"], 1)
        out = labels_rtl.label_design(words(["$dff"], []), "")
        self.assertEqual((out["register"], out["glue"]), (1, 0))

    def test_register_bank(self) -> None:
        w = words(["$dffe"] * 4, [])
        self.assertEqual(labels_rtl.label_design(w, "")["regfile"], 1)
        self.assertEqual(labels_rtl.label_design(words(["$dffe"] * 3, []), "")["regfile"], 0)

    def test_shift_and_lfsr_idioms(self) -> None:
        w = words(["$dff", "$xor"], [(0, 1), (1, 0)])
        src = "q <= {q[6:0], q[7] ^ q[3]}; // comment q <= q"
        out = labels_rtl.label_design(w, src)
        self.assertEqual((out["shift"], out["lfsr"]), (1, 1))
        self.assertEqual(labels_rtl.label_design(w, "q <= d;")["shift"], 0)

    def test_fsm_counter_link(self) -> None:
        w = words(["$dff", "$dff", "$add", "$mux", "$eq"],
                  [(1, 2), (2, 3), (3, 1), (1, 4), (4, 0)], fsm=(0,))
        self.assertEqual(labels_rtl.label_design(w, "")["fsm_counter"], 1)


class BlifTests(unittest.TestCase):
    def test_depth(self) -> None:
        text = (".model m\n.inputs a clk\n.outputs z\n.names a q1 x\n11 1\n.names x y\n1 1\n"
                ".latch y q2 re clk 2\n.latch a q1 re clk 2\n.names q2 z\n1 1\n.end\n")
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "m.blif"
            p.write_text(text, encoding="utf-8")
            g = blifgraph.Blif(p)
        self.assertEqual(g.counts()["latches"], 2)
        self.assertEqual(g.min_depth(["q1"], ["q2"]), 2)
        self.assertEqual(g.min_depth(["q2"], ["q1"]), -1)


if __name__ == "__main__":
    unittest.main()
