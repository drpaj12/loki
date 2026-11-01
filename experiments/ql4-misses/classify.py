"""The fixed classification rule of EXPERIMENT.md (pure functions, no I/O)."""

from __future__ import annotations

import math
from dataclasses import dataclass

RIGHT_COVERAGE = 0.8
RIGHT_JACCARD = 0.5
CLASSES = ("absent", "missing pattern (width)", "partition miss", "threshold miss",
           "structure miss")
DETECTOR_KIND = {"absent": "not in netlist", "missing pattern (width)": "missing detector",
                 "partition miss": "missing detector",
                 "threshold miss": "missing detector", "structure miss": "complex decoding"}


@dataclass(frozen=True)
class MissFacts:
    """What the rule needs from one miss."""

    jaccard: float
    coverage: float
    true_ff: int  # flip-flops in the true block
    has_entry: bool  # the library holds the family at the true block's flip-flop count
    t_dist: float  # distance of the TRUE block to the family's pattern (NaN: not computable)
    t_wrong: float  # best wrong pattern distance for the true block (NaN: none)
    q90: float  # 90th percentile of the hit distances of the same detector


def right_block(jaccard: float, coverage: float) -> bool:
    return coverage >= RIGHT_COVERAGE and jaccard >= RIGHT_JACCARD


def classify(f: MissFacts) -> str:
    """Rule order of EXPERIMENT.md: absent, missing pattern, partition, threshold, structure."""
    if f.true_ff == 0:
        return "absent"
    if not f.has_entry:
        return "missing pattern (width)"
    if not right_block(f.jaccard, f.coverage):
        return "partition miss"
    if f.t_dist <= f.q90:  # NaN on either side: not near, so a structure miss
        return "threshold miss"
    return "structure miss"


def rank_flag(f: MissFacts) -> bool:
    """Threshold miss where a wrong pattern is nearer than the family for the true block."""
    return not math.isnan(f.t_wrong) and f.t_wrong < f.t_dist


def percentile(values: list[float], q: float) -> float:
    """Linear-interpolated percentile (q in 0..1) of the finite values; NaN when none."""
    xs = sorted(v for v in values if not math.isnan(v))
    if not xs:
        return math.nan
    pos = q * (len(xs) - 1)
    lo = int(math.floor(pos))
    hi = min(lo + 1, len(xs) - 1)
    return xs[lo] + (xs[hi] - xs[lo]) * (pos - lo)
