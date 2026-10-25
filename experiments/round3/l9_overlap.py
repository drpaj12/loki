"""RQ-L9: are the wrong candidates fragments of ground-truth word constructs, or noise?

Definitions: ``EXPERIMENT.md`` (round 3). Reads the runs of every set of ``r3lib.SETS`` that has
runs and writes ``l9_gt.csv``, ``l9_false.csv``, ``l9_confusion.csv`` and ``l9_h9b.csv``.
"""

from __future__ import annotations

import sys
from collections import Counter, defaultdict
from collections.abc import Sequence
from dataclasses import dataclass

import r3lib

from loki.score.gt import SCORED_TYPES, STORAGE, GtInstance
from loki.score.match import natural_key
from loki.score.metrics import Pred, construct_matches

FRAG_C = 0.8
FAMILIES: dict[str, frozenset[str]] = {
    "storage": STORAGE | {"register", "counter", "fsm"},
    "mux": frozenset({"$mux", "$pmux", "mux_tree"}),
    "compare": frozenset({"$eq", "$ne", "$lt", "$le", "$gt", "$ge"}),
    "arith": frozenset({"$add", "$sub", "$mul", "counter"}),
}
KIND_FAMILY = {
    "ff_en": "storage", "ff_srst": "storage", "register": "storage", "counter": "storage",
    "fsm": "storage", "mux_bit": "mux", "mux": "mux", "mux_tree": "mux", "eq_const": "compare",
    "comparator": "compare", "adder": "arith", "subtractor": "arith", "adder_cin": "arith",
}
DECISIVE = ("ff_en", "mux_bit", "eq_const", "register")
CLASSES = ("same_extent", "fragment_related", "fragment_other", "straddle", "partial", "noise")
HARD_ONLY = frozenset({"$mul", "$mem"})


def fams_of(gtype: str) -> frozenset[str]:
    return frozenset(f for f, types in FAMILIES.items() if gtype in types)


@dataclass
class Run:
    preds: list[Pred]
    gts: list[GtInstance]
    inter: list[dict[int, int]]  # per candidate: GT index -> |c & g|
    matched_p: set[str]
    matched_g: set[str]


def index_gts(gts: Sequence[GtInstance]) -> dict[str, list[int]]:
    by_cell: dict[str, list[int]] = defaultdict(list)
    for gi, g in enumerate(gts):
        for c in g.footprint:
            by_cell[c].append(gi)
    return by_cell


def scorer_matches(preds: Sequence[Pred], gts: Sequence[GtInstance]) -> tuple[set[str], set[str]]:
    """Prediction ids and GT ids matched one-to-one, per kind as ``construct_scores`` does."""
    mp: set[str] = set()
    mg: set[str] = set()
    for kind, types in SCORED_TYPES.items():
        sel = [p for p in preds if p.kind == kind]
        kg = [g for g in gts if g.type in types]
        for pid, gid, _j in construct_matches(sel, kg):
            mp.add(pid)
            mg.add(gid)
    return mp, mg


def load_run(rs: r3lib.RunSet, design: str) -> Run:
    preds = r3lib.counted_preds(rs, design)
    gts = r3lib.gt_instances(rs, design)
    by_cell = index_gts(gts)
    inter: list[dict[int, int]] = []
    for p in preds:
        cnt: Counter[int] = Counter()
        for c in p.cells:
            cnt.update(by_cell.get(c, ()))
        inter.append(dict(cnt))
    mp, mg = scorer_matches(preds, gts)
    return Run(preds, gts, inter, mp, mg)


def jac(inter: int, a: int, b: int) -> float:
    return inter / (a + b - inter) if a + b - inter else 0.0


def classify(p: Pred, inter: dict[int, int], gts: Sequence[GtInstance]) -> str:
    """The class of a false candidate (first rule of EXPERIMENT.md that applies)."""
    fam = KIND_FAMILY.get(p.kind, "")
    n = len(p.cells)
    related = [gi for gi in inter if fam in fams_of(gts[gi].type)]
    if any(jac(inter[gi], n, len(gts[gi].footprint)) >= 0.5 for gi in related):
        return "same_extent"
    if any(inter[gi] / n >= FRAG_C and len(gts[gi].footprint) > n for gi in related):
        return "fragment_related"
    if any(inter[gi] / n >= FRAG_C for gi in inter if gi not in related):
        return "fragment_other"
    cover = frozenset().union(*(p.cells & gts[gi].footprint for gi in inter)) if inter else None
    if cover is not None:
        if len(cover) / n >= FRAG_C and len(inter) >= 2:
            return "straddle"
        if len(cover) / n >= 0.5:
            return "partial"
    return "noise"


def confusion_type(inter: dict[int, int], n: int, gts: Sequence[GtInstance]) -> str:
    keys = [(-jac(k, n, len(gts[gi].footprint)), natural_key(gts[gi].gid), gts[gi].type)
            for gi, k in inter.items()]
    return min(keys)[2] if keys else "none"


