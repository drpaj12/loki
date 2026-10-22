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


def lut_fn(g: GB, fn: Callable[[Sequence[int]], int], ins: Sequence[int]) -> int:
    """A LUT (at most six inputs) computing ``fn`` of the input bits."""
    if len(ins) > 6:
        raise ValueError("a LUT has at most six inputs")
    return g.lut(table_of(len(ins), fn), ins)


def _borrow(v: Sequence[int]) -> int:
    """Borrow out of ``x - y - c`` for inputs ``(x, y[, c])``."""
    c = v[2] if len(v) > 2 else 0
    return ((1 - v[0]) & v[1]) | ((1 - (v[0] ^ v[1])) & c)


def _parity(v: Sequence[int]) -> int:
    return sum(v) & 1


def _carry(v: Sequence[int]) -> int:
    return int(sum(v) >= 2)


def ripple(
    g: GB, a: Sequence[int], b: Sequence[int], cin: int | None = None,
    ops: Sequence[str] | None = None, sum_ids: bool = False,
) -> tuple[list[int], list[int]]:
    """A ripple of full adders (op ``add``), subtractors ``a - b`` (``sub``) or ``b - a``
    (``rsub``) per bit, one LUT per sum and per carry. Returns (sum nets, carry nets), the last
    carry being the carry-out."""
    ys: list[int] = []
    carries: list[int] = []
    c = cin
    for i, (x, y) in enumerate(zip(a, b, strict=True)):
        op = "add" if ops is None else ops[i]
        ins = [x, y] if c is None else [x, y, c]
        if op == "rsub":
            ins = [y, x] + ins[2:]
        ys.append(g.lut(table_of(len(ins), _parity), ins))
        fn = _borrow if op in ("sub", "rsub") else _carry
        c = g.lut(table_of(len(ins), fn), ins)
        carries.append(c)
    return ys, carries


def _sum_bit(i: int) -> Callable[[Sequence[int]], int]:
    """Bit ``i`` of ``A + B`` for inputs ``a[0..i], b[0..i]``."""

    def fn(v: Sequence[int]) -> int:
        lo = sum(v[j] << j for j in range(i + 1))
        hi = sum(v[i + 1 + j] << j for j in range(i + 1))
        return ((lo + hi) >> i) & 1

    return fn


def packed_adder(g: GB, a: Sequence[int], b: Sequence[int]) -> list[int]:
    """Sum bits as one LUT each over all lower operand bits (at most three bits)."""
    return [lut_fn(g, _sum_bit(i), [*a[: i + 1], *b[: i + 1]]) for i in range(len(a))]
