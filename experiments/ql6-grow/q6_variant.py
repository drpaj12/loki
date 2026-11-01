"""Post hoc diagnostic (not in the fixed plan): grow without the Bayes factor stop, then cut.

``QL6_NOSTOP=1 python -B q6_grow.py`` grows every block until its frontier is empty or 300 cells,
always taking the best candidate. This script reads $QL6_OUT/blocks_nostop and asks, per construct,
whether some prefix of some block is the right block: (a) at the prefix with the highest log odds
(known construct vs glue) along the path, a deployable stop rule; (b) at the best prefix by
Jaccard, an oracle ceiling of the growth order. Writes results/variant.csv and variant_units.csv.
"""

from __future__ import annotations

import json
import math
import statistics
from collections import defaultdict
from typing import Any

import q6_eval as ev
import q6_model as qm
import q6_net as qn
import q6_report as rp
import q6_truth as qt
from q6_env import OUT, RES, l3dlib


def prefix_hits(b: dict[str, Any], true: frozenset[int]) -> tuple[list[bool], list[int]]:
    """Per prefix (step 0 = the anchor): is it a right block, and its size."""
    inter = len(set(b["anchor"]) & true)
    size = len(b["anchor"])
    out: list[bool] = []
    sizes: list[int] = []
    for step in range(len(b["order"]) + 1):
        if step:
            size += 1
            inter += b["order"][step - 1] in true
        cov = inter / len(true)
        jac = inter / (size + len(true) - inter)
        out.append(cov >= 0.8 and jac >= 0.5)
        sizes.append(size)
    return out, sizes


def main() -> int:
    d70 = ev.d70_records()
    rows: list[dict[str, Any]] = []
    for u in qt.units("TEST"):
        p = OUT / "blocks_nostop" / f"{u.set}__{u.design}__{u.cell}.json"
        if not p.is_file():
            continue
        rec = json.loads(p.read_text(encoding="utf-8"))
        g = qn.Graph.read(u.net)
        for c in qt.constructs(u, g):
            if c.kind == "glue" or not c.cells:
                continue
            ev_right = oracle = False
            for b in rec["blocks"]:
                hits, _sizes = prefix_hits(b, c.cells)
                oracle = oracle or any(hits)
                evs = [(e if e > qm.NO_EVIDENCE / 2 else -math.inf) for e in b["evs"]]
                if hits and max(evs) > -math.inf:
                    ev_right = ev_right or hits[evs.index(max(evs))]
            d = d70.get((u.set, u.design, u.cell, c.idx, c.kind))
            rows.append({"set": u.set, "design": u.design, "cell": u.cell, "part": c.idx,
                         "kind": c.kind, "evmax_right": int(ev_right), "oracle_right": int(oracle),
                         "d70_right": int(d is not None and d["jaccard"] != "" and
                                          float(d["coverage"]) >= 0.8 and
                                          float(d["jaccard"]) >= 0.5)})
    out = []
    for name, sel in (("all", rows), *[(f"cell {c}", [r for r in rows if r["cell"] == c])
                                       for c in l3dlib.CELLS],
                      *[(f"kind {k}", [r for r in rows if r["kind"] == k])
                        for k in ("fsm", "counter", "shift", "regfile", "register")]):
        if sel:
            n = len(sel)
            out.append({"scope": name, "constructs": n,
                        "evmax_right": sum(r["evmax_right"] for r in sel),
                        "evmax_share": round(sum(r["evmax_right"] for r in sel) / n, 3),
                        "oracle_right": sum(r["oracle_right"] for r in sel),
                        "oracle_share": round(sum(r["oracle_right"] for r in sel) / n, 3),
                        "d70_share": round(sum(r["d70_right"] for r in sel) / n, 3)})
    RES.mkdir(exist_ok=True)
    l3dlib.write_csv(RES / "variant.csv", list(out[0]), out)
    units: dict[tuple[str, str, str], list[int]] = defaultdict(lambda: [0, 0, 0])
    for r in rows:
        u3 = units[(r["set"], r["design"], r["cell"])]
        u3[0] += r["evmax_right"]
        u3[1] += r["oracle_right"]
        u3[2] += r["d70_right"]
    for idx, name in ((0, "evmax"), (1, "oracle")):
        per = [{"design": k[1], "g": v[idx], "d": v[2]} for k, v in units.items()]
        pt, lo, hi = ev.boot_ci(rp.by_design(per), lambda rs: math.exp(statistics.fmean(
            math.log((r["g"] + 1) / (r["d"] + 1)) for r in rs)))
        print(name, round(pt, 3), round(lo, 3), round(hi, 3), rp.label_better(pt, lo, hi),
              len(per), "units")
    for r in out:
        print(r)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
