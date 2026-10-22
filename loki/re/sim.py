"""Bit-parallel simulation, supports and cones over an FnGraph (L1 spec 4)."""

from __future__ import annotations

import heapq
from collections.abc import Iterable, Sequence

from loki.re.fngraph import Cell, FnGraph

SUPPORT_MAX = 40
_COMB = ("lut", "const")


def _is_comb(cell: Cell) -> bool:
    return cell.kind in _COMB


def topo_order(graph: FnGraph, cells: Iterable[int]) -> list[int]:
    """Cells in topological order (ties by id); the cells of a loop follow in id order."""
    group = {c for c in cells if c in graph.cells and _is_comb(graph.cells[c])}
    waiting: dict[int, int] = {}
    users: dict[int, list[int]] = {}
    for cid in group:
        deps = {
            graph.driver[n]
            for n in graph.cells[cid].ins
            if n in graph.driver and graph.driver[n] in group and graph.driver[n] != cid
        }
        waiting[cid] = len(deps)
        for d in deps:
            users.setdefault(d, []).append(cid)
    ready = [c for c, n in waiting.items() if n == 0]
    heapq.heapify(ready)
    order: list[int] = []
    while ready:
        cid = heapq.heappop(ready)
        order.append(cid)
        for u in users.get(cid, ()):
            waiting[u] -= 1
            if waiting[u] == 0:
                heapq.heappush(ready, u)
    done = set(order)
    return order + sorted(group - done)


def _eval(cell: Cell, values: dict[int, int], mask: int) -> int:
    ins = [values.get(n, 0) & mask if n else 0 for n in cell.ins]
    out = 0
    for x in range(1 << cell.width):
        if not (cell.table >> x) & 1:
            continue
        term = mask
        for i, vec in enumerate(ins):
            term &= vec if (x >> i) & 1 else ~vec & mask
        out |= term
    return out


def simulate(
    graph: FnGraph, cells: Sequence[int], values: dict[int, int], n: int
) -> dict[int, int]:
    """Net values after evaluating ``cells`` (LUTs and constants) over ``n`` vectors at once.

    ``values`` maps nets to ``n``-bit ints; a net missing from it reads 0. Flip-flops, latches and
    hard cells are not evaluated: their outputs are inputs. The result holds ``values`` too.
    """
    mask = (1 << n) - 1
    nets = {k: v & mask for k, v in values.items()}
    for cid in topo_order(graph, cells):
        cell = graph.cells[cid]
        out = _eval(cell, nets, mask)
        for net in cell.outs:
            nets[net] = out
    return nets


def _scc(graph: FnGraph, cut: set[tuple[int, int]]) -> list[list[int]]:
    """Non-trivial strongly connected sets of the combinational graph minus the cut pins."""
    succ: dict[int, list[int]] = {}
    for cid, cell in graph.cells.items():
        if not _is_comb(cell):
            continue
        for pin, net in enumerate(cell.ins):
            d = graph.driver.get(net)
            if d is not None and _is_comb(graph.cells[d]) and (cid, pin) not in cut:
                succ.setdefault(d, []).append(cid)
    index: dict[int, int] = {}
    low: dict[int, int] = {}
    on: set[int] = set()
    stack: list[int] = []
    found: list[list[int]] = []
    for root in sorted(succ):
        if root in index:
            continue
        _tarjan(root, succ, index, low, on, stack, found)
    return found


def _tarjan(
    root: int,
    succ: dict[int, list[int]],
    index: dict[int, int],
    low: dict[int, int],
    on: set[int],
    stack: list[int],
    found: list[list[int]],
) -> None:
    work: list[tuple[int, int]] = [(root, 0)]
    while work:
        v, i = work.pop()
        if i == 0:
            index[v] = low[v] = len(index)
            stack.append(v)
            on.add(v)
        children = succ.get(v, [])
        descended = False
        while i < len(children):
            w = children[i]
            i += 1
            if w not in index:
                work.append((v, i))
                work.append((w, 0))
                descended = True
                break
            if w in on:
                low[v] = min(low[v], index[w])
        if descended:
            continue
        if low[v] == index[v]:
            comp = []
            while True:
                w = stack.pop()
                on.discard(w)
                comp.append(w)
                if w == v:
                    break
            if len(comp) > 1 or v in succ.get(v, []):
                found.append(comp)
        if work:
            parent = work[-1][0]
            low[parent] = min(low[parent], low[v])


