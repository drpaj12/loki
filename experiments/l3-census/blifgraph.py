"""Minimal BLIF reader for the census: cell counts and combinational reach between flip-flops."""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path

OUT_PINS = ("out", "sumout", "cout", "o", "y", "q")


def _lines(path: Path) -> list[list[str]]:
    rows: list[list[str]] = []
    pending = ""
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.split("#", 1)[0].rstrip()
        if line.endswith("\\"):
            pending += line[:-1] + " "
            continue
        line = pending + line
        pending = ""
        if line.strip():
            rows.append(line.split())
    return rows


class Blif:
    """Cells: ``names`` (inputs, output), ``latch`` (d, q), ``subckt`` (model, ins, outs)."""

    def __init__(self, path: Path) -> None:
        self.names: list[tuple[list[str], str]] = []
        self.latches: list[tuple[str, str]] = []
        self.subckts: list[tuple[str, list[str], list[str]]] = []
        for tok in _lines(path):
            if tok[0] == ".names" and len(tok) >= 2:
                self.names.append((tok[1:-1], tok[-1]))
            elif tok[0] == ".latch" and len(tok) >= 3:
                self.latches.append((tok[1], tok[2]))
            elif tok[0] == ".subckt" and len(tok) >= 2:
                self.subckts.append(self._subckt(tok))
        self.fanout: dict[str, list[tuple[str, int]]] = defaultdict(list)
        self.d_of_q = {q: d for d, q in self.latches}
        self.q_of_d: dict[str, list[str]] = defaultdict(list)
        for d, q in self.latches:
            self.q_of_d[d].append(q)
        self._index()

    @staticmethod
    def _subckt(tok: list[str]) -> tuple[str, list[str], list[str]]:
        ins: list[str] = []
        outs: list[str] = []
        for pin in tok[2:]:
            name, _, net = pin.partition("=")
            base = name.split("[")[0].lower()
            (outs if base in OUT_PINS or "out" in base else ins).append(net)
        return tok[1], ins, outs

    def _index(self) -> None:
        for i, (ins, _out) in enumerate(self.names):
            for n in ins:
                self.fanout[n].append(("n", i))
        for i, (_m, ins, _outs) in enumerate(self.subckts):
            for n in ins:
                self.fanout[n].append(("s", i))

    def counts(self) -> dict[str, int]:
        models: dict[str, int] = defaultdict(int)
        for m, _i, _o in self.subckts:
            models[m] += 1
        out = {"names": len(self.names), "latches": len(self.latches),
               "hard": len(self.subckts)}
        out.update({f"hard:{m}": c for m, c in sorted(models.items())})
        return out

    def min_depth(self, src: list[str], dst_q: list[str], cap: int = 8) -> int:
        """Fewest combinational cells from a net of ``src`` to the D pin of a flip-flop whose Q
        is in ``dst_q`` (0 = the net is that D); -1 when none within ``cap``."""
        targets = {self.d_of_q[q] for q in dst_q if q in self.d_of_q}
        frontier = set(src)
        seen = set(frontier)
        for depth in range(cap + 1):
            if frontier & targets:
                return depth
            nxt: set[str] = set()
            for net in frontier:
                for kind, i in self.fanout.get(net, ()):
                    outs = [self.names[i][1]] if kind == "n" else self.subckts[i][2]
                    nxt.update(o for o in outs if o not in seen)
            seen |= nxt
            frontier = nxt
        return -1
