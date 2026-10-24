"""RQ-L2: run and score `loki re` on the 150 VerilogEval netlists (floors f2 and f3).

Calibration: `loki calibrate --floor <f> --split train` on the VerilogEval dataset itself (the
117 train designs), applied to all 150 (the 33 test designs are held out of the fit).

Usage:
  l2_run.py calibrate --floor f2|f3
  l2_run.py run   --floor f2|f3 --cond calib|none [--min-nodes A --max-nodes B] [--workers 3]
  l2_run.py score --floor f2|f3 --cond calib|none
  l2_run.py table
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import r2lib

from loki.schemas import dump_json
from loki.score.metrics import score_run

BASE = r2lib.DATA / "l2"
CALIB = BASE / "calib"


def run_dir(floor: str, cond: str, design: str) -> Path:
    return BASE / "runs" / f"{floor}-{cond}" / f"{design}__{floor}" / "re"


def designs(floor: str) -> list[tuple[str, int]]:
    return r2lib.test_designs(r2lib.VEVAL, floor, None)


def split_of() -> dict[str, str]:
    manifest = json.loads((r2lib.VEVAL / "manifest.json").read_text(encoding="utf-8"))
    return {str(e["design"]): str(e["split"]) for e in manifest["designs"]}


def calibrate(floor: str) -> int:
    CALIB.mkdir(parents=True, exist_ok=True)
    out = CALIB / f"{floor}.json"
    if out.is_file():
        print(f"exists {out}")
        return 0
    cmd = [sys.executable, "-m", "loki.cli", "calibrate", "--dataset", str(r2lib.VEVAL),
           "--floor", floor, "--split", "train", "--out", str(out)]
    return subprocess.run(cmd, check=False).returncode


def score_floor(floor: str, cond: str) -> int:
    n = 0
    for d, _nodes in designs(floor):
        rd = run_dir(floor, cond, d)
        if not (rd / "overlay.json").is_file():
            continue
        score = score_run(rd, r2lib.VEVAL / d / floor, 0.5)
        (rd / "score.json").write_text(dump_json(score), encoding="utf-8")
        n += 1
    print(f"scored {n} runs ({floor}-{cond})")
    return 0


def table() -> int:
    split = split_of()
    rows: list[list[Any]] = []
    for floor in ("f2", "f3"):
        for cond in ("calib", "none"):
            root = BASE / "runs" / f"{floor}-{cond}"
            scores = r2lib.load_scores(root.glob(f"*__{floor}/re/score.json"))
            for name in ("all", "test"):
                sel = {k: v for k, v in scores.items()
                       if name == "all" or split[k.rsplit("__", 1)[0]] == "test"}
                s = r2lib.summarise(sel)
                rows.append([f"{floor}-{cond}", name, s["runs"], s["counted"], s["matched"],
                             s["gt"], s["macro_f1"], s["macro_f1_all"], s["micro_f1"], s["ece"]])
    r2lib.write_csv(r2lib.OUT / "l2_loki_scores.csv",
                    ["set", "split", "runs", "counted", "matched", "gt", "macro_f1",
                     "macro_f1_all", "micro_f1", "ece"], rows)
    for r in rows:
        print(r)
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", choices=("calibrate", "run", "score", "table"))
    ap.add_argument("--floor", choices=("f2", "f3"))
    ap.add_argument("--cond", choices=("calib", "none"))
    ap.add_argument("--min-nodes", type=int, default=0)
    ap.add_argument("--max-nodes", type=int, default=10**9)
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--timeout", type=int, default=1800)
    ap.add_argument("--rp-min-p", default="", help="run into <cond>-rp<value> with this --rp-min-p")
    args = ap.parse_args()
    if args.stage == "table":
        return table()
    if args.stage == "calibrate":
        return calibrate(args.floor)
    tag = args.cond + (f"-rp{args.rp_min_p}" if args.rp_min_p else "")
    if args.stage == "score":
        return score_floor(args.floor, tag)
    calib = CALIB / f"{args.floor}.json" if args.cond == "calib" else None
    extra = ["--rp-min-p", args.rp_min_p] if args.rp_min_p else []
    jobs = [(f"{args.floor}-{tag} {d} {n}", r2lib.VEVAL / d / args.floor / "netlist.blif",
             args.floor, calib, run_dir(args.floor, tag, d))
            for d, n in designs(args.floor) if args.min_nodes <= n <= args.max_nodes]
    r2lib.run_many(jobs, args.workers, args.timeout, extra)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
