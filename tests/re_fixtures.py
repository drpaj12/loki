"""Hand-built ``FnGraph`` builders shared by the detector tests."""

from __future__ import annotations

import random
from collections.abc import Callable, Sequence

from loki.re.bayes import DEFAULTS
from loki.re.detectors import RoundContext
from loki.re.fngraph import Cell, FnGraph
from loki.re.overlay import Overlay
from loki.re.structural import build_features
from loki.re.view import View

XOR2, AND2, XOR3, MAJ3 = 0b0110, 0b1000, 0b10010110, 0b11101000
MUX = 0b11001010  # inputs (a, b, s): s ? b : a
BUF = 0b10


def table_of(width: int, fn: Callable[[Sequence[int]], int]) -> int:
    """Truth table of ``fn`` over ``width`` inputs (input ``i`` is bit ``i`` of the pattern)."""
    return sum(fn([(x >> i) & 1 for i in range(width)]) << x for x in range(1 << width))


class GB:
    """Builds an ``FnGraph``: nets and cells get fresh ids; cell ids start at 1000."""

    def __init__(self) -> None:
        self.cells: dict[int, Cell] = {}
        self.pis: list[int] = []
        self.pos: list[int] = []
        self.names: dict[int, str] = {}
        self._net = 0
        self._cell = 1000

    def net(self, name: str = "") -> int:
        self._net += 1
        if name:
            self.names[self._net] = name
        return self._net

    def pi(self, name: str = "") -> int:
        n = self.net(name)
        self.pis.append(n)
        return n

    def pis_n(self, count: int, prefix: str) -> list[int]:
        return [self.pi(f"{prefix}{i}") for i in range(count)]

    def lut(self, table: int, ins: Sequence[int], out: int | None = None) -> int:
        """A LUT over ``ins``; returns its output net."""
        o = self.net() if out is None else out
        self._cell += 1
        self.cells[self._cell] = Cell(
            self._cell, "", "lut", "$sop", tuple(ins), (o,), table, len(ins), 0, self._cell, {}
        )
        return o

    def const(self, value: int) -> int:
        o = self.net()
        self._cell += 1
        self.cells[self._cell] = Cell(
            self._cell, "", "const", "$sop", (), (o,), value, 0, 0, self._cell, {}
        )
        return o

    def ff(self, d: int, clk: int, q: int | None = None) -> int:
        """A positive-edge flip-flop; returns Q."""
        o = self.net() if q is None else q
        self._cell += 1
        self.cells[self._cell] = Cell(
            self._cell, "", "ff", "$_DFF_P_", (d,), (o,), 0, 0, clk, self._cell, {"INIT": 0}
        )
        return o

    def cell_of(self, net: int) -> int:
        """The id of the cell driving ``net``."""
        for cid, c in self.cells.items():
            if net in c.outs:
                return cid
        raise KeyError(net)

    def build(self, pos: Sequence[int] = ()) -> FnGraph:
        driver = {n: c.id for c in self.cells.values() for n in c.outs}
        readers: dict[int, list[tuple[int, int]]] = {}
        for cid in sorted(self.cells):
            c = self.cells[cid]
            for pin, n in enumerate(c.ins):
                readers.setdefault(n, []).append((cid, pin))
        return FnGraph(
            dict(self.cells), driver, {n: tuple(r) for n, r in readers.items()}, dict(self.names),
            tuple(self.pis), tuple(pos) or tuple(self.pos), {}, ""
        )


def make_ctx(
    graph: FnGraph,
    overlay: Overlay | None = None,
    features: bool = True,
    view: View | None = None,
) -> RoundContext:
    """A round-1 context over ``graph`` with defaults calibration."""
    return RoundContext(
        round=1, floor="f2-lut", graph=graph, view=view or View.level0(graph),
        overlay=overlay or Overlay(), rng=lambda p: random.Random(f"1:{p}"), calib=DEFAULTS,
        features=build_features(graph) if features else None,
    )
