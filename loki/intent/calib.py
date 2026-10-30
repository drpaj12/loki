"""A6: the probability of a v2 claim is a calibrated posterior, and says where it comes from.

Overlay claims (bus, comparison, adder, ...) keep ``p_comp`` of the run, which is a calibrated
posterior only when the run used a calibration file (``calib/f3.json``: the F3 floor, fitted on the
train split of Loki's micro dataset). Sequential claims (counter, shift register, LFSR, FSM,
multi-mode register) are classified from an exhaustive transition table, so their uncertainty is
whether the stated sentence holds on the netlist. Their probability is the posterior mean of a
Beta(1, 1) prior after ``hits`` of ``n`` claims of that kind held when checked against the original
netlist (``loki.intent.verify``, fitted by ``experiments/llm-hints2/calib_intent.py``). A kind with
no checked claim has no probability and prints none.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

SCHEMA = 1
PRIOR = (1.0, 1.0)
ECE_BINS = 10


@dataclass(frozen=True)
class IntentCalib:
    """``kinds[kind] = (hits, n)``; ``source`` states which designs and which check fed it."""

    source: str
    kinds: dict[str, tuple[int, int]]

    def p_for(self, kind: str) -> float | None:
        """The posterior mean for ``kind``, rounded to 4 places; None without any checked claim."""
        hits, n = self.kinds.get(kind, (0, 0))
        if n == 0:
            return None
        return round((hits + PRIOR[0]) / (n + PRIOR[0] + PRIOR[1]), 4)

    def to_json(self) -> dict[str, object]:
        return {
            "schema": SCHEMA, "source": self.source, "prior": list(PRIOR),
            "kinds": {k: {"hits": h, "n": n, "p": self.p_for(k)}
                      for k, (h, n) in sorted(self.kinds.items())},
        }


def fit(outcomes: Sequence[tuple[str, bool]], source: str) -> IntentCalib:
    """Counts per kind from ``(kind, held)`` outcomes."""
    kinds: dict[str, tuple[int, int]] = {}
    for kind, held in outcomes:
        hits, n = kinds.get(kind, (0, 0))
        kinds[kind] = (hits + int(held), n + 1)
    return IntentCalib(source, kinds)


def load(path: Path) -> IntentCalib:
    obj = json.loads(path.read_text(encoding="utf-8"))
    if obj.get("schema") != SCHEMA:
        raise ValueError(f"{path}: not an intent calibration (schema {obj.get('schema')!r})")
    return IntentCalib(str(obj["source"]),
                       {k: (int(v["hits"]), int(v["n"])) for k, v in obj["kinds"].items()})


def ece(pairs: Sequence[tuple[float, bool]], bins: int = ECE_BINS) -> float | None:
    """Expected calibration error of ``(p, outcome)`` pairs over equal-width bins; None if empty."""
    if not pairs:
        return None
    total = 0.0
    for b in range(bins):
        lo, hi = b / bins, (b + 1) / bins
        inside = [(p, o) for p, o in pairs if lo <= p < hi or (b == bins - 1 and p == 1.0)]
        if inside:
            conf = sum(p for p, _ in inside) / len(inside)
            acc = sum(o for _, o in inside) / len(inside)
            total += len(inside) * abs(conf - acc)
    return round(total / len(pairs), 6)
