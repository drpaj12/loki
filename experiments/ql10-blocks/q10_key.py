"""Answer key at the state-element level from the Odin III provenance of the reference.

The veval-L0 dataset (``experiments/veval-l0``; archive ``loki-veval-exp.tar.xz``, f3 floor) has,
per cell, the HDL span of its construct and, for registers and port drivers, the RTL signal name
(``bus_name``, ``bit_index``). A key construct is the set of flip-flops of the Gate-Breaker netlist
whose output net is named ``bus[bit]`` (or ``bus`` for a scalar) by the cells of one construct
(same ``construct_type`` and HDL line and column); only constructs of 2 or more matched flip-flops
count. This is a name join, not a cell join: combinational cells have no key. A block is right for
a construct when it holds at least 0.8 of the construct's flip-flops and the Jaccard index of the
two flip-flop sets is at least 0.5 (the right-block rule of #72 to #78 on flip-flops).
"""

from __future__ import annotations

import csv
import os
from collections import defaultdict
from pathlib import Path

import q10_env as env
from q10_blocks import Block
from q10_nl import Netlist

VEVAL = Path(os.environ.get("QL10_VEVAL", str(env.RUN / "veval" / "loki-veval-exp" / "dataset")))
MIN_FF = 2
SKIP_KINDS = ("pi", "po", "const")


def labels_path(problem: str) -> Path:
    return VEVAL / f"ve_{problem}" / "f3" / "labels.csv"


def key_constructs(nl: Netlist, problem: str) -> list[frozenset[int]]:
    """Flip-flop sets (netlist cell indices) of the key constructs; [] when there is no key."""
    path = labels_path(problem)
    if not path.is_file():
        return []
    ff_of = {c.out: c.idx for c in nl.cells if c.typ.startswith("DFF")}
    groups: dict[tuple[str, str, str], set[int]] = defaultdict(set)
    with path.open(encoding="utf-8", newline="") as fh:
        for r in csv.DictReader(fh):
            if r["kind"] in SKIP_KINDS or not r["bus_name"]:
                continue
            bus, bit = r["bus_name"], int(r["bit_index"])
            for name in ((f"{bus}[{bit}]", bus) if bit == 0 else (f"{bus}[{bit}]",)):
                if name in ff_of:
                    groups[(r["construct_type"], r["hdl_line"], r["hdl_col"])].add(ff_of[name])
                    break
    return [frozenset(g) for _k, g in sorted(groups.items()) if len(g) >= MIN_FF]


def is_right(block_ffs: frozenset[int], true: frozenset[int]) -> bool:
    inter = len(block_ffs & true)
    return bool(inter / len(true) >= 0.8 and inter / len(block_ffs | true) >= 0.5)


def right_blocks(nl: Netlist, blocks: list[Block], cons: list[frozenset[int]]
                 ) -> list[list[int]]:
    """Per construct, the ids of the blocks that are right for it."""
    ffs = {b.bid: frozenset(c for c in b.cells if nl.cells[c].typ.startswith("DFF"))
           for b in blocks}
    return [[b.bid for b in blocks if ffs[b.bid] and is_right(ffs[b.bid], t)] for t in cons]
