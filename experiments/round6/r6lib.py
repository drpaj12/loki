"""Shared helpers of the round-6 scripts: paths, design sets, tables."""

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
DATA = Path(os.environ.get("LOKI_R6_DATA", str(WORK / "loki-exp6-data")))
AUDIT = Path(os.environ.get("LOKI_R6_AUDIT", str(DATA / "audit")))
C826 = Path(os.environ.get("ODIN3_ROOT", str(WORK / "odin3-c826")))
MICRO = Path(os.environ.get("LOKI_MICRO", str(WORK / "loki-rename-exp" / "dataset-rebuild")))
VEVAL = Path(os.environ.get("LOKI_VEVAL", str(WORK / "loki-veval-exp" / "dataset")))
VEVAL_SRC = Path(os.environ.get("LOKI_VEVAL_SRC", str(WORK / "loki-veval-exp" / "datasets" / "l0")))
CORPUS = Path(os.environ.get("LOKI_CORPUS", str(WORK / "loki-exp4-data" / "corpus")))
CORPUS_SRC = Path(os.environ.get(
    "LOKI_CORPUS_SRC", str(WORK / "loki-exp4-data" / "corpus-project" / "designs")))
CORPUS_CSV = Path(os.environ.get(
    "LOKI_CORPUS_CSV", str(WORK / "loki-exp4-data" / "corpus-project" / "corpus.csv")))
ARCH = Path(os.environ.get("ARCH", str(
    WS / "external/vtr-verilog-to-routing/vtr_flow/arch/timing"
    / "k6_frac_N10_frac_chain_mem32K_40nm.xml")))
SETS = ("MI", "VT", "CI")


def write_csv(path: Path, header: Sequence[str], rows: Iterable[Sequence[Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(header)
        w.writerows(rows)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def _ok(dataset: Path, split: str | None) -> list[str]:
    m = json.loads((dataset / "manifest.json").read_text(encoding="utf-8"))
    return sorted(
        str(e["design"]) for e in m["designs"]
        if e["floors"].get("f2", {}).get("status") == "ok"
        and (split is None or e["split"] == split)
    )


def design_set(name: str) -> list[tuple[str, list[Path], str]]:
    """(design, source files, top or '') of a set, in name order. Sizes are fixed by Stage 0."""
    out: list[tuple[str, list[Path], str]] = []
    if name == "MI":
        for d in _ok(MICRO, None):
            src = C826 / "tests/micro/verilog/micro" / f"{d.removeprefix('micro_')}.v"
            out.append((d, [src], ""))
    elif name == "VT":
        for d in _ok(VEVAL, "test"):
            root = VEVAL_SRC / "designs" / d
            meta = json.loads((root / "design.json").read_text(encoding="utf-8"))
            files = [root / f["path"] for f in meta["files"]]
            out.append((d, files, str(meta.get("top") or "")))
    elif name == "CI":
        iid = {r["design"] for r in read_csv(CORPUS_CSV) if r["split"] == "iid"}
        out = [(d, [CORPUS_SRC / d / f"{d}.v"], "") for d in _ok(CORPUS, None) if d in iid]
    else:
        raise ValueError(f"unknown set {name}")
    return out
