"""Describe the TEST constructs that no block touches (class NOSEED of #74).

``python -B q8b_describe.py``. Reads #74's TEST features (read only) and the answer key; writes
results/describe_untouched.csv (one row per construct) and results/describe_summary.csv.
Descriptive only: nothing here is tuned.
"""

from __future__ import annotations

import csv
import sys
from collections import Counter
from typing import Any

import q8b_env as env

q7f = env.mod("q7_feat")
qn = env.mod("q6_net")
qt = env.mod("q6_truth")
SHIFT_COMB = qn.SHIFT_COMB


def key_set() -> set[tuple[str, str, str, int, str]]:
    """Constructs of #73/#74 that D70 also scored (the 1141 of the verdicts)."""
    p = env.HERE.parent / "ql6-grow" / "results" / "construct_records.csv"
    return {(r["set"], r["design"], r["cell"], int(r["part"]), r["kind"])
            for r in env.l3dlib.read_csv(p) if r["scored"] == "1" and r["d70_known"] == "1"}


def cell_class(g: Any, i: int) -> str:
    if g.b.latch[i]:
        return "ff"
    if i in g.hard:
        return "hard"
    return "const" if not g.b.ins[i] else "comb"


def ff_facts(g: Any, ffs: list[int]) -> dict[str, Any]:
    """Why the flip-flop anchors do not take these flip-flops (the tests of q6_net.anchors)."""
    deps = {i: qn.ff_cone(g, i) for i in ffs}
    other = [len(d[0] - {i}) for i, d in deps.items()]
    ncomb = [len(d[2]) for d in deps.values()]
    cut = sum(1 for d in deps.values() for n in d[1] if g.is_cut(n))
    return {"max_ff_deps": max(other), "max_cone_cells": max(ncomb), "cut_nets_in_cones": cut,
            "self_only": sum(1 for o in other if o == 0)}


def reason(c: Counter[str], facts: dict[str, Any]) -> str:
    if c["ff"] == 0 and c["hard"] == 0:
        return "no flip-flop and no hard cell (every anchor class needs one)"
    if facts["self_only"] == c["ff"]:
        return "self-only flip-flops, not linked by a shared cone net"
    if facts["max_ff_deps"] >= 2:
        return "flip-flops read two or more other flip-flops (not a chain, not a closed loop)"
    if facts["max_cone_cells"] > SHIFT_COMB:
        return f"flip-flop chain with more than {SHIFT_COMB} cone cells per flip-flop"
    return "other"


def describe() -> list[dict[str, Any]]:
    scored = key_set()
    byk = {(x.set, x.design, x.cell): x for x in qt.units("TEST")}
    out = []
    for u in q7f.load("TEST"):
        todo = [(j, c) for j, c in enumerate(u.cons)
                if (u.set, u.design, u.cell, c[0], c[1]) in scored
                and not any(bp.inter[j, -1] for bp in u.blocks)]
        if not todo:
            continue
        uu = byk[u.key]
        g = qn.Graph.read(uu.net)
        cons = {(c.idx, c.kind): c for c in qt.constructs(uu, g)}
        anchored = {i for a in qn.anchors(g) for i in a.cells}
        for _, (part, kind, n) in todo:
            cells = sorted(cons[(part, kind)].cells)
            cc = Counter(cell_class(g, i) for i in cells)
            ffs = [i for i in cells if g.b.latch[i]]
            facts = ff_facts(g, ffs) if ffs else {"max_ff_deps": 0, "max_cone_cells": 0,
                                                  "cut_nets_in_cones": 0, "self_only": 0}
            out.append({"set": u.set, "design": u.design, "cell": u.cell, "part": part,
                        "kind": kind, "n_true": n, "n_const": cc["const"], "n_ff": cc["ff"],
                        "n_hard": cc["hard"], "n_comb": cc["comb"], **facts,
                        "ff_in_anchor": len(set(ffs) & anchored), "n_cells": g.b.n,
                        "n_anchors": len(qn.anchors(g)), "reason": reason(cc, facts)})
    return out


def summary(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for field in ("reason", "cell", "kind"):
        for k, v in sorted(Counter(r[field] for r in rows).items()):
            out.append({"by": field, "value": k, "constructs": v})
    for lab, sel in (("size 1 to 3", lambda r: r["n_true"] <= 3),
                     ("size 4 to 300", lambda r: 3 < r["n_true"] <= 300),
                     ("size above 300", lambda r: r["n_true"] > 300)):
        out.append({"by": "size", "value": lab, "constructs": sum(1 for r in rows if sel(r))})
    return out


def main() -> int:
    rows = describe()
    env.RES.mkdir(parents=True, exist_ok=True)
    for name, rs in (("describe_untouched.csv", rows), ("describe_summary.csv", summary(rows))):
        with (env.RES / name).open("w", encoding="utf-8", newline="\n") as fh:
            w = csv.DictWriter(fh, list(rs[0]), lineterminator="\n")
            w.writeheader()
            w.writerows(rs)
    print(len(rows), "constructs")
    for r in summary(rows):
        print(r)
    return 0


if __name__ == "__main__":
    sys.exit(main())
