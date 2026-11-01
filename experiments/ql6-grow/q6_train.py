"""Fit the likelihood model: ``python -B q6_train.py [JOBS]``.

Samples = signatures of prefixes of the ANSWER-KEY blocks of TUNE designs (even MD5 parity of the
design name trains the likelihood, odd calibrates the temperature). Writes $QL6_OUT/model.json,
results/model.json is a copy, results/train_summary.csv counts samples per cell and kind.
"""

from __future__ import annotations

import hashlib
import shutil
import sys
from collections import Counter
from concurrent.futures import ProcessPoolExecutor

import numpy as np
import q6_model as qm
import q6_net as qn
import q6_sig as qs
import q6_truth as qt
from q6_env import KINDS, OUT, RES, l3dlib

SCHEDULE = (2, 3, 4, 5, 6, 8, 10, 12, 16, 20, 24, 32, 48, 64, 96, 128, 192, 256, 384, 512, 600)
Sample = tuple[str, str, int, np.ndarray]


def half(design: str) -> str:
    return "train" if int(hashlib.md5(design.encode()).hexdigest(), 16) % 2 == 0 else "calib"


def seed_of(g: qn.Graph, anc: list[qn.Anchor], true: frozenset[int]) -> list[int]:
    inside = [a for a in anc if a.kind != "hard" and a.cells <= true]
    if inside:
        return sorted(max(inside, key=lambda a: (len(a.cells), -min(a.cells))).cells)
    ffs = [i for i in sorted(true) if g.b.latch[i]]
    return [ffs[0] if ffs else min(true)]


def visit_order(g: qn.Graph, true: frozenset[int], seed: list[int]) -> list[int]:
    """Breadth-first order inside the true block from the seed; jumps to the lowest unvisited
    cell when the walk is cut."""
    order = list(seed)
    seen = set(seed)
    head = 0
    while len(order) < len(true):
        if head >= len(order):
            nxt = min(true - seen)
            order.append(nxt)
            seen.add(nxt)
            continue
        for n in g.neighbours(order[head]):
            if n in true and n not in seen:
                seen.add(n)
                order.append(n)
        head += 1
    return order


def prefix_sizes(n_seed: int, n: int) -> list[int]:
    cap = min(n, 600)
    return sorted({n_seed, cap, *(s for s in SCHEDULE if n_seed < s < cap)})


def one(key: tuple[str, str, str, str]) -> list[tuple[str, str, int, np.ndarray, str]]:
    kind, design, cell, split = key
    u = next(x for x in qt.units(split, (cell,)) if x.set == kind and x.design == design)
    g = qn.Graph.read(u.net)
    anc = qn.anchors(g)
    sc = qs.SigCounter(u.net, g.b)
    out = []
    for c in qt.constructs(u, g):
        if not c.cells:
            continue
        seed = seed_of(g, anc, c.cells)
        order = visit_order(g, c.cells, seed)
        for s in prefix_sizes(len(seed), len(order)):
            x = qs.feature(sc.orbits(frozenset(order[:s])))
            out.append((cell, c.kind, s, x, half(design)))
    sc.close()
    return out


def collect(n_jobs: int) -> list[tuple[str, str, int, np.ndarray, str]]:
    keys = [(u.set, u.design, u.cell, u.split) for u in qt.units("TUNE") if qt.has_labels(u)]
    with ProcessPoolExecutor(n_jobs) as pool:
        return [r for part in pool.map(one, keys, chunksize=8) for r in part]


def main(argv: list[str]) -> int:
    n_jobs = int(argv[0]) if argv else 4
    rows = collect(n_jobs)
    train = [r[:4] for r in rows if r[4] == "train"]
    calib = [r[:4] for r in rows if r[4] == "calib"]
    model = qm.fit_all(train, qm.census_prior())
    t = qm.fit_temperature(model, calib)
    OUT.mkdir(parents=True, exist_ok=True)
    qm.save(model, OUT / "model.json")
    RES.mkdir(exist_ok=True)
    shutil.copy(OUT / "model.json", RES / "model.json")
    cnt: Counter[tuple[str, str, str]] = Counter((h, r[0], r[1]) for r in rows for h in (r[4],))
    summ = [{"half": h, "cell": c, "kind": k, "samples": n} for (h, c, k), n in sorted(cnt.items())]
    l3dlib.write_csv(RES / "train_summary.csv", list(summ[0]), summ)
    print(len(train), "train samples,", len(calib), "calibration samples, T =", t,
          "kinds", KINDS)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
