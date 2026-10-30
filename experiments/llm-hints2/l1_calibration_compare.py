"""A6: v1 against v2 calibration of Loki's own L1 claims on its micro benchmark (F3 floor).

v1 hints printed ``p_comp`` of a run with ``--calib none`` (default tables, not a posterior); v2
prints ``p_comp`` of a run with ``--calib calib/f3.json`` (fitted on the train split). The scores
are those of the F3 recovery experiment (15 test designs, all detectors; ``analysis-nocalib.json``
is v1, ``analysis.json`` is v2) read from the directory in ``LOKI_F3_SCORES`` or given as argument.
Usage: ``python -I l1_calibration_compare.py SCORES_DIR``. Writes ``l1_calibration_compare.csv``:
the expected calibration error of all counted claims and, per kind, claims counted, matched
against the L0 answer key, and precision.
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def load(path: Path) -> dict[str, object]:
    obj = json.loads(path.read_text(encoding="utf-8"))
    base: dict[str, object] = obj["variants"]["base"]
    return base


def main(argv: list[str]) -> int:
    root = Path(argv[0])
    v1, v2 = load(root / "analysis-nocalib.json"), load(root / "analysis.json")
    rows: list[dict[str, object]] = [
        {"scope": "all counted claims", "v1_counted": v1["counted"], "v1_matched": v1["matched"],
         "v1_precision": "", "v1_ece": v1["ece"], "v2_counted": v2["counted"],
         "v2_matched": v2["matched"], "v2_precision": "", "v2_ece": v2["ece"]}]
    kinds1, kinds2 = v1["kinds"], v2["kinds"]
    assert isinstance(kinds1, dict) and isinstance(kinds2, dict)
    for kind in sorted(kinds1):
        a, b = kinds1[kind], kinds2[kind]
        rows.append({
            "scope": kind, "v1_counted": a["counted"], "v1_matched": a["matched"],
            "v1_precision": "" if a["precision"] is None else a["precision"], "v1_ece": "",
            "v2_counted": b["counted"], "v2_matched": b["matched"],
            "v2_precision": "" if b["precision"] is None else b["precision"], "v2_ece": ""})
    with (HERE / "l1_calibration_compare.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, list(rows[0]), lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    for r in rows:
        print(r)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:] or ["."]))
