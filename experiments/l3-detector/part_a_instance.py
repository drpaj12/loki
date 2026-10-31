"""Part A, instance level on Odin III cells: ``python -B part_a_instance.py`` (TEST designs).

True instances are register words of the HDL word IR (``words.json``) with the census rule
(fsm flag; counter = feedback through add/sub with a constant; timer = counter whose compare
reaches it again). A detected instance maps to the register words whose footprint holds its
flip-flops (``graph.json``: net -> driver node). Yosys netlists have no names: design level only.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import l3dlib as lib
import labels_rtl as lab
import part_a as pa

from loki.l3 import catalogue
from loki.l3.detect import Detector

PATTERNS = ("fsm", "counter", "timer")


def true_words(words: dict[str, Any]) -> dict[str, set[int]]:
    kind, succ, byid = lab._graph(words)
    regs = [i for i, t in kind.items() if t in lab.REGS]
    fsm = {i for i in regs if byid[i].get("fsm")}
    loops = {r: t for r in regs if (t := lab._reach(r, succ, kind).get(r)) is not None}
    counters = {r for r, t in loops.items() if r not in fsm and any(x in lab.ARITH for x in t)}
    return {"fsm": fsm, "counter": counters,
            "timer": {r for r in counters if lab._timer(r, succ, kind)}}


def instance_words(q: frozenset[str], drv: dict[str, str], words: dict[str, Any],
                   regs: set[int]) -> set[int]:
    ffs = {drv[n] for n in q if n in drv}
    return {w["id"] for w in words["words"] if w["id"] in regs and ffs & set(w["footprint"])}


def one(row: dict[str, Any], det: Detector) -> dict[str, tuple[int, int, int]] | None:
    d = lib.CENSUS / "build" / row["cell"] / row["design"] / lib.FLOORS[row["cell"]]
    if not (d / "words.json").is_file() or not (d / "graph.json").is_file():
        return None
    words = json.loads((d / "words.json").read_text(encoding="utf-8"))
    graph = json.loads((d / "graph.json").read_text(encoding="utf-8"))
    drv = {e["net"]: e["src"] for e in graph["edges"]}
    truth = true_words(words)
    kind = {w["id"]: w["type"] for w in words["words"]}
    regs = {i for i, t in kind.items() if t in lab.REGS}
    res = det.run(row["claims"], lib.TARGET[row["cell"]], row["net"])
    out: dict[str, tuple[int, int, int]] = {}
    for e in PATTERNS:
        mapped = [instance_words(i.q, drv, words, regs) for i in res.instances.get(e, [])]
        tp = sum(1 for m in mapped if m & truth[e])
        covered = set().union(*(m & truth[e] for m in mapped)) if mapped else set()
        out[e] = (tp, len(mapped) - tp, len(truth[e] - covered))
    return out


def main() -> int:
    det = Detector(catalogue.load(), catalogue.load_tuning())
    ok = {r["design"] for r in lib.read_csv(lib.CENSUS_RES / "labels_rtl.csv")
          if r["status"] == "ok"}
    rows = [r for r in pa.load("TEST") if r["cell"].startswith("O-") and r["design"] in ok]
    out = []
    for e in PATTERNS:
        for cell in ("O-gate", "O-lut", "O-hard"):
            per = [x[e] for r in rows if r["cell"] == cell and (x := one(r, det)) is not None]
            tp, fp, fn = (sum(p[i] for p in per) for i in range(3))
            pr = tp / (tp + fp) if tp + fp else 1.0
            rc = tp / (tp + fn) if tp + fn else 1.0
            lp, lr = lib.bootstrap(per)
            out.append({"pattern": e, "cell": cell, "designs": len(per), "TP": tp, "FP": fp,
                        "FN": fn, "precision": round(pr, 3), "precision_lo": round(lp, 3),
                        "recall": round(rc, 3), "recall_lo": round(lr, 3),
                        "label": lib.label(pr, rc, lp, lr, tp + fn)})
    lib.write_csv(lib.RES / "partA_instance.csv",
                  ["pattern", "cell", "designs", "TP", "FP", "FN", "precision", "precision_lo",
                   "recall", "recall_lo", "label"], out)
    print(Path(lib.RES / "partA_instance.csv").read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
