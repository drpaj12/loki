"""Per-prefix features and answer-key hits of the paths of one order.

``python -B q8a_feat.py ORDER SPLIT...``. Reuses q7_feat (BlockPath, UnitData). E74 is #74's own
pickle ($QL7_OUT/feat_<split>.pkl, read only).
Other orders write $QL8A_OUT/feat_<order>_<split>.pkl.
"""

from __future__ import annotations

import json
import pickle
import sys
from concurrent.futures import ProcessPoolExecutor
from typing import Any

import q8a_env as env

q7f = env.mod("q7_feat")
qt = env.mod("q6_truth")


def one(args: tuple[str, str, str, str, str, str]) -> Any:
    order, split, kind, design, cell, tsplit = args
    u = next(x for x in qt.units(tsplit, (cell,)) if x.set == kind and x.design == design)
    p = env.paths_dir(order, split) / f"{kind}__{design}__{cell}.json"
    return q7f.unit_data(u, json.loads(p.read_text(encoding="utf-8")))


def collect(order: str, split: str, n_jobs: int) -> list[Any]:
    us = sorted(q7f.split_units(split), key=lambda u: u.net.stat().st_size)
    keys = [(order, split, u.set, u.design, u.cell, u.split) for u in us
            if (env.paths_dir(order, split) / f"{u.set}__{u.design}__{u.cell}.json").is_file()]
    with ProcessPoolExecutor(n_jobs) as pool:
        return list(pool.map(one, keys, chunksize=4))


def load(order: str, split: str) -> list[Any]:
    if order == "E74":
        return list(q7f.load(split))
    with (env.OUT8 / f"feat_{order}_{split}.pkl").open("rb") as fh:
        data: list[Any] = pickle.load(fh)
    return data


def main(argv: list[str]) -> int:
    order = argv[0]
    for split in argv[1:]:
        data = collect(order, split, 2)
        env.OUT8.mkdir(parents=True, exist_ok=True)
        with (env.OUT8 / f"feat_{order}_{split}.pkl").open("wb") as fh:
            pickle.dump(data, fh)
        print(order, split, len(data), "units", sum(len(d.blocks) for d in data), "blocks",
              sum(len(d.cons) for d in data), "constructs")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
