import json
import math
import tempfile
import unittest
from pathlib import Path

from loki.re import bayes
from loki.re.bayes import DEFAULTS, Calib, family_of, load_calib, logit, sigmoid, wl_npn_bin


class BayesTest(unittest.TestCase):
    def test_constants(self) -> None:
        self.assertEqual((bayes.PROOF_LO, bayes.SIM_LLR, bayes.STRUCT_CAP), (9.21, 4.61, 6.91))
        self.assertEqual((bayes.CHILD_LLR, bayes.CHILD_CAP, bayes.CHILD_NEG), (1.10, 3.30, -2.30))
        self.assertEqual((bayes.COMMIT_P, bayes.PROVE_P, bayes.REJECT_P), (0.9, 0.2, 0.01))
        self.assertEqual((bayes.MAX_PROOFS, bayes.MAX_ROUNDS), (200, 8))

    def test_logit_sigmoid(self) -> None:
        self.assertEqual(logit(0.5), 0.0)
        self.assertEqual((logit(0.0), logit(1.0)), (-math.inf, math.inf))
        self.assertAlmostEqual(sigmoid(logit(0.9)), 0.9)
        self.assertEqual((sigmoid(math.inf), sigmoid(-math.inf)), (1.0, 0.0))
        self.assertEqual(sigmoid(-2000.0), 0.0)
        self.assertEqual(sigmoid(2000.0), 1.0)

    def test_family_of(self) -> None:
        self.assertEqual(
            [family_of(f) for f in ("npn_sum", "wl_depth", "l2_part", "k", "table")],
            ["npn", "wl", "l2", "struct", "struct"])

    def test_new_constants(self) -> None:
        self.assertEqual((bayes.TRANSFER_ROUND, bayes.CALIB_WL_DEPTH), (2, 2))
        self.assertEqual((bayes.NODE_MIN_COUNT, bayes.CALIB_FOLDS), (5, 2))
        self.assertEqual(len(bayes.WEIGHT_GRID), 11)
        self.assertEqual((bayes.WEIGHT_GRID[0], bayes.WEIGHT_GRID[3], bayes.WEIGHT_GRID[10]),
                         (0.0, 0.3, 1.0))

    def test_node_score_backoff(self) -> None:
        calib = Calib("", {}, {}, "t", node_llr={"adder": {"1:b": 0.7, "0:c": -0.2}})
        self.assertEqual(calib.node_score("adder", ("2:a", "1:b", "0:c")), 0.7)
        self.assertEqual(calib.node_score("adder", ("2:a", "0:c")), -0.2)
        self.assertIsNone(calib.node_score("adder", ("2:a",)))
        self.assertIsNone(calib.node_score("mux", ("1:b",)))
        self.assertIsNone(DEFAULTS.node_score("adder", ("0:c",)))

    def test_wl_npn_bins(self) -> None:
        cases = [(-3.0, "--"), (-2.0, "-"), (-1.0, "-"), (-0.5, "0"), (0.0, "0"), (0.5, "0"),
                 (0.6, "+"), (2.0, "+"), (2.1, "++")]
        for value, want in cases:
            self.assertEqual(wl_npn_bin(value), want, value)
        self.assertEqual(wl_npn_bin(None), "unseen")

    def test_calib_floor_mismatch_refused(self) -> None:
        """A calibration file names its floor ("f2"); running it on another floor must be
        refused, not silently applied (an f2 table on an f3 run)."""
        calib = Calib("f2", {}, {}, "t")
        bayes.require_floor(calib, "f2")
        bayes.require_floor(Calib("", {}, {}, "d"), "f3")  # DEFAULTS: no floor to check
        with self.assertRaises(ValueError):
            bayes.require_floor(calib, "f3")

    def test_calib_new_fields_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "c.json"
            path.write_text(json.dumps({
                "schema": 1, "floor": "f2",
                "node_llr": {"adder": {"2:abc": 0.5, "0:def": {"pos": 6, "neg": 1, "llr": -1.5}}},
                "weights": {"npn": 0.3, "wl": 0.0},
                "reliability": {"ece": 0.04},
            }), encoding="utf-8")
            calib = load_calib(path)
        self.assertEqual(calib.node_llr, {"adder": {"2:abc": 0.5, "0:def": -1.5}})
        self.assertEqual((calib.weight("npn"), calib.weight("wl"), calib.weight("struct")),
                         (0.3, 0.0, 1.0))
        self.assertEqual(calib.node_score("adder", ("2:zzz", "0:def")), -1.5)
        self.assertEqual(DEFAULTS.node_llr, {})
        self.assertEqual(DEFAULTS.weights, {})

    def test_calib_default_and_file(self) -> None:
        self.assertIs(load_calib(None), DEFAULTS)
        self.assertEqual(DEFAULTS.prior("arith", "adder"), 0.0)
        self.assertEqual(DEFAULTS.feature_llr("bus", "k", "5-8"), 1.39)
        self.assertEqual(DEFAULTS.feature_llr("bus", "k", "none-such"), 0.0)
        self.assertEqual(DEFAULTS.feature_llr("nokind", "k", "2"), 0.0)
        self.assertEqual(DEFAULTS.feature_llr("ff_en", "en_fn_exact", "yes"), 4.61)
        with tempfile.TemporaryDirectory() as tmp:
            good = Path(tmp) / "c.json"
            good.write_text(json.dumps({
                "schema": 1, "floor": "f2",
                "priors": {"arith/adder": {"n": 4, "tp": 3, "log_odds": 0.5}},
                "llr": {"bus/k": {"2": {"pos": 1, "neg": 2, "llr": -0.4}}},
                "weights": {"wl": 0.5},
            }), encoding="utf-8")
            calib = load_calib(good)
            self.assertEqual(calib.prior("arith", "adder"), 0.5)
            self.assertEqual(calib.feature_llr("bus", "k", "2"), -0.4)
            self.assertEqual((calib.weight("wl"), calib.weight("npn")), (0.5, 1.0))
            self.assertEqual(calib.floor, "f2")
            bad = Path(tmp) / "b.json"
            bad.write_text(json.dumps({"schema": 2}), encoding="utf-8")
            with self.assertRaises(ValueError):
                load_calib(bad)

    def test_defaults_cover_spec_tables(self) -> None:
        for key in ("ff_srst/rst_fanout", "adder/npn_sum", "subtractor/npn_carry",
                    "comparator/npn_xor2", "mux_bit/npn_class", "fsm/ctrl_inputs",
                    "role/role_prop", "datapath_unit/internal_ratio", "counter/table",
                    "hard_group/shared_ctrl", "register/shared_ctrl", "bus/wl_depth"):
            self.assertIn(key, DEFAULTS.llr)
        self.assertIsInstance(Calib("", {}, {}, "x"), Calib)


if __name__ == "__main__":
    unittest.main()
