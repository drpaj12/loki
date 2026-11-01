"""Cell graph of a BLIF netlist, the cut rule, and the anchor detectors (step 0 and 1).

A cell is the index of a BLIF logic element (as in experiments/ql4-misses/blocks.py). Nets read by
``FANOUT_CUT`` or more cells are global and are cut: the grower does not cross them (the same rule
as Odin III's ``--exclude-global``: >= 16 readers).
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from q6_env import bl, mod

FANOUT_CUT = 16
CONE_CAP = 300
nl_mod = mod("loki.l3.netlist")


def hard_models(path: Path, n_cells: int) -> dict[int, str]:
    """Cell index -> subckt model name, in the cell order of ``Blif.read``."""
    out: dict[int, str] = {}
    i = 0
    for tok in nl_mod._logical_lines(path.read_text(encoding="utf-8", errors="replace")):
        if tok[0] == ".names" and len(tok) >= 2 or tok[0] == ".latch" and len(tok) >= 3:
            i += 1
        elif tok[0] == ".subckt" and len(tok) >= 2:
            out[i] = tok[1]
            i += 1
    if i != n_cells:
        raise ValueError(f"{path}: cell count {i} != {n_cells}")
    return out


@dataclass
class Graph:
    b: Any  # blocks.Blif
    hard: dict[int, str]
    readers: dict[str, list[int]]

    @classmethod
    def read(cls, path: Path) -> Graph:
        b = bl.Blif.read(path)
        readers: dict[str, list[int]] = defaultdict(list)
        for i, ins in enumerate(b.ins):
            for n in ins:
                readers[n].append(i)
        return cls(b, hard_models(path, b.n), readers)

    def is_cut(self, net: str) -> bool:
        return len(self.readers.get(net, ())) >= FANOUT_CUT

    def neighbours(self, i: int) -> list[int]:
        """Cells one net away from cell ``i`` (drivers of its inputs, readers of its outputs),
        not crossing cut nets."""
        out: set[int] = set()
        for n in self.b.ins[i]:
            p = self.b.producer.get(n)
            if p is not None and p != i and not self.is_cut(n):
                out.add(p)
        for n in self.b.outs[i]:
            if not self.is_cut(n):
                out.update(r for r in self.readers.get(n, ()) if r != i)
        return sorted(out)

    def frontier(self, block: set[int]) -> list[int]:
        out: set[int] = set()
        for i in block:
            out.update(self.neighbours(i))
        return sorted(out - block)


@dataclass
class Anchor:
    kind: str  # fsm | counter | shift | memory | register | hard
    cells: frozenset[int]  # the anchor's cells (flip-flops, or the hard cells)


def ff_cone(g: Graph, ff: int) -> tuple[set[int], set[str], set[int]]:
    """(flip-flops read, cone nets, comb cells) of the next-state logic of flip-flop ``ff``,
    walking back through combinational cells and stopping at flip-flop outputs and inputs."""
    b = g.b
    deps: set[int] = set()
    nets: set[str] = set()
    comb: set[int] = set()
    todo = list(b.ins[ff])
    while todo and len(comb) <= CONE_CAP:
        n = todo.pop()
        if n in nets:
            continue
        nets.add(n)
        p = b.producer.get(n)
        if p is None:
            continue
        if b.latch[p]:
            deps.add(p)
        else:
            comb.add(p)
            todo.extend(b.ins[p])
    return deps, nets, comb


def _components(nodes: list[int], edges: dict[int, set[int]]) -> list[list[int]]:
    seen: set[int] = set()
    out = []
    for s in nodes:
        if s in seen:
            continue
        comp = []
        todo = [s]
        seen.add(s)
        while todo:
            x = todo.pop()
            comp.append(x)
            for y in edges.get(x, ()):
                if y not in seen:
                    seen.add(y)
                    todo.append(y)
        out.append(sorted(comp))
    return out


def _sccs(nodes: list[int], succ: dict[int, set[int]]) -> list[list[int]]:
    """Strongly connected components (iterative Tarjan)."""
    index: dict[int, int] = {}
    low: dict[int, int] = {}
    on: set[int] = set()
    stack: list[int] = []
    out: list[list[int]] = []
    k = 0
    for s in nodes:
        if s in index:
            continue
        work = [(s, iter(sorted(succ.get(s, ()))))]
        index[s] = low[s] = k
        k += 1
        stack.append(s)
        on.add(s)
        while work:
            v, it = work[-1]
            for w in it:
                if w not in index:
                    index[w] = low[w] = k
                    k += 1
                    stack.append(w)
                    on.add(w)
                    work.append((w, iter(sorted(succ.get(w, ())))))
                    break
                if w in on:
                    low[v] = min(low[v], index[w])
            else:
                work.pop()
                if work:
                    low[work[-1][0]] = min(low[work[-1][0]], low[v])
                if low[v] == index[v]:
                    comp = []
                    while True:
                        w = stack.pop()
                        on.discard(w)
                        comp.append(w)
                        if w == v:
                            break
                    out.append(sorted(comp))
    return out


def _triangular(comp: list[int], deps: dict[int, set[int]]) -> bool:
    """Counter signature: dependency sets (with self) nested in a chain of >= 3 distinct sizes."""
    sets = sorted((frozenset(deps[i] | {i}) for i in comp), key=len)
    sizes = {len(s) for s in sets}
    if len(comp) < 3 or len(sizes) < 3:
        return False
    return all(a <= b for a, b in zip(sets, sets[1:], strict=False))


def _shift_chains(g: Graph, ffs: list[int]) -> list[list[int]]:
    """Flip-flops joined by a direct Q -> D wire (no cell between): chains of >= 3."""
    edges: dict[int, set[int]] = defaultdict(set)
    for i in ffs:
        p = g.b.producer.get(g.b.ins[i][0])
        if p is not None and g.b.latch[p] and p != i:
            edges[i].add(p)
            edges[p].add(i)
    return [c for c in _components(sorted(edges), edges) if len(c) >= 3]


def _hard_anchors(g: Graph) -> list[Anchor]:
    """Adder cells joined by carry nets become one chain; each other hard cell is its own."""
    adders = [i for i, m in g.hard.items() if "adder" in m.lower()]
    others = [i for i, m in g.hard.items() if "adder" not in m.lower()]
    aset = set(adders)
    edges: dict[int, set[int]] = defaultdict(set)
    for i in adders:
        for n in g.b.outs[i]:
            for r in g.readers.get(n, ()):
                if r in aset and r != i:
                    edges[i].add(r)
                    edges[r].add(i)
    out = [Anchor("hard", frozenset(c)) for c in _components(adders, edges)]
    return out + [Anchor("hard", frozenset([i])) for i in others]


def _memory_register(g: Graph, ffs: list[int], deps: dict[int, set[int]],
                     nets: dict[int, set[str]]) -> list[Anchor]:
    """Flip-flops that read only themselves, linked by a shared cone net. A component of >= 8 in
    which >= 2 nets each feed a proper subset (2 .. half) is memory (decoder selects); else a
    register of >= 2."""
    selfonly = [i for i in ffs if deps[i] <= {i}]
    by_net: dict[str, list[int]] = defaultdict(list)
    for i in selfonly:
        for n in nets[i]:
            by_net[n].append(i)
    edges: dict[int, set[int]] = defaultdict(set)
    for members in by_net.values():
        if 2 <= len(members) < len(selfonly) or (len(members) == len(selfonly) >= 2):
            for m in members[1:]:
                edges[members[0]].add(m)
                edges[m].add(members[0])
    out = []
    for comp in _components(sorted(edges), edges):
        cs = set(comp)
        sel = [n for n, ms in by_net.items()
               if 2 <= len([m for m in ms if m in cs]) <= len(cs) // 2]
        kind = "memory" if len(comp) >= 8 and len(sel) >= 2 else "register"
        out.append(Anchor(kind, frozenset(comp)))
    linked = {i for a in out for i in a.cells}
    out.extend(Anchor("register", frozenset([i])) for i in selfonly if i not in linked)
    return out


def anchors(g: Graph) -> list[Anchor]:
    """All anchors of a netlist. Priority when flip-flops overlap: shift, fsm, counter, memory or
    register. Hard-cell anchors are independent of the flip-flop ones."""
    ffs = [i for i in range(g.b.n) if g.b.latch[i]]
    out: list[Anchor] = []
    used: set[int] = set()
    for c in _shift_chains(g, ffs):
        out.append(Anchor("shift", frozenset(c)))
        used.update(c)
    deps: dict[int, set[int]] = {}
    nets: dict[int, set[str]] = {}
    for i in ffs:
        deps[i], nets[i], _ = ff_cone(g, i)
    rest = [i for i in ffs if i not in used]
    succ = {i: {d for d in deps[i] if d != i and d not in used} for i in rest}
    for comp in _sccs(rest, succ):
        cs = set(comp)
        if len(comp) >= 2 and all(deps[i] <= cs for i in comp):
            out.append(Anchor("fsm", frozenset(comp)))
            used.update(comp)
    rest = [i for i in ffs if i not in used]
    undirected: dict[int, set[int]] = defaultdict(set)
    for i in rest:
        for d in deps[i]:
            if d != i and d in rest:
                undirected[i].add(d)
                undirected[d].add(i)
    for comp in _components(sorted(undirected), undirected):
        if _triangular(comp, deps):
            out.append(Anchor("counter", frozenset(comp)))
            used.update(comp)
    rest = [i for i in ffs if i not in used]
    out.extend(_memory_register(g, rest, deps, nets))
    out.extend(_hard_anchors(g))
    return out
