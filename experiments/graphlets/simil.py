"""Signature similarity (Odin III spec 13): GDD agreement (Przulj 2007) and cosine of log(1+total).

Pure Python on the group JSON of sigs.py. Checked against ``odin3.graphlet_compare`` (see
test_graphlets.py / EXPERIMENT.md).
"""

from __future__ import annotations

import math
from typing import Any


def _norm(gdd: list[list[int]]) -> dict[int, float]:
    s = {int(k): c / k for k, c in gdd}
    t = sum(s.values())
    return {k: v / t for k, v in s.items()} if t > 0 else {}


def gdd_agreement(a: dict[str, Any], b: dict[str, Any]) -> float:
    tot = 0.0
    for ga, gb in zip(a["gdd"], b["gdd"], strict=True):
        na, nb = _norm(ga), _norm(gb)
        if not na and not nb:
            tot += 1.0
        elif not na or not nb:
            continue
        else:
            keys = na.keys() | nb.keys()
            d = math.sqrt(sum((na.get(k, 0.0) - nb.get(k, 0.0)) ** 2 for k in keys))
            tot += 1.0 - d / math.sqrt(2.0)
    return tot / len(a["gdd"])


def cosine_log(a: dict[str, Any], b: dict[str, Any]) -> float:
    x = [math.log1p(v) for v in a["orbit_totals"]]
    y = [math.log1p(v) for v in b["orbit_totals"]]
    nx, ny = math.sqrt(sum(v * v for v in x)), math.sqrt(sum(v * v for v in y))
    if nx == 0 and ny == 0:
        return 1.0
    if nx == 0 or ny == 0:
        return 0.0
    return sum(p * q for p, q in zip(x, y, strict=True)) / (nx * ny)
