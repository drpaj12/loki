"""Choose the headline order on VALIDATION: ``python -B q8a_choose.py [SPLIT]``.

See EXPERIMENT.md "Candidate orders".

END right share per order, overall and per target and set; writes results/chosen.json and
results/tuning.csv. No answer-key number of TEST is read.
"""

from __future__ import annotations

import json
import sys
from typing import Any

import q8a_env as env
import q8a_feat as feat

q7s = env.mod("q7_score")
q7r = env.mod("q7_rules")


def end_rows(order: str, split: str) -> list[dict[str, Any]]:
    units = feat.load(order, split)
    picks = [[bp.n - 1 for bp in u.blocks] for u in units]
    return list(q7s.score(units, picks)[0])


def share(rows: list[dict[str, Any]], key: str = "right") -> float:
    return round(sum(r[key] for r in rows) / len(rows), 4) if rows else float("nan")


def scopes(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    out = {"all": rows}
    for t, cs in env.TARGETS.items():
        out[f"target {t}"] = [r for r in rows if r["cell"] in cs]
    for s in ("single", "comp"):
        out[f"set {s}"] = [r for r in rows if r["set"] == s]
    return out


def main(argv: list[str]) -> int:
    split = argv[0] if argv else "VALIDATION"
    table: list[dict[str, Any]] = []
    best: dict[str, dict[str, float]] = {}
    for order in env.ORDERS:
        for name, rows in scopes(end_rows(order, split)).items():
            table.append({"split": split, "order": order, "scope": name, "constructs": len(rows),
                          "end_share": share(rows), "oracle_share": share(rows, "oracle")})
            best.setdefault(name, {})[order] = share(rows)
    env.l3dlib.write_csv(env.RES / f"tuning_{split}.csv", list(table[0]), table)
    pick = {name: max(env.CANDIDATES, key=lambda o: (v[o], -env.CANDIDATES.index(o)))
            for name, v in best.items()}
    cfg = {"headline": pick["all"], "per_target": {t: pick[f"target {t}"] for t in env.TARGETS},
           "validation_end_share": best}
    (env.RES / "chosen.json").write_text(json.dumps(cfg, sort_keys=True, indent=1) + "\n",
                                         encoding="utf-8")
    print(json.dumps(cfg, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
