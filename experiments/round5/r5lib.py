"""Shared helpers of the round-5 scripts: paths, sets, arms, run driver, scoring.

Paths come from environment variables with workspace-relative defaults: ``ODIN3_WS`` (the
directory that holds ``work/``), ``LOKI_R5_DATA`` (default ``$ODIN3_WS/work/loki-exp5-data``);
the earlier-round variables of ``r4lib`` and ``r3lib`` apply to the reused data.
"""

from __future__ import annotations

import csv
import hashlib
import json
import os
import random
import subprocess
import sys
import time
from collections.abc import Iterable, Sequence
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
WS = Path(os.environ.get("ODIN3_WS", str(HERE.parents[3])))
WORK = WS / "work"
DATA = Path(os.environ.get("LOKI_R5_DATA", str(WORK / "loki-exp5-data")))
R4DATA = Path(os.environ.get("LOKI_R4_DATA", str(WORK / "loki-exp4-data")))
R2DATA = Path(os.environ.get("LOKI_R2_DATA", str(WORK / "loki-exp2-data")))
R3DATA = Path(os.environ.get("LOKI_R3_DATA", str(WORK / "loki-exp3-data")))
MICRO = Path(os.environ.get("LOKI_MICRO", str(WORK / "loki-rename-exp" / "dataset-rebuild")))
VEVAL = Path(os.environ.get("LOKI_VEVAL", str(WORK / "loki-veval-exp" / "dataset")))
CORPUS = Path(os.environ.get("LOKI_CORPUS", str(R4DATA / "corpus")))
BIGDIR = Path(os.environ.get("LOKI_BIG", str(R4DATA / "big")))
OUT = HERE

WF_DETECTORS = "wordfirst"
WB_DETECTORS = "wordfirst,hard,ff_pattern,mux,arith,seqfn,fsm,bus,unit,role,wordgroup"
# W1, WB1: the same detector lists with the Stage-0 FSM rule (``LOKI_WF_FSM_RULE=stage0``), run by
# ``run_arms.py variants``; exploratory (review fixes), no status uses them.
ARMS = {"W": WF_DETECTORS, "WB": WB_DETECTORS, "W1": WF_DETECTORS, "WB1": WB_DETECTORS}
KDICT = ("ff_en", "ff_srst", "register", "adder", "subtractor", "comparator", "eq_const", "mux",
         "mux_tree", "counter", "fsm")
HARD = frozenset({"hard_add", "hard_mul", "hard_mem"})


def write_csv(path: Path, header: Sequence[str], rows: Iterable[Sequence[Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(header)
        w.writerows(rows)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def r6(x: float) -> float:
    return round(x, 6)


def seed_rng(*parts: object) -> random.Random:
    h = hashlib.sha256(":".join(str(p) for p in parts).encode()).hexdigest()
    return random.Random(int(h[:16], 16))


def manifest(dataset: Path) -> dict[str, Any]:
    obj = json.loads((dataset / "manifest.json").read_text(encoding="utf-8"))
    assert isinstance(obj, dict)
    return obj


def ok_designs(dataset: Path, floor: str, split: str | None = None) -> list[str]:
    out = []
    for e in manifest(dataset)["designs"]:
        if e["floors"].get(floor, {}).get("status") != "ok":
            continue
        if split is None or e["split"] == split:
            out.append(str(e["design"]))
    return sorted(out)


def corpus_split() -> dict[str, tuple[str, str]]:
    rows = read_csv(R4DATA / "corpus-project" / "corpus.csv")
    return {r["design"]: (r["family"], r["split"]) for r in rows}


def eval_sets(floor: str) -> dict[str, list[tuple[Path, str]]]:
    """(dataset, design) pairs per evaluation set (EXPERIMENT.md)."""
    cs = corpus_split()
    ok = ok_designs(CORPUS, floor)
    return {
        "MI": [(MICRO, d) for d in ok_designs(MICRO, floor)],
        "VT": [(VEVAL, d) for d in ok_designs(VEVAL, floor, "test")],
        "CI": [(CORPUS, d) for d in ok if cs[d][1] == "iid"],
        "CO": [(CORPUS, d) for d in ok if cs[d][1] == "ood"],
    }


def run_dir(arm: str, set_name: str, floor: str, design: str) -> Path:
    return DATA / "runs" / f"{arm}-{set_name}-{floor}" / f"{design}__{floor}" / "re"


def run_one(label: str, netlist: Path, floor: str, detectors: str, out: Path,
            dataset: Path, design: str, timeout: int, features: str) -> str:
    """One ``loki re`` run scored in the same call; skipped when ``score.json`` exists."""
    if (out / "score.json").is_file():
        return f"{label} exists"
    out.parent.mkdir(parents=True, exist_ok=True)
    cmd = [sys.executable, "-m", "loki.cli", "re", str(netlist), "--floor", floor, "--calib",
           "none", "--detectors", detectors, "--features", features, "--out", str(out),
           "--score-dataset", str(dataset), "--score-design", design]
    start = time.monotonic()
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        (out.parent / "timeout.txt").write_text(str(timeout), encoding="utf-8")
        return f"{label} timeout"
    sec = round(time.monotonic() - start, 2)
    if not (out / "score.json").is_file():
        (out.parent / "stderr.txt").write_text(proc.stderr[-3000:], encoding="utf-8")
        return f"{label} error {proc.returncode}"
    (out.parent / "seconds.txt").write_text(str(sec), encoding="utf-8")
    return f"{label} ok {sec}"


def run_jobs(jobs: Sequence[tuple[str, Path, str, str, Path, Path, str, int, str]],
             workers: int) -> None:
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for line in pool.map(lambda j: run_one(*j), jobs):
            print(line, flush=True)


def summarise(scores: Iterable[dict[str, Any]]) -> dict[str, dict[str, int]]:
    kinds: dict[str, dict[str, int]] = {}
    for s in scores:
        for k, v in s["constructs"].items():
            row = kinds.setdefault(k, {"counted": 0, "matched": 0, "gt": 0})
            for key in row:
                row[key] += int(v[key])
    return kinds
