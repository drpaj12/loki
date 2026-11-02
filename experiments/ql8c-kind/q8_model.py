"""The three likelihoods of Q-L8c (EXPERIMENT.md) and the tempered posterior.

Every model gives log P(features, size | kind) per target cell, with the pooled (cell = ALL) fit
as the fallback when a cell-kind has fewer than MIN_N samples. Posterior: prior * exp(T * loglik).
Samples are dicts with cell, kind, size, x (the q8_feat vector); empty signatures are dropped.
"""

from __future__ import annotations

import math
from typing import Any, Protocol

import numpy as np
import q8_env as env
import q8_feat as qf
from sklearn.mixture import GaussianMixture

qm = env.mod("q6_model")
KINDS = env.KINDS
ALL = "ALL"
MIN_N = 40
N_PCA = 24
N_BINS = 6
SHRINK_N = 200.0
T_GRID = (0.002, 0.005, 0.01, 0.02, 0.03, 0.05, 0.075, 0.1, 0.15, 0.2, 0.3, 0.5, 1.0)


class Likelihood(Protocol):
    def loglik(self, cell: str, x: np.ndarray, size: int) -> np.ndarray: ...


def groups(samples: list[dict[str, Any]]) -> dict[tuple[str, str], list[int]]:
    by: dict[tuple[str, str], list[int]] = {}
    for i, s in enumerate(samples):
        by.setdefault((s["cell"], s["kind"]), []).append(i)
        by.setdefault((ALL, s["kind"]), []).append(i)
    return by


