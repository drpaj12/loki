import json
import unittest
from pathlib import Path

from loki.rp.build import natural_key, num, sorted_names
from loki.schemas import validate_reverse_provenance
from tests.helpers import can_run_f2
from tests.rp_fixtures import ADD2, FSM2, fsm_run, run_re

FILE = "reverse-provenance.json"


def load(out: Path) -> dict[str, object]:
    obj = json.loads((out / FILE).read_text(encoding="utf-8"))
    assert isinstance(obj, dict)
    return obj


class HelpersTest(unittest.TestCase):
    def test_natural_order(self) -> None:
        self.assertEqual(sorted_names(["g10", "g2", "a"]), ["a", "g2", "g10"])
        self.assertEqual(sorted_names(["g2", "g2"]), ["g2", "g2"])
        self.assertLess(natural_key("n9"), natural_key("n10"))

    def test_num_format(self) -> None:
        self.assertEqual(num(0.1234567), 0.123457)
        self.assertEqual(num(float("inf")), "inf")
        self.assertEqual(num(float("-inf")), "-inf")

    def test_validator_rejects_bad_objects(self) -> None:
        self.assertTrue(validate_reverse_provenance([]))
        errs = validate_reverse_provenance({"schema": 2})
        self.assertIn("rp: schema must be 1", errs)
        self.assertIn("rp: missing key 'header'", errs)


@unittest.skipUnless(can_run_f2(), "needs Odin III, ABC and an F2 architecture")
class RealRunTest(unittest.TestCase):
    def test_arithmetic_validates(self) -> None:
        rp = load(run_re(ADD2))
        self.assertEqual(validate_reverse_provenance(rp), [])
        els = rp["elements"]
        assert isinstance(els, list)
        adder = next(e for e in els if e["kind"] == "adder")
        self.assertEqual(adder["status"], "committed")
        self.assertEqual(adder["fn"], "Y = A + B")
        self.assertEqual(adder["proof"]["label"], "equivalent")
        self.assertEqual(adder["recovered"]["module"], "adder_h1")
        self.assertEqual(adder["cells"], ["n10", "n11", "n12"])

    def test_header_and_coverage(self) -> None:
        rp = load(run_re(ADD2))
        head = rp["header"]
        assert isinstance(head, dict)
        self.assertEqual(head["commit_threshold"], 0.9)
        self.assertEqual(head["candidate_threshold"], 0.5)
        self.assertEqual(len(head["input"]["sha256"]), 64)
        cov = rp["coverage"]
        assert isinstance(cov, dict)
        self.assertEqual(cov["cells_total"], 4)
        self.assertEqual(cov["committed"]["cells"] + cov["uncovered"]["cells"], 4)

    def test_hid_matches_inline_attribute(self) -> None:
        out = run_re(ADD2)
        design = (out / "design.v").read_text(encoding="utf-8")
        rp = load(out)
        els = rp["elements"]
        assert isinstance(els, list)
        for e in els:
            if e["status"] == "committed" and e["recovered"]["form"] != "attrs":
                self.assertIn(f'loki_hid = "{e["id"]}"', design)

    def test_fsm_candidate_block(self) -> None:
        rp = load(fsm_run())
        self.assertEqual(validate_reverse_provenance(rp), [])
        fsms = rp["fsms"]
        assert isinstance(fsms, list)
        self.assertEqual([f["states"] for f in fsms], [3, 4])
        self.assertEqual(fsms[0]["state_nets"], ["n6", "n7", "n5"])

    def test_rp_min_p_filters_candidates(self) -> None:
        low = load(fsm_run())["elements"]
        high = load(run_re(FSM2))["elements"]
        assert isinstance(low, list) and isinstance(high, list)
        self.assertGreater(len(low), len(high))

    def test_deterministic(self) -> None:
        a = run_re(ADD2)
        b = run_re(ADD2, tag="again")
        self.assertEqual((a / FILE).read_bytes(), (b / FILE).read_bytes())


if __name__ == "__main__":
    unittest.main()
