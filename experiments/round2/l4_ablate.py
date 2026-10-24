"""RQ-L4: which evidence family drives the calibrated posterior?

Families (``loki.re.bayes.family_of``): ``npn`` (npn_* features), ``wl`` (wl_* features and the
calibrated node table that yields ``wl_npn``), ``l2`` (l2_* features), ``struct`` (the rest).
`loki re` produces no ``l2_`` feature (they exist only in the ReverseProvenance document), which
the collect stage verifies; that family is reported as not applicable.

Stages (the first and third need Odin III: run them under the heavy lock):
  collect  run the DEFAULTS flow on every f2 train design of the micro dataset and of VerilogEval
           (``loki.score.calibrate.design_data``) and pickle the hypotheses and ground truth
  fit      refit the calibration with one family removed (``loki.score.calibrate.fit`` on the
           stripped data; the family's weight is set to 0), writing ``<data>/l4/calib/<name>.json``
  run      `loki re` on the f2 test designs of both datasets per ablation, then score
  table    macro-F1, micro-F1, ECE per ablation with a design bootstrap interval
"""

from __future__ import annotations

import argparse
import json
import pickle
import random
from dataclasses import replace
from pathlib import Path
from typing import Any, cast

import r2lib

from loki.re import bayes
from loki.re.bayes import family_of
from loki.re.loop import ReOptions
from loki.schemas import dump_json
from loki.score.calibrate import DesignData, NodeCounts, design_data, fit, write_calib
from loki.score.metrics import reliability, score_run

BASE = r2lib.DATA / "l4"
DATASETS = {"micro": r2lib.MICRO, "veval": r2lib.VEVAL}
FAMILIES = ("npn", "wl", "struct")
ABLATIONS: dict[str, tuple[str, ...]] = {
    "full": (), "drop-npn": ("npn",), "drop-wl": ("wl",), "drop-struct": ("struct",),
    "priors-only": FAMILIES,
}
FLOOR = "f2"


def split_designs(split: str) -> list[tuple[str, str, Path]]:
    """(dataset label, design, floor dir) of the ok f2 designs of ``split``."""
    out = []
    for label, root in DATASETS.items():
        manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
        for e in sorted(manifest["designs"], key=lambda e: str(e["design"])):
            info = e["floors"].get(FLOOR)
            if e["split"] == split and info is not None and info["status"] == "ok":
                out.append((label, str(e["design"]), root / e["design"] / FLOOR))
    return out


def collect() -> int:
    data: list[DesignData] = []
    for label, design, floor_dir in split_designs("train"):
        opts = ReOptions(
            netlist=floor_dir / "netlist.blif", floor=FLOOR, odin3_root=None, techlib=None,
            calib=None, seed=1, max_rounds=bayes.MAX_ROUNDS, timeout=30, time_budget=3600,
            detectors=None, commit=True, keep_levels=None, features="all")
        data.append(design_data(design, floor_dir, opts))
        print("collected", label, design, flush=True)
    BASE.mkdir(parents=True, exist_ok=True)
    with (BASE / "designdata.pkl").open("wb") as fh:
        pickle.dump(data, fh)
    fams: dict[str, int] = {}
    for d in data:
        for p in d.preds:
            for feat in p.features:
                fams[family_of(feat)] = fams.get(family_of(feat), 0) + 1
    (BASE / "feature_families.json").write_text(
        json.dumps(fams, sort_keys=True, indent=1) + "\n", encoding="utf-8")
    print("feature occurrences by family (DEFAULTS flow, train):", fams)
    return 0


def strip(d: DesignData, drop: tuple[str, ...]) -> DesignData:
    preds = [replace(p, features={k: v for k, v in p.features.items()
                                  if family_of(k) not in drop}) for p in d.preds]
    return replace(d, preds=preds, nodes=NodeCounts() if "wl" in drop else d.nodes)


def fit_all() -> int:
    with (BASE / "designdata.pkl").open("rb") as fh:
        data: list[DesignData] = pickle.load(fh)
    (BASE / "calib").mkdir(parents=True, exist_ok=True)
    for name, drop in ABLATIONS.items():
        obj = fit([strip(d, drop) for d in data], FLOOR, "round2-micro+veval", "train")
        weights = dict(cast(dict[str, float], obj["weights"]))
        for fam in drop:
            weights[fam] = 0.0
        obj["weights"] = dict(sorted(weights.items()))
        if "wl" in drop:
            obj["node_llr"] = {}
        write_calib(obj, BASE / "calib" / f"{name}.json")
        ece = cast(dict[str, Any], obj["reliability"])["ece"]
        print("fitted", name, "weights", obj["weights"], "ece", ece)
    return 0


