"""Exploratory measurements of the review fixes (dated 2026-10-25-c; EXPERIMENT.md). None of these
changes a Stage-0 status. Writes ``l16_x_*.csv``; ``paper_tables.py`` turns them into macros.

Usage: l16_explore.py fsm | eqconst | nullmix | fsmcomp | bigwb | all

* ``fsm``     counted ``fsm`` candidates of arms W, WB, W1, WB1 (W1, WB1: the Stage-0 FSM rule)
              classified by the ground-truth kind of the best-overlapping instance (item 2, 8), the
              kind-level ``fsm`` scores of the six arms, and the H16d chain table for W1, WB1.
* ``eqconst`` the cell sets of the counted ``eq_const`` candidates of W against R2N and WB (item 5).
* ``nullmix`` tiling and its random null by candidate subset (``ff_en`` and the rest) (item 4).
* ``fsmcomp`` fate of the ``fsm`` hypotheses that match a ground-truth FSM (item 11).
* ``bigwb``   arm WB on BIG, with the repetition filter, against arm W on the same designs.
"""

from __future__ import annotations

import json
import statistics
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

import l16_big
import l16_eval as E
import r5lib

from loki.score.gt import GtInstance, derive_instances
from loki.score.match import jaccard

SETS = ("MI", "VT", "CI", "CO")
ARMS6 = ("R2N", "R2C", "W", "WB", "W1", "WB1")
J_MIN = 0.5


def units(arms: tuple[str, ...]) -> list[tuple[str, str]]:
    """(set, design) pairs with a complete run in every arm."""
    out = []
    for s in SETS:
        for d in E.designs(s, "f2"):
            if all(E.have(E.run_path(a, s, "f2", d)) for a in arms):
                out.append((s, d))
    return out


def ff_group(cells: frozenset[str], nk: dict[str, str], gts: list[GtInstance]) -> tuple[str, float]:
    """Ground-truth kind of a candidate by its flip-flops: ``fsm`` when at least half of them lie
    in one ground-truth FSM instance, else ``counter``, else ``register`` (a ground-truth register
    that is neither: shift registers, LFSRs and the other coupled registers have no kind of their
    own in the ground truth), else ``none``. Returns the kind and the best containment."""
    ffs = frozenset(c for c in cells if nk.get(c) == "ff")
    if not ffs:
        return "none", 0.0
    best: dict[str, float] = {}
    for g in gts:
        if g.type in ("fsm", "counter", "register"):
            best[g.type] = max(best.get(g.type, 0.0), len(ffs & g.footprint) / len(ffs))
    for kind in ("fsm", "counter", "register"):
        if best.get(kind, 0.0) >= J_MIN:
            return kind, best[kind]
    return "none", max(best.values(), default=0.0)


def hyps(rd: Path) -> list[dict[str, Any]]:
    obj = json.loads((rd / "overlay.json").read_text(encoding="utf-8"))
    out = obj["hypotheses"]
    assert isinstance(out, list)
    return out


