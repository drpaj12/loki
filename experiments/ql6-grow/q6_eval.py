"""Evaluation on TEST: ``python -B q6_eval.py`` after q6_grow.py. See EXPERIMENT.md "Evaluation".

Writes the CSVs of results/ (construct_records, right_block, pr_by_kind, reliability,
entropy_size, small_pieces, confusion, mixed_provenance, failure_modes, verdict, unknown_cohesive).
"""

from __future__ import annotations

import csv
import json
import math
import random
import re
from collections import Counter
from collections.abc import Callable
from pathlib import Path
from typing import Any

import numpy as np
import q6_model as qm
import q6_net as qn
import q6_truth as qt
from q6_env import KINDS, OUT, bl, l3dlib

BINS = ((1, 3), (4, 7), (8, 15), (16, 31), (32, 10**9))
BIN_NAMES = ("1-3", "4-7", "8-15", "16-31", "32+")
NB = 1000


def bin_of(size: int) -> int:
    return next(i for i, (lo, hi) in enumerate(BINS) if lo <= size <= hi)


def right(cells: set[int], true: frozenset[int]) -> tuple[bool, float, float]:
    jac, cov = bl.jaccard(cells, set(true))
    return (cov >= 0.8 and jac >= 0.5), jac, cov


def plurality(cells: set[int], lab: list[str]) -> str | None:
    c = Counter("glue" if lab[i] == "top" else lab[i] for i in cells)
    if not c:
        return None
    k, n = c.most_common(1)[0]
    return k if k in KINDS and n * 2 >= len(cells) else None


def read_blocks(u: qt.Unit) -> dict[str, Any] | None:
    p = OUT / "blocks" / f"{u.set}__{u.design}__{u.cell}.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.is_file() else None


def final_cells(b: dict[str, Any]) -> set[int]:
    return set(b["anchor"]) | set(b["order"])


def step_labels(b: dict[str, Any], lab: list[str]) -> list[str | None]:
    """Plurality label of the block after each trajectory step (step 0 = the anchor)."""
    cells = set(b["anchor"])
    out = [plurality(cells, lab)]
    for c in b["order"]:
        cells.add(c)
        out.append(plurality(cells, lab))
    return out


def boot_ci(by_design: dict[str, list[Any]], stat: Callable[[list[Any]], float],
            n: int = NB, seed: int = 1) -> tuple[float, float, float]:
    """(point, 5th, 95th percentile) of ``stat`` over designs resampled with replacement."""
    names = sorted(by_design)
    pt = stat([x for d in names for x in by_design[d]])
    rng = random.Random(seed)
    vals = []
    for _ in range(n):
        s = [x for d in (names[rng.randrange(len(names))] for _ in names) for x in by_design[d]]
        v = stat(s)
        if not math.isnan(v):
            vals.append(v)
    vals.sort()
    if not vals:
        return pt, math.nan, math.nan
    return pt, vals[int(0.05 * len(vals))], vals[min(len(vals) - 1, int(0.95 * len(vals)))]


def spearman(x: list[float], y: list[float]) -> float:
    def rank(v: list[float]) -> np.ndarray:
        a = np.asarray(v)
        order = a.argsort(kind="mergesort")
        r = np.empty(len(a))
        r[order] = np.arange(len(a))
        for val in np.unique(a):
            m = a == val
            r[m] = r[m].mean()
        return r

    rx, ry = rank(x), rank(y)
    if rx.std() == 0 or ry.std() == 0:
        return math.nan
    return float(np.corrcoef(rx, ry)[0, 1])


def d70_records() -> dict[tuple[str, str, str, int, str], dict[str, str]]:
    p = Path(__file__).resolve().parent.parent / "ql4-misses" / "results" / "records.csv"
    rows = l3dlib.read_csv(p)
    return {(r["set"], r["design"], r["cell"], int(r["part"]), r["family"]): r
            for r in rows if r["detector"] == "D70"}


def evaluate() -> dict[str, Any]:
    prior = qm.census_prior()
    prior_top3 = tuple(sorted(KINDS, key=lambda k: -prior[k])[:3])
    prior_vec = np.array([prior[k] for k in KINDS])
    d70 = d70_records()
    cons: list[dict[str, Any]] = []
    claims: list[dict[str, Any]] = []  # final blocks
    steps: list[dict[str, Any]] = []  # trajectory steps with a label
    trajs: list[dict[str, Any]] = []  # per block: rho
    comp_rows: list[dict[str, Any]] = []
    unk: list[dict[str, Any]] = []
    mixed: Counter[tuple[str, str]] = Counter()
    n_units = 0
    for u in qt.units("TEST"):
        rec = read_blocks(u)
        if rec is None:
            continue
        n_units += 1
        g = qn.Graph.read(u.net)
        cs = qt.constructs(u, g)
        scored = bool(cs) and qt.has_labels(u)
        lab = qt.cell_kinds(u, g) if scored else []
        blocks = rec["blocks"]
        cells_of = [final_cells(b) for b in blocks]
        if u.cell in qt.O_CELLS:
            mixed.update(_mixed_counts(u))
        for c in cs:
            if c.kind == "glue":
                continue
            row = _construct_row(u, c, blocks, cells_of, d70)
            cons.append(row)
        for bi, b in enumerate(blocks):
            claims.append(_claim_row(u, b, cells_of[bi], cs, lab, scored))
            if b["unknown_cohesive"]:
                unk.append({"set": u.set, "design": u.design, "cell": u.cell, "bid": b["bid"],
                            "size": len(cells_of[bi]), "anchor": b["anchor_kind"],
                            "label": plurality(cells_of[bi], lab) if scored else "n/a",
                            "top3": json.dumps(b["final"])})
            if scored:
                _step_rows(u, b, lab, steps, trajs, prior_vec)
        for cp in rec["composites"]:
            comp_rows.append({"set": u.set, "design": u.design, "cell": u.cell, "a": cp["a"],
                              "b": cp["b"], "kinds": "+".join(cp["kinds"]),
                              "union_top": cp["union_top3"][0][0],
                              "union_p": cp["union_top3"][0][1],
                              "union_entropy": cp["union_entropy"]})
    return {"cons": cons, "claims": claims, "steps": steps, "trajs": trajs, "comp": comp_rows,
            "unk": unk, "mixed": mixed, "n_units": n_units, "prior_top3": prior_top3,
            "prior": prior}


