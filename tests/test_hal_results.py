"""Checks on the committed result files of the HAL comparison (``experiments/hal/results``)."""

import csv
import unittest
from pathlib import Path

from loki.hal.wordscore import GtWord, group_shape

RESULTS = Path(__file__).resolve().parents[1] / "experiments" / "hal" / "results"


def rows(name: str) -> list[dict[str, str]]:
    with (RESULTS / name).open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


class ResultFilesTest(unittest.TestCase):
    def test_dana_f2_and_f3_partitions_equal_per_design(self) -> None:
        f2f3 = rows("f2f3.csv")
        self.assertEqual(len(f2f3), 98)
        self.assertEqual([r["key"] for r in f2f3 if r["partitions"] != "equal"], [])

    def test_no_dffsr_in_mi_and_vt_netlists(self) -> None:
        dsr = rows("dffsr.csv")
        self.assertEqual(len(dsr), 199)
        self.assertEqual([r["key"] for r in dsr if r["dffsr_cells"] != "0"], [])

    def test_lut_check_tables_and_counts(self) -> None:
        lut = rows("lutcheck.csv")
        self.assertEqual(len(lut), 100)
        self.assertEqual(sum(int(r["mismatches"]) for r in lut), 0)
        self.assertEqual(sum(int(r["count_mismatch"]) for r in lut), 0)

    def test_determinism_runs_identical(self) -> None:
        for name in ("determinism.csv", "determinism-fresh.csv", "permutation.csv"):
            self.assertTrue(all(r["partitions"] == "identical" for r in rows(name)), name)


class GroupShapeTest(unittest.TestCase):
    def test_sizes_and_merging(self) -> None:
        gt = [GtWord("a", frozenset({"1", "2", "3"})), GtWord("b", frozenset({"4", "5"})),
              GtWord("c", frozenset({"4", "5"})),  # repeats b: not a merge
              GtWord("d", frozenset({"6"}), scored=False)]
        pred = [{"1", "2"}, {"3", "4"}, {"4", "5"}, {"4", "5"}, {"1", "x"}, {"x", "y"}]
        sizes, merging = group_shape(pred, gt)
        self.assertEqual(sorted(sizes), [2, 2, 2, 2, 2])  # the repeated set counts once
        self.assertEqual(merging, 1)  # only {3, 4}


if __name__ == "__main__":
    unittest.main()