# -- fsm -----------------------------------------------------------------------------------------
def fsm_rows() -> None:
    cand: list[list[Any]] = []
    for arm in ("W", "WB", "W1", "WB1"):
        for s, d in units(("W", "WB", "W1", "WB1")):
            rd = E.run_path(arm, s, "f2", d)
            fd = E.floor_dir(s, "f2", d)
            gts = derive_instances(json.loads((fd / "words.json").read_text(encoding="utf-8")))
            nk = E.node_kinds(fd)
            live = {p.id: p for p in E.counted(rd)}
            for h in hyps(rd):
                if h["kind"] != "fsm" or h["detector"] != "wordfirst":
                    continue
                cells = frozenset(h["cells"])
                grp, j = ff_group(cells, nk, gts)
                cand.append([arm, s, d, h["id"], int(h["id"] in live), h["status"],
                             h["params"].get("decoders", 0), grp, r5lib.r6(j)])
    r5lib.write_csv(r5lib.OUT / "l16_x_fsmcand.csv",
                    ["arm", "set", "design", "id", "counted", "status", "decoders", "gt_group",
                     "ff_containment"], cand)
    kinds: list[list[Any]] = []
    for arm in ARMS6:
        for s, d in units(ARMS6):
            rd = E.run_path(arm, s, "f2", d)
            v = json.loads((rd / "score.json").read_text(encoding="utf-8"))["constructs"].get(
                "fsm")
            if v:
                kinds.append([arm, s, d, v["counted"], v["matched"], v["gt"]])
    r5lib.write_csv(r5lib.OUT / "l16_x_fsmkind.csv",
                    ["arm", "set", "design", "counted", "matched", "gt"], kinds)
    triples = [("f2", s, a) for s in ("MI", "VT") for a in ("W1", "WB1")]
    r5lib.write_csv(r5lib.OUT / "l16_x_chain.csv",
                    ["arm", "set", "design", "item", "complete", "kind_correct", "reg", "dec",
                     "sink"], E.chain_table(triples))


# -- eqconst -------------------------------------------------------------------------------------
def eqconst_rows() -> None:
    rows: list[list[Any]] = []
    for s in ("MI", "VT"):
        for d in E.designs(s, "f2"):
            runs = {a: E.run_path(a, s, "f2", d) for a in ("R2N", "W", "WB")}
            if not all(E.have(r) for r in runs.values()):
                continue
            sets = {a: {p.cells for p in E.counted(r) if p.kind == "eq_const"}
                    for a, r in runs.items()}
            ne = [h for h in hyps(runs["W"]) if h["kind"] == "eq_const"
                  and h["detector"] == "wordfirst" and h["params"].get("op") == "ne"]
            rows.append([s, d, len(sets["R2N"]), len(sets["W"]), len(sets["WB"]),
                         len(sets["W"] - sets["R2N"]), int(sets["WB"] == sets["R2N"]),
                         len(ne), sum(1 for h in ne if h["status"] == "refuted")])
    r5lib.write_csv(r5lib.OUT / "l16_x_eqconst.csv",
                    ["set", "design", "r2n", "w", "wb", "w_not_in_r2n", "wb_equals_r2n",
                     "w_ne", "w_ne_refuted"], rows)


# -- nullmix -------------------------------------------------------------------------------------
def nullmix_rows() -> None:
    rows: list[list[Any]] = []
    for s in SETS:
        for arm in ("R2N", "WB"):
            acc: dict[str, list[float]] = defaultdict(lambda: [0.0, 0.0, 0.0, 0.0])
            sizes: dict[str, list[int]] = defaultdict(list)
            for d in E.designs(s, "f2"):
                rd = E.run_path(arm, s, "f2", d)
                if not (E.have(rd) and E.have(E.run_path("R2C", s, "f2", d))):
                    continue
                fd = E.floor_dir(s, "f2", d)
                gts = derive_instances(json.loads((fd / "words.json").read_text(encoding="utf-8")))
                pool, nk = E.node_pool(fd), E.node_kinds(fd)
                preds = E.counted(rd)
                for name, sub in (("all", preds),
                                  ("ff_en", [p for p in preds if p.kind == "ff_en"]),
                                  ("other", [p for p in preds if p.kind != "ff_en"])):
                    real = E.tally(sub, gts)
                    inst = sum(v[0] for v in real.values())
                    cov = sum(v[1] for v in real.values())
                    ncov = 0.0
                    for draw in range(E.DRAWS):
                        nv = E.tally(E.null_preds(sub, pool, nk, d, draw), gts)
                        ncov += sum(v[1] for v in nv.values()) / E.DRAWS
                    a = acc[name]
                    a[0] += inst
                    a[1] += cov
                    a[2] += ncov
                    a[3] += len(sub)
                    sizes[name] += [len(p.cells) for p in sub]
            for name in ("all", "ff_en", "other"):
                a = acc[name]
                med = statistics.median(sizes[name]) if sizes[name] else 0
                small = sum(1 for x in sizes[name] if x <= 2)
                big = sum(1 for x in sizes[name] if x >= 10)
                rows.append([s, arm, name, int(a[3]), med, small, big,
                             max(sizes[name], default=0), int(a[0]), int(a[1]), r5lib.r6(a[2])])
    r5lib.write_csv(r5lib.OUT / "l16_x_nullmix.csv",
                    ["set", "arm", "subset", "candidates", "median_cells", "cells_le2",
                     "cells_ge10", "max_cells", "instances", "covered_real", "covered_null"], rows)


