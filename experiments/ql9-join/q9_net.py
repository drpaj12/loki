"""Block-level structure of a netlist graph: links between cells, control nets, Fiedler cuts."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

import numpy as np


class Links:
    """Non-global driver-to-reader links of a graph (one per net and reader), per-cell degree and
    the global nets each cell reads."""

    def __init__(self, g: Any) -> None:
        self.pairs: list[tuple[int, int]] = []
        self.deg: dict[int, int] = defaultdict(int)
        self.ctrl: dict[int, frozenset[str]] = {}
        for i in range(g.b.n):
            self.ctrl[i] = frozenset(n for n in g.b.ins[i] if g.is_cut(n))
        for net, rs in g.readers.items():
            p = g.b.producer.get(net)
            if p is None or g.is_cut(net):
                continue
            for r in rs:
                if r != p:
                    self.pairs.append((p, r))
                    self.deg[p] += 1
                    self.deg[r] += 1

    def between(self, owner: dict[int, int]) -> dict[tuple[int, int], int]:
        """Links per pair of blocks (a < b) for a cell -> block map."""
        out: dict[tuple[int, int], int] = defaultdict(int)
        for p, r in self.pairs:
            a, b = owner.get(p), owner.get(r)
            if a is not None and b is not None and a != b:
                out[(min(a, b), max(a, b))] += 1
        return dict(out)

    def block_deg(self, cells: frozenset[int]) -> int:
        return sum(self.deg[c] for c in cells)

    def block_ctrl(self, cells: frozenset[int]) -> frozenset[str]:
        return frozenset().union(*(self.ctrl[c] for c in cells)) if cells else frozenset()


def adjacency(links: Links, cells: frozenset[int]) -> dict[int, dict[int, int]]:
    """Undirected weighted adjacency inside a block."""
    adj: dict[int, dict[int, int]] = {c: {} for c in cells}
    for p, r in links.pairs:
        if p in adj and r in adj:
            adj[p][r] = adj[p].get(r, 0) + 1
            adj[r][p] = adj[r].get(p, 0) + 1
    return adj


def components(adj: dict[int, dict[int, int]]) -> list[list[int]]:
    seen: set[int] = set()
    out = []
    for s in sorted(adj):
        if s in seen:
            continue
        comp, todo = [], [s]
        seen.add(s)
        while todo:
            c = todo.pop()
            comp.append(c)
            for m in sorted(adj[c]):
                if m not in seen:
                    seen.add(m)
                    todo.append(m)
        out.append(sorted(comp))
    return out


def sweep(order: list[int], adj: dict[int, dict[int, int]], min_side: int
          ) -> tuple[frozenset[int], frozenset[int]] | None:
    """Prefix cut of least conductance of cells sorted by a vector (ties: the smaller prefix)."""
    deg = {c: sum(adj[c].values()) for c in order}
    vol_all = sum(deg.values())
    inside: set[int] = set()
    cut = vol = 0
    best: tuple[float, int] | None = None
    for m, c in enumerate(order[:-1], start=1):
        w_in = sum(w for n, w in adj[c].items() if n in inside)
        cut += deg[c] - 2 * w_in
        vol += deg[c]
        inside.add(c)
        if m >= min_side and len(order) - m >= min_side:
            den = min(vol, vol_all - vol)
            phi = cut / den if den > 0 else 1.0
            if best is None or phi < best[0] - 1e-12:
                best = (phi, m)
    if best is None:
        return None
    return frozenset(order[:best[1]]), frozenset(order[best[1]:])


def fiedler_cut(links: Links, cells: frozenset[int], min_side: int
                ) -> tuple[frozenset[int], frozenset[int]] | None:
    """The cut of least conductance along the Fiedler vector; a disconnected block is cut as
    its largest component against the rest."""
    adj = adjacency(links, cells)
    comps = components(adj)
    if len(comps) > 1:
        big = max(comps, key=lambda c: (len(c), -c[0]))
        rest = frozenset(cells - set(big))
        return (frozenset(big), rest) if len(rest) >= min_side and len(big) >= min_side else None
    nodes = sorted(cells)
    idx = {c: i for i, c in enumerate(nodes)}
    a = np.zeros((len(nodes), len(nodes)))
    for c in nodes:
        for n, w in adj[c].items():
            a[idx[c], idx[n]] = w
    d = a.sum(axis=1)
    if (d <= 0).any():
        return None
    dm = 1.0 / np.sqrt(d)
    lap = np.eye(len(nodes)) - dm[:, None] * a * dm[None, :]
    _, vecs = np.linalg.eigh(lap)
    vec = vecs[:, 1] * dm
    if vec[int(np.argmax(np.abs(vec)))] < 0:
        vec = -vec
    order = [nodes[i] for i in sorted(range(len(nodes)), key=lambda i: (float(vec[i]), nodes[i]))]
    return sweep(order, adj, min_side)
