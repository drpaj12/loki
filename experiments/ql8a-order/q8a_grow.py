"""Growth orders OA, OB, OC (EXPERIMENT.md "Candidate orders").

``python -B q8a_grow.py ORDER SPLIT [JOBS]``. ``OrderedGrower`` is the #73 no-stop grower with
another choice of the next frontier cell. Paths go to
$QL8A_OUT/paths_<ORDER>/<SPLIT>/<set>__<design>__<cell>.json, smallest unit first, at most 2
processes.
"""

from __future__ import annotations

import json
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Any

import q8a_env as env

q6g = env.mod("q6_grow")
q6m = env.mod("q6_model")
qn = env.mod("q6_net")
qs = env.mod("q6_sig")
qt = env.mod("q6_truth")
q7f = env.mod("q7_feat")


class OrderedGrower(q6g.Grower):
    """Grower whose next cell for a block is chosen by ``order`` (OA, OB or OC)."""

    def __init__(self, g: Any, sc: Any, model: Any, cell: str, order: str) -> None:
        super().__init__(g, sc, model, cell)
        self.order = order

    def nets(self, c: int) -> list[str]:
        b = self.g.b
        return [n for n in dict.fromkeys([*b.ins[c], *b.outs[c]]) if not self.g.is_cut(n)]

    def free_frontier(self, b: Any) -> list[int]:
        fr: list[int] = super().free_frontier(b)
        if self.order != "OB":
            return fr
        extra: set[int] = set(fr)
        for i in b.cells:
            for n in self.g.b.ins[i]:
                if not self.g.is_cut(n):
                    extra.update(r for r in self.g.readers.get(n, ()) if r not in b.cells
                                 and r not in self.owner)
        return sorted(extra)

    def block_nets(self, b: Any) -> tuple[set[str], dict[str, int]]:
        """(non-global nets touched by the block, readers inside the block per net)."""
        touched: set[str] = set()
        readers: dict[str, int] = {}
        for i in b.cells:
            for n in self.nets(i):
                touched.add(n)
            for n in self.g.b.ins[i]:
                if not self.g.is_cut(n):
                    readers[n] = readers.get(n, 0) + 1
        return touched, readers

    def key(self, b: Any, c: int, d: float, touched: set[str], readers: dict[str, int]
            ) -> tuple[float, ...]:
        g = self.g
        attach = sum(1 for n in self.nets(c) if n in touched)
        drives = any(n in readers for n in g.b.outs[c] if not g.is_cut(n))
        reads = any(g.b.producer.get(n) in b.cells for n in g.b.ins[c] if not g.is_cut(n))
        if self.order == "OA":
            return (attach, d)
        if self.order == "OC":
            return (1.0 if drives else 0.0, d)
        sibling = any(readers.get(n, 0) >= 2 for n in g.b.ins[c] if not g.is_cut(n))
        tier = 2 if drives and reads else 1 if sibling else 0
        return (tier, attach, d)

    def propose(self, b: Any) -> int | None:
        if self.order == "E74":
            pick: int | None = super().propose(b)
            return pick
        live = {c: d for c, d in b.cand.items() if c not in self.owner}
        if not live:
            return None
        touched, readers = self.block_nets(b)
        best = max(live, key=lambda c: (*self.key(b, c, live[c], touched, readers), -c))
        return int(best)


def grow_unit(u: Any, model: Any, order: str) -> dict[str, Any]:
    """The path record of one unit, same fields as q7_paths.grow_unit."""
    g = qn.Graph.read(u.net)
    anc = qn.anchors(g)
    sc = qs.SigCounter(u.net, g.b)
    blocks = OrderedGrower(g, sc, model, u.cell, order).grow(anc)
    rec = {"unit": [u.set, u.design, u.cell], "n_cells": g.b.n, "n_anchors": len(anc),
           "blocks": [{"bid": b.bid, "anchor_kind": b.kind, "anchor": b.anchor, "order": b.order,
                       "evs": [round(float(e), 3) for e in b.evs], "stop": b.stop,
                       "traj": [[int(t[0]), *[round(float(v), 4) for v in t[1:]]]
                                for t in b.traj]} for b in blocks]}
    sc.close()
    return rec


def run_unit(key: tuple[str, str, str, str, str, str]) -> int:
    order, split, kind, design, cell, tsplit = key
    dest = env.paths_dir(order, split) / f"{kind}__{design}__{cell}.json"
    if dest.is_file():
        return 0
    u = next(x for x in qt.units(tsplit, (cell,)) if x.set == kind and x.design == design)
    rec = grow_unit(u, q6m.load(env.OUT6 / "model.json"), order)
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = Path(str(dest) + ".part")
    tmp.write_text(json.dumps(rec, sort_keys=True), encoding="utf-8")
    tmp.replace(dest)
    return 1


def main(argv: list[str]) -> int:
    order, split = argv[0], argv[1]
    n_jobs = min(int(argv[2]) if len(argv) > 2 else 2, 2)
    us = sorted(q7f.split_units(split), key=lambda u: u.net.stat().st_size)
    keys = [(order, split, u.set, u.design, u.cell, u.split) for u in us]
    with ProcessPoolExecutor(n_jobs) as pool:
        done = sum(pool.map(run_unit, keys, chunksize=1))
    print(order, split, len(keys), "units,", done, "grown")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
