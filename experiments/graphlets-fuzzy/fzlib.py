"""Shared loading and features for the fuzzy-signature experiment (library + partitions)."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "graphlets"))
sys.path.insert(0, str(HERE.parent / "l3-detector"))
import fuzz  # noqa: E402
import gen  # noqa: E402
import live  # noqa: E402
import match_run as mr  # noqa: E402
import sigs  # noqa: E402

OUT = live.OUT / "fuzzy"
RES = HERE / "results"
CELLS = live.CELLS
PATS = ("fsm", "counter", "shift", "lfsr", "timer", "regfile", "register")
CLASSES = (*PATS, "glue")
NORB = {"undirected": 73, "directed": 129}
GRID = np.arange(0.0, 17.0, 0.25)
LEVELS = ("und", "dir", "dir_a0.25", "dir_a0.5", "dir_a1", "dir_col")


def level_matrix(level: str) -> np.ndarray | None:
    """Linear map on directed orbit vectors for one tolerance level (None for exact/undirected)."""
    if level == "dir_col":
        cm = fuzz.collapse_map()
        m = np.zeros((max(cm) + 1, 129))
        for o, c in enumerate(cm):
            m[c, o] = 1.0
        return m
    if level.startswith("dir_a"):
        return np.eye(129) + float(level[5:]) * np.array(fuzz.flip_matrix(), dtype=float)
    return None


def mode_of(level: str) -> str:
    return "undirected" if level == "und" else "directed"


def per_orbit(sig: dict[str, Any], k: int) -> dict[str, np.ndarray]:
    """Totals, quantiles of log1p(count) over nodes (median, p90, max) and the CDF on GRID."""
    nodes = max(1, int(sig["nodes"]))
    tot = np.array(sig["orbit_totals"], dtype=float)
    q = np.zeros((3, k))
    cdf = np.zeros((k, len(GRID)), dtype=np.float32)
    for o, pairs in enumerate(sig["gdd"]):
        zeros = nodes - sum(c for _d, c in pairs)
        vals = [(0.0, float(zeros))] + [(float(np.log1p(d)), float(c)) for d, c in pairs]
        vals.sort()
        cum = np.cumsum([c for _v, c in vals]) / nodes
        xs = np.array([v for v, _c in vals])
        q[0, o] = xs[np.searchsorted(cum, 0.5)]
        q[1, o] = xs[min(len(xs) - 1, np.searchsorted(cum, 0.9))]
        q[2, o] = xs[-1]
        idx = np.searchsorted(xs, GRID, side="right") - 1
        cdf[o] = np.where(idx >= 0, cum[np.clip(idx, 0, None)], 0.0)
    return {"tot": tot, "q": q, "cdf": cdf}


def feature(po: dict[str, np.ndarray], sig_nodes: int, ff: int, cell: str,
            level: str) -> np.ndarray:
    m = level_matrix(level)
    tot, q = po["tot"], po["q"]
    if m is not None:
        w = m @ np.ones(129)
        tot = m @ tot
        q = np.stack([(m @ r) / w for r in q])
    s = tot.sum()
    onehot = [1.0 if c == cell else 0.0 for c in CELLS]
    return np.concatenate([tot / s if s > 0 else tot, q.ravel(),
                           [np.log1p(sig_nodes), np.log1p(ff)], onehot])


def raw_smoothed(po: dict[str, np.ndarray], level: str) -> np.ndarray:
    m = level_matrix(level)
    return np.log1p(m @ po["tot"] if m is not None else po["tot"])


class Lib:
    """Library entries: per (cell, mode) list of (pattern, name, width, ff, per_orbit)."""

    def __init__(self) -> None:
        self.rows: dict[tuple[str, str], list[dict[str, Any]]] = {}
        for cell in CELLS:
            for mode in sigs.MODES:
                lst = []
                for inst in gen.instances():
                    p = sigs.sig_path(mode, cell, inst.name)
                    ij = live.OUT / "re" / cell / inst.name / "intent.json"
                    if not p.is_file():
                        continue
                    s = json.loads(p.read_text(encoding="utf-8"))
                    lst.append({"pattern": inst.pattern, "name": inst.name, "width": inst.width,
                                "ff": mr.ffcount(ij) if ij.is_file() else -1, "nodes": s["nodes"],
                                "po": per_orbit(s, NORB[mode])})
                self.rows[(cell, mode)] = lst


def read_parts() -> list[dict[str, Any]]:
    return [json.loads(x) for x in (OUT / "part_sigs.jsonl").read_text(
        encoding="utf-8").splitlines()]
