"""Loki's joined blocks of a LUT-level netlist (the Q-L10 builder, run on the census BLIF).

Same rules as ``ql10-blocks/q10_blocks.py``: anchors bank+loop+const, grown to the end by the #73
model, one JCOND join at 0.2, blocks above 300 cells never made, cells in no block grouped by
connected component (chunks of at most 300) into ``residual`` blocks. The cell class is ``O-lut``
(k4) or ``O-hard`` (k6) instead of ``O-gate``. The BLIF is read by ``q6_net.Graph``; its cell index
is the cell index of ``q12_nl.Netlist``. Constants and buffers (``Cell.glue``) are glue of the top
module and belong to no block. No kind guess (the arms of Q-L12 have no hint). Needs
libodin3 (the graphlet signature pass).
"""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Any

import q12_env as env
from q12_nl import Netlist

Block: Any = env.mod("q10_blocks").Block
q9rules: Any = env.mod("q9_rules")
q9net: Any = env.mod("q9_net")
q9units: Any = env.mod("q9_units")
qn: Any = env.mod("q6_net")
qs: Any = env.mod("q6_sig")
q6m: Any = env.mod("q6_model")
qa: Any = env.mod("q8b_anchors")
q8bg: Any = env.mod("q8b_grow")


def residual(nl: Netlist, left: set[int]) -> list[list[int]]:
    """Components of the uncovered cells (undirected over any net, clock nets included), chunks of
    at most 300 cells, in traversal order."""
    drv = nl.driver()
    rd: dict[str, list[int]] = defaultdict(list)
    for c in nl.cells:
        for n in c.reads:
            rd[n].append(c.idx)
    seen: set[int] = set()
    out: list[list[int]] = []
    for s in sorted(left):
        if s in seen:
            continue
        comp, todo = [], [s]
        seen.add(s)
        while todo:
            x = todo.pop()
            comp.append(x)
            nb = [drv[n] for n in nl.cells[x].reads if n in drv]
            for o in nl.cells[x].outs:
                nb += rd.get(o, [])
            for y in sorted(nb):
                if y in left and y not in seen:
                    seen.add(y)
                    todo.append(y)
        comp.sort()
        out += [comp[i:i + env.MAX_BLOCK_CELLS] for i in range(0, len(comp), env.MAX_BLOCK_CELLS)]
    return out


def to_blocks(nl: Netlist, sets: list[Any]) -> list[Any]:
    blocks: list[Any] = []
    taken: set[int] = set()
    for b in sets:
        cells = sorted(c for c in set(b.cells) - taken if not nl.cells[c].glue)
        if not cells:
            continue
        taken.update(cells)
        blocks.append(Block(len(blocks), b.kind, cells, "", []))
    for comp in residual(nl, set(nl.logic()) - taken):
        blocks.append(Block(len(blocks), "residual", comp))
    return blocks


def build(nl: Netlist, blif: Path, cell_class: str) -> list[Any]:
    """Loki's joined blocks of the netlist; ``cell_class`` is ``O-lut`` or ``O-hard``."""
    g = qn.Graph.read(blif)
    if g.b.n != len(nl.cells):
        raise ValueError(f"{blif}: {g.b.n} graph cells, {len(nl.cells)} netlist cells")
    old = qn.anchors(g)
    anc = old + qa.extra_anchors(g, old, ("bank", "loop", "const"))
    sc = qs.SigCounter(blif, g.b)
    try:
        grown = q8bg.Frozen(g, sc, q6m.load(env.q10_env.q9env.OUT6 / "model.json"),
                            cell_class).grow(anc)
        start = [q9units.Blk(frozenset(b.anchor) | frozenset(b.order), b.kind) for b in grown]
        cfg = q9rules.Config("HEAD", "JOIN", "cond", "E73", env.JOIN_T)
        joined, _nj, _ns = q9rules.apply(cfg, start, q9net.Links(g), None)
    finally:
        sc.close()
    return to_blocks(nl, joined)
