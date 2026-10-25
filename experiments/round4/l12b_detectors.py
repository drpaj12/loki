"""RQ-L12b detector arms: new ``loki re`` runs on the corpus test split (f2) and per-design rows.

Usage: l12b_detectors.py calibrate | run | score | rows   (run under the heavy lock)
Arms: N = uncalibrated, C = calibrated (corpus train, f2). Real-design arms are the existing
round-2 sets (``r3lib.SETS``): M2N/M2C/V2N/V2C at f2, M3N/M3C/V3N/V3C at f3, restricted to the
designs of the evaluation sets of ``r4lib.eval_sets``.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import dictlib
import r2lib
import r3lib
import r4lib

from loki.schemas import dump_json
from loki.score.metrics import score_run

RUNS = r4lib.DATA / "runs"
CALIB = r4lib.DATA / "calib" / "f2.json"
REAL = {("micro", "f2"): ("M2N", "M2C"), ("micro", "f3"): ("M3N", "M3C"),
        ("vetest", "f2"): ("V2N", "V2C"), ("vetest", "f3"): ("V3N", "V3C")}


def corpus_run_dir(arm: str, design: str) -> Path:
    return RUNS / f"{arm}-f2" / f"{design}__f2" / "re"


def corpus_test() -> list[str]:
    sets = r4lib.eval_sets("f2")
    return [d for _, d in sets["iid"] + sets["ood"]]


def calibrate() -> int:
    CALIB.parent.mkdir(parents=True, exist_ok=True)
    if CALIB.is_file():
        return 0
    cmd = [sys.executable, "-m", "loki.cli", "calibrate", "--dataset", str(r4lib.CORPUS),
           "--floor", "f2", "--split", "train", "--out", str(CALIB)]
    return subprocess.run(cmd, check=False).returncode


def run(workers: int = 3) -> int:
    designs = corpus_test()
    for arm, calib in (("N", None), ("C", CALIB)):
        jobs = [(f"{arm} {d}", r4lib.CORPUS / d / "f2" / "netlist.blif", "f2", calib,
                 corpus_run_dir(arm, d)) for d in designs]
        r2lib.run_many(jobs, workers, 900)
    return 0


def score() -> int:
    n = 0
    for arm in ("N", "C"):
        for d in corpus_test():
            rd = corpus_run_dir(arm, d)
            if (rd / "overlay.json").is_file():
                s = score_run(rd, r4lib.CORPUS / d / "f2", 0.5)
                (rd / "score.json").write_text(dump_json(s), encoding="utf-8")
                n += 1
    print("scored", n)
    return 0


def _rows_of(arm: str, floor: str, sname: str, design: str, path: Path) -> list[list[Any]]:
    if not path.is_file():
        return []
    sc = json.loads(path.read_text(encoding="utf-8"))["constructs"]
    out = []
    for k in dictlib.KDICT:
        v = sc.get(k)
        if v and (v["counted"] or v["gt"]):
            out.append([arm, floor, sname, design, k, v["counted"], v["matched"], v["gt"]])
    return out


def rows() -> int:
    out: list[list[Any]] = []
    for floor in r4lib.FLOORS:
        sets = r4lib.eval_sets(floor)
        for (sname, fl), (n_arm, c_arm) in REAL.items():
            if fl != floor:
                continue
            for arm_name, label in ((n_arm, "det-N"), (c_arm, "det-C")):
                rs = r3lib.SETS[arm_name]
                for _, d in sets[sname]:
                    out += _rows_of(label, floor, sname, d, r3lib.run_dir(rs, d) / "score.json")
        if floor == "f2":
            for sname in ("iid", "ood"):
                for _, d in sets[sname]:
                    for arm in ("N", "C"):
                        out += _rows_of(f"det-{arm}", floor, sname, d,
                                        corpus_run_dir(arm, d) / "score.json")
    r4lib.write_csv(r4lib.OUT / "l12b_det_rows.csv",
                    ["arm", "floor", "set", "design", "kind", "counted", "matched", "gt"],
                    sorted(out, key=lambda r: (r[0], r[1], r[2], r[3], r[4])))
    print(len(out), "rows")
    return 0


def main() -> int:
    stage = sys.argv[1] if len(sys.argv) > 1 else ""
    fn = {"calibrate": calibrate, "run": run, "score": score, "rows": rows}.get(stage)
    if fn is None:
        raise SystemExit(__doc__)
    return fn()


if __name__ == "__main__":
    raise SystemExit(main())
