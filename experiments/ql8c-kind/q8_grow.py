"""Grow the #74 paths on the FIT designs: ``python -B q8_grow.py [JOBS]`` (at most 2 processes).

Same grower as q7_paths (q6_grow no-stop variant), on the units of the even TUNE half of at most 400
cells, written to $QL8C_OUT/paths_fit/<set>__<design>__<cell>.json. Smallest first. Used only
to give the glue class its wrong grown blocks (EXPERIMENT.md, deviation 2).
"""

from __future__ import annotations

import json
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Any

import q8_env as env

q7p = env.mod("q7_paths")
qm6 = env.mod("q6_model")
qn = env.mod("q6_net")
qt = env.mod("q6_truth")
PATHS = env.OUT8 / "paths_fit"


def fit_units() -> list[Any]:
    us = [u for u in qt.units("TUNE") if qt.has_labels(u) and env.design_set(u.design) == "FIT"
          and u.net.stat().st_size > 0]
    return sorted(us, key=lambda u: u.net.stat().st_size)


def run_unit(key: tuple[str, str, str]) -> int:
    kind, design, cell = key
    dest = PATHS / f"{kind}__{design}__{cell}.json"
    if dest.is_file():
        return 0
    u = next(x for x in qt.units("TUNE", (cell,)) if x.set == kind and x.design == design)
    if qn.Graph.read(u.net).b.n > env.q7env.MAX_UNIT_CELLS:
        return 0
    rec = q7p.grow_unit(u, qm6.load(env.OUT6 / "model.json"))
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = Path(str(dest) + ".part")
    tmp.write_text(json.dumps(rec, sort_keys=True), encoding="utf-8")
    tmp.replace(dest)
    return 1


def main(argv: list[str]) -> int:
    n_jobs = min(int(argv[0]) if argv else 2, 2)
    keys = [(u.set, u.design, u.cell) for u in fit_units()]
    with ProcessPoolExecutor(n_jobs) as pool:
        done = sum(pool.map(run_unit, keys, chunksize=1))
    print(len(keys), "units,", done, "grown")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
