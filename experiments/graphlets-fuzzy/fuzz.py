"""Directed-orbit catalogue relations: one-edge-flip graph and undirected collapse.

Built from data/directed_catalogue.json (the table of Odin III docs/user/graphlets.md): per graphlet
the arcs in canonical labels and one node of each orbit. ``flip_matrix`` is the 129 x 129 0/1
matrix A
with A[o][o'] = 1 when o' is o with the direction of exactly one edge of its graphlet reversed;
``collapse_map`` sends a directed orbit to the id of its underlying undirected (graphlet, position).
"""

from __future__ import annotations

import json
from itertools import permutations
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
Arcs = frozenset[tuple[int, int]]


def catalogue() -> list[dict[str, Any]]:
    return json.loads((HERE / "data" / "directed_catalogue.json").read_text(encoding="utf-8"))


def _perm_arcs(arcs: Arcs, p: tuple[int, ...]) -> Arcs:
    return frozenset((p[a], p[b]) for a, b in arcs)


def _classes(n: int, arcs: Arcs) -> list[int]:
    """Automorphism class (smallest member) of each node of a directed graph."""
    cls = list(range(n))
    for p in permutations(range(n)):
        if _perm_arcs(arcs, p) == arcs:
            for v in range(n):
                cls[v] = min(cls[v], p[v])
    return cls


def orbit_table() -> tuple[dict[tuple[int, int], int], dict[Arcs, tuple[int, int]],
                           dict[int, tuple[int, Arcs, int]]]:
    """(node -> orbit id keyed (graphlet, node), arcs -> graphlet, orbit -> (n, arcs, rep node))."""
    node_orbit: dict[tuple[int, int], int] = {}
    by_arcs: dict[Arcs, tuple[int, int]] = {}
    info: dict[int, tuple[int, Arcs, int]] = {}
    for r in catalogue():
        arcs: Arcs = frozenset((a, b) for a, b in r["arcs"])
        by_arcs[arcs] = (r["g"], r["n"])
        cls = _classes(r["n"], arcs)
        rep = {cls[n]: o for o, n in r["orbits"]}
        for v in range(r["n"]):
            node_orbit[(r["g"], v)] = rep[cls[v]]
        for o, n in r["orbits"]:
            info[o] = (r["n"], arcs, n)
    return node_orbit, by_arcs, info


def flip_matrix() -> list[list[int]]:
    node_orbit, by_arcs, info = orbit_table()
    a = [[0] * 129 for _ in range(129)]
    for o, (n, arcs, v) in info.items():
        for e in arcs:
            flipped = frozenset((arcs - {e}) | {(e[1], e[0])})
            for p in permutations(range(n)):
                img = _perm_arcs(flipped, p)
                if img in by_arcs:
                    a[o][node_orbit[(by_arcs[img][0], p[v])]] = 1
                    break
    return a


def collapse_map() -> list[int]:
    """Directed orbit -> class id of the same position of the underlying undirected graph."""
    _no, _ba, info = orbit_table()
    keys: dict[tuple[int, tuple[tuple[int, int], ...], int], int] = {}
    out = [0] * 129
    for o in range(129):
        n, arcs, v = info[o]
        und = frozenset(frozenset(a) for a in arcs)
        best: tuple[tuple[tuple[int, int], ...], int] | None = None
        for p in permutations(range(n)):
            code = tuple(sorted(tuple(sorted((p[a], p[b]))) for a, b in
                                (tuple(e) for e in und)))
            cand = (code, p[v])
            if best is None or cand[0] < best[0]:
                best = (code, p[v])
        assert best is not None
        # class under undirected automorphisms: smallest image of v among perms giving the code
        imgs = [p[v] for p in permutations(range(n))
                if tuple(sorted(tuple(sorted((p[a], p[b]))) for a, b in
                                (tuple(e) for e in und))) == best[0]]
        out[o] = keys.setdefault((n, best[0], min(imgs)), len(keys))
    return out
