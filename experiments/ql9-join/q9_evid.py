"""Evidence of a block and the kind posterior: E73 (the #73 likelihood) and EM2 (the #75 M2).

ev(B) = log odds that B is a known construct against glue, in the form of ``Model.evidence``
(weights = the block's own posterior over the five kinds); 0 for a block without edges.
"""

from __future__ import annotations

import math
import pickle
from typing import Any

import numpy as np
import q9_env as env

qm6 = env.mod("q6_model")
qs = env.mod("q6_sig")
qf = env.mod("q8_feat")
qm8 = env.mod("q8_model")
SOURCES = ("E73", "EM2")


def weights(post: np.ndarray) -> np.ndarray:
    """Posterior weights of the five kinds (glue removed), uniform when all mass was glue."""
    w = post.copy()
    w[env.GLUE] = 0.0
    s = w.sum()
    if s > 0:
        return np.asarray(w / s)
    u = np.ones(len(env.KINDS))
    u[env.GLUE] = 0.0
    return np.asarray(u / u.sum())


def evidence_from(ll: np.ndarray, temp: float, w: np.ndarray) -> float:
    raw = temp * ll
    s = raw + np.log(np.maximum(w, 1e-300))
    m = float(s.max())
    return m + math.log(float(np.exp(s - m).sum())) - float(raw[env.GLUE])


def load_m2() -> dict[str, Any]:
    with (env.q8env.OUT8 / "models.pkl").open("rb") as fh:
        m: dict[str, Any] = pickle.load(fh)
    return {"lik": m["lik"]["M2"], "post": qm8.Posterior(m["prior"], m["temps"]["M2"])}


class Evid:
    """Cached evidence and kind posterior of the cell sets of one unit."""

    def __init__(self, g: Any, sc: Any, cell: str, m2: dict[str, Any] | None) -> None:
        self.g, self.sc, self.cell, self.m2 = g, sc, cell, m2
        self.m73 = qm6.load(env.OUT6 / "model.json")
        self.ctx = qf.make_ctx(g, sc) if m2 is not None else None
        self.cache: dict[tuple[str, frozenset[int]], tuple[float, np.ndarray]] = {}

    def _e73(self, cells: frozenset[int]) -> tuple[float, np.ndarray]:
        x = qs.feature(self.sc.orbits(cells))
        post = self.m73.posterior(self.cell, x, len(cells))
        if not x.any():
            return 0.0, post
        ll = self.m73.logliks(self.cell, x, len(cells))
        return evidence_from(ll, self.m73.T, weights(post)), post

    def _em2(self, cells: frozenset[int]) -> tuple[float, np.ndarray]:
        if self.m2 is None or self.ctx is None:
            raise ValueError("EM2 needs the M2 model")
        x = qf.featurize(self.ctx, cells)
        ll = np.asarray(self.m2["lik"].loglik(self.cell, x, len(cells)))
        empty = not x[qf.H].any()
        post = self.m2["post"].post(ll, empty)
        if empty:
            return 0.0, post
        return evidence_from(ll, self.m2["post"].T, weights(post)), post

    def both(self, src: str, cells: frozenset[int]) -> tuple[float, np.ndarray]:
        key = (src, cells)
        hit = self.cache.get(key)
        if hit is None:
            hit = self._e73(cells) if src == "E73" else self._em2(cells)
            self.cache[key] = hit
        return hit

    def ev(self, src: str, cells: frozenset[int]) -> float:
        return self.both(src, cells)[0]

    def post(self, src: str, cells: frozenset[int]) -> np.ndarray:
        return self.both(src, cells)[1]
