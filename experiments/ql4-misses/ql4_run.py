"""Misses of the graphlet detectors read in directed signature terms: ``python -B ql4_run.py``.

Needs $QL4_OUT/tsig (tsig.py) and the outputs of #68 to #71 in $GLET_OUT. Writes
results/records.csv (one row per construct x detector) and the tables of report.py.
See EXPERIMENT.md for the rule that classifies the misses.
"""

from __future__ import annotations

import json
import math
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import blocks as bl  # noqa: E402
import classify as cl  # noqa: E402
import dets  # noqa: E402
import fzlib as fl  # noqa: E402
import l3dlib  # noqa: E402
import live  # noqa: E402
import match_eval as me  # noqa: E402
import match_run as mr  # noqa: E402
import pt_ctx  # noqa: E402
import tsig  # noqa: E402

RES = HERE / "results"
NAN = math.nan
FAMS = ("fsm", "counter", "shift")
DETECTORS = ("D68", "D69", "D70", "D71h", "D71c")


@dataclass
class Construct:
    set: str
    design: str
    cell: str
    idx: int  # part index (0 for a single)
    family: str
    true: set[int] | None  # cells of the true block (None: no provenance for this cell)
    true_ff: int
    sig: dict[str, Any] | None
    n_by_line: int = 0


@dataclass
class Cand:
    """A block a detector compared: cells, the detector's score of it, and its group index."""

    gi: int
    cells: set[int]
    score: dets.BlockScore
    ff: int


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines()]


def constructs(ctxs: dict[tuple[str, str, str], pt_ctx.Ctx], split: dict[str, str],
               fam: dict[str, str], rule_keys: set[tuple[str, str]]) -> list[Construct]:
    out: list[Construct] = []
    for (kind, design, cell), ctx in sorted(ctxs.items()):
        if kind == "single":
            if split.get(design) != "TEST" or fam.get(design, "glue") == "glue" \
                    or (design, cell) not in rule_keys:
                continue
            p = live.OUT / "sig_l3" / "directed" / cell / f"{design}.json"
            sig = json.loads(p.read_text(encoding="utf-8")) if p.is_file() else None
            allc = set(range(ctx.blif.n))
            out.append(Construct("single", design, cell, 0, fam[design], allc,
                                 ctx.blif.n_latches(allc), sig))
            continue
        truth = json.loads((l3dlib.OUT / "composites" / design / "truth.json").read_text(
            encoding="utf-8"))
        tp = tsig.tsig_path(cell, design)
        tdata = json.loads(tp.read_text(encoding="utf-8")) if tp.is_file() else None
        ranges = {}
        if tdata is not None:
            ranges = bl.module_ranges(l3dlib.OUT / "composites" / design / f"{design}.sv",
                                      {p["idx"]: p["problem"] for p in truth["parts"]})
        parts = bl.part_blocks(ctx.blif, ctx.labels, ranges)[0] if tdata is not None else {}
        for part in truth["parts"]:
            for f in part["families"]:
                if f not in FAMS:
                    continue
                g = (tdata or {}).get(str(part["idx"]))
                if tdata is None:
                    out.append(Construct("comp", design, cell, part["idx"], f, None, -1, None))
                    continue
                sig = g if g is not None and "error" not in g else None
                out.append(Construct("comp", design, cell, part["idx"], f,
                                     parts.get(part["idx"], set()),
                                     int((g or {}).get("n_latches", 0)), sig,
                                     int((g or {}).get("n_by_line", 0))))
    return out


def candidates(det: str, ctx: pt_ctx.Ctx, nearest: dict[str, dets.Nearest],
               fuzzy: dict[str, dets.Fuzzy], rows: dict[str, dict[Any, Any]]) -> list[Cand]:
    kind, design, cell = ctx.key
    if det == "D68":
        r = rows["D68"].get((design, cell))
        if r is None or kind != "single":
            return []
        return [Cand(0, set(range(ctx.blif.n)), nearest["D68"].from_best(r["ff"]), -1)]
    out = []
    for gi, qs in enumerate(ctx.groups):
        key = (kind, design, cell, gi)
        if det in ("D69", "D70"):
            r = rows[det].get(key)
            if r is None:
                continue
            sc = nearest[det].from_best(r["ff"]) if "ff" in r else dets.BlockScore()
            out.append(Cand(gi, ctx.unb[gi] if det == "D69" else ctx.bnd[gi], sc, len(qs)))
        else:
            r = rows["sig"].get(key)
            if r is None:
                continue
            sc = fuzzy[det].score(r, r["ff"], cell) if "gdd" in r else dets.BlockScore()
            out.append(Cand(gi, ctx.bnd[gi], sc, len(qs)))
    return out


