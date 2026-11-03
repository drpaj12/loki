"""Tests of the Q-L11 statistics (no Odin III, no data): ``python -m unittest test_q11`` from this
directory with PYTHONPATH set as in ql10-out/env.sh plus the repository root."""

from __future__ import annotations

import importlib
import sys
import unittest
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

cmp: Any = importlib.import_module("q11_compare")
why: Any = importlib.import_module("q11_why")


def row(design: str, right: int, n: int, cls: str = "") -> dict[str, str]:
    return {"set": "s", "design": design, "cell": "O-gate", "right": str(right), "n_true": str(n),
            "cls": cls, "kind": "fsm", "endpoint": "gate"}


class WhyTest(unittest.TestCase):
    def test_status(self) -> None:
        self.assertEqual(why.status(row("a", 1, 3)), "recovered")
        self.assertEqual(why.status(row("a", 0, 3, "SPLIT")), "partly")
        self.assertEqual(why.status(row("a", 0, 3, "NOSEED")), "missed")

    def test_label(self) -> None:
        self.assertEqual(why.label(-0.3, -0.1), "SUPPORTED")
        self.assertEqual(why.label(-0.3, 0.0), "INCONCLUSIVE")
        self.assertEqual(why.label(0.1, 0.3), "DISMISSED")

    def test_boot_diff_sign_and_determinism(self) -> None:
        rows = [row(f"d{i}", 1, 50) for i in range(20)] + [row(f"e{i}", 0, 5) for i in range(20)]

        def big(r: dict[str, str]) -> bool:
            return int(r["n_true"]) > 10

        a = why.boot_diff(rows, big)
        self.assertEqual(a, why.boot_diff(rows, big))
        self.assertAlmostEqual(a[0], 1.0)
        self.assertGreater(a[1], 0.0)

    def test_taxonomy_counts(self) -> None:
        rows = [row("a", 1, 3), row("b", 0, 3, "SPLIT"), row("c", 0, 3, "NOSEED")]
        t = [r for r in why.taxonomy(rows) if r["kind"] == "fsm" and r["endpoint"] == "gate"][0]
        self.assertEqual((t["recovered"], t["partly"], t["missed"]), (1, 1, 1))


class CompareTest(unittest.TestCase):
    def test_paired_common_draws_only(self) -> None:
        a = {("X", "p"): {1: 1.0, 2: 0.5}, ("X", "q"): {1: 0.2}}
        b = {("Y", "p"): {2: 0.25, 3: 1.0}}
        d = cmp.paired(a, b, "X", "Y")
        self.assertEqual(d, {"p": {2: 0.25}})

    def test_summarise_labels(self) -> None:
        a = {("X", f"p{i}"): {1: 1.0} for i in range(30)}
        b = {("Y", f"p{i}"): {1: 0.0} for i in range(30)}
        d = cmp.paired(a, b, "X", "Y")
        s = cmp.summarise(d, a, b, "X", "Y")
        self.assertEqual((s["label"], s["draws_WLT"], s["problems_WLT"]),
                         ("BETTER", "30/0/0", "30/0/0"))


if __name__ == "__main__":
    unittest.main()
