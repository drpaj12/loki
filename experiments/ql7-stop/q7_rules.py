"""The stop rules of Q-L7 (EXPERIMENT.md "Candidate stop rules"): each picks one prefix per block.

A rule maps a BlockPath to the index k of the chosen prefix (0 = the anchor). Rules a and b have
one parameter (lambda, L0) chosen on TRAIN; rule c is a classifier fitted on TRAIN; rule d combines
two chosen prefixes. Ties go to the smaller prefix.
"""

from __future__ import annotations

import math
from collections.abc import Callable

import numpy as np
import q7_env as env
import q7_feat as ft
from sklearn.ensemble import HistGradientBoostingClassifier

Picker = Callable[[ft.BlockPath], int]
LAMBDAS = (-1.0, -0.5, 0.0, 0.5, 1.0, 2.0, 4.0)
L0S = (2, 4, 8, 16)
OPERATORS = ("smaller", "larger", "middle")
GLUE = env.KINDS.index("glue")
FEATURES = ("log2_size", "p_ng", "p_glue", "entropy", "ev", "odds", "d_p_ng", "d_ev", "phi",
            "d_phi", "phi_above_min", "p_ng_below_max", "fan_in", "fan_out", "ff_share")


def mask(bp: ft.BlockPath) -> np.ndarray:
    """Prefixes a rule may choose: those with a signature, all of them if none has."""
    m = bp.has_signal()
    return m if m.any() else np.ones(bp.n, dtype=bool)


def p_ng(bp: ft.BlockPath) -> np.ndarray:
    return np.asarray(np.delete(bp.post, GLUE, axis=1).max(axis=1))


def odds(bp: ft.BlockPath) -> np.ndarray:
    """L = ln p_ng - ln P(glue), glue clamped at 1e-4 (the posterior is stored to 4 digits)."""
    return np.log(np.maximum(p_ng(bp), 1e-4)) - np.log(np.maximum(bp.post[:, GLUE], 1e-4))


def first_best(score: np.ndarray, ok: np.ndarray) -> int:
    s = np.where(ok, score, -np.inf)
    return int(np.argmax(s))  # first maximum = the smaller prefix


def rule_a(bp: ft.BlockPath, lam: float) -> int:
    return first_best(odds(bp) - lam * np.log(bp.size), mask(bp))


def rule_b(bp: ft.BlockPath, l0: int) -> int:
    phi, ok = bp.phi, mask(bp)
    for k in range(bp.n):
        if not ok[k] or (k > 0 and not phi[k] < phi[k - 1]):
            continue
        w = max(l0, math.ceil(0.25 * int(bp.size[k])))
        ahead = phi[k + 1:k + 1 + w]
        if len(ahead) == 0 or phi[k] <= ahead.min():
            return k
    return first_best(-phi, ok)


def features(bp: ft.BlockPath) -> np.ndarray:
    """(K, len(FEATURES)) matrix of the per-prefix features of the classifier."""
    pn, pg, od = p_ng(bp), bp.post[:, GLUE], odds(bp)
    ent = -np.sum(np.where(bp.post > 0, bp.post * np.log2(np.maximum(bp.post, 1e-12)), 0.0), axis=1)
    ev = np.maximum(bp.ev, ft.NO_EV_CLIP)
    d_pn = np.diff(pn, prepend=pn[0])
    d_ev = np.diff(ev, prepend=ev[0])
    d_phi = np.diff(bp.phi, prepend=bp.phi[0])
    return np.stack([np.log2(bp.size), pn, pg, ent, ev, od, d_pn, d_ev, bp.phi, d_phi,
                     bp.phi - np.minimum.accumulate(bp.phi),
                     np.maximum.accumulate(pn) - pn, bp.fan_in, bp.fan_out, bp.ff], axis=1)


def right_any(bp: ft.BlockPath) -> np.ndarray:
    """Label of rule c: the prefix is right for some construct of its unit."""
    return np.asarray(bp.right.any(axis=0)) if bp.inter.shape[0] else np.zeros(bp.n, dtype=bool)


def fit_classifier(blocks: list[ft.BlockPath], n_cons: list[int],
                   ) -> HistGradientBoostingClassifier:
    xs, ys = [], []
    for bp, nc in zip(blocks, n_cons, strict=True):
        if nc:
            xs.append(features(bp))
            ys.append(right_any(bp))
    clf = HistGradientBoostingClassifier(max_depth=3, max_iter=100, learning_rate=0.1,
                                         random_state=0)
    clf.fit(np.vstack(xs), np.concatenate(ys).astype(int))
    return clf


def rule_c(bp: ft.BlockPath, clf: HistGradientBoostingClassifier) -> int:
    p = clf.predict_proba(features(bp))[:, 1]
    return first_best(p, mask(bp))


def combine(op: str, ka: int, kb: int, bp: ft.BlockPath) -> int:
    if op == "smaller":
        return min(ka, kb)
    if op == "larger":
        return max(ka, kb)
    target = math.sqrt(float(bp.size[ka]) * float(bp.size[kb]))
    return int(np.argmin(np.abs(np.log(bp.size) - math.log(target))))


def end_of_path(bp: ft.BlockPath) -> int:
    return bp.n - 1


def pickers(cfg: dict[str, object], clf: HistGradientBoostingClassifier) -> dict[str, Picker]:
    """Named pickers for the chosen settings: a, b, c, d (when cfg has the pair and operator),
    plus the reference END."""
    lam, l0 = float(str(cfg["lambda"])), int(str(cfg["L0"]))
    out: dict[str, Picker] = {
        "a": lambda bp: rule_a(bp, lam),
        "b": lambda bp: rule_b(bp, l0),
        "c": lambda bp: rule_c(bp, clf),
    }
    pair, op = cfg.get("pair"), cfg.get("operator")
    if isinstance(pair, list) and isinstance(op, str):
        pa, pb = out[pair[0]], out[pair[1]]
        out["d"] = lambda bp: combine(op, pa(bp), pb(bp), bp)
    out["END"] = end_of_path
    return out
