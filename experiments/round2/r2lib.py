"""Shared helpers of the round-2 experiments: score aggregation, run driver, CSV writing.

``summarise`` follows the f3-recovery analysis (experiments/f3-recovery/tools/analyze_f3.py):
kind precision/recall are micro sums over the designs; ``macro_f1`` averages the F1 of kinds that
have ground truth and at least one counted prediction (the protocol), ``macro_f1_all`` averages
over every kind with ground truth, counting a silent kind as 0; ``micro_f1`` is
2 matched / (counted + gt).
"""

from __future__ import annotations

import csv
import hashlib
import json
import os
import subprocess
import sys
import time
from collections import defaultdict
from collections.abc import Iterable, Sequence
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

from loki.score.metrics import reliability

# Workspace layout: <ws>/work/<this worktree>/experiments/round2; override with ODIN3_WS.
WS = Path(os.environ.get("ODIN3_WS", str(Path(__file__).resolve().parents[4])))
WORK = WS / "work"
ODIN3_ROOT = Path(os.environ.get("ODIN3_ROOT", str(WS / "odin3")))
DATA = Path(os.environ.get("LOKI_R2_DATA", str(WORK / "loki-exp2-data")))
TMP = Path(os.environ.get("LOKI_R2_TMP", str(Path(os.environ.get("TMPDIR", "/tmp")) / "le2")))
GB = WORK / "gatebreaker-exp2"
MICRO = WORK / "loki-rename-exp" / "dataset-rebuild"
VEVAL = WORK / "loki-veval-exp" / "dataset"
OUT = Path(__file__).resolve().parent


def f1(prec: float | None, rec: float | None) -> float | None:
    if prec is None or rec is None:
        return None
    return 0.0 if prec + rec == 0 else 2 * prec * rec / (prec + rec)


def r6(x: float | None) -> float | None:
    return None if x is None else round(x, 6)


def load_scores(paths: Iterable[Path]) -> dict[str, dict[str, Any]]:
    """``score.json`` objects keyed by the run name (``<design>__<floor>``) two levels up."""
    return {p.parent.parent.name: json.loads(p.read_text(encoding="utf-8"))
            for p in sorted(paths)}


HARD = frozenset({"hard_add", "hard_mul", "hard_mem"})


def summarise(scores: dict[str, dict[str, Any]], skip: frozenset[str] = HARD) -> dict[str, Any]:
    """Aggregates over ``scores``; the kinds in ``skip`` stay in ``kinds`` but are left out of the
    totals and both macro averages (the hard kinds share their word types with ``adder`` and
    ``mul`` and need a hard cell no LUT or gate floor holds)."""
    kinds: dict[str, dict[str, int]] = defaultdict(lambda: {"counted": 0, "matched": 0, "gt": 0})
    points: list[tuple[float, bool]] = []
    bus = {"counted": 0, "matched": 0, "gt": 0}
    for score in scores.values():
        for kind, data in score["constructs"].items():
            for key in ("counted", "matched", "gt"):
                kinds[kind][key] += int(data[key])
        for key in bus:
            bus[key] += int(score["bus"][key])
        for plist in score["points"].values():
            points += [(float(p), bool(y)) for p, y in plist]
    table: dict[str, Any] = {}
    f_proto: list[float] = []
    f_all: list[float] = []
    for kind, row in sorted(kinds.items()):
        prec = row["matched"] / row["counted"] if row["counted"] else None
        rec = row["matched"] / row["gt"] if row["gt"] else None
        f = f1(prec, rec)
        table[kind] = {**row, "precision": r6(prec), "recall": r6(rec), "f1": r6(f)}
        if row["gt"] and kind not in skip:
            f_all.append(f if f is not None else 0.0)
            if f is not None:
                f_proto.append(f)
    live = [v for k, v in kinds.items() if k not in skip]
    counted = sum(v["counted"] for v in live)
    matched = sum(v["matched"] for v in live)
    gt = sum(v["gt"] for v in live)
    return {
        "runs": len(scores), "kinds": table,
        "macro_f1": r6(sum(f_proto) / len(f_proto)) if f_proto else 0.0,
        "macro_f1_all": r6(sum(f_all) / len(f_all)) if f_all else 0.0,
        "micro_f1": r6(2 * matched / (counted + gt)) if counted + gt else 0.0,
        "counted": counted, "matched": matched, "gt": gt, "bus": bus,
        "ece": reliability(points)["ece"] if points else None,
    }


def digest(paths: Iterable[Path]) -> str:
    h = hashlib.sha256()
    for p in sorted(paths):
        h.update(p.parent.parent.name.encode())
        h.update(p.read_bytes())
    return h.hexdigest()


def run_re(netlist: Path, floor: str, calib: Path | None, out: Path, timeout: int,
           extra: Sequence[str] = ()) -> dict[str, Any]:
    """One ``loki re`` subprocess; skipped when ``report.json`` exists (restartable)."""
    if (out / "report.json").is_file():
        return {"status": "exists"}
    out.parent.mkdir(parents=True, exist_ok=True)
    cmd = [sys.executable, "-m", "loki.cli", "re", str(netlist), "--floor", floor,
           "--calib", "none" if calib is None else str(calib), "--out", str(out), *extra]
    start = time.monotonic()
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return {"status": "timeout", "seconds": timeout}
    seconds = round(time.monotonic() - start, 1)
    status = "ok" if proc.returncode in (0, 1) else f"error {proc.returncode}"
    if proc.returncode not in (0, 1):
        out.mkdir(parents=True, exist_ok=True)
        (out / "stderr.txt").write_text(proc.stderr[-4000:], encoding="utf-8")
    report = out / "report.json"
    equiv = "missing"
    if report.is_file():
        equiv = json.loads(report.read_text(encoding="utf-8"))["final_equiv"]["status"]
    return {"status": status, "seconds": seconds, "equiv": equiv}


def run_many(jobs: Sequence[tuple[str, Path, str, Path | None, Path]], workers: int,
             timeout: int, extra: Sequence[str] = ()) -> None:
    """Run ``(label, netlist, floor, calib, out)`` jobs on ``workers`` threads, in order."""
    def one(job: tuple[str, Path, str, Path | None, Path]) -> str:
        label, netlist, floor, calib, out = job
        res = run_re(netlist, floor, calib, out, timeout, extra)
        return f"{label} {json.dumps(res)}"

    with ThreadPoolExecutor(max_workers=workers) as pool:
        for line in pool.map(one, jobs):
            print(line, flush=True)


def write_csv(path: Path, header: Sequence[str], rows: Iterable[Sequence[object]]) -> None:
    """Deterministic CSV: UTF-8, ``\\n`` line ends."""
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(header)
        w.writerows(rows)


def test_designs(dataset: Path, floor: str, split: str | None) -> list[tuple[str, int]]:
    """Designs with a built ``floor`` (smallest node count first), optionally one split."""
    manifest = json.loads((dataset / "manifest.json").read_text(encoding="utf-8"))
    out = []
    for e in manifest["designs"]:
        info = e["floors"].get(floor)
        ok = info is not None and info.get("status") == "ok"
        if ok and (split is None or e["split"] == split):
            out.append((str(e["design"]), int(info["nodes"])))
    return sorted(out, key=lambda x: (x[1], x[0]))