def gt_rows(rs: r3lib.RunSet, run: Run, acc: dict[str, list[float]]) -> None:
    """Accumulate per GT type: n, matched, hit, touched, sum bestJ, sum frag, sum cov, cov>=0.8."""
    per_g: dict[int, list[tuple[int, int]]] = defaultdict(list)  # gi -> (cand idx, inter)
    for ci, inter in enumerate(run.inter):
        for gi, k in inter.items():
            per_g[gi].append((ci, k))
    for gi, g in enumerate(run.gts):
        if g.type in HARD_ONLY or not any(g.type in t for t in SCORED_TYPES.values()):
            continue
        size = len(g.footprint)
        hits = per_g.get(gi, [])
        best = max((jac(k, len(run.preds[ci].cells), size) for ci, k in hits), default=0.0)
        cov = frozenset().union(*(run.preds[ci].cells & g.footprint for ci, _k in hits)) \
            if hits else frozenset()
        row = acc.setdefault(g.type, [0.0] * 9)
        row[0] += 1
        row[1] += 1 if g.gid in run.matched_g else 0
        row[2] += 1 if best >= 0.5 else 0
        row[3] += 1 if hits else 0
        row[4] += best
        row[5] += len(hits)
        row[6] += len(cov) / size
        row[7] += 1 if len(cov) / size >= 0.8 else 0
        row[8] += 1 if size >= 2 else 0


def h9b_rows(run: Run, acc: dict[str, list[float]]) -> None:
    """Per decisive kind K, per GT instance of its types with >= 2 cells: fragment coverage."""
    per_g: dict[int, list[int]] = defaultdict(list)
    for ci, inter in enumerate(run.inter):
        for gi in inter:
            per_g[gi].append(ci)
    for kind in DECISIVE:
        for gi, g in enumerate(run.gts):
            if g.type not in SCORED_TYPES[kind] or len(g.footprint) < 2:
                continue
            fam = fams_of(g.type)
            frag: set[str] = set()
            anyc: set[str] = set()
            for ci in per_g.get(gi, []):
                p = run.preds[ci]
                anyc |= p.cells & g.footprint
                if KIND_FAMILY.get(p.kind) in fam and \
                        run.inter[ci][gi] / len(p.cells) >= FRAG_C:
                    frag |= p.cells & g.footprint
            size = len(g.footprint)
            row = acc.setdefault(kind, [0.0] * 6)
            row[0] += 1
            row[1] += 1 if g.gid in run.matched_g else 0
            row[2] += 1 if len(frag) / size >= 0.8 else 0
            row[3] += 1 if len(anyc) / size >= 0.8 else 0
            row[4] += len(frag) / size
            row[5] += len(anyc) / size


def false_rows(run: Run, acc: dict[str, Counter[str]]) -> None:
    for p, inter in zip(run.preds, run.inter, strict=True):
        c = acc.setdefault(p.kind, Counter())
        c["cand"] += 1
        if p.id in run.matched_p:
            c["matched"] += 1
        else:
            c["false"] += 1
            c[classify(p, inter, run.gts)] += 1


def main() -> int:
    gt_out: list[list[object]] = []
    false_out: list[list[object]] = []
    conf_out: list[list[object]] = []
    h9b_out: list[list[object]] = []
    design_out: list[list[object]] = []
    only = set(sys.argv[1:])
    for name, rs in r3lib.SETS.items():
        designs = r3lib.run_designs(rs)
        if not designs or (only and name not in only):
            continue
        gt_acc: dict[str, list[float]] = {}
        fa: dict[str, Counter[str]] = {}
        conf: Counter[tuple[str, str]] = Counter()
        hb: dict[str, list[float]] = {}
        for d in designs:
            run = load_run(rs, d)
            gt_rows(rs, run, gt_acc)
            false_rows(run, fa)
            da: dict[str, Counter[str]] = {}
            false_rows(run, da)
            for kind in DECISIVE:
                c = da.get(kind, Counter())
                design_out.append([name, d, kind, c["cand"], c["false"], *(c[k] for k in CLASSES)])
            h9b_rows(run, hb)
            for p, inter in zip(run.preds, run.inter, strict=True):
                conf[(p.kind, confusion_type(inter, len(p.cells), run.gts))] += 1
        for t, r in sorted(gt_acc.items()):
            gt_out.append([name, len(designs), t, int(r[0]), int(r[8]), int(r[1]), int(r[2]),
                           int(r[3]), r3lib.r6(r[4]), int(r[5]), r3lib.r6(r[6]), int(r[7])])
        for kind, c in sorted(fa.items()):
            false_out.append([name, len(designs), kind, c["cand"], c["matched"], c["false"],
                              *(c[k] for k in CLASSES)])
        for (ck, gtt), n in sorted(conf.items()):
            conf_out.append([name, ck, gtt, n])
        for kind in DECISIVE:
            r = hb.get(kind, [0.0] * 6)
            h9b_out.append([name, kind, int(r[0]), int(r[1]), int(r[2]), int(r[3]),
                            r3lib.r6(r[4]), r3lib.r6(r[5])])
        print("done", name, len(designs), flush=True)
    out = r3lib.HERE
    r3lib.write_csv(out / "l9_gt.csv",
                    ["set", "runs", "gt_type", "n_gt", "n_ge2", "n_matched", "n_hit_j05",
                     "n_touched", "sum_best_j", "sum_frag_n", "sum_cov_any", "n_cov_any_ge08"],
                    gt_out)
    r3lib.write_csv(out / "l9_false.csv",
                    ["set", "runs", "kind", "n_cand", "n_matched", "n_false", *CLASSES],
                    false_out)
    r3lib.write_csv(out / "l9_false_design.csv",
                    ["set", "design", "kind", "n_cand", "n_false", *CLASSES], design_out)
    r3lib.write_csv(out / "l9_confusion.csv", ["set", "cand_kind", "gt_type", "n"], conf_out)
    r3lib.write_csv(out / "l9_h9b.csv",
                    ["set", "kind", "n_gt", "n_matched", "n_cov_frag_ge08", "n_cov_any_ge08",
                     "sum_cov_frag", "sum_cov_any"], h9b_out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
