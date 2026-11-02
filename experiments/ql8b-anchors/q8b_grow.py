"""Grow with the new anchors: ``python -B q8b_grow.py CLASSES SPLIT [JOBS]``.

CLASSES like bank+loop. The #74 grower (q6_grow no-stop variant, #74 order) with the old anchors
plus the new classes; a ``const`` anchor does not grow. Only units that get a new anchor are
grown; the others keep their #74 paths (q8b_feat reads them from there). Written to
$QL8B_OUT/paths_<CLASSES>/<SPLIT>/..., smallest unit first, at most 2 processes.
"""

from __future__ import annotations

import json
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Any

import q8b_anchors as qa
import q8b_env as env

q6g = env.mod("q6_grow")
q6m = env.mod("q6_model")
qn = env.mod("q6_net")
qs = env.mod("q6_sig")
qt = env.mod("q6_truth")
q7f = env.mod("q7_feat")


class Frozen(q6g.Grower):
    """Grower in which a block of anchor kind ``const`` never takes a cell."""

    def propose(self, b: Any) -> int | None:
        if b.kind == "const":
            return None
        pick: int | None = super().propose(b)
        return pick


def variant(classes: tuple[str, ...]) -> str:
    return "+".join(classes)


def anchors_of(g: Any, classes: tuple[str, ...]) -> tuple[list[Any], int]:
    old = qn.anchors(g)
    return old + qa.extra_anchors(g, old, classes), len(old)


def grow_unit(u: Any, model: Any, classes: tuple[str, ...]) -> dict[str, Any] | None:
    """Path record of one unit, or None when the classes add no anchor to it."""
    g = qn.Graph.read(u.net)
    anc, n_old = anchors_of(g, classes)
    if len(anc) == n_old:
        return None
    sc = qs.SigCounter(u.net, g.b)
    blocks = Frozen(g, sc, model, u.cell).grow(anc)
    rec = {"unit": [u.set, u.design, u.cell], "n_cells": g.b.n, "n_anchors": len(anc),
           "n_old_anchors": n_old,
           "blocks": [{"bid": b.bid, "anchor_kind": b.kind, "anchor": b.anchor, "order": b.order,
                       "evs": [round(float(e), 3) for e in b.evs], "stop": b.stop,
                       "traj": [[int(t[0]), *[round(float(v), 4) for v in t[1:]]]
                                for t in b.traj]} for b in blocks]}
    sc.close()
    return rec


def run_unit(key: tuple[str, str, str, str, str, str]) -> int:
    var, split, kind, design, cell, tsplit = key
    dest = env.paths_dir(var, split) / f"{kind}__{design}__{cell}.json"
    if dest.is_file():
        return 0
    u = next(x for x in qt.units(tsplit, (cell,)) if x.set == kind and x.design == design)
    rec = grow_unit(u, q6m.load(env.OUT6 / "model.json"), tuple(var.split("+")))
    if rec is None:
        return 0
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = Path(str(dest) + ".part")
    tmp.write_text(json.dumps(rec, sort_keys=True), encoding="utf-8")
    tmp.replace(dest)
    return 1


def main(argv: list[str]) -> int:
    var, split = argv[0], argv[1]
    n_jobs = min(int(argv[2]) if len(argv) > 2 else 2, 2)
    us = sorted(q7f.split_units(split), key=lambda u: u.net.stat().st_size)
    keys = [(var, split, u.set, u.design, u.cell, u.split) for u in us]
    with ProcessPoolExecutor(n_jobs) as pool:
        done = sum(pool.map(run_unit, keys, chunksize=1))
    print(var, split, len(keys), "units,", done, "grown")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
