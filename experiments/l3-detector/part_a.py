"""Part A: single-pattern detection. ``python -B part_a.py tune|eval``.

tune: grid over min_p, regfile_k, max_depth on TUNE only, writes loki/l3/catalogue/tuning.json.
eval: runs the tuned detector on TEST (and TUNE, shown separately) and writes results/partA_*.csv.
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

import l3dlib as lib

from loki.l3 import catalogue
from loki.l3.detect import Detector
from loki.l3.netlist import Netlist

TUNING = Path(catalogue.CATALOGUE_DIR) / "tuning.json"
GRID_P = (0.0, 0.5, 0.9)
GRID_K = (2, 3, 4, 6, 8)
GRID_K2 = (4, 8, 16, 32)
GRID_D = (2, 4, 6, 8)


def labels() -> dict[str, dict[str, str]]:
    return {r["design"]: r for r in lib.read_csv(lib.CENSUS_RES / "labels_rtl.csv")
            if r["status"] in ("ok", "manual")}


def excluded() -> set[tuple[str, str]]:
    return {(r["design"], r["cell"]) for r in lib.read_csv(lib.CENSUS_RES / "excluded_ffsub.csv")}


def load(split: str) -> list[dict[str, Any]]:
    """Designs x cells of one split with a finished loki re: claims (and netlist for O-hard)."""
    lab, skip = labels(), excluded()
    rows = []
    for r in lib.read_csv(lib.RES / "split_single.csv"):
        if r["split"] != split:
            continue
        for cell in lib.CELLS:
            ij = lib.intent_path(lib.CENSUS, cell, r["design"])
            if (r["design"], cell) in skip or not ij.is_file():
                continue
            row = {"design": r["design"], "cell": cell, "label": lab[r["design"]],
                   "claims": lib.load_claims(ij), "net": None}
            row["net"] = Netlist.read(lib.netlist_path(lib.CENSUS, cell, r["design"]))
            rows.append(row)
    return rows


def predict(det: Detector, row: dict[str, Any]) -> dict[str, Any]:
    d = det.run(row["claims"], lib.TARGET[row["cell"]], row["net"])
    return {"det": d, **{e: int(d.found(e)) for e in lib.ENTRIES}}


def truth(row: dict[str, Any], e: str) -> int:
    return int(row["label"][e] not in ("", "0"))


def f1(rows: list[dict[str, Any]], preds: list[dict[str, Any]], pats: tuple[str, ...],
       cells: tuple[str, ...] = lib.CELLS) -> float:
    tp = fp = fn = 0
    for row, pr in zip(rows, preds, strict=True):
        if row["cell"] not in cells:
            continue
        for e in pats:
            t, p = truth(row, e), pr[e]
            tp += t & p
            fp += (1 - t) & p
            fn += t & (1 - p)
    return 2 * tp / (2 * tp + fp + fn) if tp + fp + fn else 1.0


def run_cfg(rows: list[dict[str, Any]], cfg: dict[str, Any]) -> list[dict[str, Any]]:
    det = Detector(catalogue.load(), cfg)
    return [predict(det, r) for r in rows]


def best(rows: list[dict[str, Any]], base: dict[str, Any], key: str, grid: tuple[Any, ...],
         pats: tuple[str, ...], cells: tuple[str, ...] = lib.CELLS) -> Any:
    scores = [(f1(rows, run_cfg(rows, {**base, key: g}), pats, cells), i, g)
              for i, g in enumerate(grid)]
    return max(scores, key=lambda s: (round(s[0], 6), -s[1]))[2]


def tune() -> int:
    rows = load("TUNE")
    cfg: dict[str, Any] = {"max_depth": 6, "min_p": 0.0, "regfile_k": 4, "regfile_k2": 16}
    cfg["min_p"] = best(rows, cfg, "min_p", GRID_P, lib.ENTRIES)
    cfg["regfile_k"] = best(rows, cfg, "regfile_k", GRID_K, ("regfile", "register"))
    cfg["regfile_k2"] = best(rows, cfg, "regfile_k2", GRID_K2, ("regfile", "register"))
    cfg["max_depth"] = best(rows, cfg, "max_depth", GRID_D, ("counter", "timer"))
    TUNING.write_text(json.dumps(cfg, sort_keys=True, indent=1) + "\n", encoding="utf-8")
    print("tuned", cfg, "on", len(rows), "design x cell rows")
    return 0


def counts(rows: list[dict[str, Any]], preds: list[dict[str, Any]], e: str, cell: str
           ) -> list[tuple[int, int, int]]:
    out = []
    for row, pr in zip(rows, preds, strict=True):
        if row["cell"] == cell:
            t, p = truth(row, e), pr[e]
            out.append((t & p, (1 - t) & p, t & (1 - p)))
    return out


def table(rows: list[dict[str, Any]], preds: list[dict[str, Any]], split: str
          ) -> list[dict[str, Any]]:
    out = []
    for e in lib.ENTRIES:
        for cell in lib.CELLS:
            c = counts(rows, preds, e, cell)
            if not c:
                continue
            tp, fp, fn = (sum(x[i] for x in c) for i in range(3))
            pr = tp / (tp + fp) if tp + fp else 1.0
            rc = tp / (tp + fn) if tp + fn else 1.0
            lp, lr = lib.bootstrap(c)
            out.append({"split": split, "pattern": e, "cell": cell, "designs": len(c),
                        "TP": tp, "FP": fp, "FN": fn, "precision": round(pr, 3),
                        "precision_lo": round(lp, 3), "recall": round(rc, 3),
                        "recall_lo": round(lr, 3),
                        "label": lib.label(pr, rc, lp, lr, tp + fn)})
    return out


def misses(rows: list[dict[str, Any]], preds: list[dict[str, Any]]) -> list[dict[str, Any]]:
    cnt: Counter[tuple[str, str, str]] = Counter()
    for row, pr in zip(rows, preds, strict=True):
        for e in lib.ENTRIES:
            if truth(row, e) and not pr[e]:
                cnt[(e, row["cell"], pr["det"].reason[e])] += 1
    return [{"pattern": e, "cell": c, "reason": r, "designs": n}
            for (e, c, r), n in sorted(cnt.items())]


def evaluate() -> int:
    cfg = catalogue.load_tuning()
    out, miss = [], []
    for split in ("TEST", "TUNE"):
        rows = load(split)
        preds = run_cfg(rows, cfg)
        out += table(rows, preds, split)
        if split == "TEST":
            miss = misses(rows, preds)
            lib.write_csv(lib.RES / "partA_design.csv",
                          ["design", "cell", *[f"{k}_{e}" for e in lib.ENTRIES
                                               for k in ("truth", "found")]],
                          [{"design": r["design"], "cell": r["cell"],
                            **{f"truth_{e}": truth(r, e) for e in lib.ENTRIES},
                            **{f"found_{e}": p[e] for e in lib.ENTRIES}}
                           for r, p in zip(rows, preds, strict=True)])
    cols = ["split", "pattern", "cell", "designs", "TP", "FP", "FN", "precision", "precision_lo",
            "recall", "recall_lo", "label"]
    lib.write_csv(lib.RES / "partA_table.csv", cols, out)
    lib.write_csv(lib.RES / "partA_misses.csv", ["pattern", "cell", "reason", "designs"], miss)
    print(len(out), "table rows;", cfg)
    return 0


if __name__ == "__main__":
    raise SystemExit({"tune": tune, "eval": evaluate}[sys.argv[1]]())
