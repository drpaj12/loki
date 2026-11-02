"""Scoring of a posterior on the grown and true blocks (EXPERIMENT.md "Evaluation").

``unit_vector`` turns one unit record and a posterior into a flat vector of counts, so that sums
over units, scopes and bootstrap resamples are plain sums. Layout (K = 5 kinds, NB = 10 bins):
claims K, tp K, cons K, rec K (grown) | tclaims K, ttp K, tcons K (true) | for each of the
three calibration sets (grown all, grown right, true) NB x (n, confidence sum, correct) | top-3
right (n, hits) | top-3 true (n, hits) | nll sum, nll n (grown all).
"""

from __future__ import annotations

import math
import random
from collections.abc import Callable
from typing import Any

import numpy as np
import q8_env as env
import q8_model as qm

K = len(env.KINDS5)
NB = 10
MIN_CLAIM = 4
Post = Callable[[str, np.ndarray, int], np.ndarray]
O_CLAIMS, O_TP, O_CONS, O_REC = 0, K, 2 * K, 3 * K
O_TCLAIMS, O_TTP, O_TCONS = 4 * K, 5 * K, 6 * K
O_CAL = 7 * K  # three calibration sets of NB x 3
O_TOP3 = O_CAL + 3 * NB * 3
O_NLL = O_TOP3 + 4
LEN = O_NLL + 2
CAL_SETS = ("grown_all", "grown_right", "true")


def cal_add(v: np.ndarray, which: int, p: np.ndarray, label: list[int]) -> None:
    conf = float(p.max())
    b = min(int(conf * NB), NB - 1)
    o = O_CAL + (which * NB + b) * 3
    v[o] += 1
    v[o + 1] += conf
    v[o + 2] += int(int(np.argmax(p)) in label)


def unit_vector(rec: dict[str, Any], post: Post) -> np.ndarray:
    v = np.zeros(LEN)
    cons = {(p, k) for p, k, _n in rec["cons"]}
    for _p, k, _n in rec["cons"]:
        v[O_CONS + env.KINDS5.index(k)] += 1
    recovered: set[tuple[int, str]] = set()
    for b in rec["blocks"]:
        p = post(rec["cell"], b["x"], b["size"])
        arg = int(np.argmax(p))
        kinds = sorted({k for _p, k in b["right"]})
        label = qm.label_set(kinds)
        if arg != env.GLUE and b["size"] >= MIN_CLAIM:
            i = env.KINDS5.index(env.KINDS[arg])
            v[O_CLAIMS + i] += 1
            v[O_TP + i] += env.KINDS[arg] in kinds
            recovered.update((pt, k) for pt, k in b["right"] if k == env.KINDS[arg])
        cal_add(v, 0, p, label)
        v[O_NLL] += -math.log(max(float(p[label].sum()), 1e-12))
        v[O_NLL + 1] += 1
        if kinds:
            cal_add(v, 1, p, label)
            v[O_TOP3] += 1
            v[O_TOP3 + 1] += bool(set(label) & set(np.argsort(-p)[:3].tolist()))
    for _pt, k in recovered & cons:
        v[O_REC + env.KINDS5.index(k)] += 1
    for t in rec["true"]:
        p = post(rec["cell"], t["x"], t["size"])
        arg = int(np.argmax(p))
        ki = env.KINDS.index(t["kind"])
        if arg != env.GLUE and t["size"] >= MIN_CLAIM:
            i = env.KINDS5.index(env.KINDS[arg])
            v[O_TCLAIMS + i] += 1
            v[O_TTP + i] += arg == ki
        v[O_TCONS + env.KINDS5.index(t["kind"])] += 1
        cal_add(v, 2, p, [ki])
        v[O_TOP3 + 2] += 1
        v[O_TOP3 + 3] += ki in np.argsort(-p)[:3].tolist()
    return v


def f1s(tp: np.ndarray, claims: np.ndarray, cons: np.ndarray, rec: np.ndarray) -> np.ndarray:
    """Per-kind F1 from precision tp/claims and recall rec/cons (0 when undefined)."""
    prec = np.divide(tp, claims, out=np.zeros(K), where=claims > 0)
    recall = np.divide(rec, cons, out=np.zeros(K), where=cons > 0)
    den = prec + recall
    out: np.ndarray = np.divide(2 * prec * recall, den, out=np.zeros(K), where=den > 0)
    return out