def claim_family_of(c: Cand, kind: str) -> str:
    """Composite parts merge counter+timer and shift+lfsr (#69 to #71); singles use the pattern."""
    return dets.FAMILY.get(c.score.accepted, c.score.accepted) if kind == "comp" \
        else c.score.accepted


def assign(cons: list[Construct], cands: list[Cand]) -> dict[int, Cand]:
    """Greedy one-to-one: accepted candidates to constructs of the same family, by overlap."""
    pairs = []
    for i, k in enumerate(cons):
        for j, c in enumerate(cands):
            if claim_family_of(c, k.set) == k.family:
                jac = bl.jaccard(c.cells, k.true)[0] if k.true is not None else 0.0
                pairs.append((-jac, i, j))
    got: dict[int, Cand] = {}
    used: set[int] = set()
    for _jac, i, j in sorted(pairs):
        if i not in got and j not in used:
            got[i] = cands[j]
            used.add(j)
    return got


def best_overlap(k: Construct, cands: list[Cand]) -> Cand | None:
    if not cands:
        return None
    if k.true is None:
        return cands[0]
    return max(cands, key=lambda c: (bl.jaccard(c.cells, k.true or set())[0], -c.gi))


def true_score(det: str, k: Construct, ctx: pt_ctx.Ctx, nearest: dict[str, dets.Nearest],
               fuzzy: dict[str, dets.Fuzzy], comp: Cand | None) -> dets.BlockScore | None:
    """Score of the TRUE block by the same detector. D68's compared block is the true block."""
    if k.sig is None:
        return None
    if det in nearest:
        return nearest[det].from_sig(k.cell, k.sig, k.true_ff)
    return fuzzy[det].score(k.sig, k.true_ff, k.cell)


def record(det: str, k: Construct, ctx: pt_ctx.Ctx, hit: bool, comp: Cand | None,
           ts: dets.BlockScore | None, thr: float) -> dict[str, Any]:
    jac, cov = (bl.jaccard(comp.cells, k.true) if comp is not None and k.true is not None
                else (0.0 if comp is None else NAN, 0.0 if comp is None else NAN))
    b = comp.score if comp is not None else dets.BlockScore()
    mg = k.set == "comp"
    n_true = len(k.true) if k.true is not None else -1
    return {
        "detector": det, "set": k.set, "design": k.design, "cell": k.cell, "part": k.idx,
        "family": k.family, "hit": int(hit), "no_partition": int(comp is None),
        "jaccard": jac, "coverage": cov, "n_true_cells": n_true,
        "true_ff": k.true_ff, "true_by_line": k.n_by_line,
        "ff_compared": comp.ff if comp is not None else -1,
        "b_dist": b.fam_dist(k.family, mg), "b_wrong": b.wrong_dist(k.family, mg),
        "b_score": b.fam_score(k.family, mg) if comp is not None else NAN,
        "b_accepted": b.accepted,
        "t_dist": ts.fam_dist(k.family, mg) if ts is not None else NAN,
        "t_wrong": ts.wrong_dist(k.family, mg) if ts is not None else NAN,
        "t_score": ts.fam_score(k.family, mg) if ts is not None else NAN,
        "t_accepted": ts.accepted if ts is not None else "",
        "threshold": thr,
    }


