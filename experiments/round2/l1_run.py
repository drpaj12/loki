"""RQ-L1: run and score L1 on the LUT6 re-mapped f3 netlists and on the native f2 floor.

Sets:  lut     the f3 gate netlist re-mapped to LUT6 (l1_lutmap.py), read as floor f2; scored
               against the f3 answer key after each LUT is expanded to the gates it covers
       native  the f2 floor of the same design (the L0 dataset's own LUT6 netlist)
Conditions: calib (micro-fit f2 calibration, experiments/rename-l2/calib/f2.json) and none.

Usage:
  l1_run.py run   --set lut|native --cond calib|none --min-nodes A --max-nodes B [--workers 3]
  l1_run.py score --set lut|native --cond calib|none
  l1_run.py table                      (writes l1_summary.csv and l1_kinds.csv)
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import r2lib

from loki.schemas import dump_json
from loki.score.metrics import score_run

CALIB = Path(__file__).resolve().parents[1] / "rename-l2" / "calib" / "f2.json"
RUNS = r2lib.DATA / "l1" / "runs"
LUT = r2lib.DATA / "l1" / "lut"
TRANSLATED = Path("/tmp/claude-1000/le2-translated")


def designs() -> list[tuple[str, int, str]]:
    """(design, f3 nodes, split) for every design with an f3 floor, smallest first."""
    manifest = json.loads((r2lib.MICRO / "manifest.json").read_text(encoding="utf-8"))
    out = [(str(e["design"]), int(e["floors"]["f3"]["nodes"]), str(e["split"]))
           for e in manifest["designs"] if e["floors"].get("f3", {}).get("status") == "ok"]
    return sorted(out, key=lambda x: (x[1], x[0]))


def run_dir(set_: str, cond: str, design: str) -> Path:
    return RUNS / f"{set_}-{cond}" / f"{design}__f2" / "re"


def netlist(set_: str, design: str) -> Path:
    if set_ == "lut":
        return LUT / design / "f2" / "netlist.blif"
    return r2lib.MICRO / design / "f2" / "netlist.blif"


def expand(obj: Any, cover: dict[str, list[str]], netmap: dict[str, str], key: str = "") -> Any:
    """Translate a ``cells`` list to gate cnames and a ``nets`` mapping to f3 net names."""
    if isinstance(obj, dict):
        return {k: expand(v, cover, netmap, k) for k, v in obj.items()}
    if isinstance(obj, list):
        if key == "cells":
            return sorted({g for c in obj for g in cover.get(c, [c])})
        if key in ("nets", "slice") or key.startswith("slice") or key in ("d", "q", "rst"):
            return [netmap.get(n, n) if isinstance(n, str) else n for n in obj]
        return [expand(v, cover, netmap, key) for v in obj]
    return obj


def translate_report(report: dict[str, Any], cover: dict[str, list[str]]) -> dict[str, Any]:
    """Expand the cell lists of the committed pieces."""
    out = dict(report)
    out["pieces"] = [
        {**p, "cells": sorted({g for c in p["cells"] for g in cover.get(c, [c])})}
        for p in report.get("pieces", [])
    ]
    return out


def translate_overlay(overlay: dict[str, Any], cover: dict[str, list[str]],
                      netmap: dict[str, str]) -> dict[str, Any]:
    hyps = []
    for h in overlay["hypotheses"]:
        g = dict(h)
        g["cells"] = sorted({x for c in h["cells"] for x in cover.get(c, [c])})
        g["nets"] = {k: [netmap.get(n, n) for n in v] for k, v in h.get("nets", {}).items()}
        hyps.append(g)
    return {**overlay, "hypotheses": hyps}


def score_set(set_: str, cond: str) -> int:
    n = 0
    for d, _nodes, _split in designs():
        rd = run_dir(set_, cond, d)
        if not (rd / "overlay.json").is_file():
            continue
        target = rd
        if set_ == "lut":
            info = json.loads((LUT / d / "cover.json").read_text(encoding="utf-8"))
            tdir = TRANSLATED / f"{set_}-{cond}" / d
            tdir.mkdir(parents=True, exist_ok=True)
            ov = json.loads((rd / "overlay.json").read_text(encoding="utf-8"))
            rp = json.loads((rd / "report.json").read_text(encoding="utf-8"))
            (tdir / "overlay.json").write_text(
                json.dumps(translate_overlay(ov, info["cover"], info["netmap"])), encoding="utf-8")
            (tdir / "report.json").write_text(
                json.dumps(translate_report(rp, info["cover"])), encoding="utf-8")
            target, floor = tdir, "f3"
        else:
            floor = "f2"
        score = score_run(target, r2lib.MICRO / d / floor, 0.5)
        (rd / "score.json").write_text(dump_json(score), encoding="utf-8")
        n += 1
    print(f"scored {n} runs ({set_}-{cond})")
    return 0


def summaries() -> dict[str, Any]:
    split = {d: s for d, _n, s in designs()}
    out: dict[str, Any] = {}
    for set_ in ("lut", "native"):
        for cond in ("calib", "none"):
            root = RUNS / f"{set_}-{cond}"
            scores = r2lib.load_scores(root.glob("*__f2/re/score.json"))
            for name, subset in (("test", "test"), ("all", None)):
                sel = {k: v for k, v in scores.items()
                       if subset is None or split[k.removesuffix("__f2")] == subset}
                out[f"{set_}-{cond}-{name}"] = r2lib.summarise(sel)
    return out


def table() -> int:
    summ = summaries()
    rows = []
    kinds = []
    for label, s in summ.items():
        rows.append([label, s["runs"], s["counted"], s["matched"], s["gt"], s["macro_f1"],
                     s["macro_f1_all"], s["micro_f1"], s["ece"]])
        for kind, row in s["kinds"].items():
            kinds.append([label, kind, row["counted"], row["matched"], row["gt"],
                          row["precision"], row["recall"], row["f1"]])
    f3exp = Path("/home/jamiespa/odin3-ws/work/loki-f3-exp")
    for label, sub in (("gate-calib-test", "runs"), ("gate-none-test", "runs-nocalib")):
        s = r2lib.summarise(r2lib.load_scores((f3exp / sub / "base").glob("*__f3/re/score.json")))
        summ[label] = s
        rows.append([label, s["runs"], s["counted"], s["matched"], s["gt"], s["macro_f1"],
                     s["macro_f1_all"], s["micro_f1"], s["ece"]])
        for kind, row in s["kinds"].items():
            kinds.append([label, kind, row["counted"], row["matched"], row["gt"],
                          row["precision"], row["recall"], row["f1"]])
    r2lib.write_csv(r2lib.OUT / "l1_summary.csv",
                    ["set", "runs", "counted", "matched", "gt", "macro_f1", "macro_f1_all",
                     "micro_f1", "ece"], rows)
    r2lib.write_csv(r2lib.OUT / "l1_kinds.csv",
                    ["set", "kind", "counted", "matched", "gt", "precision", "recall", "f1"], kinds)
    for r in rows:
        print(r)
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", choices=("run", "score", "table"))
    ap.add_argument("--set", choices=("lut", "native"))
    ap.add_argument("--cond", choices=("calib", "none"))
    ap.add_argument("--min-nodes", type=int, default=0)
    ap.add_argument("--max-nodes", type=int, default=10**9)
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--timeout", type=int, default=3600)
    args = ap.parse_args()
    if args.stage == "table":
        return table()
    if args.stage == "score":
        return score_set(args.set, args.cond)
    calib = CALIB if args.cond == "calib" else None
    jobs = [(f"{args.set}-{args.cond} {d} {n}", netlist(args.set, d), "f2", calib,
             run_dir(args.set, args.cond, d))
            for d, n, _s in designs() if args.min_nodes <= n <= args.max_nodes]
    r2lib.run_many(jobs, args.workers, args.timeout)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
