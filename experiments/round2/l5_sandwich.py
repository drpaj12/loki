"""RQ-L5: the must/may bracket as an uncertainty measure.

From each run's ``reverse-provenance.json``: ``must`` = cells of committed elements (proved and
raised), ``may`` = must plus the cells of candidate elements (live, ``p_comp >= --rp-min-p``).
Bracket width = candidate fraction of the cells. Per design:
  H5a  Spearman correlation of width with the design's construct F1 (2 matched / (counted + gt),
       designs with ground truth only), and of the committed and uncovered fractions as controls.
  Soundness  with T the union of the scored ground-truth footprints: must precision |M & T| / |M|,
       may recall |U & T| / |T| (does the upper bracket contain the truth) and must recall.
Runs are read from ``<data>/l2/runs/<set>`` (VerilogEval) and ``<data>/l1/runs/native-<cond>``
(micro f2).  Writes ``l5_corr.csv`` and ``l5_soundness.csv``.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import r2lib
from scipy.stats import spearmanr

from loki.score.gt import SCORED_TYPES, load_gt

SETS: dict[str, tuple[Path, str, Path]] = {
    "l2-f2-calib": (r2lib.DATA / "l2" / "runs" / "f2-calib", "f2", r2lib.VEVAL),
    "l2-f2-calib-rp0.1": (r2lib.DATA / "l2" / "runs" / "f2-calib-rp0.1", "f2", r2lib.VEVAL),
    "l2-f2-none": (r2lib.DATA / "l2" / "runs" / "f2-none", "f2", r2lib.VEVAL),
    "l2-f3-none": (r2lib.DATA / "l2" / "runs" / "f3-none", "f3", r2lib.VEVAL),
    "l1-native-calib": (r2lib.DATA / "l1" / "runs" / "native-calib", "f2", r2lib.MICRO),
    "l1-native-none": (r2lib.DATA / "l1" / "runs" / "native-none", "f2", r2lib.MICRO),
}


def read(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def design_row(run: Path, floor_dir: Path, rp_min_p: float) -> dict[str, Any] | None:
    rp = read(run / "reverse-provenance.json")
    score = read(run / "score.json")
    cons = score["constructs"].values()
    counted = sum(int(c["counted"]) for c in cons)
    matched = sum(int(c["matched"]) for c in cons)
    gt = sum(int(c["gt"]) for c in cons)
    cov = rp["coverage"]
    must: set[str] = set()
    cand: set[str] = set()
    for e in rp["elements"]:
        status = e.get("status", "")
        if status == "committed":
            must.update(e["cells"])
        elif status == "candidate" and float(e["p_comp"]) >= rp_min_p:
            cand.update(e["cells"])
    truth: set[str] = set()
    for inst in load_gt(floor_dir)[0]:
        if inst.type in {t for ts in SCORED_TYPES.values() for t in ts}:
            truth |= inst.footprint
    upper = must | cand
    return {
        "gt": gt, "f1": 2 * matched / (counted + gt) if gt else None,
        "width": float(cov["candidate"]["fraction"]),
        "must": float(cov["committed"]["fraction"]),
        "uncovered": float(cov["uncovered"]["fraction"]),
        "must_n": len(must), "upper_n": len(upper), "truth_n": len(truth),
        "must_in_truth": len(must & truth), "truth_in_upper": len(truth & upper),
        "truth_in_must": len(truth & must),
    }


def rho(rows: list[dict[str, Any]], key: str) -> tuple[float | None, float | None, int]:
    sel = [r for r in rows if r["f1"] is not None]
    xs, ys = [r[key] for r in sel], [r["f1"] for r in sel]
    if len(sel) < 3 or len(set(xs)) < 2 or len(set(ys)) < 2:
        return None, None, len(sel)
    res = spearmanr(xs, ys)
    return round(float(res.statistic), 6), round(float(res.pvalue), 6), len(sel)


def main() -> int:
    corr: list[list[Any]] = []
    sound: list[list[Any]] = []
    for label, (root, floor, dataset) in SETS.items():
        rows = []
        for rd in sorted(root.glob(f"*__{floor}/re")):
            if not (rd / "score.json").is_file() or not (rd / "reverse-provenance.json").is_file():
                continue
            design = rd.parent.name.rsplit("__", 1)[0]
            minp = 0.1 if label.endswith("rp0.1") else 0.5
            row = design_row(rd, dataset / design / floor, minp)
            if row is not None:
                rows.append(row)
        if not rows:
            continue
        for key in ("width", "must", "uncovered"):
            r, p, n = rho(rows, key)
            corr.append([label, key, n, r, p, sum(1 for x in rows if x["width"] > 0)])
        s = {k: sum(int(r[k]) for r in rows) for k in
             ("must_n", "upper_n", "truth_n", "must_in_truth", "truth_in_upper", "truth_in_must")}
        sound.append([label, len(rows), s["must_n"], s["must_in_truth"],
                      round(s["must_in_truth"] / s["must_n"], 6) if s["must_n"] else "",
                      s["truth_n"], s["truth_in_must"],
                      round(s["truth_in_must"] / s["truth_n"], 6) if s["truth_n"] else "",
                      s["upper_n"], s["truth_in_upper"],
                      round(s["truth_in_upper"] / s["truth_n"], 6) if s["truth_n"] else ""])
    r2lib.write_csv(r2lib.OUT / "l5_corr.csv",
                    ["set", "variable", "designs_with_gt", "spearman", "p", "designs_width_gt0"],
                    corr)
    r2lib.write_csv(r2lib.OUT / "l5_soundness.csv",
                    ["set", "designs", "must_cells", "must_in_truth", "must_precision",
                     "truth_cells", "truth_in_must", "must_recall", "upper_cells",
                     "truth_in_upper", "may_recall"], sound)
    for line in corr + sound:
        print(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