def _mixed_counts(u: qt.Unit) -> Counter[tuple[str, str]]:
    out: Counter[tuple[str, str]] = Counter()
    with (u.net.parent / "labels.csv").open(encoding="utf-8", newline="") as fh:
        for r in csv.DictReader(fh):
            if r["kind"] in ("pi", "po"):
                continue
            mp = r["module_path"]
            cat = "mixed (*)" if "*" in mp else ("part" if re.search(r"/u\d+(?:/|$)", mp)
                                                 else "top-level or single")
            out[(u.cell, cat)] += 1
            if int(r["n_spans"] or 0) > 1:
                out[(u.cell, "more than one span")] += 1
            out[(u.cell, "all")] += 1
    return out


def _construct_row(u: qt.Unit, c: qt.Construct, blocks: list[dict[str, Any]],
                   cells_of: list[set[int]], d70: dict[Any, dict[str, str]]) -> dict[str, Any]:
    row: dict[str, Any] = {"set": u.set, "design": u.design, "cell": u.cell, "part": c.idx,
                           "kind": c.kind, "n_true": len(c.cells), "scored": int(bool(c.cells)),
                           "right": 0, "jaccard": 0.0, "coverage": 0.0, "cell_precision": 0.0,
                           "block": -1, "argmax": "", "pmax": 0.0, "in_top3": 0, "seeded": 0,
                           "stop": "",
                           "block_size": 0}
    key = (u.set, u.design, u.cell, c.idx, c.kind)
    d = d70.get(key)
    row["d70_right"] = int(d is not None and d["jaccard"] not in ("", "nan") and
                           float(d["coverage"]) >= 0.8 and float(d["jaccard"]) >= 0.5)
    row["d70_known"] = int(d is not None)
    row["d70_hit"] = int(d is not None and d["hit"] == "1")
    row["d70_class"] = d["class"] if d is not None else ""
    if not c.cells:
        return row
    best = -1
    best_j = -1.0
    for bi, cells in enumerate(cells_of):
        if cells & c.cells:
            row["seeded"] = 1
        j = bl.jaccard(cells, set(c.cells))[0]
        if j > best_j or (j == best_j and best >= 0 and len(cells) < len(cells_of[best])):
            best, best_j = bi, j
    if best >= 0 and best_j > 0:
        b = blocks[best]
        ok, jac, cov = right(cells_of[best], c.cells)
        row.update({"right": int(ok), "jaccard": round(jac, 4), "coverage": round(cov, 4),
                    "cell_precision": round(len(cells_of[best] & c.cells) / len(cells_of[best]), 4),
                    "block": best, "argmax": b["final"][0][0], "pmax": b["final"][0][1],
                    "in_top3": int(c.kind in [k for k, _ in b["final"]]), "stop": b["stop"],
                    "block_size": len(cells_of[best])})
    return row


def _claim_row(u: qt.Unit, b: dict[str, Any], cells: set[int], cs: list[qt.Construct],
               lab: list[str], scored: bool) -> dict[str, Any]:
    argmax = b["final"][0][0]
    pmax = b["final"][0][1]
    match = ""
    if scored:
        for c in cs:
            if c.cells and c.kind != "glue" and right(cells, c.cells)[0]:
                match = c.kind
    return {"set": u.set, "design": u.design, "cell": u.cell, "bid": b["bid"],
            "anchor": b["anchor_kind"], "size": len(cells), "argmax": argmax, "pmax": pmax,
            "entropy": b["entropy"], "scored": int(scored), "right_for": match,
            "label": (plurality(cells, lab) or "") if scored else "", "stop": b["stop"],
            "looks": b["looks"]}


def _step_rows(u: qt.Unit, b: dict[str, Any], lab: list[str], steps: list[dict[str, Any]],
               trajs: list[dict[str, Any]], prior: np.ndarray) -> None:
    labels = step_labels(b, lab)
    n_kinds = len(KINDS)
    xs: list[float] = []
    hs: list[float] = []
    for t, label in zip(b["traj"], labels, strict=False):
        size, ent, post = t[0], t[1], t[2:2 + n_kinds]
        if float(np.abs(np.array(post) - prior).max()) < 1e-3:  # no signature yet: the prior
            continue
        order = sorted(range(n_kinds), key=lambda k: -post[k])
        steps.append({"design": u.design, "cell": u.cell, "size": size, "entropy": ent,
                      "pmax": post[order[0]], "argmax": KINDS[order[0]], "label": label or "",
                      "top3": [KINDS[k] for k in order[:3]]})
        xs.append(math.log2(size))
        hs.append(ent)
    if len(xs) >= 6:
        trajs.append({"design": u.design, "cell": u.cell, "rho": spearman(xs, hs)})