def main() -> int:
    mr.load_lib()
    split = {r["design"]: r["split"] for r in l3dlib.read_csv(l3dlib.RES / "split_single.csv")}
    fam = me.truth_family()
    rule_keys = {(r["design"], r["cell"]) for r in
                 l3dlib.read_csv(l3dlib.RES / "partA_design.csv")}
    nearest = dets.calibrations(split, fam)
    sigrows = [r for r in fl.read_parts() if r["mode"] == "directed" and not r.get("error")]
    fz_csv = HERE.parent / "graphlets-fuzzy" / "results" / "fz_threshold.csv"
    fuzzy = {"D71h": dets.Fuzzy("D71h", "emd", dets.read_thr(fz_csv, method="nn-emd:dir:ff")),
             "D71c": dets.Fuzzy("D71c", "rf", dets.read_thr(fz_csv, method="clf-rf:dir"))}
    tune = [(fl.per_orbit(r, fl.NORB["directed"]), int(r["nodes"]), int(r["ff"]), r["cell"],
             fam[r["design"]]) for r in sigrows
            if r["set"] == "single" and split.get(r["design"]) == "TUNE" and r["design"] in fam]
    for f in fuzzy.values():
        f.fit(tune)
        print(f.name, "fitted on", len(tune), "TUNE partitions", flush=True)
    rows: dict[str, dict[Any, Any]] = {"D68": {}, "D69": {}, "D70": {}, "sig": {}}
    for r in read_jsonl(live.OUT / "match" / "scores.jsonl"):
        if r["set"] == "l3" and r["mode"] == "directed":
            rows["D68"][(r["design"], r["cell"])] = r
    for det, fname in (("D69", "part_scores.jsonl"), ("D70", "part_scores_bounded.jsonl")):
        for r in read_jsonl(live.OUT / "match" / fname):
            if r["mode"] == "directed":
                rows[det][(r["set"], r["design"], r["cell"], r["gi"])] = r
    for r in fl.read_parts():
        if r["mode"] == "directed":
            rows["sig"][(r["set"], r["design"], r["cell"], r["gi"])] = r
    keys = sorted({("single", r["design"], r["cell"]) for r in fl.read_parts()
                   if r["set"] == "single" and split.get(r["design"]) == "TEST"
                   and fam.get(r["design"], "glue") != "glue"}
                  | {("comp", r["design"], r["cell"]) for r in fl.read_parts()
                     if r["set"] == "comp" and r["design"] in {
                         x["name"] for x in l3dlib.read_csv(l3dlib.RES / "composites.csv")
                         if x["split"] == "TEST"}})
    ctxs = {k: pt_ctx.build(*k) for k in keys}
    print(len(ctxs), "contexts", flush=True)
    cons = constructs(ctxs, split, fam, rule_keys)
    print(len(cons), "constructs", flush=True)
    by_ctx: dict[tuple[str, str, str], list[Construct]] = defaultdict(list)
    for k in cons:
        by_ctx[(k.set, k.design, k.cell)].append(k)
    recs: list[dict[str, Any]] = []
    for det in DETECTORS:
        thr = nearest[det].thr if det in nearest else fuzzy[det].thr
        for key, ks in sorted(by_ctx.items()):
            if det == "D68" and key[0] != "single":
                continue
            ctx = ctxs[key]
            cands = candidates(det, ctx, nearest, fuzzy, rows)
            got = assign(ks, cands)
            for i, k in enumerate(ks):
                hit = i in got
                comp = got.get(i) or best_overlap(k, cands)
                ts = true_score(det, k, ctx, nearest, fuzzy, comp)
                recs.append(record(det, k, ctx, hit, comp, ts, thr))
        print(det, "done", flush=True)
    classify_all(recs)
    RES.mkdir(exist_ok=True)
    cols = list(recs[0])
    l3dlib.write_csv(RES / "records.csv", cols, recs)
    print(len(recs), "records")
    return 0


def q90_table(recs: list[dict[str, Any]]) -> dict[tuple[str, str], float]:
    """90th percentile of hit distances per detector and family (pooled when < 10 hits)."""
    hits: dict[tuple[str, str], list[float]] = defaultdict(list)
    pooled: dict[str, list[float]] = defaultdict(list)
    for r in recs:
        if r["hit"] and not math.isnan(r["b_dist"]):
            hits[(r["detector"], r["family"])].append(r["b_dist"])
            pooled[r["detector"]].append(r["b_dist"])
    out = {}
    for (det, f), v in hits.items():
        out[(det, f)] = cl.percentile(v if len(v) >= 10 else pooled[det], 0.9)
    for det in {r["detector"] for r in recs}:
        for f in {r["family"] for r in recs}:
            out.setdefault((det, f), cl.percentile(pooled[det], 0.9))
    return out


def classify_all(recs: list[dict[str, Any]]) -> None:
    q90 = q90_table(recs)
    for r in recs:
        r["q90"] = q90[(r["detector"], r["family"])]
        r["class"] = ""
        r["kind"] = ""
        r["rank"] = 0
        if r["hit"]:
            continue
        if r["n_true_cells"] < 0:
            r["class"] = "unclassified (no provenance)"
            continue
        has = bool(dets.has_entry(r["cell"], r["family"], r["true_ff"], r["set"] == "comp")) \
            if r["true_ff"] > 0 else False
        sigless = math.isnan(r["t_dist"]) and r["true_ff"] > 0 and has
        f = cl.MissFacts(r["jaccard"], r["coverage"], r["true_ff"], has, r["t_dist"],
                         r["t_wrong"], r["q90"])
        r["class"] = "unclassified (no signature)" if sigless else cl.classify(f)
        r["rank"] = int(r["class"] == "threshold miss" and cl.rank_flag(f))
        r["kind"] = cl.DETECTOR_KIND.get(r["class"], "")


if __name__ == "__main__":
    raise SystemExit(main())