def _loop_cuts(graph: FnGraph) -> tuple[set[tuple[int, int]], int]:
    """Pins to ignore so the combinational graph is acyclic: per loop, the input pins of its
    lowest-ID cell that are driven from inside the loop. Returns (pins, number of cuts)."""
    cut: set[tuple[int, int]] = set()
    count = 0
    while True:
        loops = _scc(graph, cut)
        if not loops:
            return cut, count
        for comp in loops:
            members = set(comp)
            low = min(members)
            for pin, net in enumerate(graph.cells[low].ins):
                if graph.driver.get(net) in members:
                    cut.add((low, pin))
            count += 1


class Support:
    """Source nets in the transitive fan-in of a net (spec 4), cached.

    A combinational loop is cut at its lowest-ID cell (counted in ``loops_cut``). ``None`` means
    the support is larger than ``SUPPORT_MAX`` (too wide for chain detection).
    """

    def __init__(self, graph: FnGraph, extra_sources: frozenset[int] = frozenset()) -> None:
        self.graph = graph
        self.extra = extra_sources
        self.sources = graph.sources() | extra_sources
        self.cut, self.loops_cut = _loop_cuts(graph)
        self.cache: dict[int, frozenset[int] | None] = {}

    def _is_leaf(self, net: int) -> bool:
        d = self.graph.driver.get(net)
        return net in self.sources or d is None or not _is_comb(self.graph.cells[d])

    def _children(self, net: int) -> list[int]:
        cid = self.graph.driver[net]
        cell = self.graph.cells[cid]
        return [n for pin, n in enumerate(cell.ins) if n and (cid, pin) not in self.cut]

    def of(self, net: int) -> frozenset[int] | None:
        """The support of ``net``; a net with no driver is its own support."""
        if net == 0:
            return frozenset()
        stack = [net]
        while stack:
            cur = stack[-1]
            if cur in self.cache:
                stack.pop()
                continue
            if self._is_leaf(cur):
                self.cache[cur] = frozenset({cur})
                stack.pop()
                continue
            pending = [c for c in self._children(cur) if c not in self.cache]
            if pending:
                stack.extend(pending)
                continue
            self.cache[cur] = self._union(self._children(cur))
            stack.pop()
        return self.cache[net]

    def _union(self, children: list[int]) -> frozenset[int] | None:
        out: set[int] = set()
        for c in children:
            sub = self.cache[c]
            if sub is None:
                return None
            out |= sub
            if len(out) > SUPPORT_MAX:
                return None
        return frozenset(out)


def cone(
    graph: FnGraph, inputs: frozenset[int], outputs: Sequence[int], stop: frozenset[int]
) -> tuple[tuple[int, ...], frozenset[int]]:
    """Cells from ``outputs`` back to ``inputs`` (sorted by id) and the side inputs.

    The walk stops at ``inputs``, at ``stop``, and at sources (including undriven nets); a net it
    stops at that is not in ``inputs`` is a side input. Net 0 (unconnected) is ignored.
    """
    sources = graph.sources()
    cells: set[int] = set()
    side: set[int] = set()
    seen: set[int] = set()
    todo = list(outputs)
    while todo:
        net = todo.pop()
        if net == 0 or net in seen:
            continue
        seen.add(net)
        if net in inputs:
            continue
        d = graph.driver.get(net)
        if net in stop or net in sources or d is None or not _is_comb(graph.cells[d]):
            side.add(net)
            continue
        cells.add(d)
        todo.extend(graph.cells[d].ins)
    return tuple(sorted(cells)), frozenset(side)
