"""Stage 2 evaluation rows: per-design kind scores, tiling, chains, seeding (EXPERIMENT.md).

Usage: l16_eval.py kinds | tiling | chain | seed     (each writes its ``l16_*.csv``)
Arms: W, WB (new runs, ``r5lib.run_dir``) and R2N, R2C (existing runs, ``base_dir``).
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

import l10_propagate
import l11_chain
import r3lib
import r5lib

from loki.score.gt import SCORED_TYPES, GtInstance, derive_instances
from loki.score.match import jaccard
from loki.score.metrics import Pred, load_preds

PLAN = (("f2", ("MI", "VT", "CI", "CO")), ("f3", ("MI", "VT")), ("f1-k6", ("MI",)))
BASE_SETS = {("MI", "f2"): ("M2N", "M2C"), ("VT", "f2"): ("V2N", "V2C"),
             ("MI", "f3"): ("M3N", "M3C"), ("VT", "f3"): ("V3N", "V3C"),
             ("MI", "f1-k6"): ("M1N", "M1N")}
NEW_ARMS = ("W", "WB", "W1", "WB1")  # W1, WB1: Stage-0 FSM rule variants (l16_explore.py)
ALL_ARMS = ("R2N", "R2C", "W", "WB")
FRAG = 0.8
DRAWS = 5
FAMILIES: dict[str, frozenset[str]] = {
    "storage": frozenset({"$dff", "$dffe", "$adff", "$adffe", "$sdff", "$sdffe", "$sdffce",
                          "$dffsr", "$dffsre", "$aldff", "$aldffe", "$dlatch", "$adlatch",
                          "$dlatchsr", "register", "counter", "fsm"}),
    "mux": frozenset({"$mux", "$pmux", "mux_tree"}),
    "compare": frozenset({"$eq", "$ne", "$lt", "$le", "$gt", "$ge"}),
    "arith": frozenset({"$add", "$sub", "$mul", "counter"}),
}
KIND_FAMILY = {"ff_en": "storage", "ff_srst": "storage", "register": "storage",
               "counter": "storage", "fsm": "storage", "mux_bit": "mux", "mux": "mux",
               "mux_tree": "mux", "eq_const": "compare", "comparator": "compare",
               "adder": "arith", "subtractor": "arith", "adder_cin": "arith"}


def dataset_of(name: str) -> Path:
    return {"MI": r5lib.MICRO, "VT": r5lib.VEVAL}.get(name, r5lib.CORPUS)


def run_path(arm: str, name: str, floor: str, design: str) -> Path:
    """The ``re`` run directory of (arm, set, design)."""
    if arm in NEW_ARMS:
        return r5lib.run_dir(arm, name, floor, design)
    if name in ("CI", "CO"):
        return r5lib.R4DATA / "runs" / f"{'N' if arm == 'R2N' else 'C'}-f2" / f"{design}__f2" / "re"
    sets = BASE_SETS[(name, floor)]
    rs = r3lib.SETS[sets[0] if arm == "R2N" else sets[1]]
    return r3lib.run_dir(rs, design)


def have(rd: Path) -> bool:
    return (rd / "overlay.json").is_file() and (rd / "score.json").is_file()


def designs(name: str, floor: str) -> list[str]:
    if floor == "f1-k6":
        return r5lib.ok_designs(r5lib.MICRO, floor)
    return [d for _, d in r5lib.eval_sets(floor)[name]]


def counted(rd: Path) -> list[Pred]:
    ov = json.loads((rd / "overlay.json").read_text(encoding="utf-8"))
    return [p for p in load_preds(ov)
            if p.kind in SCORED_TYPES and p.kind not in r5lib.HARD and p.counted(0.5)]


def live_buses(rd: Path) -> list[Pred]:
    ov = json.loads((rd / "overlay.json").read_text(encoding="utf-8"))
    return [p for p in load_preds(ov) if p.kind == "bus" and p.status != "rejected"]


def floor_dir(name: str, floor: str, design: str) -> Path:
    return dataset_of(name) / design / floor


def plan() -> list[tuple[str, str, str]]:
    return [(floor, name, arm) for floor, names in PLAN for name in names for arm in ALL_ARMS
            if not (floor == "f1-k6" and arm == "R2C")]


# -- kinds ---------------------------------------------------------------------------------------
def kinds_rows() -> int:
    rows: list[list[Any]] = []
    avail: list[list[Any]] = []
    for floor, name, arm in plan():
        for d in designs(name, floor):
            rd = run_path(arm, name, floor, d)
            if not have(rd):
                continue
            sec = ""
            sp = rd.parent / "seconds.txt"
            if sp.is_file():
                sec = sp.read_text(encoding="utf-8").strip()
            nodes = len(json.loads((floor_dir(name, floor, d) / "words.json").read_text(
                encoding="utf-8"))["words"])
            avail.append([arm, name, floor, d, nodes, sec])
            sc = json.loads((rd / "score.json").read_text(encoding="utf-8"))["constructs"]
            for k in sorted(sc):
                v = sc[k]
                if k not in r5lib.HARD and (v["counted"] or v["gt"]):
                    rows.append([arm, name, floor, d, k, v["counted"], v["matched"], v["gt"]])
    r5lib.write_csv(r5lib.OUT / "l16_kinds.csv",
                    ["arm", "set", "floor", "design", "kind", "counted", "matched", "gt"], rows)
    r5lib.write_csv(r5lib.OUT / "l16_designs.csv",
                    ["arm", "set", "floor", "design", "words", "seconds"], avail)
    return 0


# -- tiling --------------------------------------------------------------------------------------
def covered(g: GtInstance, preds: list[Pred]) -> bool:
    fams = {f for f, t in FAMILIES.items() if g.type in t}
    cover: set[str] = set()
    for p in preds:
        if (KIND_FAMILY.get(p.kind) in fams and p.cells
                and len(p.cells & g.footprint) / len(p.cells) >= FRAG):
            cover |= p.cells & g.footprint
    return len(cover) / len(g.footprint) >= FRAG


def tally(preds: list[Pred], gts: list[GtInstance]) -> dict[str, list[int]]:
    acc: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for g in gts:
        if len(g.footprint) < 2:
            continue
        for k in r5lib.KDICT:
            if g.type in SCORED_TYPES[k]:
                acc[k][0] += 1
                acc[k][1] += int(covered(g, preds))
    return acc


def node_pool(fdir: Path) -> dict[str, list[str]]:
    """Non-I/O non-constant node ids per cell kind (sorted)."""
    obj = json.loads((fdir / "graph.json").read_text(encoding="utf-8"))
    pool: dict[str, list[str]] = defaultdict(list)
    for n in obj["nodes"]:
        if n["kind"] not in ("pi", "po", "const"):
            pool[str(n["kind"])].append(str(n["id"]))
    return {k: sorted(v) for k, v in pool.items()}


def node_kinds(fdir: Path) -> dict[str, str]:
    obj = json.loads((fdir / "graph.json").read_text(encoding="utf-8"))
    return {str(n["id"]): str(n["kind"]) for n in obj["nodes"]}


def null_preds(preds: list[Pred], pool: dict[str, list[str]], nk: dict[str, str],
               design: str, draw: int) -> list[Pred]:
    """Each prediction replaced by random cells of the same size (same cell-kind multiset)."""
    rng = r5lib.seed_rng(design, draw)
    out = []
    for p in preds:
        cells: set[str] = set()
        want: dict[str, int] = defaultdict(int)
        for c in p.cells:
            want[nk.get(c, "lut")] += 1
        for k in sorted(want):
            src = pool.get(k, [])
            cells.update(rng.sample(src, min(want[k], len(src))))
        out.append(Pred(p.id, p.kind, frozenset(cells), p.p, p.status, p.detector, p.op))
    return out


def tiling_rows() -> int:
    rows: list[list[Any]] = []
    for floor, name, arm in plan():
        if floor != "f2":
            continue
        for d in designs(name, floor):
            rd = run_path(arm, name, floor, d)
            if not have(rd):
                continue
            fd = floor_dir(name, floor, d)
            gts = derive_instances(json.loads((fd / "words.json").read_text(encoding="utf-8")))
            preds = counted(rd)
            for k, (n, c) in sorted(tally(preds, gts).items()):
                rows.append([arm, name, d, k, n, c])
            if arm in ("W", "WB"):
                pool, nk = node_pool(fd), node_kinds(fd)
                acc: dict[str, float] = defaultdict(float)
                tot: dict[str, int] = {}
                for draw in range(DRAWS):
                    for k, (n, c) in tally(null_preds(preds, pool, nk, d, draw), gts).items():
                        acc[k] += c / DRAWS
                        tot[k] = n
                for k in sorted(tot):
                    rows.append([f"null-{arm}", name, d, k, tot[k], round(acc[k], 6)])
    r5lib.write_csv(r5lib.OUT / "l16_tiling.csv",
                    ["arm", "set", "design", "kind", "instances", "covered"], rows)
    return 0


# -- chains --------------------------------------------------------------------------------------
def chain_table(triples: list[tuple[str, str, str]]) -> list[list[Any]]:
    """Chain and FSM rows of (floor, set, arm) triples (floor f2, sets MI and VT only)."""
    rows: list[list[Any]] = []
    for floor, name, arm in triples:
        if floor != "f2" or name not in ("MI", "VT"):
            continue
        for d in designs(name, floor):
            rd = run_path(arm, name, floor, d)
            if not have(rd):
                continue
            words = json.loads((floor_dir(name, floor, d) / "words.json").read_text("utf-8"))
            c = l11_chain.analyse(words)
            gts = {g.gid: g for g in derive_instances(words)}
            preds = counted(rd)
            by_cell: dict[str, list[int]] = defaultdict(list)
            for i, p in enumerate(preds):
                for cell in p.cells:
                    by_cell[cell].append(i)
            res: dict[tuple[str, int], tuple[int, int, int]] = {}
            for role, ids in (("fb_register", c.fb), ("decoder", set(c.dec)),
                              ("sink", set(c.sinks))):
                for wid in sorted(ids):
                    g = l11_chain.element_gid(gts, wid, role == "fb_register")
                    if g is not None:
                        res[(role, wid)] = l11_chain.proposed(g, preds, by_cell)
            for x, decs in sorted(c.sinks.items()):
                for dd in sorted(decs):
                    for s in sorted(c.dec[dd]):
                        el = [res.get(("fb_register", s)), res.get(("decoder", dd)),
                              res.get(("sink", x))]
                        if None in el:
                            continue
                        ok = int(all(e and e[0] for e in el))
                        kc = int(all(e and e[1] for e in el))
                        rows.append([arm, name, d, f"{s}_{dd}_{x}", ok, kc,
                                     *(int(bool(e and e[0])) for e in el)])
            for g in gts.values():
                if g.type == "fsm":
                    hit = int(any(p.kind == "fsm" and jaccard(p.cells, g.footprint) >= 0.5
                                  for p in preds))
                    rows.append([arm, name, d, f"fsm_{g.gid}", hit, hit, 0, 0, 0])
    return rows


def chain_rows() -> int:
    rows = chain_table(plan())
    r5lib.write_csv(r5lib.OUT / "l16_chain.csv",
                    ["arm", "set", "design", "item", "complete", "kind_correct", "reg", "dec",
                     "sink"], rows)
    return 0


# -- seeding -------------------------------------------------------------------------------------
def seeded(kinds: dict[str, str], insts: list[GtInstance],
           words: list[frozenset[str]]) -> dict[str, int]:
    by_cell: dict[str, list[int]] = defaultdict(list)
    for i, y in enumerate(words):
        for c in y:
            by_cell[c].append(i)
    out: dict[str, int] = {}
    for g in insts:
        if g.gid not in kinds:
            continue
        near = {i for c in g.footprint for i in by_cell.get(c, ())}
        out[g.gid] = int(any(
            len(words[i] & g.footprint) >= 2
            and len(words[i] & g.footprint) / len(words[i]) >= 0.5 for i in near))
    return out


def seed_rows() -> int:
    rows: list[list[Any]] = []
    for floor, name, arm in plan():
        if floor != "f2" or name not in ("MI", "VT"):
            continue
        for d in designs(name, floor):
            rd = run_path(arm, name, floor, d)
            if not have(rd):
                continue
            fd = floor_dir(name, floor, d)
            words = json.loads((fd / "words.json").read_text(encoding="utf-8"))
            insts = derive_instances(words)
            kinds = l10_propagate.kinds_of(words, insts)
            preds = counted(rd)
            ws = [p.cells for p in preds] + [p.cells for p in live_buses(rd)]
            hit = seeded(kinds, insts, [w for w in ws if w])
            tot: dict[str, list[float]] = defaultdict(lambda: [0.0, 0.0])
            for g, k in kinds.items():
                tot[k][0] += 1
                tot[k][1] += hit.get(g, 0)
            for k in sorted(tot):
                rows.append([arm, name, d, k, tot[k][0], tot[k][1]])
            if arm in ("W", "WB"):
                pool, nk = node_pool(fd), node_kinds(fd)
                allw = preds + live_buses(rd)
                nacc: dict[str, float] = defaultdict(float)
                for draw in range(DRAWS):
                    nw = [p.cells for p in null_preds(allw, pool, nk, d, draw) if p.cells]
                    nh = seeded(kinds, insts, nw)
                    for g, k in kinds.items():
                        nacc[k] += nh.get(g, 0) / DRAWS
                for k in sorted(tot):
                    rows.append([f"null-{arm}", name, d, k, tot[k][0], round(nacc[k], 6)])
    r5lib.write_csv(r5lib.OUT / "l16_seed.csv",
                    ["arm", "set", "design", "kind", "constructs", "seeded"], rows)
    return 0


if __name__ == "__main__":
    fn = {"kinds": kinds_rows, "tiling": tiling_rows, "chain": chain_rows,
          "seed": seed_rows}.get(sys.argv[1] if len(sys.argv) > 1 else "")
    raise SystemExit(fn() if fn else print(__doc__) or 2)