def run_dir(name: str, design: str) -> Path:
    return BASE / "runs" / name / f"{design}__{FLOOR}" / "re"


def run_all(workers: int) -> int:
    jobs = []
    for name in (*ABLATIONS, "none"):
        calib = None if name == "none" else BASE / "calib" / f"{name}.json"
        for label, design, floor_dir in split_designs("test"):
            jobs.append((f"{name} {label} {design}", floor_dir / "netlist.blif", FLOOR, calib,
                         run_dir(name, design)))
    r2lib.run_many(jobs, workers, 1800)
    for name in (*ABLATIONS, "none"):
        n = 0
        for _label, design, floor_dir in split_designs("test"):
            rd = run_dir(name, design)
            if (rd / "overlay.json").is_file():
                (rd / "score.json").write_text(dump_json(score_run(rd, floor_dir, 0.5)),
                                               encoding="utf-8")
                n += 1
        print("scored", name, n)
    return 0


def design_f1(score: dict[str, Any]) -> tuple[int, int, int]:
    c = score["constructs"]
    return (sum(int(v["counted"]) for v in c.values()), sum(int(v["matched"]) for v in c.values()),
            sum(int(v["gt"]) for v in c.values()))


def boot_micro_f1(rows: list[tuple[int, int, int]], n: int = 2000) -> tuple[float, float]:
    rng = random.Random(20261024)
    vals = []
    for _ in range(n):
        s = [rows[rng.randrange(len(rows))] for _ in rows]
        counted, matched, gt = (sum(x[i] for x in s) for i in range(3))
        vals.append(2 * matched / (counted + gt) if counted + gt else 0.0)
    vals.sort()
    return vals[int(0.025 * n)], vals[int(0.975 * n)]


def auc(points: list[tuple[float, bool]]) -> float | None:
    """Rank AUC of ``p_comp`` against the match label over all live hypotheses (ties count 1/2)."""
    pos = [p for p, y in points if y]
    neg = [p for p, y in points if not y]
    if not pos or not neg:
        return None
    wins = 0.0
    for p in pos:
        wins += sum(1.0 if p > q else 0.5 if p == q else 0.0 for q in neg)
    return wins / (len(pos) * len(neg))


def table() -> int:
    rows: list[list[Any]] = []
    kinds: list[list[Any]] = []
    for name in ("none", *ABLATIONS):
        scores = r2lib.load_scores((BASE / "runs" / name).glob(f"*__{FLOOR}/re/score.json"))
        s = r2lib.summarise(scores)
        per = [design_f1(v) for v in scores.values()]
        lo, hi = boot_micro_f1(per)
        pts = [(float(p), bool(y)) for v in scores.values() for pl in v["points"].values()
               for p, y in pl]
        a = auc(pts)
        rows.append([name, s["runs"], s["counted"], s["matched"], s["gt"], s["macro_f1"],
                     s["macro_f1_all"], s["micro_f1"], round(lo, 6), round(hi, 6),
                     reliability(pts)["ece"] if pts else None, len(pts),
                     sum(1 for _p, y in pts if y), None if a is None else round(a, 6)])
        for kind, k in s["kinds"].items():
            kinds.append([name, kind, k["counted"], k["matched"], k["gt"], k["precision"],
                          k["recall"], k["f1"]])
    r2lib.write_csv(r2lib.OUT / "l4_ablation.csv",
                    ["ablation", "runs", "counted", "matched", "gt", "macro_f1", "macro_f1_all",
                     "micro_f1", "micro_f1_lo", "micro_f1_hi", "ece", "points", "true_points",
                     "auc"], rows)
    wrows = []
    for name in ABLATIONS:
        w = json.loads((BASE / "calib" / f"{name}.json").read_text(encoding="utf-8"))["weights"]
        wrows.append([name, *(w.get(f, "") for f in FAMILIES)])
    r2lib.write_csv(r2lib.OUT / "l4_weights.csv", ["ablation", *FAMILIES], wrows)
    r2lib.write_csv(r2lib.OUT / "l4_kinds.csv",
                    ["ablation", "kind", "counted", "matched", "gt", "precision", "recall", "f1"],
                    kinds)
    for r in rows:
        print(r)
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", choices=("collect", "fit", "run", "table"))
    ap.add_argument("--workers", type=int, default=3)
    args = ap.parse_args()
    if args.stage == "collect":
        return collect()
    if args.stage == "fit":
        return fit_all()
    if args.stage == "run":
        return run_all(args.workers)
    return table()


if __name__ == "__main__":
    raise SystemExit(main())
