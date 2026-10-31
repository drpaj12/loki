"""Sequential groups: the flip-flop sets that are analysed as one counter, shift register or FSM.

A group is a strongly connected set of the flip-flop dependency graph (size 2 or more, or one
flip-flop that reads itself) plus its feeders: flip-flops outside the set that feed it and read
only the group (the low bit of a binary counter reads only itself and the reset, and no flip-flop
of the loop reads it back). Weakly connected components come first because a shift register is a
chain of single-flip-flop loops. Pure given an ``FnGraph``.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from loki.re.detectors.seqfn import GROUP_MAX, _tarjan
from loki.re.fngraph import FnGraph
from loki.re.sim import Support


@dataclass(frozen=True)
class Group:
    """``loop`` is the strongly connected core, ``feeders`` the flip-flops added to it. A group
    with ``is_loop`` False is a weakly connected component with no loop of two or more
    flip-flops (a pipeline, a shift chain): it can be a shift register, never a state machine."""

    loop: frozenset[int]
    feeders: frozenset[int]
    is_loop: bool = True

    @property
    def ffs(self) -> frozenset[int]:
        return self.loop | self.feeders


def ff_cells(graph: FnGraph) -> dict[int, list[int]]:
    """Single-input single-output flip-flops by clock net."""
    out: dict[int, list[int]] = {}
    for cid, cell in sorted(graph.cells.items()):
        if cell.kind == "ff" and len(cell.ins) == 1 and len(cell.outs) == 1 and cell.ins[0]:
            out.setdefault(cell.clock, []).append(cid)
    return out


def ff_deps(graph: FnGraph, ffs: Sequence[int], support: Support) -> dict[int, frozenset[int]]:
    """Per flip-flop, the flip-flops whose Q is in the support of its D (itself included)."""
    cell_of_q = {graph.cells[c].outs[0]: c for c in ffs}
    deps: dict[int, frozenset[int]] = {}
    for c in ffs:
        sup = support.of(graph.cells[c].ins[0])
        if sup is not None:
            deps[c] = frozenset(cell_of_q[n] for n in sup if n in cell_of_q)
    return deps


def _loops(members: list[int], deps: dict[int, frozenset[int]]) -> list[frozenset[int]]:
    succ = {i: [j for j in members if j != i and i in deps[j]] for i in members}
    found = [frozenset(c) for c in _tarjan(members, succ) if len(c) <= GROUP_MAX]
    in_loop = {c for f in found for c in f}
    found += [frozenset({c}) for c in members if c in deps[c] and c not in in_loop]
    return found


def _feeders(loop: frozenset[int], deps: dict[int, frozenset[int]]) -> frozenset[int]:
    """Flip-flops outside ``loop`` that read nothing but the group and themselves, and at least
    one flip-flop (a plain delay of an input is not a state bit)."""
    group = set(loop)
    added: set[int] = set()
    grew = True
    while grew:
        grew = False
        upstream = {f for c in group for f in deps[c] if f not in group and f in deps}
        for f in sorted(upstream):
            reads = deps[f]
            if reads and reads <= group | {f}:
                group.add(f)
                added.add(f)
                grew = True
    return frozenset(added)


def _components(members: list[int], deps: dict[int, frozenset[int]]) -> list[frozenset[int]]:
    """Weakly connected sets of the dependency graph with at least two flip-flops."""
    adj: dict[int, set[int]] = {c: set() for c in members}
    for c in members:
        for d in deps[c]:
            if d != c and d in adj:
                adj[c].add(d)
                adj[d].add(c)
    seen: set[int] = set()
    out: list[frozenset[int]] = []
    for c in members:
        if c in seen:
            continue
        comp, todo = {c}, [c]
        while todo:
            for n in adj[todo.pop()]:
                if n not in comp:
                    comp.add(n)
                    todo.append(n)
        seen |= comp
        if len(comp) >= 2:
            out.append(frozenset(comp))
    return out


def sequential_groups(graph: FnGraph, claimed: frozenset[int] = frozenset()) -> list[Group]:
    """Candidate groups of every clock: weakly connected components, then the loop-plus-feeders
    groups, largest first (ties by smallest cell id). A group is at most ``GROUP_MAX`` cells.

    Flip-flops in ``claimed`` are left out and their reads ignored, so a digit steered by a digit
    that is already explained keeps its own low bit (a feeder reads nothing outside the group)."""
    support = Support(graph)
    found: dict[frozenset[int], Group] = {}
    for ffs in ff_cells(graph).values():
        deps = ff_deps(graph, ffs, support)
        deps = {c: d - claimed for c, d in deps.items() if c not in claimed}
        members = sorted(deps)
        loops = _loops(members, deps)
        for comp in _components(members, deps):
            cyclic = any(len(loop) >= 2 and loop <= comp for loop in loops)
            if len(comp) <= GROUP_MAX:
                found.setdefault(comp, Group(comp, frozenset(), cyclic))
        for loop in loops:
            g = Group(loop, _feeders(loop, deps))
            if len(g.ffs) <= GROUP_MAX:
                found[g.ffs] = g
    return sorted(found.values(), key=lambda g: (-len(g.ffs), min(g.ffs)))
