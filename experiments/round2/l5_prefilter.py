"""RQ-L5 (H5b): would-be pruning of prover calls by a cheap structural prefilter, measured offline.

A call is a hypothesis with a ``cone_check`` (SAT) evidence record, or a ``truth_table`` one.
A rule is a pair ``(kind, feature, bin)`` over the structural features the hypothesis already
carries (carry and sum cut shape ``npn_carry``/``npn_sum`` for the adder family, ``npn_class`` for
muxes, ``width``, ``out_reads``, ``k``): the rule prunes every call of that kind with that
feature bin. For each rule the file reports the calls pruned and the ``equivalent`` verdicts that
pruning would have lost. Exhaustive over the rules; no held-out data, so this is an upper bound
on what a prefilter could save, not a measured saving.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

import r2lib

RUN_ROOTS = [
    r2lib.DATA / "l2" / "runs" / "f2-calib", r2lib.DATA / "l2" / "runs" / "f2-none",
    r2lib.DATA / "l2" / "runs" / "f3-calib", r2lib.DATA / "l2" / "runs" / "f3-none",
    r2lib.DATA / "l1" / "runs" / "native-calib", r2lib.DATA / "l1" / "runs" / "native-none",
    r2lib.DATA / "l1" / "runs" / "lut-calib", r2lib.DATA / "l1" / "runs" / "lut-none",
]
PROVERS = ("cone_check", "truth_table")
FEATURES = ("npn_carry", "npn_sum", "npn_class", "npn_xor2", "width", "out_reads", "k",
            "sel_shared", "shared_ctrl", "rst_fanout")


def calls() -> list[tuple[str, str, dict[str, str], str]]:
    """(prover, kind, features, verdict) of every proof call that left an evidence record."""
    out = []
    for root in RUN_ROOTS:
        for path in sorted(root.glob("*/re/overlay.json")):
            for h in json.loads(path.read_text(encoding="utf-8"))["hypotheses"]:
                for e in h["evidence"]:
                    if e["source"] in PROVERS:
                        out.append((e["source"], h["kind"], h["features"], e["value"]))
    return out


def main() -> int:
    data = calls()
    total: Counter[str] = Counter(p for p, _k, _f, _v in data)
    equiv_total: Counter[str] = Counter(p for p, _k, _f, v in data if v == "equivalent")
    pruned: Counter[tuple[str, str, str, str]] = Counter()
    lost: Counter[tuple[str, str, str, str]] = Counter()
    for prover, kind, feats, verdict in data:
        for feat in FEATURES:
            if feat in feats:
                key = (prover, kind, feat, feats[feat])
                pruned[key] += 1
                lost[key] += 1 if verdict == "equivalent" else 0
    rows: list[list[Any]] = []
    for key in sorted(pruned):
        prover, kind, feat, b = key
        rows.append([prover, kind, feat, b, pruned[key], lost[key], total[prover],
                     equiv_total[prover], round(pruned[key] / total[prover], 6)])
    r2lib.write_csv(Path(__file__).resolve().parent / "l5_prefilter.csv",
                    ["prover", "kind", "feature", "bin", "calls_pruned", "equivalent_lost",
                     "calls_total", "equivalent_total", "fraction_pruned"], rows)
    zero = [r for r in rows if r[5] == 0 and r[0] == "cone_check"]
    best = max(zero, key=lambda r: r[4], default=None)
    print("calls", dict(total), "equivalent", dict(equiv_total))
    print("best zero-loss cone_check rule", best)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
