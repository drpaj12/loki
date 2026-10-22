"""L1 exit test (spec 15): ``loki re`` on the L0 micro subset at floor F2, ``--calib none``.

Needs ``LOKI_DATASET`` (an assembled L0 dataset with the micros, docs/runbook-l1.md). The
twelfth subset design of L0, the FSM fixture ``micro_fsm2``, is not a dataset design and is not
part of this run.
"""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

from loki.re import bayes
from loki.re.main import main as re_main
from loki.score.gt import SCORED_TYPES, derive_instances, load_gt, read_labels
from loki.score.metrics import construct_matches, load_preds
from tests.helpers import odin3_root, odin_available

SUBSET = (
    "bm_DL_2_1_mux", "bm_DL_4_bit_comparator", "bm_DL_four_bit_adder_continuous_assign",
    "bm_DL_4_bit_shift_register", "bm_DL_Dff_w_synch_reset", "bm_DL_D_flipflop", "bm_my_D_latch1",
    "bm_base_multiply", "bm_DL_74381_ALU", "bm_DL_BCD_adder", "bm_dag1_mod",
)
DATASET = os.environ.get("LOKI_DATASET", "")
IDENTITY_SKIP = ("timing.json",)
# The byte-identity second pass runs in a fresh interpreter (spec 15 item 1: a hash-order
# dependent output must show up as a difference, and one process has one PYTHONHASHSEED).
_RE_MAIN = "from loki.re.main import main; import sys; raise SystemExit(main(sys.argv[1:]))"
HASH_SEED = "12345"


def _read(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _live(overlay: Any, kind: str) -> list[Any]:
    return [h for h in overlay["hypotheses"] if h["kind"] == kind]


@unittest.skipUnless(
    odin_available() and odin3_root() is not None and DATASET, "needs Odin III and LOKI_DATASET"
)
class AcceptanceL1Test(unittest.TestCase):
    out: Path
    again: Path
    tmp: tempfile.TemporaryDirectory[str]

    @classmethod
    def setUpClass(cls) -> None:
        cls.tmp = tempfile.TemporaryDirectory(prefix="loki-l1-acc-")
        root = Path(cls.tmp.name)
        cls.out, cls.again = root / "a", root / "b"
        for name in SUBSET:
            did = f"micro_{name}"
            net = Path(DATASET) / did / "f2" / "netlist.blif"
            args = [str(net), "--floor", "f2", "--calib", "none"]
            rc = re_main([*args, "--out", str(cls.out / did)])
            assert rc == 0, f"{did}: loki re exit {rc}"
            env = dict(os.environ, PYTHONHASHSEED=HASH_SEED)
            proc = subprocess.run(
                [sys.executable, "-c", _RE_MAIN, *args, "--out", str(cls.again / did)],
                capture_output=True, text=True, env=env, check=False,
            )
            assert proc.returncode == 0, (
                f"{did}: loki re exit {proc.returncode}: {proc.stderr[-400:]}"
            )

    @classmethod
    def tearDownClass(cls) -> None:
        cls.tmp.cleanup()

    def overlay(self, name: str) -> Any:
        return _read(self.out / f"micro_{name}" / "overlay.json")

    def floor(self, name: str) -> Path:
        return Path(DATASET) / f"micro_{name}" / "f2"

    def test_1_equivalent_and_byte_identical(self) -> None:
        for name in SUBSET:
            did = f"micro_{name}"
            report = _read(self.out / did / "report.json")
            self.assertEqual(report["final_equiv"]["status"], "equivalent", did)
            files = sorted(p.name for p in (self.out / did).iterdir())
            self.assertEqual(files, sorted(p.name for p in (self.again / did).iterdir()))
            for f in files:
                if f in IDENTITY_SKIP:
                    continue
                self.assertEqual(
                    (self.out / did / f).read_bytes(), (self.again / did / f).read_bytes(),
                    f"{did}/{f}",
                )

    def test_2_adder(self) -> None:
        name = "bm_DL_four_bit_adder_continuous_assign"
        ov = self.overlay(name)
        committed = [h for h in ov["hypotheses"]
                     if h["kind"] in ("adder", "adder_cin") and h["status"] == "committed"
                     and h["params"].get("width") == 4]
        self.assertTrue(committed)
        self.assertTrue(all(h["proof"]["verdict"] == "equivalent" for h in committed))
        # The micro is gate-level (fulladd modules of ``^ & |``): L0 holds no ``$add`` word, so the
        # match is against the logic nodes of the design (spec 15 item 2, deviation).
        logic = {r["node_id"] for r in read_labels(self.floor(name)) if r["kind"] == "lut"}
        best = max(len(set(h["cells"]) & logic) / len(set(h["cells"]) | logic) for h in committed)
        self.assertGreaterEqual(best, 0.5)

    def test_3_mux(self) -> None:
        name = "bm_DL_2_1_mux"
        ov = self.overlay(name)
        committed = [h for h in _live(ov, "mux") if h["status"] == "committed"]
        self.assertTrue(committed)
        gts = [g for g in derive_instances(_read(self.floor(name) / "words.json"))
               if g.type in SCORED_TYPES["mux"]]
        preds = [p for p in load_preds(ov) if p.id in {h["id"] for h in committed}]
        self.assertTrue(construct_matches(preds, gts))

    def test_4_comparator(self) -> None:
        ov = self.overlay("bm_DL_4_bit_comparator")
        proved = [h for h in _live(ov, "comparator")
                  if h["proof"] is not None and h["proof"]["verdict"] == "equivalent"]
        self.assertTrue(proved)

    def test_5_shift_register(self) -> None:
        ov = self.overlay("bm_DL_4_bit_shift_register")
        shifts = [h for h in _live(ov, "shift_reg")
                  if h["params"].get("width") == 4 and h["status"] in ("committed", "confirmed")]
        self.assertTrue(shifts)

    def test_6_sync_reset(self) -> None:
        name = "bm_DL_Dff_w_synch_reset"
        ov = self.overlay(name)
        ffs = [r["node_id"] for r in read_labels(self.floor(name))
               if r["kind"] == "ff" and r["construct_type"] == "$sdff"]
        self.assertTrue(ffs)
        srst = [h for h in _live(ov, "ff_srst") if h["status"] not in ("rejected", "refuted")]
        for ff in ffs:
            mine = [h for h in srst if ff in h["cells"]]
            self.assertTrue(mine, ff)
            # Spec constants (prior 0, rst_fanout "1" bin -1.10) give p = 0.25 for a lone reset:
            # the plan's p_comp >= 0.5 needs calibrated priors, so only "not rejected" is pinned.
            self.assertTrue(all(h["p_comp"] >= bayes.REJECT_P for h in mine))

    def test_7_no_transfer_failures(self) -> None:
        for name in SUBSET:
            report = _read(self.out / f"micro_{name}" / "report.json")
            self.assertEqual(report["features"]["transfer_failures"], 0, name)

    def test_ground_truth_loads(self) -> None:
        for name in SUBSET:
            load_gt(self.floor(name))


if __name__ == "__main__":
    unittest.main()