def macro_f1(v: np.ndarray, true: bool = False) -> float:
    if true:
        return float(f1s(v[O_TTP:O_TTP + K], v[O_TCLAIMS:O_TCLAIMS + K],
                         v[O_TCONS:O_TCONS + K], v[O_TTP:O_TTP + K]).mean())
    return float(f1s(v[O_TP:O_TP + K], v[O_CLAIMS:O_CLAIMS + K], v[O_CONS:O_CONS + K],
                     v[O_REC:O_REC + K]).mean())


def ece(v: np.ndarray, which: int) -> float:
    a = v[O_CAL + which * NB * 3:O_CAL + (which + 1) * NB * 3].reshape(NB, 3)
    n = a[:, 0].sum()
    if n == 0:
        return math.nan
    ok = a[:, 0] > 0
    return float(np.sum(np.abs(a[ok, 2] - a[ok, 1])) / n)


def top3(v: np.ndarray, true: bool) -> float:
    o = O_TOP3 + (2 if true else 0)
    return float(v[o + 1] / v[o]) if v[o] else math.nan


def reliability(v: np.ndarray, which: int) -> list[dict[str, Any]]:
    a = v[O_CAL + which * NB * 3:O_CAL + (which + 1) * NB * 3].reshape(NB, 3)
    return [{"bin": f"{b / NB:.1f}-{(b + 1) / NB:.1f}", "n": int(a[b, 0]),
             "confidence": round(a[b, 1] / a[b, 0], 4) if a[b, 0] else "",
             "accuracy": round(a[b, 2] / a[b, 0], 4) if a[b, 0] else ""} for b in range(NB)]


def kind_rows(v: np.ndarray, true: bool) -> list[dict[str, Any]]:
    if true:
        cl, tp, cons, rec = (v[O_TCLAIMS:O_TCLAIMS + K], v[O_TTP:O_TTP + K],
                             v[O_TCONS:O_TCONS + K], v[O_TTP:O_TTP + K])
    else:
        cl, tp, cons, rec = (v[O_CLAIMS:O_CLAIMS + K], v[O_TP:O_TP + K], v[O_CONS:O_CONS + K],
                             v[O_REC:O_REC + K])
    f = f1s(tp, cl, cons, rec)
    out = [{"kind": k, "claims": int(cl[i]), "tp": int(tp[i]),
            "precision": round(tp[i] / cl[i], 3) if cl[i] else "", "constructs": int(cons[i]),
            "recalled": int(rec[i]), "recall": round(rec[i] / cons[i], 3) if cons[i] else "",
            "f1": round(float(f[i]), 3)} for i, k in enumerate(env.KINDS5)]
    c, t, n, r = (float(a.sum()) for a in (cl, tp, cons, rec))
    out.append({"kind": "all", "claims": int(c), "tp": int(t),
                "precision": round(t / c, 3) if c else "", "constructs": int(n),
                "recalled": int(r), "recall": round(r / n, 3) if n else "",
                "f1": round(float(f.mean()), 3)})
    return out


def boot(by_design: dict[str, np.ndarray], stat: Callable[[np.ndarray], float], n: int = 1000,
         seed: int = 1) -> tuple[float, float, float]:
    """(point, 5th, 95th percentile) of ``stat`` of the summed vector over resampled designs."""
    names = sorted(by_design)
    mat = np.stack([by_design[d] for d in names])
    pt = stat(mat.sum(axis=0))
    rng = random.Random(seed)
    vals = []
    for _ in range(n):
        idx = [rng.randrange(len(names)) for _ in names]
        s = stat(mat[idx].sum(axis=0))
        if not math.isnan(s):
            vals.append(s)
    vals.sort()
    if not vals:
        return pt, math.nan, math.nan
    return pt, vals[int(0.05 * len(vals))], vals[min(len(vals) - 1, int(0.95 * len(vals)))]
