"""Tests for the llm-full helpers (no model, no Odin III): run with ``python -m unittest``."""

from __future__ import annotations

import importlib
import sys
import unittest
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
analyze_full: Any = importlib.import_module("analyze_full")
build_full: Any = importlib.import_module("build_full")
fullcfg: Any = importlib.import_module("fullcfg")


class PassAtK(unittest.TestCase):
    def test_values(self) -> None:
        f = analyze_full.pass_at_k
        self.assertEqual(f(3, 3, 1), 1.0)
        self.assertAlmostEqual(f(3, 1, 1), 1 / 3)
        self.assertEqual(f(3, 0, 3), 0.0)
        self.assertEqual(f(3, 1, 3), 1.0)
        self.assertAlmostEqual(f(3, 2, 1), 2 / 3)

    def test_holm(self) -> None:
        self.assertEqual(analyze_full.holm([0.01, 0.04, 0.03]), [0.03, 0.06, 0.06])
        self.assertEqual(analyze_full.holm([0.5]), [0.5])


class Tests(unittest.TestCase):
    def test_pooled_equals_mcnemar(self) -> None:
        counts = {}
        quart = {}
        for i in range(8):
            p = f"P{i}"
            quart[p] = "Q1" if i < 4 else "Q2"
            counts[("A", p)] = 0
            counts[("B", p)] = 3 if i != 7 else 0
            counts[("C", p)] = 0
        rows = analyze_full.tests(counts, quart, "MAJ")
        pooled = [r for r in rows if r.cmp == "A vs B" and r.stratum.startswith("all")][0]
        self.assertEqual((pooled.x_only, pooled.y_only), (0, 7))
        self.assertAlmostEqual(pooled.p, 2 * 0.5**7)

    def test_call_file(self) -> None:
        text = build_full.call_file_text("sys", "usr\n")
        self.assertTrue(text.startswith(build_full.DELIM_SYS + "sys"))
        self.assertTrue(text.endswith(build_full.DELIM_USER + "usr\n"))
        self.assertEqual(fullcfg.DRAWS, (1, 2, 3))


if __name__ == "__main__":
    unittest.main()
