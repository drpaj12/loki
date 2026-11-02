"""Build the feature records of every set: ``python -B q8_data.py SET [JOBS]`` (SET = FIT, CAL, VAL, TEST).

FIT: prefixes of the answer-key blocks of the even-half TUNE designs (the #73 training samples).
CAL, VAL, TEST: per unit the grown blocks of #74 rule d (cut at the chosen prefix) and the answer-key
true blocks. Writes $QL8C_OUT/data_<SET>.pkl. Units run smallest first, at most 2 processes.
"""

from __future__ import annotations

import json
import pickle
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Any

import numpy as np
import q8_env as env
import q8_feat as qf

qn = env.mod("q6_net")
qs = env.mod("q6_sig")
qt = env.mod("q6_truth")
qtr = env.mod("q6_train")
q7f = env.mod("q7_feat")
rules = env.mod("q7_rules")
bl = env.mod("blocks")

SPLIT7 = {"CAL": "TRAIN", "VAL": "VALIDATION", "TEST": "TEST"}
MAX_UNIT = env.q7env.MAX_UNIT_CELLS


def is_right(cells: set[int] | frozenset[int], true: frozenset[int]) -> bool:
    jac, cov = bl.jaccard(set(cells), set(true))
    return bool(cov >= 0.8 and jac >= 0.5)


def fit_unit(key: tuple[str, str, str]) -> list[dict[str, Any]]:
    kind, design, cell = key
    u = next(x for x in qt.units("TUNE", (cell,)) if x.set == kind and x.design == design)
    g = qn.Graph.read(u.net)
    anc = qn.anchors(g)
    sc = qs.SigCounter(u.net, g.b)
    ctx = qf.make_ctx(g, sc)
    out = []
    for c in qt.constructs(u, g):
        if not c.cells:
            continue
        seed = qtr.seed_of(g, anc, c.cells)
        order = qtr.visit_order(g, c.cells, seed)
        for s in qtr.prefix_sizes(len(seed), len(order)):
            cells = frozenset(order[:s])
            out.append({"cell": cell, "kind": c.kind, "size": s, "x": qf.featurize(ctx, cells)})
    sc.close()
    return out


def eval_unit(args: tuple[str, str, str, str, list[int]]) -> dict[str, Any]:
    kind, design, cell, tsplit, picks = args
    u = next(x for x in qt.units(tsplit, (cell,)) if x.set == kind and x.design == design)
    split = "TEST" if tsplit == "TEST" else "TRAIN"
    rec = json.loads((env.q7env.paths_dir(split) / f"{kind}__{design}__{cell}.json").read_text(
        encoding="utf-8"))
    g = qn.Graph.read(u.net)
    cons = [c for c in qt.constructs(u, g) if c.kind != "glue" and c.cells]
    sc = qs.SigCounter(u.net, g.b)
    ctx = qf.make_ctx(g, sc)
    blocks = []
    for b, k in zip(rec["blocks"], picks, strict=True):
        cells = frozenset(b["anchor"]) | frozenset(b["order"][:k])
        right = [(c.idx, c.kind) for c in cons if is_right(cells, c.cells)]
        blocks.append({"bid": b["bid"], "size": len(cells), "right": right,
                       "x": qf.featurize(ctx, cells)})
    true = [{"part": c.idx, "kind": c.kind, "size": len(c.cells), "x": qf.featurize(ctx, c.cells)}
            for c in cons]
    sc.close()
    return {"set": kind, "design": design, "cell": cell, "n_cells": g.b.n,
            "cons": [(c.idx, c.kind, len(c.cells)) for c in cons], "blocks": blocks, "true": true}


def chosen_picks(units: list[Any]) -> list[list[int]]:
    cfg = json.loads((env.q7env.RES / "chosen.json").read_text(encoding="utf-8"))
    with (env.OUT7 / "clf.pkl").open("rb") as fh:
        clf = pickle.load(fh)
    pick = rules.pickers(cfg, clf)[cfg["headline"]]
    return [[pick(bp) for bp in u.blocks] for u in units]


def build(name: str, n_jobs: int) -> list[Any]:
    if name == "FIT":
        us = [u for u in qt.units("TUNE") if qt.has_labels(u) and env.design_set(u.design) == "FIT"
              and u.net.stat().st_size > 0]
        us.sort(key=lambda u: u.net.stat().st_size)
        with ProcessPoolExecutor(n_jobs) as pool:
            return [r for part in pool.map(fit_unit, [(u.set, u.design, u.cell) for u in us],
                                           chunksize=4) for r in part]
    data = [d for d in q7f.load(SPLIT7[name]) if d.n_cells <= MAX_UNIT]
    picks = chosen_picks(data)
    tsplit = "TEST" if name == "TEST" else "TUNE"
    order = sorted(range(len(data)), key=lambda i: data[i].n_cells)
    args = [(data[i].set, data[i].design, data[i].cell, tsplit, picks[i]) for i in order]
    with ProcessPoolExecutor(n_jobs) as pool:
        return list(pool.map(eval_unit, args, chunksize=2))


def main(argv: list[str]) -> int:
    name = argv[0]
    n_jobs = min(int(argv[1]) if len(argv) > 1 else 2, 2)
    env.OUT8.mkdir(parents=True, exist_ok=True)
    rows = build(name, n_jobs)
    with (env.OUT8 / f"data_{name}.pkl").open("wb") as fh:
        pickle.dump(rows, fh)
    if name == "FIT":
        print(name, len(rows), "samples", np.mean([r["x"].any() for r in rows]))
    else:
        print(name, len(rows), "units", sum(len(r["blocks"]) for r in rows), "blocks",
              sum(len(r["cons"]) for r in rows), "constructs")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
