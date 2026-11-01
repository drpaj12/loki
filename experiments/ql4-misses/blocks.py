"""Blocks of cells: partitions the detectors compared and true blocks cut out by the answer key.

A cell is the index of a BLIF logic element (``.names``, ``.latch`` or ``.subckt``). A block is a set of
cell indices; ports are not cells. Partition blocks use the cone definitions of
experiments/graphlets/partitions.py (unbounded: fan-in closure through flip-flops; bounded: stops at
other groups). True blocks come from the labels of an Odin III build (``module_path`` = ``.../u<idx>``).
"""

from __future__ import annotations

import csv
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "graphlets"))
import partitions as pt  # noqa: E402

from loki.l3.netlist import Netlist, _logical_lines, _subckt  # noqa: E402


@dataclass
class Blif:
    """Cells in file order: ``outs[i]`` and ``ins[i]`` are net names, ``cname[i]`` the label or ''."""

    ins: list[list[str]] = field(default_factory=list)
    outs: list[list[str]] = field(default_factory=list)
    cname: list[str] = field(default_factory=list)
    latch: list[bool] = field(default_factory=list)
    inputs: set[str] = field(default_factory=set)
    producer: dict[str, int] = field(default_factory=dict)

    @classmethod
    def read(cls, path: Path) -> Blif:
        b = cls()
        for tok in _logical_lines(path.read_text(encoding="utf-8", errors="replace")):
            head = tok[0]
            if head == ".inputs":
                b.inputs.update(tok[1:])
            elif head == ".names" and len(tok) >= 2:
                b._add(tok[1:-1], [tok[-1]], False)
            elif head == ".latch" and len(tok) >= 3:
                b._add([tok[1]], [tok[2]], True)
            elif head == ".subckt" and len(tok) >= 2:
                ins, outs = _subckt(tok)
                b._add(ins, outs, False)
            elif head == ".cname" and len(tok) >= 2 and b.cname:
                b.cname[-1] = tok[1]
        return b

    def _add(self, ins: list[str], outs: list[str], latch: bool) -> None:
        i = len(self.outs)
        self.ins.append(ins)
        self.outs.append(outs)
        self.cname.append("")
        self.latch.append(latch)
        for o in outs:
            self.producer[o] = i

    @property
    def n(self) -> int:
        return len(self.outs)

    def cells_of_nets(self, nets: set[str]) -> set[int]:
        return {self.producer[n] for n in nets if n in self.producer}

    def n_latches(self, block: set[int]) -> int:
        return sum(1 for i in block if self.latch[i])


def unbounded_block(b: Blif, qs: list[str]) -> set[int]:
    """Fan-in closure of the group's flip-flop outputs through every cell and flip-flop."""
    seen: set[str] = set()
    todo = list(qs)
    while todo:
        net = todo.pop()
        if net in seen:
            continue
        seen.add(net)
        i = b.producer.get(net)
        if i is not None:
            todo.extend(b.ins[i])
    return b.cells_of_nets(seen)


def bounded_block(b: Blif, nl: Netlist, groups: list[list[str]], gi: int) -> set[int]:
    other = {q: g for g, qs in enumerate(groups) for q in qs}
    nets, _links = pt.bounded_cone(nl, groups[gi], other)
    return b.cells_of_nets(nets)


def module_ranges(sv: Path, problems: dict[int, str]) -> dict[int, tuple[int, int]]:
    """Part index -> (first, last) source line of its module ``P<problem>`` in the composite file."""
    spans: dict[str, tuple[int, int]] = {}
    start: dict[str, int] = {}
    for n, line in enumerate(sv.read_text(encoding="utf-8").splitlines(), start=1):
        m = re.match(r"module\s+P(\w+)", line)
        if m:
            start[m.group(1)] = n
        elif line.startswith("endmodule") and start:
            name = max(start, key=lambda k: start[k])
            spans[name] = (start.pop(name), n)
    return {i: spans[p] for i, p in problems.items() if p in spans}


def part_blocks(b: Blif, labels: Path, ranges: dict[int, tuple[int, int]]
                ) -> tuple[dict[int, set[int]], dict[int, int]]:
    """Part index -> its cells, and part index -> number of cells attributed by source line.

    A cell belongs to part k when its ``module_path`` is ``.../u<k>``; a cell with a mixed or
    top-level label is attributed by the source line of its first span (module ``P<problem>`` of the
    part); other cells (top-level wiring, ports) belong to no part."""
    by_cname = {c: i for i, c in enumerate(b.cname) if c}
    out: dict[int, set[int]] = {}
    by_line: dict[int, int] = {}
    with labels.open(encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            i = by_cname.get(row["node_id"])
            if i is None or row["kind"] in ("pi", "po"):
                continue
            m = re.search(r"/u(\d+)(?:/|$)", row["module_path"])
            if m:
                out.setdefault(int(m.group(1)), set()).add(i)
                continue
            line = int(row["hdl_line"] or 0)
            for k, (lo, hi) in ranges.items():
                if lo <= line <= hi:
                    out.setdefault(k, set()).add(i)
                    by_line[k] = by_line.get(k, 0) + 1
                    break
    return out, by_line


def jaccard(p: set[int], t: set[int]) -> tuple[float, float]:
    """(Jaccard, coverage = share of the true block inside p)."""
    if not t:
        return 0.0, 0.0
    inter = len(p & t)
    union = len(p | t)
    return (inter / union if union else 0.0), inter / len(t)


def block_nodes(b: Blif, block: set[int]) -> tuple[list[str], list[str]]:
    """Output nets of the block's cells, and primary-input nets feeding it (for the cells file)."""
    outs = sorted(o for i in block for o in b.outs[i])
    pis = sorted({n for i in block for n in b.ins[i] if n not in b.producer and n in b.inputs})
    return outs, pis
