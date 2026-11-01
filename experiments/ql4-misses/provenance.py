"""Construct types (Odin III provenance) of the true blocks of structure misses and absent
constructs: ``python -B provenance.py`` after ql4_run.py and report.py.

Writes results/structure_provenance.csv: per detector, class and family, the construct types
(``construct_type`` of the labels) of the cells of the true block, as shares of those cells. Only
the three Odin III cells carry labels.
"""

from __future__ import annotations

import csv
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import blocks as bl  # noqa: E402
import l3dlib  # noqa: E402
import report as rp  # noqa: E402

RES = HERE / "results"
CLASSES = ("structure miss", "absent")
TOP = 6


def true_rows(r: dict[str, Any]) -> list[dict[str, str]]:
    """Label rows of the cells of the true block of one record."""
    kind, design, cell = r["set"], r["design"], r["cell"]
    root = l3dlib.CENSUS if kind == "single" else l3dlib.OUT
    net = l3dlib.netlist_path(root, cell, design)
    labels = net.parent / "labels.csv"
    with labels.open(encoding="utf-8", newline="") as fh:
        rows = [x for x in csv.DictReader(fh) if x["kind"] not in ("pi", "po")]
    if kind == "single":
        return rows
    b = bl.Blif.read(net)
    truth = json.loads((root / "composites" / design / "truth.json").read_text(encoding="utf-8"))
    ranges = bl.module_ranges(root / "composites" / design / f"{design}.sv",
                              {p["idx"]: p["problem"] for p in truth["parts"]})
    parts, _ = bl.part_blocks(b, labels, ranges)
    names = {b.cname[i] for i in parts.get(int(r["part"]), set())}
    return [x for x in rows if x["node_id"] in names]


def main() -> int:
    recs = [r for r in rp.read_records() if r["detector"] in ("D70", "D71c")
            and r["class"] in CLASSES and r["cell"].startswith("O-")]
    seen: set[tuple[str, str, str, str, str]] = set()
    agg: dict[tuple[str, str, str], Counter[str]] = defaultdict(Counter)
    cells: dict[tuple[str, str, str], int] = defaultdict(int)
    nconst: dict[tuple[str, str, str], int] = defaultdict(int)
    for r in recs:
        key = (r["class"], r["family"], r["cell"])
        uid = (r["class"], r["set"], r["design"], r["cell"], str(r["part"]))
        if uid in seen:
            continue
        seen.add(uid)
        nconst[key] += 1
        for x in true_rows(r):
            agg[key][x["construct_type"]] += 1
            cells[key] += 1
    out = []
    for key in sorted(agg):
        for t, n in agg[key].most_common(TOP):
            out.append({"class": key[0], "family": key[1], "cell": key[2],
                        "constructs": nconst[key], "true_cells": cells[key],
                        "construct_type": t, "cells": n, "share": round(n / cells[key], 3)})
    rp.write("structure_provenance.csv", out)
    print(len(out), "rows;", len(seen), "constructs")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
