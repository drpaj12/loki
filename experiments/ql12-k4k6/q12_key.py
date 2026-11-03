"""Answer key at the flip-flop level from the Odin III provenance of the LUT netlist.

``labels.csv`` of the census build has, per cell (node id = the ``.cname`` of the BLIF cell), the
construct type and the HDL line and column of its construct. A key construct is a set of at least 2
flip-flops (``kind`` ``ff``) with the same construct type, line and column. The join is on the
cell name (no name guess, unlike the gate netlists of Q-L10). A block is right for a construct
when it holds at least 0.8 of its flip-flops and the Jaccard index of the two sets is at least 0.5
(the right-block rule of #72 to #78 on flip-flops).
"""

from __future__ import annotations

import csv
from collections import defaultdict
from typing import Any

import q12_nl as nlm
from q12_nl import Netlist

MIN_FF = 2


def key_constructs(nl: Netlist, endpoint: str, problem: str) -> list[frozenset[int]]:
    """Flip-flop sets (cell indices) of the key constructs; [] when there is no label file."""
    path = nlm.census_dir(endpoint, problem) / "labels.csv"
    if not path.is_file():
        return []
    cell_of = {c.cname: c.idx for c in nl.cells if c.kind == "ff" and c.cname}
    groups: dict[tuple[str, str, str], set[int]] = defaultdict(set)
    with path.open(encoding="utf-8", newline="") as fh:
        for r in csv.DictReader(fh):
            if r["kind"] == "ff" and r["node_id"] in cell_of:
                groups[(r["construct_type"], r["hdl_line"], r["hdl_col"])].add(
                    cell_of[r["node_id"]])
    return [frozenset(g) for _k, g in sorted(groups.items()) if len(g) >= MIN_FF]


def is_right(block_ffs: frozenset[int], true: frozenset[int]) -> bool:
    inter = len(block_ffs & true)
    return bool(inter / len(true) >= 0.8 and inter / len(block_ffs | true) >= 0.5)


def right_blocks(nl: Netlist, blocks: list[Any], cons: list[frozenset[int]]) -> list[list[int]]:
    """Per construct, the ids of the blocks that are right for it."""
    ffs = {b.bid: frozenset(c for c in b.cells if nl.cells[c].kind == "ff") for b in blocks}
    return [[bid for bid, f in ffs.items() if f and is_right(f, true)] for true in cons]
