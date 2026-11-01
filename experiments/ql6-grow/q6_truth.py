"""Units (design x cell), their graph, and the answer-key constructs and blocks.

Singles: the whole design is one construct of the design's family (glue included, as a training
kind). Composites: parts of family fsm, counter or shift (timer and lfsr merged, as in #69 to #72)
cut out by the Odin III provenance labels; only the three Odin III cells have labels. The key is
the same as in experiments/ql4-misses (blocks.part_blocks).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Any

from q6_env import KINDS, MERGE, bl, l3dlib, mod
from q6_net import Graph

me = mod("match_eval")
O_CELLS = ("O-gate", "O-lut", "O-hard")
PART_KINDS = ("fsm", "counter", "shift")


@dataclass
class Construct:
    idx: int  # part index (0 for a single)
    kind: str
    cells: frozenset[int]


@dataclass
class Unit:
    set: str  # single | comp
    design: str
    cell: str
    split: str
    net: Path

    @property
    def key(self) -> tuple[str, str, str]:
        return (self.set, self.design, self.cell)


@cache
def _family() -> dict[str, str]:
    return me.truth_family()


def units(split: str, cells: tuple[str, ...] = tuple(l3dlib.CELLS)) -> list[Unit]:
    out: list[Unit] = []
    fam = _family()
    for r in l3dlib.read_csv(l3dlib.RES / "split_single.csv"):
        if r["split"] != split or r["design"] not in fam:
            continue
        for c in cells:
            p = l3dlib.netlist_path(l3dlib.CENSUS, c, r["design"])
            if p.is_file():
                out.append(Unit("single", r["design"], c, split, p))
    for r in l3dlib.read_csv(l3dlib.RES / "composites.csv"):
        if r["split"] != split:
            continue
        for c in cells:
            p = l3dlib.netlist_path(l3dlib.OUT, c, r["name"])
            if p.is_file():
                out.append(Unit("comp", r["name"], c, split, p))
    return out


def has_labels(u: Unit) -> bool:
    return u.set == "single" or u.cell in O_CELLS


def constructs(u: Unit, g: Graph) -> list[Construct]:
    """Answer-key constructs of one unit (empty when the unit has no provenance)."""
    if u.set == "single":
        kind = MERGE.get(_family()[u.design], _family()[u.design])
        return [Construct(0, kind, frozenset(range(g.b.n)))]
    if u.cell not in O_CELLS:
        return []
    root = l3dlib.OUT
    truth = json.loads((root / "composites" / u.design / "truth.json").read_text(
        encoding="utf-8"))
    ranges = bl.module_ranges(root / "composites" / u.design / f"{u.design}.sv",
                              {p["idx"]: p["problem"] for p in truth["parts"]})
    parts = bl.part_blocks(g.b, u.net.parent / "labels.csv", ranges)[0]
    out = []
    for p in truth["parts"]:
        for f in p["families"]:
            kind = MERGE.get(f, f)
            if kind in PART_KINDS:
                out.append(Construct(p["idx"], kind, frozenset(parts.get(p["idx"], set()))))
    return out


def cell_kinds(u: Unit, g: Graph) -> list[str]:
    """Kind of every cell: its construct's kind, 'mixed' for a cell in two, 'top' for none."""
    lab = ["top"] * g.b.n
    if u.set == "single":
        return [constructs(u, g)[0].kind] * g.b.n
    for c in constructs(u, g):
        for i in c.cells:
            lab[i] = c.kind if lab[i] in ("top", c.kind) else "mixed"
    return lab


def known_kind(k: str) -> bool:
    return k in KINDS


def split_of_design(rows: list[dict[str, Any]]) -> dict[str, str]:
    return {r["design"]: r["split"] for r in rows}
