"""Tuning on TRAIN and VALIDATION: ``python -B q9_tune.py STEP`` (never reads TEST).

Steps: join_train (joingrid on TRAIN, best threshold per rule), join_val (val4 on VALIDATION,
headline join), split (splitgrid on TRAIN and VALIDATION), order (orders on VALIDATION). Tables
go to results/tuning_*.csv and the choices to results/chosen.json.
"""

from __future__ import annotations

import json
import pickle
import sys
from typing import Any

import q9_cfg as cfgs
import q9_env as env
import q9_rules as rules


def load(stage: str, split: str) -> list[dict[str, Any]]:
    with (env.OUT9 / f"res_{stage}_{split}.pkl").open("rb") as fh:
        data: list[dict[str, Any]] = pickle.load(fh)
    return data


def nets(res: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    """Per config: constructs right before, after, gained, lost, joins, splits."""
    out: dict[str, dict[str, int]] = {}
    names = [n for n in res[0]["cfg"] if n != "BASE"]
    for n in names:
        row = dict.fromkeys(("before", "after", "gained", "lost", "joins", "splits"), 0)
        for u in res:
            for a, b in zip(u["cfg"]["BASE"]["rows"], u["cfg"][n]["rows"], strict=True):
                row["before"] += a["right"]
                row["after"] += b["right"]
                row["gained"] += int(b["right"] and not a["right"])
                row["lost"] += int(a["right"] and not b["right"])
            row["joins"] += u["cfg"][n]["joins"]
            row["splits"] += u["cfg"][n]["splits"]
        row["net"] = row["gained"] - row["lost"]
        out[n] = row
    return out


def table(split: str, res: list[dict[str, Any]], cfg_by: dict[str, rules.Config]
          ) -> list[dict[str, Any]]:
    return [{"split": split, "config": n, "constructs": sum(len(u["cfg"]["BASE"]["rows"])
                                                           for u in res), **r}
            for n, r in nets(res).items() if n in cfg_by]


def write(name: str, rows: list[dict[str, Any]]) -> None:
    env.l3dlib.write_csv(env.RES / name, list(rows[0]), rows)


def save(update: dict[str, Any]) -> None:
    ch = cfgs.read_chosen()
    ch.update(update)
    env.RES.mkdir(parents=True, exist_ok=True)
    cfgs.CHOSEN.write_text(json.dumps(ch, sort_keys=True, indent=1) + "\n", encoding="utf-8")


def best(rows: list[dict[str, Any]], key: Any) -> dict[str, Any]:
    """Highest net; ties: the strictest (``key`` is the strictness, higher = stricter)."""
    return max(rows, key=lambda r: (r["net"], key(r)))


def join_train() -> None:
    res = load("joingrid", "TRAIN")
    cfg_by = {c.name: c for c in cfgs.join_grid()}
    rows = table("TRAIN", res, cfg_by)
    write("tuning_join_TRAIN.csv", rows)
    chosen = {}
    for r_, s_ in cfgs.JOIN_RULES:
        rid = cfgs.rule_id(r_, s_)
        mine = [r for r in rows
                if (cfg_by[r["config"]].jrule, cfg_by[r["config"]].jsrc) == (r_, s_)]
        b = best(mine, lambda r: cfg_by[r["config"]].jt)
        chosen[rid] = cfg_by[b["config"]].jt
        print(rid, b)
    save({"join_train": chosen})


def join_val() -> None:
    res = load("val4", "VALIDATION")
    cfg_by = {c.name: c for c in cfgs.join_chosen()}
    rows = table("VALIDATION", res, cfg_by)
    write("tuning_join_VALIDATION.csv", rows)
    top = max(rows, key=lambda r: r["net"])
    if top["net"] > 0:
        c = cfg_by[top["config"]]
        save({"join": {"rule": c.jrule, "src": c.jsrc, "t": c.jt}})
    else:
        save({"join": None})
    print(top, cfgs.read_chosen().get("join"))


def split_step() -> None:
    cfg_by = {c.name: c for c in cfgs.split_grid()}
    rows = []
    for split in ("TRAIN", "VALIDATION"):
        rows += table(split, load("splitgrid", split), cfg_by)
    write("tuning_split.csv", rows)
    train = [r for r in rows if r["split"] == "TRAIN"]
    b = best(train, lambda r: cfg_by[r["config"]].st)
    v = next(r for r in rows if r["split"] == "VALIDATION" and r["config"] == b["config"])
    c = cfg_by[b["config"]]
    save({"split": {"src": c.ssrc, "t": c.st} if v["net"] > 0 else None,
          "split_train": {"src": c.ssrc, "t": c.st}})
    print(b, v, cfgs.read_chosen().get("split"))


def order_step() -> None:
    res = load("orders", "VALIDATION")
    cfg_by = {c.name: c for c in cfgs.orders()}
    rows = table("VALIDATION", res, cfg_by)
    write("tuning_order.csv", rows)
    top = max(rows, key=lambda r: (r["net"], -rules.ORDERS.index(r["config"])))
    save({"order": top["config"]})
    print(top)


def main(argv: list[str]) -> int:
    {"join_train": join_train, "join_val": join_val, "split": split_step,
     "order": order_step}[argv[0]]()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
