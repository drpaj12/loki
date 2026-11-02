"""Features of the grown paths of a class set: ``python -B q8b_feat.py CLASSES SPLIT...``.

Units that got a new anchor are rebuilt from $QL8B_OUT/paths_<CLASSES>/<SPLIT>; every other unit is
#74's own (q7_feat pickle, read only). Writes $QL8B_OUT/feat_<CLASSES>_<SPLIT>.pkl.
"""

from __future__ import annotations

import json
import pickle
import sys
from typing import Any

import q8b_env as env

q7f = env.mod("q7_feat")
qt = env.mod("q6_truth")


def rebuild(var: str, split: str, old: list[Any]) -> list[Any]:
    d = env.paths_dir(var, split)
    units = {(u.set, u.design, u.cell): u for u in q7f.split_units(split)}
    out = []
    for ud in old:
        p = d / f"{ud.set}__{ud.design}__{ud.cell}.json"
        if p.is_file():
            u = units[ud.key]
            ud = q7f.unit_data(u, json.loads(p.read_text(encoding="utf-8")))
        out.append(ud)
    return out


def load(var: str, split: str) -> list[Any]:
    if var == "OLD":
        return list(q7f.load(split))
    with (env.OUT8 / f"feat_{var}_{split}.pkl").open("rb") as fh:
        data: list[Any] = pickle.load(fh)
    return data


def main(argv: list[str]) -> int:
    var = argv[0]
    for split in argv[1:]:
        data = rebuild(var, split, list(q7f.load(split)))
        env.OUT8.mkdir(parents=True, exist_ok=True)
        with (env.OUT8 / f"feat_{var}_{split}.pkl").open("wb") as fh:
            pickle.dump(data, fh)
        print(var, split, len(data), "units", sum(len(d.blocks) for d in data), "blocks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