def nonempty(samples: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [s for s in samples if s["x"][qf.H].any()]


def pooled_first(by: dict[tuple[str, str], list[int]]) -> list[tuple[tuple[str, str], list[int]]]:
    return sorted(by.items(), key=lambda kv: kv[0][0] != ALL)


class Reduced:
    """Standard-scale and PCA of the feature vectors, fitted on FIT pooled over kinds."""

    def __init__(self, xs: np.ndarray, n_comp: int = N_PCA) -> None:
        self.mu = xs.mean(axis=0)
        sd = xs.std(axis=0)
        self.sd = np.where(sd > 1e-9, sd, 1.0)
        z = (xs - self.mu) / self.sd
        _u, _s, vt = np.linalg.svd(z, full_matrices=False)
        self.comp = vt[:n_comp]

    def __call__(self, x: np.ndarray) -> np.ndarray:
        return np.asarray(((x - self.mu) / self.sd) @ self.comp.T)


class Binned:
    """M1: naive Bayes on quantile-binned D, S and log2 n features, Laplace smoothed."""

    name = "M1"

    def __init__(self, samples: list[dict[str, Any]]) -> None:
        samples = nonempty(samples)
        xs = np.array([self.vec(s["x"], s["size"]) for s in samples])
        self.keep = np.where(xs.std(axis=0) > 1e-9)[0]
        xs = xs[:, self.keep]
        qs = np.linspace(0, 1, N_BINS + 1)[1:-1]
        self.edges = [np.unique(np.quantile(xs[:, f], qs)) for f in range(xs.shape[1])]
        bins = self.bin(xs)
        self.nb = np.array([len(e) + 1 for e in self.edges])
        width = int(self.nb.max())
        self.lp: dict[tuple[str, str], np.ndarray] = {}
        pooled: dict[str, np.ndarray] = {}
        by = groups(samples)
        for (cell, kind), idx in pooled_first(by):
            cnt = np.zeros((len(self.nb), width))
            for f in range(len(self.nb)):
                cnt[f] = np.bincount(bins[idx, f], minlength=width)
            if cell == ALL:
                p = (cnt + 1.0) / (cnt.sum(axis=1, keepdims=True) + self.nb[:, None])
                pooled[kind] = p
                self.lp[(cell, kind)] = np.log(p)
            else:
                p = (cnt + 10.0 * pooled[kind]) / (len(idx) + 10.0)
                self.lp[(cell, kind)] = np.log(p / p.sum(axis=1, keepdims=True))
        self.n = {key: len(idx) for key, idx in by.items()}

    @staticmethod
    def vec(x: np.ndarray, size: int) -> np.ndarray:
        return np.concatenate([x[qf.D], x[qf.S]])

    def bin(self, xs: np.ndarray) -> np.ndarray:
        return np.stack([np.searchsorted(self.edges[f], xs[:, f], side="right")
                         for f in range(xs.shape[1])], axis=1)

    def loglik(self, cell: str, x: np.ndarray, size: int) -> np.ndarray:
        b = self.bin(self.vec(x, size)[None, self.keep])[0]
        rows = np.arange(len(self.keep))
        out = []
        for k in KINDS:
            key = (cell, k) if self.n.get((cell, k), 0) >= MIN_N else (ALL, k)
            out.append(float(self.lp[key][rows, b].sum()))
        return np.array(out)


class Gauss:
    """M2: full-covariance Gaussian on PCA components, mean a ridge line in log2 size."""

    name = "M2"

    def __init__(self, samples: list[dict[str, Any]], red: Reduced) -> None:
        samples = nonempty(samples)
        self.red = red
        z = np.array([red(s["x"]) for s in samples])
        ls = np.log2([max(s["size"], 1) for s in samples])
        by = groups(samples)
        self.fit: dict[tuple[str, str], tuple[np.ndarray, np.ndarray, float, int]] = {}
        pooled: dict[str, np.ndarray] = {}
        for (cell, kind), idx in pooled_first(by):
            coef, cov = self._fit(z[idx], ls[idx])
            if cell == ALL:
                pooled[kind] = np.diag(cov)
            sig = self._shrink(cov, len(idx), None if cell == ALL else pooled[kind])
            self.fit[(cell, kind)] = (coef, np.linalg.inv(sig),
                                      float(np.linalg.slogdet(sig)[1]), len(idx))

    @staticmethod
    def _fit(z: np.ndarray, ls: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        design = np.stack([np.ones_like(ls), ls], axis=1)
        coef = np.linalg.solve(design.T @ design + 1e-3 * np.eye(2), design.T @ z)
        r = z - design @ coef
        return coef, (r.T @ r) / len(z)

    @staticmethod
    def _shrink(cov: np.ndarray, n: int, pooled_diag: np.ndarray | None) -> np.ndarray:
        sig = 0.7 * cov + 0.3 * np.diag(np.diag(cov)) + 1e-3 * np.eye(len(cov))
        if pooled_diag is not None:
            sig = (n * sig + SHRINK_N * np.diag(pooled_diag + 1e-3)) / (n + SHRINK_N)
        return sig

    def loglik(self, cell: str, x: np.ndarray, size: int) -> np.ndarray:
        z = self.red(x)
        ls = math.log2(max(size, 1))
        out = []
        for k in KINDS:
            f = self.fit.get((cell, k))
            if f is None or f[3] < MIN_N:
                f = self.fit[(ALL, k)]
            r = z - (f[0][0] + f[0][1] * ls)
            out.append(-0.5 * float(r @ f[1] @ r + f[2]))
        return np.array(out)


class Mixture:
    """M3: per-kind diagonal Gaussian mixture on PCA components and standardised log2 size."""

    name = "M3"

    def __init__(self, samples: list[dict[str, Any]], red: Reduced) -> None:
        samples = nonempty(samples)
        self.red = red
        ls = np.log2([max(s["size"], 1) for s in samples])
        self.ls_mu, self.ls_sd = float(ls.mean()), float(ls.std()) or 1.0
        z = np.array([self.joint(red(s["x"]), int(s["size"])) for s in samples])
        self.gm: dict[tuple[str, str], tuple[GaussianMixture, int]] = {}
        for key, idx in groups(samples).items():
            k = 1 if len(idx) < 80 else min(3, len(idx) // 40)
            gm = GaussianMixture(k, covariance_type="diag", reg_covar=1e-3, random_state=0,
                                 n_init=2).fit(z[idx])
            self.gm[key] = (gm, len(idx))

    def joint(self, z: np.ndarray, size: int) -> np.ndarray:
        return np.append(z, (math.log2(max(size, 1)) - self.ls_mu) / self.ls_sd)

    def loglik(self, cell: str, x: np.ndarray, size: int) -> np.ndarray:
        v = self.joint(self.red(x), size)[None, :]
        out = []
        for k in KINDS:
            g = self.gm.get((cell, k))
            if g is None or g[1] < MIN_N:
                g = self.gm[(ALL, k)]
            out.append(float(g[0].score_samples(v)[0]))
        return np.array(out)


class Baseline:
    """B73: the #73 likelihood on the Hellinger feature (q6_model.Model)."""

    name = "B73"

    def __init__(self) -> None:
        self.m = qm.load(env.OUT6 / "model.json")
        self.T0: float = self.m.T

    def loglik(self, cell: str, x: np.ndarray, size: int) -> np.ndarray:
        return np.asarray(self.m.logliks(cell, x[qf.H], size))


class Posterior:
    """Tempered Bayes posterior over the six kinds from any likelihood."""

    def __init__(self, prior: dict[str, float], temperature: float) -> None:
        self.T = temperature
        tot = sum(prior.values())
        self.prior = np.array([prior[k] for k in KINDS]) / tot
        self.logprior = np.log(self.prior)

    def post(self, ll: np.ndarray, empty: bool) -> np.ndarray:
        if empty:
            return self.prior
        s = self.T * ll + self.logprior
        s -= s.max()
        p = np.exp(s)
        return np.asarray(p / p.sum())


def label_set(kinds: list[str]) -> list[int]:
    return [KINDS.index(k) for k in kinds] if kinds else [env.GLUE]


def fit_temperature(lik: Likelihood, prior: dict[str, float],
                    blocks: list[tuple[str, np.ndarray, int, list[str]]]) -> float:
    """T minimising the negative log posterior of the label on (cell, x, size, right kinds) blocks."""
    rows = [(np.asarray(lik.loglik(c, x, s)), label_set(ks)) for c, x, s, ks in blocks
            if x[qf.H].any()]
    best, best_nll = 1.0, math.inf
    for t in T_GRID:
        post = Posterior(prior, t)
        nll = sum(-math.log(max(float(post.post(ll, False)[lab].sum()), 1e-12))
                  for ll, lab in rows)
        if nll < best_nll:
            best, best_nll = t, nll
    return best


def build_models(samples: list[dict[str, Any]]) -> dict[str, Likelihood]:
    red = Reduced(np.array([s["x"] for s in nonempty(samples)]))
    return {"M1": Binned(samples), "M2": Gauss(samples, red), "M3": Mixture(samples, red)}
