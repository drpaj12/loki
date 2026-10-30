"""Shared paths and loaders of the L3 detector experiment."""

from __future__ import annotations

import csv
import json
import os
import random
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
RES = HERE / "results"
CENSUS_RES = HERE.parent / "l3-census" / "results"
WS = Path(os.environ.get("L3_WS", str(HERE.parent.parent.parent.parent)))
CENSUS = WS / "work" / "l3-out"
OUT = WS / "work" / "l3d-out"
CELLS = ("O-gate", "O-lut", "O-hard", "Y-gate", "Y-lut")
FLOORS = {"O-gate": "f3", "O-lut": "f2", "O-hard": "f1-k6"}
TARGET = {"O-gate": "gate", "O-lut": "lut", "O-hard": "lut+hard", "Y-gate": "gate",
          "Y-lut": "lut"}
ENTRIES = ("fsm", "counter", "shift", "lfsr", "timer", "regfile", "register", "glue")


def netlist_path(root: Path, cell: str, design: str) -> Path:
    if cell in FLOORS:
        return root / "build" / cell / design / FLOORS[cell] / "netlist.blif"
    return root / "build" / cell / design / "netlist.blif"


def intent_path(root: Path, cell: str, design: str) -> Path:
    return root / "re" / cell / design / "intent.json"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def write_csv(path: Path, cols: list[str], rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, cols, lineterminator="\n", extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def load_claims(path: Path) -> list[dict[str, Any]]:
    claims: list[dict[str, Any]] = json.loads(path.read_text(encoding="utf-8"))["claims"]
    return claims


def bootstrap(pairs: list[tuple[int, int, int]], n: int = 2000) -> tuple[float, float]:
    """Lower 5th percentile of precision and recall over resampled designs;
    ``pairs`` holds (TP, FP, FN) per design."""
    rng = random.Random(1)
    prec: list[float] = []
    rec: list[float] = []
    for _ in range(n):
        s = [pairs[rng.randrange(len(pairs))] for _ in pairs]
        tp, fp, fn = (sum(x[i] for x in s) for i in range(3))
        prec.append(tp / (tp + fp) if tp + fp else 1.0)
        rec.append(tp / (tp + fn) if tp + fn else 1.0)
    prec.sort()
    rec.sort()
    k = int(0.05 * n)
    return prec[k], rec[k]


def label(point_p: float, point_r: float, lo_p: float, lo_r: float, n_pos: int,
          thr: float = 0.80) -> str:
    """The plan's rule: WORKING / INCONCLUSIVE / NOT WORKING."""
    if point_p < thr or point_r < thr:
        return "NOT WORKING" if n_pos >= 5 else "INCONCLUSIVE"
    if n_pos < 5 or lo_p < thr or lo_r < thr:
        return "INCONCLUSIVE"
    return "WORKING"
