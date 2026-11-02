"""Grow the TRAIN and VALIDATION paths: ``python -B q7_paths.py [JOBS]``.

Same grower as #73's no-stop variant (q6_grow with QL6_NOSTOP=1), on the TUNE units of the odd
(calibration) half, written to $QL7_OUT/paths/<set>__<design>__<cell>.json. Units run smallest
first, at most JOBS processes.
"""

from __future__ import annotations

import json
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Any

import q7_env as env

q6g = env.mod("q6_grow")
qm = env.mod("q6_model")
qn = env.mod("q6_net")
qs = env.mod("q6_sig")
qt = env.mod("q6_truth")


def grow_unit(u: Any, model: Any) -> dict[str, Any]:
    """The path record of one unit (the same fields as q6_grow.run_unit that the stop rules use)."""
    g = qn.Graph.read(u.net)
    anc = qn.anchors(g)
    sc = qs.SigCounter(u.net, g.b)
    blocks = q6g.Grower(g, sc, model, u.cell).grow(anc)
    rec = {"unit": [u.set, u.design, u.cell], "n_cells": g.b.n, "n_anchors": len(anc),
           "blocks": [{"bid": b.bid, "anchor_kind": b.kind, "anchor": b.anchor, "order": b.order,
                       "evs": [round(float(e), 3) for e in b.evs], "stop": b.stop,
                       "traj": [[int(t[0]), *[round(float(v), 4) for v in t[1:]]]
                                for t in b.traj]} for b in blocks]}
    sc.close()
    return rec


def run_unit(key: tuple[str, str, str, str]) -> str:
    kind, design, cell, split = key
    dest = env.paths_dir("TRAIN") / f"{kind}__{design}__{cell}.json"
    if dest.is_file():
        return ""
    u = next(x for x in qt.units(split, (cell,)) if x.set == kind and x.design == design)
    rec = grow_unit(u, qm.load(env.OUT6 / "model.json"))
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = Path(str(dest) + ".part")
    tmp.write_text(json.dumps(rec, sort_keys=True), encoding="utf-8")
    tmp.replace(dest)
    return ""


def stop_units() -> list[Any]:
    out = []
    for u in qt.units("TUNE"):
        if qt.has_labels(u) and env.stop_split(u.design) and u.net.stat().st_size > 0:
            out.append(u)
    return out


def main(argv: list[str]) -> int:
    n_jobs = min(int(argv[0]) if argv else 4, 4)
    us = sorted(stop_units(), key=lambda u: u.net.stat().st_size)
    keys = []
    for u in us:
        g = qn.Graph.read(u.net)
        if g.b.n <= env.MAX_UNIT_CELLS:
            keys.append((u.set, u.design, u.cell, u.split))
    with ProcessPoolExecutor(n_jobs) as pool:
        list(pool.map(run_unit, keys, chunksize=1))
    print(len(keys), "units")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
