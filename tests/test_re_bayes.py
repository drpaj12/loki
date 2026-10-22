import json
import math
import tempfile
import unittest
from pathlib import Path

from loki.re import bayes
from loki.re.bayes import DEFAULTS, Calib, family_of, load_calib, logit, sigmoid


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
