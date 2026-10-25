"""RQ-L12b: mine the signature dictionary on the corpus train split and score it.

Writes ``l12b_dict_rows.csv`` (per design and kind, variants V0/V1/V2 at the selected radius, the
other radii in the data directory), ``l12b_radius.csv`` (radius selection on the iid test) and
``l12b_stability.csv`` (floor stability of cone classes). Variants (EXPERIMENT.md, entry
2026-10-25-a): V0 = 4 leaves, G1; V1 = 6 leaves, G1; V2 = 6 leaves, G2.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import r4lib
from dictlib import KDICT, Dictionary, kinds_of_cells, load_fg, match, signatures

from loki.score.gt import derive_instances
from loki.score.metrics import construct_scores

VARIANTS: dict[str, tuple[int, bool]] = {"V0": (4, False), "V1": (6, False), "V2": (6, True)}
RADII = (0, 1, 2, 3)


def mine(floor: str, kmax: int) -> Dictionary:
    d = Dictionary(kmax)
    cs = r4lib.corpus_split()
    for des in r4lib.ok_designs(r4lib.CORPUS, floor):
        if cs[des][1] != "train":
            continue
        fdir = r4lib.CORPUS / des / floor
        sg = signatures(load_fg(fdir / "graph.json"), kmax)
        words = json.loads((fdir / "words.json").read_text(encoding="utf-8"))
        d.add(sg, kinds_of_cells(words))
    return d


def score_design(
    fdir: Path, d: Dictionary, kmax: int
) -> dict[tuple[int, bool], dict[str, tuple[int, int, int]]]:
    """Per (radius, clock_union): kind -> (counted, matched, gt) for one design."""
    sg = signatures(load_fg(fdir / "graph.json"), kmax)
    words = json.loads((fdir / "words.json").read_text(encoding="utf-8"))
    inst = derive_instances(words)
    out: dict[tuple[int, bool], dict[str, tuple[int, int, int]]] = {}
    for r in RADII:
        for cu in (False, True):
            preds = match(sg, d, r, cu)
            sc = construct_scores(preds, inst, 0.5)
            out[(r, cu)] = {k: (int(sc[k]["counted"]), int(sc[k]["matched"]), int(sc[k]["gt"]))
                            if k in sc else (0, 0, 0) for k in KDICT}
    return out


def micro_f1(rows: list[tuple[int, int, int]]) -> float:
    c = sum(x[0] for x in rows)
    m = sum(x[1] for x in rows)
    g = sum(x[2] for x in rows)
    return 2 * m / (c + g) if c + g else 0.0


def run_floor(floor: str) -> tuple[list[list[Any]], list[list[Any]], dict[str, Dictionary]]:
    sets = r4lib.eval_sets(floor)
    rows: list[list[Any]] = []
    radius_rows: list[list[Any]] = []
    cone_dicts: dict[str, Dictionary] = {}
    for var, (kmax, cu) in VARIANTS.items():
        d = mine(floor, kmax)
        cone_dicts[var] = d
        res: dict[tuple[str, str], dict[tuple[int, bool], dict[str, tuple[int, int, int]]]] = {}
        for sname, items in sets.items():
            for dataset, des in items:
                res[(sname, des)] = score_design(dataset / des / floor, d, kmax)
        f1s = {r: micro_f1([v for (s, _), x in res.items() if s == "iid"
                            for v in x[(r, cu)].values()]) for r in RADII}
        best = max(RADII, key=lambda r: (round(f1s[r], 9), -r))
        for r in RADII:
            radius_rows.append([floor, var, r, int(cu), round(f1s[r], 6), int(r == best)])
        for (sname, des), x in sorted(res.items()):
            for k in KDICT:
                c, m, g = x[(best, cu)][k]
                if c or g:
                    rows.append([f"dict-{var}", floor, sname, des, k, c, m, g])
        print(floor, var, "r", best, {r: round(v, 3) for r, v in f1s.items()}, flush=True)
    return rows, radius_rows, cone_dicts


def stability(dicts: dict[str, dict[str, Dictionary]]) -> list[list[Any]]:
    out: list[list[Any]] = []
    for var in ("V0", "V1"):
        f2, f3 = dicts["f2"][var], dicts["f3"][var]
        for k in KDICT:
            s2 = {c for c in f2.cone_tab if k in f2.cone_fires(c)}
            s3 = {c for c in f3.cone_tab if k in f3.cone_fires(c)}
            both = s2 & s3
            union = s2 | s3
            out.append([var, k, len(s2), len(s3), len(both),
                        round(len(both) / len(union), 6) if union else 0.0,
                        len(s3 - s2), len(s2 - s3)])
    return out


def main() -> int:
    if len(sys.argv) > 1:
        raise SystemExit("l12b_dict.py takes no arguments")
    rows: list[list[Any]] = []
    rad: list[list[Any]] = []
    dicts: dict[str, dict[str, Dictionary]] = {}
    for floor in r4lib.FLOORS:
        r, rr, dd = run_floor(floor)
        rows += r
        rad += rr
        dicts[floor] = dd
    r4lib.write_csv(r4lib.OUT / "l12b_dict_rows.csv",
                    ["arm", "floor", "set", "design", "kind", "counted", "matched", "gt"], rows)
    r4lib.write_csv(r4lib.OUT / "l12b_radius.csv",
                    ["floor", "variant", "radius", "clock_union", "iid_micro_f1", "selected"], rad)
    r4lib.write_csv(r4lib.OUT / "l12b_stability.csv",
                    ["variant", "kind", "n_f2", "n_f3", "shared", "jaccard", "lost_at_f2",
                     "lost_at_f3"], stability(dicts))
    print(len(rows), "rows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
