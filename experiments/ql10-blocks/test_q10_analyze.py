"""Tests of the Q-L10 analysis helpers (no model, no data files): ``python -m unittest``."""

from __future__ import annotations

import importlib
import sys
import unittest
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
an: Any = importlib.import_module("q10_analyze")


class StatsTest(unittest.TestCase):
    def test_mcnemar_exact(self) -> None:
        self.assertEqual(an.mcnemar(0, 0), 1.0)
        self.assertAlmostEqual(an.mcnemar(0, 5), 0.0625)
        self.assertEqual(an.mcnemar(3, 3), 1.0)

    def test_holm_monotone(self) -> None:
        out = an.holm([0.01, 0.04, 0.03])
        self.assertEqual([round(x, 2) for x in out], [0.03, 0.06, 0.06])

    def test_boot_deterministic_and_bounds(self) -> None:
        xs = [0.0, 0.1, -0.1, 0.0, 0.2]
        self.assertEqual(an.boot_ci(xs), an.boot_ci(xs))
        lo, hi = an.boot_ci(xs)
        self.assertLessEqual(lo, an.mean(xs))
        self.assertGreaterEqual(hi, an.mean(xs))
        self.assertEqual(an.boot_ci([0.5, 0.5, 0.5]), (0.5, 0.5))

    def test_wlt_and_compare(self) -> None:
        pairs = {"a": ({1: 1, 2: 1, 3: 1}, {1: 1, 2: 0, 3: 0}), "b": ({1: 0, 2: 1}, {1: 1, 2: 1})}
        self.assertEqual(an.wlt(pairs), (2, 1, 2))
        c = an.compare(pairs)
        self.assertEqual(c["maj_first"], 1)
        self.assertEqual(c["maj_second"], 1)
        self.assertEqual(c["wlt_problem"], (1, 1, 0))

    def test_verdict_rules(self) -> None:
        base: dict[str, Any] = {"lo": -0.02, "hi": 0.04, "diff": 0.01}
        self.assertEqual(an.verdict_a(base), "SUPPORTED")
        self.assertEqual(an.verdict_a({"lo": -0.1, "hi": 0.04}), "INCONCLUSIVE")
        self.assertEqual(an.verdict_a({"lo": -0.2, "hi": -0.05}), "CONTRADICTED")
        self.assertEqual(an.verdict_c({"lo": -0.03, "hi": 0.03, "diff": 0.0}, 1.0), "DISMISSED")
        self.assertEqual(an.verdict_c({"lo": 0.0, "hi": 0.3, "diff": 0.2}, 0.01), "USEFUL")
        self.assertEqual(an.verdict_c({"lo": -0.2, "hi": 0.0, "diff": -0.1}, 1.0), "INCONCLUSIVE")

    def test_compare_cont(self) -> None:
        pairs = {"a": ({1: 0.5, 2: 0.7}, {1: 0.5, 2: 0.4}), "b": ({1: 0.2}, {1: 0.4})}
        c = an.compare_cont(pairs)
        self.assertEqual(c["wlt_draw"], (1, 1, 1))
        self.assertAlmostEqual(c["diff"], (0.15 - 0.2) / 2)


if __name__ == "__main__":
    unittest.main()
