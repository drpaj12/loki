import json
import tempfile
import unittest
from pathlib import Path

from loki.intent import calib


class IntentCalibTest(unittest.TestCase):
    def test_posterior_is_laplace_smoothed(self) -> None:
        c = calib.fit([("fsm", True)] * 19 + [("counter", True), ("counter", False)], "test")
        self.assertEqual(c.p_for("fsm"), round(20 / 21, 4))
        self.assertEqual(c.p_for("counter"), 0.5)
        self.assertIsNone(c.p_for("lfsr"))

    def test_json_round_trip(self) -> None:
        c = calib.fit([("fsm", True), ("fsm", True), ("shift_reg", False)], "unit test")
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "c.json"
            path.write_text(json.dumps(c.to_json()), encoding="utf-8")
            back = calib.load(path)
        self.assertEqual(back, c)

    def test_wrong_schema_refused(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "c.json"
            path.write_text(json.dumps({"schema": 9}), encoding="utf-8")
            with self.assertRaises(ValueError):
                calib.load(path)

    def test_ece(self) -> None:
        self.assertIsNone(calib.ece([]))
        self.assertEqual(calib.ece([(1.0, True), (1.0, True)]), 0.0)
        self.assertEqual(calib.ece([(0.9, True), (0.9, False)]), 0.4)
        self.assertEqual(calib.ece([(0.95, True)] * 3), 0.05)


if __name__ == "__main__":
    unittest.main()
