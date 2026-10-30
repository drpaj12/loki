"""Q-L3: score the memory-word rule (``OUT/re/v3``) against v2 (``OUT/re/v2``) on the fixed
TUNE / TEST split of the plan amendment 2026-10-30 (TUNE = even design suffix, TEST = odd).

``score_v3.py``: writes ``results/v3/{per_design,summary,families,paired}.csv``.
Per split, per arm x floor: recall, pooled claim precision, design precision, false claims per
negative family; paired recall difference (new minus v2) over the positives of the split with a
bootstrap CI (Holm over the six cells); pooled-over-cells numbers for the hypothesis.
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
lib: Any = importlib.import_module("fsmlib")
sc: Any = importlib.import_module("score_v2")


def split_of(design: str) -> str:
    return "tune" if int(design.rsplit("_", 1)[1]) % 2 == 0 else "test"


def family(r: dict[str, Any]) -> str:
    return "fsm" if r["role"] == "pos" else str(r["design"]).split("_")[1]


def prec(rows: list[dict[str, Any]]) -> tuple[int, int, float | str]:
    cnt = sum(r["n_counted"] for r in rows)
    ok = sum(r["n_counted_match"] for r in rows)
    return ok, cnt, round(ok / cnt, 3) if cnt else "n/a"


def block(tag: str, rows: list[dict[str, Any]], arm: str, floor: str, sp: str) -> dict[str, Any]:
    pos = [r for r in rows if r["role"] == "pos"]
    ok, cnt, p = prec(rows)
    dcnt = sum(1 for r in rows if r["n_counted"])
    dok = sum(r["matched"] for r in pos)
    return {"tag": tag, "split": sp, "arm": arm, "floor": floor, "n_pos": len(pos),
            "recall": round(dok / len(pos), 3), "recall_n": dok, "counted": cnt,
            "counted_true": ok, "precision": p,
            "design_precision": round(dok / dcnt, 3) if dcnt else "n/a",
            "neg_designs_with_fp": sum(1 for r in rows if r["role"] == "neg" and r["n_counted"])}


def main() -> int:
    pop = lib.population()
    odir = lib.HERE / "results" / "v3"
    odir.mkdir(parents=True, exist_ok=True)
    allrows: list[dict[str, Any]] = []
    summ: list[dict[str, Any]] = []
    fams: list[dict[str, Any]] = []
    paired: list[dict[str, Any]] = []
    pooled: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for sp in ("tune", "test"):
        for arm in lib.ARMS:
            for floor in lib.FLOORS:
                got: dict[str, list[dict[str, Any]]] = {}
                for tag in ("v2", "v3"):
                    rows = [r for d in pop if split_of(d["design"]) == sp
                            and (r := sc.v2_row(arm, floor, d, tag)) is not None]
                    for r in rows:
                        r["tag"], r["split"] = tag, sp
                    got[tag] = rows
                    allrows += rows
                    summ.append(block(tag, rows, arm, floor, sp))
                    pooled.setdefault((tag, sp), []).extend(rows)
                    for fam in ("fsm", *lib.NEG_FAMILIES):
                        fr = [r for r in rows if family(r) == fam]
                        fams.append({"tag": tag, "split": sp, "arm": arm, "floor": floor,
                                     "family": fam, "designs": len(fr),
                                     "counted_claims": sum(r["n_counted"] for r in fr),
                                     "designs_with_claim": sum(1 for r in fr if r["n_counted"]),
                                     "matched_claims": sum(r["n_counted_match"] for r in fr)})
                old = {r["design"]: r["matched"] for r in got["v2"] if r["role"] == "pos"}
                ds = [r["matched"] - old[r["design"]] for r in got["v3"]
                      if r["role"] == "pos" and r["design"] in old]
                m, lo, hi, p = sc.boot(ds)
                paired.append({"split": sp, "arm": arm, "floor": floor, "n": len(ds),
                               "diff_recall": round(m, 3), "ci_lo": round(lo, 3),
                               "ci_hi": round(hi, 3), "p": round(p, 4)})
    for sp in ("tune", "test"):
        part = [r for r in paired if r["split"] == sp]
        for r, h in zip(part, sc.holm([float(x["p"]) for x in part]), strict=True):
            r["holm_p"] = round(h, 4)
    for (tag, sp), rows in sorted(pooled.items()):
        pos = [r for r in rows if r["role"] == "pos"]
        ok, cnt, p = prec(rows)
        summ.append({"tag": tag, "split": sp, "arm": "all", "floor": "all", "n_pos": len(pos),
                     "recall": round(sum(r["matched"] for r in pos) / len(pos), 3),
                     "recall_n": sum(r["matched"] for r in pos), "counted": cnt,
                     "counted_true": ok, "precision": p,
                     "design_precision": round(
                         sum(r["matched"] for r in pos)
                         / max(1, sum(1 for r in rows if r["n_counted"])), 3),
                     "neg_designs_with_fp": sum(
                         1 for r in rows if r["role"] == "neg" and r["n_counted"])})
    sc.write(odir / "per_design.csv", allrows)
    sc.write(odir / "summary.csv", summ)
    sc.write(odir / "families.csv", fams)
    sc.write(odir / "paired.csv", paired)
    for t in (summ, paired):
        for r in t:
            if r.get("arm") in (None, "all") or t is paired:
                print(r)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