# -- fsmcomp -------------------------------------------------------------------------------------
def fsmcomp_rows() -> None:
    rows: list[list[Any]] = []
    for arm in ("W", "WB"):
        for s, d in units(("W", "WB")):
            rd = E.run_path(arm, s, "f2", d)
            fd = E.floor_dir(s, "f2", d)
            gts = [g for g in derive_instances(
                json.loads((fd / "words.json").read_text(encoding="utf-8"))) if g.type == "fsm"]
            hs = {h["id"]: h for h in hyps(rd)}
            live = {p.id for p in E.counted(rd)}
            for h in hs.values():
                if h["kind"] != "fsm" or h["detector"] != "wordfirst":
                    continue
                cells = frozenset(h["cells"])
                j = max((jaccard(cells, g.footprint) for g in gts), default=0.0)
                if j < J_MIN:
                    continue
                conf = sorted({hs[c]["kind"] for c in h.get("conflicts", []) if c in hs})
                rows.append([arm, s, d, h["id"], h["status"], int(h["id"] in live),
                             r5lib.r6(j), "+".join(conf)])
    r5lib.write_csv(r5lib.OUT / "l16_x_fsmcomp.csv",
                    ["arm", "set", "design", "id", "status", "counted", "jaccard",
                     "conflicts_with"], rows)


# -- bigwb ---------------------------------------------------------------------------------------
def bigwb_rows() -> None:
    order = json.loads((r5lib.DATA / "big_order.json").read_text(encoding="utf-8"))
    rows: list[list[Any]] = []
    status: list[list[Any]] = []
    for name in order:
        ds = r5lib.BIGDIR / name / "dataset"
        sub = next(ds.iterdir()).name
        rd = r5lib.run_dir("WB", "BIG", "f2", name)
        sp = rd.parent / "seconds.txt"
        if (rd / "score.json").is_file():
            st = "ok"
        elif (rd.parent / "timeout.txt").is_file():
            st = "timeout"
        elif (rd.parent / "stderr.txt").is_file():
            st = "error"
        else:
            st = "missing"
        status.append([name, st, sp.read_text(encoding="utf-8").strip() if sp.is_file() else ""])
        if st != "ok":
            continue
        for arm in ("W", "WB"):
            r, _flags = l16_big.design_rows(name, ds, sub, arm)
            rows += [[arm, *x] for x in r]
    r5lib.write_csv(r5lib.OUT / "l16_x_bigwb.csv",
                    ["arm", "design", "kind", "counted", "matched", "gt", "counted_F",
                     "matched_F"], rows)
    r5lib.write_csv(r5lib.OUT / "l16_x_bigwb_time.csv", ["design", "status", "seconds"], status)


def main() -> int:
    fns = {"fsm": fsm_rows, "eqconst": eqconst_rows, "nullmix": nullmix_rows,
           "fsmcomp": fsmcomp_rows, "bigwb": bigwb_rows}
    what = sys.argv[1] if len(sys.argv) > 1 else ""
    if what == "all":
        for fn in fns.values():
            fn()
        return 0
    if what not in fns:
        print(__doc__)
        return 2
    fns[what]()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
