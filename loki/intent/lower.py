"""Lower asynchronous-reset flip-flop cells (``DFFSR``) to ``ff`` plus a LUT in an ``FnGraph``.

``FnGraph`` reads only ``$_DFF_*`` cells as flip-flops; a ``DFFSR`` cell of the cmos6 library is a
``hard`` cell whose Q pin looks like an input, so state machines with an asynchronous reset are
invisible to the detectors. For claims the reset is modelled as dominant at the next clock
(``Q' = R ? 0 : S ? 1 : D``), the usual abstraction for state-space exploration. The returned map
names, per lowered flip-flop, the asynchronous control nets, so a claim can say "asynchronous".
"""

from __future__ import annotations

from dataclasses import replace

from loki.re.fngraph import Cell, FnGraph

DFFSR = "DFFSR"


def _is_dffsr(cell: Cell) -> bool:
    return cell.kind == "hard" and cell.type == DFFSR and cell.in_pins == ("C", "D", "S", "R", "Q")


def _next_table() -> int:
    """Truth table of ``R ? 0 : (S ? 1 : D)`` over inputs ``(D, S, R)`` (input i is bit i)."""
    table = 0
    for x in range(8):
        d, s, r = x & 1, (x >> 1) & 1, (x >> 2) & 1
        table |= (0 if r else (1 if s else d)) << x
    return table


def lower_async_ff(graph: FnGraph) -> tuple[FnGraph, dict[int, tuple[int, int]]]:
    """``(graph without DFFSR cells, {Q net: (set net, reset net)})``.

    A set or reset pin tied to a constant is kept as a pin; the LUT reads it as a net."""
    old = [c for c in graph.cells.values() if _is_dffsr(c)]
    if not old:
        return graph, {}
    cells = {cid: c for cid, c in graph.cells.items() if not _is_dffsr(c)}
    names = dict(graph.names)
    next_cell = max(graph.cells) + 1
    used = [n for c in graph.cells.values() for n in (*c.ins, *c.outs)]
    next_net = max([*names, *used, 0]) + 1
    asyn: dict[int, tuple[int, int]] = {}
    for c in sorted(old, key=lambda c: c.id):
        clk, d, s, r, q = c.ins
        dn = next_net
        next_net += 1
        cells[next_cell] = Cell(next_cell, "", "lut", "$sop", (d, s, r), (dn,), _next_table(), 3,
                                0, c.line, {})
        cells[c.id] = Cell(c.id, c.name, "ff", "$_DFF_P_", (dn,), (q,), 0, 0, clk, c.line,
                           {"INIT": 0})
        next_cell += 1
        asyn[q] = (s, r)
    driver = {n: c.id for c in cells.values() for n in c.outs}
    readers: dict[int, list[tuple[int, int]]] = {}
    for cid in sorted(cells):
        for pin, n in enumerate(cells[cid].ins):
            readers.setdefault(n, []).append((cid, pin))
    out = replace(graph, cells=cells, driver=driver,
                  readers={n: tuple(r) for n, r in readers.items()}, names=names)
    return out, asyn


def tie_net(graph: FnGraph, net: int, value: int) -> FnGraph:
    """``graph`` with every reader of ``net`` reading a new constant net instead (``net`` itself
    stays, so a claim can still name it)."""
    used = [n for c in graph.cells.values() for n in (*c.ins, *c.outs)]
    new_net = max([*graph.names, *used, 0]) + 1
    new_cell = max(graph.cells) + 1
    cells = {
        cid: (replace(c, ins=tuple(new_net if n == net else n for n in c.ins))
              if net in c.ins else c)
        for cid, c in graph.cells.items()
    }
    cells[new_cell] = Cell(new_cell, "", "const", "$sop", (), (new_net,), value & 1, 0, 0,
                           new_cell, {"WIDTH": 0, "COVER": ""})
    driver = {n: c.id for c in cells.values() for n in c.outs}
    readers: dict[int, list[tuple[int, int]]] = {}
    for cid in sorted(cells):
        for pin, n in enumerate(cells[cid].ins):
            readers.setdefault(n, []).append((cid, pin))
    return replace(graph, cells=cells, driver=driver,
                   readers={n: tuple(r) for n, r in readers.items()})
