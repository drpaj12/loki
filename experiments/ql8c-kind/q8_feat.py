"""Block features of Q-L8c: orbit shares, orbit density, boundary, feedback and typed-cell scalars.

``featurize(ctx, cells)`` returns the vector [H (129), D (129), S (len(SCALARS))] of one block
(a set of cell indices). Orbit counts are the Odin III graphlets pass (q6_sig.SigCounter);
everything else
is computed on the cell graph of q6_net.Graph.
"""

from __future__ import annotations

import copy
import math
from dataclasses import dataclass
from typing import Any

import numpy as np
import q8_env as env

qn = env.mod("q6_net")
qs = env.mod("q6_sig")
q7f = env.mod("q7_feat")

N_ORB = qs.N_ORBITS
SCALARS = ("log2n", "ff", "hard", "adder", "mem", "mult", "lut_in", "edges_pc", "self_pc", "phi",
           "fin_pc", "fout_pc", "pi_pc", "n_scc", "scc_cells", "scc_big", "scc_ff", "cyc_pc",
           "depth")
N_FEAT = 2 * N_ORB + len(SCALARS)
H = slice(0, N_ORB)
D = slice(N_ORB, 2 * N_ORB)
S = slice(2 * N_ORB, N_FEAT)


@dataclass
class Ctx:
    g: Any  # q6_net.Graph
    sc: Any  # q6_sig.SigCounter
    geo: Any  # q7_feat.Geometry (state is reset per block)


def make_ctx(g: Any, sc: Any) -> Ctx:
    return Ctx(g, sc, q7f.Geometry(g))


def hard_kind(model: str) -> str:
    m = model.lower()
    if "adder" in m:
        return "adder"
    if "mult" in m:
        return "mult"
    if "ram" in m or "mem" in m:
        return "mem"
    return "other"


def internal_edges(g: Any, cells: set[int]) -> dict[int, set[int]]:
    """Driver to reader links between block cells through non-global nets (self links kept)."""
    succ: dict[int, set[int]] = {i: set() for i in cells}
    for i in cells:
        for n in g.b.outs[i]:
            if g.is_cut(n):
                continue
            succ[i].update(r for r in g.readers.get(n, ()) if r in cells)
    return succ


def feedback(g: Any, cells: set[int], succ: dict[int, set[int]]) -> tuple[int, int, int, int, int]:
    """(nontrivial SCC count, cells inside, largest SCC, flip-flops inside, cycle rank)."""
    n_scc = inside = big = ffs = rank = 0
    for comp in qn._sccs(sorted(cells), succ):
        cs = set(comp)
        if len(comp) < 2 and comp[0] not in succ[comp[0]]:
            continue
        n_scc += 1
        inside += len(comp)
        big = max(big, len(comp))
        ffs += sum(1 for i in comp if g.b.latch[i])
        rank += sum(len(succ[i] & cs) for i in comp) - len(comp) + 1
    return n_scc, inside, big, ffs, rank


def comb_depth(g: Any, cells: set[int], succ: dict[int, set[int]]) -> int:
    """Longest chain of combinational cells in the internal graph with flip-flops cut."""
    comb = {i for i in cells if not g.b.latch[i]}
    indeg = {i: 0 for i in comb}
    for i in comb:
        for r in succ[i]:
            if r in comb and r != i:
                indeg[r] += 1
    depth = dict.fromkeys(comb, 1)
    todo = [i for i in comb if indeg[i] == 0]
    while todo:
        i = todo.pop()
        for r in succ[i]:
            if r in comb and r != i:
                depth[r] = max(depth[r], depth[i] + 1)
                indeg[r] -= 1
                if indeg[r] == 0:
                    todo.append(r)
    return max(depth.values(), default=0)


def boundary(ctx: Ctx, cells: set[int]) -> tuple[float, int, int]:
    geo = copy.copy(ctx.geo)
    geo.inside, geo.block, geo.pin, geo.pout = {}, set(), {}, {}
    geo.cut = geo.vol = geo.n_ff = 0
    for c in sorted(cells):
        geo.add(c)
    return geo.phi(), len(geo.pin), len(geo.pout)


def scalars(ctx: Ctx, cells: set[int]) -> np.ndarray:
    g, b = ctx.g, ctx.g.b
    n = len(cells)
    kinds = [hard_kind(g.hard[i]) for i in cells if i in g.hard]
    logic = [i for i in cells if not b.latch[i] and i not in g.hard]
    succ = internal_edges(g, cells)
    n_edges = sum(len(v) for v in succ.values())
    n_self = sum(1 for i in cells if i in succ[i])
    pis = {m for i in cells for m in b.ins[i] if m not in b.producer and not g.is_cut(m)}
    n_scc, inside, big, ffs, rank = feedback(g, cells, succ)
    n_ff = sum(1 for i in cells if b.latch[i])
    phi, fin, fout = boundary(ctx, cells)
    lut_in = float(np.mean([len(b.ins[i]) for i in logic])) if logic else 0.0
    return np.array([
        math.log2(n), n_ff / n, len(kinds) / n, kinds.count("adder") / n, kinds.count("mem") / n,
        kinds.count("mult") / n, lut_in, n_edges / n, n_self / n, phi, fin / n, fout / n,
        len(pis) / n, n_scc, inside / n, big / n, ffs / max(n_ff, 1), rank / n,
        math.log1p(comb_depth(g, cells, succ))])


def featurize(ctx: Ctx, cells: frozenset[int]) -> np.ndarray:
    """The feature vector of a block of cells; all zeros in H and D when it has no edges."""
    tot = ctx.sc.orbits(cells)
    x = np.zeros(N_FEAT)
    x[H] = qs.feature(tot)
    x[D] = np.log1p(tot / len(cells))
    x[S] = scalars(ctx, set(cells))
    return x
