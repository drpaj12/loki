"""Fuzzy signature methods fit on TUNE, scored on TEST: ``python -B fz_run.py``.

Methods (see EXPERIMENT.md): nn-emd (histogram distance, GDD marginals), nn-cos (cosine of log
totals,
fuzzy directed levels), clf-lr and clf-rf (learned classifiers) on the levels und, dir, dir_a0.25,
dir_a0.5, dir_a1, dir_col. Each method gives per-partition pattern probabilities; the acceptance
threshold is fit on TUNE out-of-fold probabilities. Writes results/fz_*.csv.
"""

from __future__ import annotations

import os
import random
import sys
from collections import defaultdict
from typing import Any

import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

os.environ.setdefault("PART_PREFIX", "fz")
import fzlib as fl  # noqa: E402
import l3dlib  # noqa: E402
import match_eval as me  # noqa: E402
import part_eval as pe  # noqa: E402

ENT = fl.PATS
SEED = 7


class Prob:
    """Stand-in for Calib: row[tag][p] = [probability, 0]."""

    def post(self, g: float, c: float) -> float:  # noqa: ARG002
        return g


def make_model(kind: str) -> Any:
    if kind == "rf":
        return RandomForestClassifier(n_estimators=200, min_samples_leaf=2, n_jobs=8,
                                      class_weight="balanced_subsample", random_state=SEED)
    return make_pipeline(StandardScaler(), LogisticRegression(C=1.0, max_iter=3000,
                                                              class_weight="balanced"))


def proba(model: Any, x: np.ndarray) -> np.ndarray:
    """(n, 7) probabilities over PATS (missing classes 0; glue mass dropped)."""
    p = model.predict_proba(x)
    out = np.zeros((len(x), len(ENT)))
    for j, c in enumerate(model.classes_):
        if c in ENT:
            out[:, ENT.index(c)] = p[:, j]
    return out


