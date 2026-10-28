"""Checks on ``experiments/quartiles/quartiles.py`` (per-quartile tables, no model calls)."""

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "experiments" / "quartiles" / "quartiles.py"


def load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("quartiles_script", SCRIPT)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules["quartiles_script"] = mod
    spec.loader.exec_module(mod)
    return mod


class McNemarTest(unittest.TestCase):
    def test_known_values_from_pilot(self) -> None:
        q = load()
        self.assertAlmostEqual(q.mcnemar_p(2, 0), 0.5)
        self.assertAlmostEqual(q.mcnemar_p(5, 1), 0.21875)
        self.assertAlmostEqual(q.mcnemar_p(7, 1), 0.0703125)
        self.assertEqual(q.mcnemar_p(0, 0), 1.0)

    def test_power_floor(self) -> None:
        q = load()
        self.assertEqual(q.min_discordant(), 6)
        self.assertIsNone(q.min_majority(5))
        self.assertEqual(q.min_majority(8), 8)
        self.assertEqual(q.min_majority(10), 9)


class PilotRowsTest(unittest.TestCase):
    def test_totals_match_results_md(self) -> None:
        q = load()
        cells, tests = q.pilot_rows()
        allc = next(r for r in cells if r["quartile"] == "All" and r["view"] == "all_calls")
        self.assertEqual((allc["pass_A"], allc["pass_B"], allc["pass_C"]), ("35", "35", "30"))
        pair = next(r for r in cells if r["quartile"] == "All" and r["view"] == "paired")
        self.assertEqual(pair["n"], "38")
        p = next(r for r in tests if r["quartile"] == "All" and r["view"] == "paired"
                 and r["comparison"] == "B vs C")
        self.assertEqual(p["p"], "0.0703")
        self.assertFalse(any(r["quartile"] == "Stratified" for r in tests))

    def test_all_row_is_pooled_discordant_pairs(self) -> None:
        q = load()
        _, tests = q.pilot_rows()
        for view in ("all_calls", "paired"):
            for cmp in ("B vs A", "B vs C", "A vs C"):
                rs = [r for r in tests if r["view"] == view and r["comparison"] == cmp]
                allr = next(r for r in rs if r["quartile"] == "All")
                for k in ("first_only", "second_only"):
                    self.assertEqual(int(allr[k]), sum(int(r[k]) for r in rs
                                                       if r["quartile"] != "All"))

    def test_four_quartiles_of_ten(self) -> None:
        q = load()
        cells, _ = q.pilot_rows()
        sizes = [r["n"] for r in cells if r["view"] == "all_calls" and r["quartile"] != "All"]
        self.assertEqual(sizes, ["10", "10", "10", "10"])


class PartitionTest(unittest.TestCase):
    def test_gb_files_144_and_match_pilot_selection(self) -> None:
        q = load()
        gb = q.gb_problems()
        counts = [sum(1 for v in gb.values() if v == x) for x in q.QS]
        self.assertEqual(counts, [41, 36, 36, 31])
        quart, _ = q.pilot_outcomes()
        self.assertTrue(all(gb[p] == v for p, v in quart.items()))

    def test_crosstab_and_unbuilt(self) -> None:
        q = load()
        xt = q.crosstab()
        self.assertEqual(sum(int(r["designs"]) for r in xt), 150)
        self.assertEqual(sum(int(r["designs"]) for r in xt if r["gb_quartile"] == "none"), 12)
        self.assertEqual(sum(int(r["designs"]) for r in xt
                             if r["gb_quartile"] == r["bin_quartile"]), 103)
        nb = q.not_built()
        self.assertEqual([r["gb_quartile"] for r in nb].count("Q3"), 3)
        self.assertEqual([r["gb_quartile"] for r in nb].count("Q4"), 3)
        self.assertNotIn("UNEXPLAINED", [r["reason"] for r in nb])

    def test_bin_partition_reproduces_committed_headtohead(self) -> None:
        q = load()
        loki = q.loki_only_rows(q.bench_part())
        for r in q.read(q.EXP / "round2/l2_headtohead.csv"):
            if r["variant"] != "f3-calib":
                continue
            row = q.get(loki, "round2 per design", f"{r['set']} f3-calib ast_mean", r["quartile"])
            self.assertEqual(row["n"], r["n"])
            if r["n"] != "0":
                self.assertAlmostEqual(float(row["value"]), float(r["ast_mean"]), places=3)


class OutputTest(unittest.TestCase):
    def test_deterministic_and_committed(self) -> None:
        q = load()
        with tempfile.TemporaryDirectory(prefix="lqp-test-") as d:
            a, b = Path(d) / "a", Path(d) / "b"
            a.mkdir()
            b.mkdir()
            q.build(a, a / "t.tex")
            q.build(b, b / "t.tex")
            for name in ("pilot_cells.csv", "pilot_tests.csv", "loki_only.csv",
                         "loki_only_bins.csv", "comparison.csv", "partition_crosstab.csv",
                         "not_built.csv"):
                self.assertEqual((a / name).read_bytes(), (b / name).read_bytes())
                self.assertEqual((a / name).read_bytes(), (SCRIPT.parent / name).read_bytes())
            self.assertEqual((a / "t.tex").read_bytes(), (b / "t.tex").read_bytes())
            committed = ROOT / "docs" / "paper" / "quartile-tables.tex"
            self.assertEqual((a / "t.tex").read_bytes(), committed.read_bytes())


if __name__ == "__main__":
    unittest.main()
