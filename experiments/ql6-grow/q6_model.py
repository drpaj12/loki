"""Likelihood of a block's directed graphlet signature per construct kind, and the posterior.

Feature x(B): Hellinger-scaled orbit frequencies (129 values, q6_sig.feature). Per target cell
and kind k: x ~ Normal(a_k + b_k * log2(size), diag(v_k)), a ridge-regressed mean line in log size
(so the likelihood of a 4-cell piece and of a 400-cell block of the same kind differ) and a
residual variance shrunk toward the pooled one. The 129 orbits are far from independent, so the
log-likelihood is tempered: P(k | B) proportional to prior_k * exp(T * loglik_k). T is fitted on
held-out TUNE blocks (q6_train.py), never on TEST. Cells with fewer than MIN_N training
samples of a kind use the kind's fit pooled over all cells.
"""

from __future__ import annotations

import csv
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from q6_env import EXP, KINDS

MIN_N = 12
VAR_FLOOR = 1e-3
SHRINK_N = 20.0
ALL = "ALL"


def census_prior() -> dict[str, float]:
    """Kind priors from the L3 census, VerilogEval corpus (frequency.csv): counter includes
    timer, shift includes lfsr, the rest as named."""
    merge = {"timer": "counter", "lfsr": "shift"}
    raw = dict.fromkeys(KINDS, 0.0)
    with (EXP / "l3-census" / "results" / "frequency.csv").open(encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            if r["corpus"] == "veval":
                k = merge.get(r["pattern"], r["pattern"])
                if k in raw:
                    raw[k] += float(r["fraction"])
    tot = sum(raw.values())
    return {k: v / tot for k, v in raw.items()}


@dataclass
class KindFit:
    a: np.ndarray
    b: np.ndarray
    var: np.ndarray
    n: int

    def loglik(self, x: np.ndarray, size: int) -> float:
        mu = self.a + self.b * math.log2(max(size, 1))
        return float(-0.5 * np.sum((x - mu) ** 2 / self.var + np.log(self.var)))


def fit_kind(xs: np.ndarray, sizes: np.ndarray, pooled_var: np.ndarray | None) -> KindFit:
    s = np.log2(np.maximum(sizes, 1))
    design = np.stack([np.ones_like(s), s], axis=1)
    ridge = 1e-3 * np.eye(2)
    coef = np.linalg.solve(design.T @ design + ridge, design.T @ xs)
    resid = xs - design @ coef
    n = len(xs)
    v = (resid ** 2).mean(axis=0) + VAR_FLOOR
    if pooled_var is not None:
        v = (n * v + SHRINK_N * pooled_var) / (n + SHRINK_N)
    return KindFit(coef[0], coef[1], np.maximum(v, VAR_FLOOR), n)


class Model:
    def __init__(self, fits: dict[tuple[str, str], KindFit], prior: dict[str, float],
                 temperature: float = 1.0) -> None:
        self.fits = fits
        self.prior = prior
        self.T = temperature

    def fit_for(self, cell: str, kind: str) -> KindFit:
        f = self.fits.get((cell, kind))
        if f is None or f.n < MIN_N:
            f = self.fits[(ALL, kind)]
        return f

    def logliks(self, cell: str, x: np.ndarray, size: int) -> np.ndarray:
        return np.array([self.fit_for(cell, k).loglik(x, size) for k in KINDS])

    def posterior(self, cell: str, x: np.ndarray, size: int) -> np.ndarray:
        ll = self.T * self.logliks(cell, x, size) + np.log([self.prior[k] for k in KINDS])
        ll -= ll.max()
        p = np.exp(ll)
        return p / p.sum()

    def evidence(self, cell: str, x: np.ndarray, size: int, w: np.ndarray) -> float:
        """log sum_k w_k exp(T loglik_k): the block's evidence under kind weights ``w``."""
        ll = self.T * self.logliks(cell, x, size) + np.log(np.maximum(w, 1e-300))
        m = ll.max()
        return float(m + math.log(np.exp(ll - m).sum()))

    def to_json(self) -> dict[str, Any]:
        return {"schema": 1, "kinds": list(KINDS), "temperature": self.T, "prior": self.prior,
                "fits": {f"{c}|{k}": {"n": f.n, "a": np.round(f.a, 6).tolist(),
                                      "b": np.round(f.b, 6).tolist(),
                                      "var": np.round(f.var, 6).tolist()}
                         for (c, k), f in sorted(self.fits.items())}}

    @classmethod
    def from_json(cls, d: dict[str, Any]) -> Model:
        fits = {}
        raw: dict[str, dict[str, Any]] = d["fits"]
        for key, v in raw.items():
            c, k = key.split("|")
            fits[(c, k)] = KindFit(np.array(v["a"]), np.array(v["b"]), np.array(v["var"]),
                                   int(v["n"]))
        prior: dict[str, float] = d["prior"]
        return cls(fits, {k: float(prior[k]) for k in KINDS}, float(d["temperature"]))


def entropy_bits(p: np.ndarray) -> float:
    q = p[p > 0]
    return float(-(q * np.log2(q)).sum())


def fit_all(samples: list[tuple[str, str, int, np.ndarray]], prior: dict[str, float]) -> Model:
    """samples: (cell, kind, size, feature)."""
    by: dict[tuple[str, str], list[int]] = {}
    for i, (c, k, _s, _x) in enumerate(samples):
        by.setdefault((c, k), []).append(i)
        by.setdefault((ALL, k), []).append(i)
    xs_all = np.array([x for *_a, x in samples])
    sz_all = np.array([s for _c, _k, s, _x in samples])
    pooled: dict[str, np.ndarray] = {}
    for k in KINDS:
        idx = by.get((ALL, k), [])
        if idx:
            pooled[k] = fit_kind(xs_all[idx], sz_all[idx], None).var
    fits = {}
    for (c, k), idx in by.items():
        if idx:
            fits[(c, k)] = fit_kind(xs_all[idx], sz_all[idx], None if c == ALL else pooled[k])
    return Model(fits, prior)


def fit_temperature(model: Model, samples: list[tuple[str, str, int, np.ndarray]]) -> float:
    """Temperature minimising the held-out negative log posterior of the true kind."""
    best, best_nll = 1.0, math.inf
    for t in (0.002, 0.005, 0.01, 0.02, 0.03, 0.05, 0.075, 0.1, 0.15, 0.2, 0.3, 0.5, 1.0):
        model.T = t
        nll = 0.0
        for c, k, s, x in samples:
            nll -= math.log(max(model.posterior(c, x, s)[KINDS.index(k)], 1e-12))
        if nll < best_nll:
            best, best_nll = t, nll
    model.T = best
    return best


def save(model: Model, path: Path) -> None:
    path.write_text(json.dumps(model.to_json(), sort_keys=True), encoding="utf-8")


def load(path: Path) -> Model:
    return Model.from_json(json.loads(path.read_text(encoding="utf-8")))
