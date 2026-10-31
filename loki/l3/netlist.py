"""Small BLIF graph for L3: cells, flip-flops, constants and bounded forward reach."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from pathlib import Path

OUT_PINS = ("out", "sumout", "cout", "o", "y", "q")


def _logical_lines(text: str) -> list[list[str]]:
    rows: list[list[str]] = []
    pending = ""
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].rstrip()
        if line.endswith("\\"):
            pending += line[:-1] + " "
            continue
        line = pending + line
        pending = ""
        if line.strip():
            rows.append(line.split())
    return rows


def _subckt(tok: list[str]) -> tuple[list[str], list[str]]:
    ins: list[str] = []
    outs: list[str] = []
    for pin in tok[2:]:
        name, _, net = pin.partition("=")
        base = name.split("[")[0].lower()
        (outs if base in OUT_PINS or "out" in base else ins).append(net)
    return ins, outs


class Netlist:
    """Combinational cells are ``.names`` and ``.subckt`` blocks; flip-flops are ``.latch``."""

    def __init__(self, text: str) -> None:
        self.cells: list[tuple[list[str], list[str]]] = []
        self.latches: list[tuple[str, str]] = []
        self.consts: set[str] = set()
        for tok in _logical_lines(text):
            if tok[0] == ".names" and len(tok) >= 2:
                ins, out = tok[1:-1], tok[-1]
                self.cells.append((ins, [out]))
                if not ins:
                    self.consts.add(out)
            elif tok[0] == ".latch" and len(tok) >= 3:
                self.latches.append((tok[1], tok[2]))
            elif tok[0] == ".subckt" and len(tok) >= 2:
                self.cells.append(_subckt(tok))
        self.fanout: dict[str, list[int]] = defaultdict(list)
        for i, (ins, _outs) in enumerate(self.cells):
            for n in ins:
                self.fanout[n].append(i)
        self.latch_of_d: dict[str, list[str]] = defaultdict(list)
        for d, q in self.latches:
            self.latch_of_d[d].append(q)

    @classmethod
    def read(cls, path: Path) -> Netlist:
        return cls(path.read_text(encoding="utf-8", errors="replace"))

    def forward(self, start: Iterable[str], cap: int) -> dict[str, int]:
        """Net -> fewest combinational cells crossed from ``start`` (0 = a start net), walking
        forward through cells only (a flip-flop D pin ends the walk), at most ``cap`` cells."""
        seen: dict[str, int] = {n: 0 for n in start}
        frontier = list(seen)
        for depth in range(1, cap + 1):
            nxt: list[str] = []
            for net in frontier:
                for i in self.fanout.get(net, ()):
                    for o in self.cells[i][1]:
                        if o not in seen:
                            seen[o] = depth
                            nxt.append(o)
            frontier = nxt
        return seen

    def feedback_q(self, ys: Iterable[str], operands: set[str], cap: int) -> list[str]:
        """Q nets of flip-flops whose D is reached from ``ys`` within ``cap`` cells and whose Q
        reaches one of ``operands`` within ``cap`` cells (a register loop through an adder)."""
        reach = self.forward(ys, cap)
        qs = [q for d in reach for q in self.latch_of_d.get(d, ())]
        return [q for q in sorted(set(qs)) if set(self.forward([q], cap)) & operands]
