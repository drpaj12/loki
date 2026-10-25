"""Shared helpers of the round-3 experiments: paths, run sets, loading of runs and ground truth.

Run sets are those of ``EXPERIMENT.md``. Round-2 runs are read where they are; the round-3 runs
(M3N, M3C, M1N) live under ``<LOKI_R3_DATA>/runs``.
"""

from __future__ import annotations

import csv
import json
import os
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from loki.score.gt import SCORED_TYPES, GtInstance, derive_instances
from loki.score.metrics import Pred, load_preds

HERE = Path(__file__).resolve().parent
WS = Path(os.environ.get("ODIN3_WS", str(HERE.parents[3])))
WORK = WS / "work"
R2DATA = Path(os.environ.get("LOKI_R2_DATA", str(WORK / "loki-exp2-data")))
DATA = Path(os.environ.get("LOKI_R3_DATA", str(WORK / "loki-exp3-data")))
MICRO = Path(os.environ.get("LOKI_MICRO", str(WORK / "loki-rename-exp" / "dataset-rebuild")))
VEVAL = Path(os.environ.get("LOKI_VEVAL", str(WORK / "loki-veval-exp" / "dataset")))
# Plain-gate GT word types (generic logic glue), used by the exploratory noise' class only.
PLAIN_GATES = frozenset({
    "$and", "$or", "$not", "$xor", "$xnor", "$logic_not", "$logic_and", "$logic_or",
    "$reduce_and", "$reduce_or", "$reduce_xor", "$reduce_bool",
})
HARD = frozenset({"hard_add", "hard_mul", "hard_mem"})
P_MIN = 0.5


@dataclass(frozen=True)
class RunSet:
    name: str
    dataset: Path
    floor: str
    root: Path  # run directories are <root>/<design>__<floor>/re


SETS: dict[str, RunSet] = {s.name: s for s in (
    RunSet("M2N", MICRO, "f2", R2DATA / "l1/runs/native-none"),
    RunSet("M2C", MICRO, "f2", R2DATA / "l1/runs/native-calib"),
    RunSet("V2N", VEVAL, "f2", R2DATA / "l2/runs/f2-none"),
    RunSet("V2C", VEVAL, "f2", R2DATA / "l2/runs/f2-calib"),
    RunSet("V3N", VEVAL, "f3", R2DATA / "l2/runs/f3-none"),
    RunSet("V3C", VEVAL, "f3", R2DATA / "l2/runs/f3-calib"),
    RunSet("M3N", MICRO, "f3", DATA / "runs/M3N"),
    RunSet("M3C", MICRO, "f3", DATA / "runs/M3C"),
    RunSet("M1N", MICRO, "f1-k6", DATA / "runs/M1N"),
)}


def run_designs(rs: RunSet) -> list[str]:
    """Designs of ``rs`` with an ``overlay.json`` (sorted)."""
    suffix = len(rs.floor) + 2
    return [p.parent.parent.name[:-suffix]
            for p in sorted(rs.root.glob(f"*__{rs.floor}/re/overlay.json"))]


def floor_dir(rs: RunSet, design: str) -> Path:
    return rs.dataset / design / rs.floor


def run_dir(rs: RunSet, design: str) -> Path:
    return rs.root / f"{design}__{rs.floor}" / "re"


def counted_preds(rs: RunSet, design: str) -> list[Pred]:
    """Counted candidates (committed, or live with p >= 0.5) of the construct kinds, hard kinds
    left out. Checks the total against the counted sum of ``score.json`` when it exists."""
    ov = json.loads((run_dir(rs, design) / "overlay.json").read_text(encoding="utf-8"))
    preds = [p for p in load_preds(ov)
             if p.kind in SCORED_TYPES and p.kind not in HARD and p.counted(P_MIN)]
    score = run_dir(rs, design) / "score.json"
    if score.is_file():
        s = json.loads(score.read_text(encoding="utf-8"))
        want = sum(int(v["counted"]) for k, v in s["constructs"].items() if k not in HARD)
        if want != len(preds):
            raise ValueError(f"{rs.name} {design}: counted {len(preds)} != score.json {want}")
    return preds


def read_words(rs: RunSet, design: str) -> dict[str, Any]:
    obj = json.loads((floor_dir(rs, design) / "words.json").read_text(encoding="utf-8"))
    assert isinstance(obj, dict)
    return obj


def gt_instances(rs: RunSet, design: str) -> list[GtInstance]:
    return derive_instances(read_words(rs, design))


def designs_of(dataset: Path, floor: str) -> list[str]:
    """Designs with an ok ``floor`` in the manifest (sorted)."""
    m = json.loads((dataset / "manifest.json").read_text(encoding="utf-8"))
    return sorted(str(e["design"]) for e in m["designs"]
                  if e["floors"].get(floor, {}).get("status") == "ok")


def write_csv(path: Path, header: Sequence[str], rows: Iterable[Sequence[Any]]) -> None:
    """Deterministic CSV: UTF-8, ``\\n`` line ends."""
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(header)
        w.writerows(rows)


def r6(x: float) -> float:
    return round(x, 6)