def fit_oof(kind: str, xl: np.ndarray, yl: list[str], xt: np.ndarray, yt: list[str],
            gt: list[str], xo: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """OOF probabilities on TUNE rows (group k-fold by design; library always in training) and
    probabilities of the final model (library + all TUNE) on the other rows ``xo``."""
    oof = np.zeros((len(xt), len(ENT)))
    folds = GroupKFold(n_splits=5)
    for tr, te in folds.split(xt, yt, gt):
        m = make_model(kind)
        m.fit(np.vstack([xl, xt[tr]]) if len(xl) else xt[tr],
              [*yl, *[yt[i] for i in tr]] if len(xl) else [yt[i] for i in tr])
        oof[te] = proba(m, xt[te])
    m = make_model(kind)
    m.fit(np.vstack([xl, xt]) if len(xl) else xt, [*yl, *yt])
    return oof, proba(m, xo)


def emd_dists(q: np.ndarray, lib: np.ndarray, pats: np.ndarray, ffq: int, ffl: np.ndarray,
              tag: str) -> np.ndarray:
    """Per pattern the smallest mean-over-orbits W1 (log1p counts) to library entries."""
    sel = np.ones(len(pats), bool) if tag == "all" else ffl == ffq
    d = np.full(len(ENT), np.nan)
    if not sel.any():
        return d
    w = np.abs(lib[sel] - q[None]).sum(axis=2).mean(axis=1) * 0.25  # sum |dF| * grid step
    for j, p in enumerate(ENT):
        m = pats[sel] == p
        if m.any():
            d[j] = w[m].min()
    return d


def cos_dists(q: np.ndarray, lib: np.ndarray, pats: np.ndarray, ffq: int, ffl: np.ndarray,
              tag: str) -> np.ndarray:
    sel = np.ones(len(pats), bool) if tag == "all" else ffl == ffq
    d = np.full(len(ENT), np.nan)
    if not sel.any():
        return d
    ln = np.linalg.norm(lib[sel], axis=1)
    qn = np.linalg.norm(q)
    c = (lib[sel] @ q) / np.where(ln * qn > 0, ln * qn, 1.0)
    for j, p in enumerate(ENT):
        m = pats[sel] == p
        if m.any():
            d[j] = 1.0 - c[m].max()
    return d


def fill(d: np.ndarray) -> np.ndarray:
    big = np.nanmax(d) if np.isfinite(d).any() else 1.0
    return np.where(np.isnan(d), big * 1.5 + 0.01, d)


def main() -> int:
    parts = [r for r in fl.read_parts() if r["mode"] != "none" and not r.get("error")]
    lib = fl.Lib()
    fam = me.truth_family()
    split = {r["design"]: r["split"] for r in l3dlib.read_csv(l3dlib.RES / "split_single.csv")}
    ng = {(r["design"], r["cell"]): r["n_groups"] for r in fl.read_parts()}
    # per (level) partition table
    by_mode: dict[str, list[dict[str, Any]]] = {"undirected": [], "directed": []}
    for r in parts:
        by_mode[r["mode"]].append(r)
    for rs in by_mode.values():
        for r in rs:
            r["po"] = fl.per_orbit(r, fl.NORB[r["mode"]])
            r["tune"] = r["set"] == "single" and split.get(r["design"]) == "TUNE" \
                and r["design"] in fam
            r["lab"] = fam.get(r["design"], "glue") if r["set"] == "single" else ""
    # methods: name -> (rows, probs (n,7))
    methods: dict[str, tuple[list[dict[str, Any]], np.ndarray]] = {}
    oof_of: dict[str, np.ndarray] = {}
    tune_idx: dict[str, list[int]] = {}
    for level in fl.LEVELS:
        mode = fl.mode_of(level)
        rows = by_mode[mode]
        x = np.array([fl.feature(r["po"], r["nodes"], r["ff"], r["cell"], level) for r in rows])
        ti = [i for i, r in enumerate(rows) if r["tune"]]
        xl, yl = [], []
        for cell in fl.CELLS:
            for e in lib.rows[(cell, mode)]:
                xl.append(fl.feature(e["po"], e["nodes"], max(e["ff"], 0), cell, level))
                yl.append(e["pattern"])
        xl_a = np.array(xl)
        for kind in ("lr", "rf"):
            oof, allp = fit_oof(kind, xl_a, yl, x[ti], [rows[i]["lab"] for i in ti],
                                [rows[i]["design"] for i in ti], x)
            name = f"clf-{kind}:{level}"
            methods[name] = (rows, allp)
            oof_of[name] = oof
            tune_idx[name] = ti
            print(name, "done", flush=True)
    # nearest-entry methods
    for level in fl.LEVELS:
        mode = fl.mode_of(level)
        rows = by_mode[mode]
        ti = [i for i, r in enumerate(rows) if r["tune"]]
        for tag in ("ff", "all"):
            kinds = ["cos"] + (["emd"] if level in ("und", "dir") else [])
            for kind in kinds:
                d = np.zeros((len(rows), len(ENT)))
                for cell in fl.CELLS:
                    ents = lib.rows[(cell, mode)]
                    pats = np.array([e["pattern"] for e in ents])
                    ffl = np.array([e["ff"] for e in ents])
                    if kind == "emd":
                        mat = np.array([e["po"]["cdf"] for e in ents])
                    else:
                        mat = np.array([fl.raw_smoothed(e["po"], level) for e in ents])
                    for i, r in enumerate(rows):
                        if r["cell"] != cell:
                            continue
                        if kind == "emd":
                            d[i] = fill(emd_dists(r["po"]["cdf"], mat, pats, r["ff"], ffl, tag))
                        else:
                            d[i] = fill(cos_dists(fl.raw_smoothed(r["po"], level), mat, pats,
                                                  r["ff"], ffl, tag))
                oof, allp = fit_oof("lr", np.zeros((0, len(ENT))), [], d[ti],
                                    [rows[i]["lab"] for i in ti], [rows[i]["design"] for i in ti],
                                    d)
                name = f"nn-{kind}:{level}:{tag}"
                methods[name] = (rows, allp)
                oof_of[name] = oof
                tune_idx[name] = ti
                print(name, "done", flush=True)
    report(methods, oof_of, tune_idx, fam, split, ng)
    return 0


def to_by(methods: dict[str, tuple[list[dict[str, Any]], np.ndarray]]
          ) -> dict[tuple[str, str, str, str], list[dict[str, Any]]]:
    by: dict[tuple[str, str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for name, (rows, pr) in methods.items():
        for r, p in zip(rows, pr, strict=True):
            row = {"gi": r["gi"], "links": r["links"], "ff": {q: [float(p[j]), 0.0]
                                                           for j, q in enumerate(ENT)}}
            by[(r["set"], r["design"], r["cell"], name)].append(row)
    return by


def report(methods: dict[str, tuple[list[dict[str, Any]], np.ndarray]],
           oof_of: dict[str, np.ndarray], tune_idx: dict[str, list[int]], fam: dict[str, str],
           split: dict[str, str], ng: dict[tuple[str, str], int]) -> None:
    cal = Prob()
    by = to_by(methods)
    thr_of: dict[str, float] = {}
    rows_thr: list[dict[str, Any]] = []
    all_single = sorted({(r["design"], r["cell"]) for r in fl.read_parts() if r["set"] == "single"})
    for name in methods:
        rows = methods[name][0]
        ti = tune_idx[name]
        oof = oof_of[name]
        tune_by: dict[tuple[str, str], list[np.ndarray]] = defaultdict(list)
        for k, i in enumerate(ti):
            tune_by[(rows[i]["design"], rows[i]["cell"])].append(oof[k])
        tune_keys = [dc for dc in all_single if split.get(dc[0]) == "TUNE" and dc[0] in fam]

        def f1(thr: float, name: str = name, tune_by: Any = tune_by, tune_keys: Any = tune_keys
               ) -> float:
            tp = fp = fn = 0
            for d, c in tune_keys:
                f = {ENT[int(np.argmax(v))] for v in tune_by.get((d, c), [])
                     if v.max() >= thr}
                if ng.get((d, c), 0) == 0:
                    f.add("glue")
                for p in (*ENT, "glue"):
                    t, x = int(fam[d] == p), int(p in f)
                    tp += t & x
                    fp += (1 - t) & x
                    fn += t & (1 - x)
            return 2 * tp / (2 * tp + fp + fn) if tp + fp + fn else 0.0

        grid = [x / 100 for x in range(5, 100, 5)]
        thr = max(grid, key=lambda t: (round(f1(t), 6), t))
        thr_of[name] = thr
        rows_thr.append({"method": name, "threshold": thr, "tune_F1": round(f1(thr), 3)})
    l3dlib.write_csv(fl.RES / "fz_threshold.csv", list(rows_thr[0]), rows_thr)
    cals = {(name, "ff"): (cal, thr_of[name]) for name in methods}
    # singles
    rule: dict[tuple[str, str], dict[str, int]] = {}
    for r in l3dlib.read_csv(l3dlib.RES / "partA_design.csv"):
        rule[(r["design"], r["cell"])] = {e: int(r[f"found_{e}"]) for e in l3dlib.ENTRIES}
    test = [(d, c) for d, c in all_single if split.get(d) == "TEST" and (d, c) in rule
            and d in fam]
    tune_s = [(d, c) for d, c in all_single if split.get(d) == "TUNE" and (d, c) in rule
              and d in fam]
    found: dict[tuple[str, str, str], set[str]] = {}
    for name in methods:
        for d, c in [*test, *tune_s]:
            f = {pe.accepted(cal, r, "ff", thr_of[name]) for r in by.get(("single", d, c, name), [])
                 } - {""}
            if ng.get((d, c), 0) == 0:
                f.add("glue")
            found[(name, d, c)] = f
    per: dict[tuple[str, str, str], dict[str, tuple[int, int, int]]] = defaultdict(dict)
    variants = ["rule", *methods, *[f"hybrid:{m}" for m in methods]]
    for v in variants:
        for p in l3dlib.ENTRIES:
            for d, c in test:
                t = int(fam[d] == p)
                if v == "rule":
                    x = rule[(d, c)][p]
                elif v.startswith("hybrid:"):
                    x = int(rule[(d, c)][p] or p in found[(v[7:], d, c)])
                else:
                    x = int(p in found[(v, d, c)])
                per[(v, p, c)][d] = (t & x, (1 - t) & x, t & (1 - x))
    tab = single_table(per)
    # per-pattern hybrid choice (TUNE F1 of rule vs rule OR signature), for the best clf on TUNE
    best = max((r for r in rows_thr if r["method"].startswith("clf")), key=lambda r: r["tune_F1"])
    choice = {}
    for p in l3dlib.ENTRIES:
        def pf1(use_sig: bool, p: str = p) -> float:
            tp = fp = fn = 0
            for d, c in tune_s:
                x = rule[(d, c)][p] or (use_sig and p in found[(best["method"], d, c)])
                t = int(fam[d] == p)
                tp += t & int(bool(x))
                fp += (1 - t) & int(bool(x))
                fn += t & (1 - int(bool(x)))
            return 2 * tp / (2 * tp + fp + fn) if tp + fp + fn else 0.0
        choice[p] = pf1(True) > pf1(False)
    pname = "pp:" + best["method"]
    for p in l3dlib.ENTRIES:
        for d, c in test:
            t = int(fam[d] == p)
            x = int(rule[(d, c)][p] or (choice[p] and p in found[(best["method"], d, c)]))
            per[(pname, p, c)][d] = (t & x, (1 - t) & x, t & (1 - x))
    tab = single_table(per)
    l3dlib.write_csv(fl.RES / "fz_table.csv", list(tab[0]), tab)
    ch = [{"pattern": p, "use_signature_with_rule": int(v), "method": best["method"]}
          for p, v in choice.items()]
    l3dlib.write_csv(fl.RES / "fz_hybrid_choice.csv", list(ch[0]), ch)
    # reliability
    rel: dict[tuple[str, int], list[int]] = defaultdict(lambda: [0, 0])
    for name, (rows, pr) in methods.items():
        for r, p in zip(rows, pr, strict=True):
            if r["set"] == "single" and split.get(r["design"]) == "TEST" and r["design"] in fam:
                for j, q in enumerate(ENT):
                    a = rel[(name, min(9, int(p[j] * 10)))]
                    a[0] += 1
                    a[1] += int(q == fam[r["design"]])
    l3dlib.write_csv(fl.RES / "fz_reliability.csv", ["method", "bin", "pairs", "observed_same"],
                        [{"method": k[0], "bin": f"{k[1] / 10:.1f}-{(k[1] + 1) / 10:.1f}",
                          "pairs": v[0], "observed_same": round(v[1] / v[0], 3)}
                         for k, v in sorted(rel.items())])
    # composites and wires (part_eval machinery); per-pattern hybrid as method "pp"
    pp_methods = dict(methods)
    ppname = "pp"
    rows, pr = methods[best["method"]]
    pr2 = pr.copy()
    for j, p in enumerate(ENT):
        if not choice[p]:
            pr2[:, j] = 0.0
    pp_methods[ppname] = (rows, pr2)
    cals[(ppname, "ff")] = (cal, thr_of[best["method"]])
    pe.comp_eval(to_by(pp_methods), cals)
    print("best", best, "choice", choice)


def single_table(per: dict[tuple[str, str, str], dict[str, tuple[int, int, int]]]
                 ) -> list[dict[str, Any]]:
    tab = []
    for (v, p, c), dd in sorted(per.items()):
        cnt = list(dd.values())
        tp, fp, fn = (sum(x[i] for x in cnt) for i in range(3))
        pr, rc = me.prf(cnt)
        lp, lr = l3dlib.bootstrap(cnt)
        tab.append({"variant": v, "pattern": p, "cell": c, "designs": len(cnt), "TP": tp, "FP": fp,
                    "FN": fn, "precision": round(pr, 3), "precision_lo": round(lp, 3),
                    "recall": round(rc, 3), "recall_lo": round(lr, 3),
                    "label": l3dlib.label(pr, rc, lp, lr, tp + fn)})
    return tab


if __name__ == "__main__":
    random.seed(SEED)
    sys.exit(main())
