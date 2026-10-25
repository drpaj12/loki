"""Shared helpers of the round-4 scripts: paths, split tables, per-design scoring rows.

Paths come from environment variables with workspace-relative defaults: ``ODIN3_WS`` (the
directory that holds ``work/``), ``LOKI_R4_DATA`` (round-4 data, default
``$ODIN3_WS/work/loki-exp4-data``), ``LOKI_MICRO`` and ``LOKI_VEVAL`` as in round 3.
"""

from __future__ import annotations

import csv
import json
import os
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
WS = Path(os.environ.get("ODIN3_WS", str(HERE.parents[3])))
WORK = WS / "work"
DATA = Path(os.environ.get("LOKI_R4_DATA", str(WORK / "loki-exp4-data")))
R2DATA = Path(os.environ.get("LOKI_R2_DATA", str(WORK / "loki-exp2-data")))
MICRO = Path(os.environ.get("LOKI_MICRO", str(WORK / "loki-rename-exp" / "dataset-rebuild")))
VEVAL = Path(os.environ.get("LOKI_VEVAL", str(WORK / "loki-veval-exp" / "dataset")))
CORPUS = Path(os.environ.get("LOKI_CORPUS", str(DATA / "corpus")))
TWINS = Path(os.environ.get("LOKI_TWINS", str(DATA / "twins")))
OUT = HERE
FLOORS = ("f2", "f3")


def write_csv(path: Path, header: Sequence[str], rows: Iterable[Sequence[Any]]) -> None:
    """Deterministic CSV: UTF-8, ``\\n`` line ends."""
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(header)
        w.writerows(rows)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def r6(x: float) -> float:
    return round(x, 6)


def manifest(dataset: Path) -> dict[str, Any]:
    obj = json.loads((dataset / "manifest.json").read_text(encoding="utf-8"))
    assert isinstance(obj, dict)
    return obj


def ok_designs(dataset: Path, floor: str, split: str | None = None) -> list[str]:
    """Designs with an ok ``floor`` (sorted), optionally of one manifest split."""
    out = []
    for e in manifest(dataset)["designs"]:
        if e["floors"].get(floor, {}).get("status") != "ok":
            continue
        if split is None or e["split"] == split:
            out.append(str(e["design"]))
    return sorted(out)


def corpus_split() -> dict[str, tuple[str, str]]:
    """design -> (family, split) with split in train, iid, ood (``corpus.csv``)."""
    rows = read_csv(DATA / "corpus-project" / "corpus.csv")
    return {r["design"]: (r["family"], r["split"]) for r in rows}


def eval_sets(floor: str) -> dict[str, list[tuple[Path, str]]]:
    """The evaluation sets of RQ-L12b: (dataset, design) pairs per set name."""
    cs = corpus_split()
    ok = set(ok_designs(CORPUS, floor))
    out: dict[str, list[tuple[Path, str]]] = {
        "iid": [(CORPUS, d) for d in sorted(ok) if cs[d][1] == "iid"],
        "ood": [(CORPUS, d) for d in sorted(ok) if cs[d][1] == "ood"],
        "micro": [(MICRO, d) for d in ok_designs(MICRO, floor)],
        "vetest": [(VEVAL, d) for d in ok_designs(VEVAL, floor, "test")],
    }
    return out
