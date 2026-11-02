"""Fit and choose on TRAIN and VALIDATION only: ``python -B q7_tune.py``.

lambda (rule a) and L0 (rule b) by right share on TRAIN; classifier (rule c) on TRAIN; on VALIDATION
the best two rules, the operator of rule d and the headline rule. No TEST file is read. Writes
results/tuning.csv, results/chosen.json and $QL7_OUT/clf.pkl.
"""

from __future__ import annotations

import json
import pickle
from typing import Any

import q7_env as env
import q7_feat as ft
import q7_rules as rules
import q7_score as sc


def picks_of(units: list[ft.UnitData], pick: rules.Picker) -> list[list[int]]:
    return [[pick(bp) for bp in u.blocks] for u in units]


def share_of(units: list[ft.UnitData], pick: rules.Picker) -> float:
    return sc.share(sc.score(units, picks_of(units, pick))[0])


def oracle_share(units: list[ft.UnitData]) -> float:
    rows = sc.score(units, picks_of(units, rules.end_of_path))[0]
    return sum(r["oracle"] for r in rows) / len(rows)


def set_share(units: list[ft.UnitData], pick: rules.Picker, sname: str, key: str) -> float:
    """Share of constructs of one set (single or comp) with ``key`` (right or oracle) set."""
    rows = [r for r in sc.score(units, picks_of(units, pick))[0] if r["set"] == sname]
    return round(sum(r[key] for r in rows) / len(rows), 4) if rows else float("nan")


def best_of(grid: list[tuple[Any, float]]) -> Any:
    """Highest share; ties go to the earlier grid value (the grids start at the smaller / lower)."""
    return max(grid, key=lambda g: g[1])[0]


def main() -> int:
    train, val = ft.load("TRAIN"), ft.load("VALIDATION")
    rows: list[dict[str, Any]] = []
    ga = [(lam, share_of(train, lambda bp, lam=lam: rules.rule_a(bp, lam)))
          for lam in sorted(rules.LAMBDAS, key=abs)]
    gb = [(l0, share_of(train, lambda bp, l0=l0: rules.rule_b(bp, l0))) for l0 in rules.L0S]
    lam, l0 = best_of(ga), best_of(gb)
    for lam_i, s in ga:
        v_share = share_of(val, lambda bp, v=lam_i: rules.rule_a(bp, v))
        rows.append({"rule": "a", "param": f"lambda={lam_i}", "train": round(s, 4),
                     "validation": round(v_share, 4)})
    for l0_i, s in gb:
        v_share = share_of(val, lambda bp, v=l0_i: rules.rule_b(bp, v))
        rows.append({"rule": "b", "param": f"L0={l0_i}", "train": round(s, 4),
                     "validation": round(v_share, 4)})
    blocks = [bp for u in train for bp in u.blocks]
    ncons = [len(u.cons) for u in train for _ in u.blocks]
    clf = rules.fit_classifier(blocks, ncons)
    cfg: dict[str, Any] = {"lambda": lam, "L0": l0}
    pk = rules.pickers(cfg, clf)
    vs = {n: share_of(val, pk[n]) for n in ("a", "b", "c")}
    best_two = sorted(vs, key=lambda n: (-vs[n], n))[:2]
    ops = {op: share_of(val, lambda bp, op=op: rules.combine(
        op, pk[best_two[0]](bp), pk[best_two[1]](bp), bp)) for op in rules.OPERATORS}
    op = max(rules.OPERATORS, key=lambda o: ops[o])
    cfg.update({"pair": best_two, "operator": op})
    pk = rules.pickers(cfg, clf)
    vs["d"] = ops[op]
    head = max("abcd", key=lambda n: vs[n])  # ties: a before b before c before d
    cfg["headline"] = head
    for name in "abcd":
        rows.append({"rule": name, "param": "chosen", "train": round(share_of(train, pk[name]), 4),
                     "validation": round(vs[name], 4)})
    for o, s in ops.items():
        rows.append({"rule": "d", "param": f"operator={o} of {best_two[0]}+{best_two[1]}",
                     "train": "", "validation": round(s, 4)})
    for name in ("END",):
        rows.append({"rule": name, "param": "", "train": round(share_of(train, pk[name]), 4),
                     "validation": round(share_of(val, pk[name]), 4)})
    rows.append({"rule": "ORACLE", "param": "", "train": round(oracle_share(train), 4),
                 "validation": round(oracle_share(val), 4)})
    def pick_of(name: str) -> rules.Picker:
        return pk.get(name, rules.end_of_path)  # ORACLE needs no picker, END is a reference

    by_set = [{"rule": name, "set": sname, "train": set_share(train, pick_of(name), sname, key),
               "validation": set_share(val, pick_of(name), sname, key)}
              for name, key in (*[(n, "right") for n in ("a", "b", "c", "d", "END")],
                                ("ORACLE", "oracle"))
              for sname in ("single", "comp")]
    env.RES.mkdir(exist_ok=True)
    env.l3dlib.write_csv(env.RES / "tuning_by_set.csv", list(by_set[0]), by_set)
    env.l3dlib.write_csv(env.RES / "tuning.csv", list(rows[0]), rows)
    (env.RES / "chosen.json").write_text(json.dumps(cfg, sort_keys=True) + "\n", encoding="utf-8")
    with (env.OUT7 / "clf.pkl").open("wb") as fh:
        pickle.dump(clf, fh)
    for r in rows:
        print(r)
    print(cfg)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
