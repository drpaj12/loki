"""The grower: all anchors grow at once, one cell per step, by Bayes factor.

See EXPERIMENT.md "The method". ``python -B q6_grow.py [JOBS]`` grows blocks in every TEST unit
and writes $QL6_OUT/blocks/<set>__<design>__<cell>.json.
"""

from __future__ import annotations

import json
import sys
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass, field
from typing import Any

import numpy as np

import q6_model as qm
import q6_net as qn
import q6_sig as qs
import q6_truth as qt
from q6_env import KINDS, OUT

CAP = 600
EPS = 1e-9
LOOK_FRONTIER = 40
LOOK_NEIGH = 6
GLUE = KINDS.index("glue")


@dataclass
class Block:
    bid: int
    kind: str  # anchor class
    anchor: list[int]
    cells: set[int]
    order: list[int] = field(default_factory=list)
    traj: list[list[float]] = field(default_factory=list)  # per step: size, entropy, 6 posteriors
    touches: set[int] = field(default_factory=set)
    cand: dict[int, float] = field(default_factory=dict)  # cell -> log Bayes factor
    post: np.ndarray = field(default_factory=lambda: np.zeros(len(KINDS)))
    ev: float = 0.0
    done: bool = False
    looks: int = 0
    stop: str = ""


class Grower:
    def __init__(self, g: qn.Graph, sc: qs.SigCounter, model: qm.Model, cell: str) -> None:
        self.g, self.sc, self.model, self.cell = g, sc, model, cell
        self.owner: dict[int, int] = {}
        self.blocks: list[Block] = []

    def posterior(self, cells: frozenset[int]) -> tuple[np.ndarray, np.ndarray]:
        x = qs.feature(self.sc.orbits(cells))
        return self.model.posterior(self.cell, x, len(cells)), x

    def weights(self, post: np.ndarray) -> np.ndarray:
        w = post.copy()
        w[GLUE] = 0.0
        s = w.sum()
        return w / s if s > 0 else np.full(len(KINDS), 1.0) * (np.arange(len(KINDS)) != GLUE) / (
            len(KINDS) - 1)

    def evidence(self, cells: frozenset[int], w: np.ndarray) -> float:
        x = qs.feature(self.sc.orbits(cells))
        return self.model.evidence(self.cell, x, len(cells), w)

    def record(self, b: Block) -> None:
        p, _ = self.posterior(frozenset(b.cells))
        b.post = p
        b.ev = self.evidence(frozenset(b.cells), self.weights(p))
        b.traj.append([float(len(b.cells)), qm.entropy_bits(p), *map(float, p)])
        self.score_frontier(b)

    def free_frontier(self, b: Block) -> list[int]:
        fr = self.g.frontier(b.cells)
        for c in fr:
            o = self.owner.get(c)
            if o is not None and o != b.bid:
                b.touches.add(o)
        return [c for c in fr if c not in self.owner]

    def score_frontier(self, b: Block) -> None:
        w = self.weights(b.post)
        b.cand = {c: self.evidence(frozenset(b.cells | {c}), w) - b.ev
                  for c in self.free_frontier(b)}

    def lookahead(self, b: Block) -> int | None:
        """Cell whose best two-cell extension has a Bayes factor above 1, or None."""
        w = self.weights(b.post)
        best: tuple[float, int] | None = None
        for c in sorted(b.cand)[:LOOK_FRONTIER]:
            for c2 in self.g.neighbours(c)[:LOOK_NEIGH]:
                if c2 in b.cells or c2 == c or c2 in self.owner:
                    continue
                d = self.evidence(frozenset(b.cells | {c, c2}), w) - b.ev
                if d > EPS and (best is None or d > best[0]):
                    best = (d, c)
        return None if best is None else best[1]

    def propose(self, b: Block) -> int | None:
        live = {c: d for c, d in b.cand.items() if c not in self.owner}
        if live:
            c, d = max(live.items(), key=lambda kv: (kv[1], -kv[0]))
            if d > EPS:
                return c
        c2 = self.lookahead(b) if live and len(b.cells) < CAP else None
        if c2 is not None:
            b.looks += 1
        return c2

    def win(self, b: Block, c: int) -> float:
        p, _ = self.posterior(frozenset(b.cells | {c}))
        q = p.copy()
        q[GLUE] = 0.0
        return float(q.max())

    def grow(self, anchors: list[qn.Anchor]) -> list[Block]:
        for i, a in enumerate(anchors):
            b = Block(i, a.kind, sorted(a.cells), set(a.cells))
            for c in a.cells:
                self.owner[c] = i
            self.blocks.append(b)
        for b in self.blocks:
            self.record(b)
        while True:
            props: dict[int, list[Block]] = {}
            for b in self.blocks:
                if b.done:
                    continue
                if len(b.cells) >= CAP:
                    b.done, b.stop = True, "cap"
                    continue
                c = self.propose(b)
                if c is None:
                    b.done, b.stop = True, "no Bayes factor above 1"
                else:
                    props.setdefault(c, []).append(b)
            if not props:
                break
            for c, bs in sorted(props.items()):
                if c in self.owner:
                    continue
                w = bs[0] if len(bs) == 1 else max(bs, key=lambda x: (self.win(x, c), -x.bid))
                w.cells.add(c)
                w.order.append(c)
                self.owner[c] = w.bid
                self.record(w)
        return self.blocks


