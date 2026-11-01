"""Step 0, anchor survival census: ``python -B q6_census.py [JOBS]``.

Per construct kind x cell (TEST constructs with provenance): the share whose matching anchor class
survives, and the share with any anchor, an anchor surviving = at least half of its cells inside
the true block. Writes results/census.csv and results/census_units.csv.
"""

from __future__ import annotations

import sys
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor
from typing import Any

import q6_net as qn
import q6_truth as qt
from q6_env import RES, l3dlib

MATCH = {"fsm": ("fsm",), "counter": ("counter", "hard"), "shift": ("shift",),
         "regfile": ("memory",), "register": ("register",)}


def survives(a: qn.Anchor, block: frozenset[int]) -> bool:
    return len(a.cells & block) * 2 >= len(a.cells)


def one(key: tuple[str, str, str, str]) -> list[dict[str, Any]]:
    kind, design, cell, split = key
    u = next(x for x in qt.units(split, (cell,)) if x.set == kind and x.design == design)
    g = qn.Graph.read(u.net)
    anc = qn.anchors(g)
    rows = []
    for c in qt.constructs(u, g):
        if not c.cells or c.kind == "glue":
            continue
        match = any(survives(a, c.cells) and a.kind in MATCH.get(c.kind, ()) for a in anc)
        anyc = any(survives(a, c.cells) for a in anc)
        rows.append({"set": kind, "design": design, "cell": cell, "part": c.idx,
                     "kind": c.kind, "n_cells": len(c.cells), "match": int(match),
                     "any": int(anyc), "n_anchors": len(anc)})
    return rows


def main(argv: list[str]) -> int:
    n = int(argv[0]) if argv else 4
    keys = [(u.set, u.design, u.cell, u.split) for u in qt.units("TEST") if qt.has_labels(u)]
    with ProcessPoolExecutor(n) as pool:
        rows = [r for part in pool.map(one, keys, chunksize=8) for r in part]
    RES.mkdir(exist_ok=True)
    l3dlib.write_csv(RES / "census_units.csv", list(rows[0]), rows)
    agg: dict[tuple[str, str], list[int]] = defaultdict(lambda: [0, 0, 0])
    for r in rows:
        for k in ((r["kind"], r["cell"]), (r["kind"], "all")):
            agg[k][0] += 1
            agg[k][1] += r["match"]
            agg[k][2] += r["any"]
    out = [{"kind": k, "cell": c, "constructs": v[0], "match_anchor": v[1],
            "match_share": round(v[1] / v[0], 3), "any_anchor": v[2],
            "any_share": round(v[2] / v[0], 3)} for (k, c), v in sorted(agg.items())]
    l3dlib.write_csv(RES / "census.csv", list(out[0]), out)
    for r in out:
        print(r)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