def top3(p: np.ndarray) -> list[list[Any]]:
    idx = np.argsort(-p)[:3]
    return [[KINDS[i], round(float(p[i]), 4)] for i in idx]


def unknown_cohesive(b: Block) -> bool:
    return len(b.cells) >= 8 and b.post[GLUE] < 0.25 and float(b.post.max()) < 0.5


def run_unit(key: tuple[str, str, str, str]) -> str:
    kind, design, cell, split = key
    dest = OUT / "blocks" / f"{kind}__{design}__{cell}.json"
    if dest.is_file():
        return ""
    u = next(x for x in qt.units(split, (cell,)) if x.set == kind and x.design == design)
    g = qn.Graph.read(u.net)
    anc = qn.anchors(g)
    sc = qs.SigCounter(u.net, g.b)
    model = qm.load(OUT / "model.json")
    gr = Grower(g, sc, model, cell)
    blocks = gr.grow(anc)
    pairs = sorted({(min(b.bid, o), max(b.bid, o)) for b in blocks for o in b.touches})
    comp = []
    for a, c in pairs[:50]:
        ba, bc = blocks[a], blocks[c]
        if len(ba.cells) >= 8 and len(bc.cells) >= 8:
            p, _ = gr.posterior(frozenset(ba.cells | bc.cells))
            comp.append({"a": a, "b": c, "kinds": [KINDS[int(np.argmax(ba.post))],
                                                  KINDS[int(np.argmax(bc.post))]],
                         "union_top3": top3(p), "union_entropy": round(qm.entropy_bits(p), 4)})
    rec = {"unit": [kind, design, cell], "n_cells": g.b.n, "pass_runs": sc.calls,
           "n_anchors": len(anc), "composites": comp,
           "blocks": [{"bid": b.bid, "anchor_kind": b.kind, "anchor": b.anchor,
                       "order": b.order, "final": top3(b.post), "post": np.round(b.post, 4).tolist(),
                       "entropy": round(qm.entropy_bits(b.post), 4), "stop": b.stop,
                       "looks": b.looks, "touches": sorted(b.touches),
                       "unknown_cohesive": bool(unknown_cohesive(b)),
                       "traj": [[int(t[0]), *np.round(t[1:], 4).tolist()] for t in b.traj]}
                      for b in blocks]}
    sc.close()
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(rec, sort_keys=True), encoding="utf-8")
    return ""


def main(argv: list[str]) -> int:
    n_jobs = int(argv[0]) if argv else 4
    split = argv[1] if len(argv) > 1 else "TEST"
    keys = [(u.set, u.design, u.cell, u.split) for u in qt.units(split)]
    with ProcessPoolExecutor(n_jobs) as pool:
        list(pool.map(run_unit, keys, chunksize=4))
    print(len(keys), "units")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
