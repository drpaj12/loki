"""The config lists of the tuning stages and of the TEST run (EXPERIMENT.md "Split of the data and
tuning"). The choices made by q9_tune are read from results/chosen.json."""

from __future__ import annotations

import json
from typing import Any

import q9_env as env
from q9_rules import JOIN_GRIDS, ORDERS, SPLIT_GRID, Config

JOIN_RULES = (("bf", "E73"), ("bf", "EM2"), ("cond", "E73"), ("ctrl", "E73"))
CHOSEN = env.RES / "chosen.json"


def rule_id(rule: str, src: str) -> str:
    return f"{rule}-{src}" if rule == "bf" else rule


def read_chosen() -> dict[str, Any]:
    if not CHOSEN.is_file():
        return {}
    data: dict[str, Any] = json.loads(CHOSEN.read_text(encoding="utf-8"))
    return data


def join_grid() -> list[Config]:
    return [Config(f"{rule_id(r, s)}@{t}", "JOIN", r, s, t)
            for r, s in JOIN_RULES for t in JOIN_GRIDS[r]]


def join_chosen() -> list[Config]:
    ch = read_chosen()["join_train"]
    return [Config(f"{rule_id(r, s)}@{ch[rule_id(r, s)]}", "JOIN", r, s, ch[rule_id(r, s)])
            for r, s in JOIN_RULES]


def split_grid() -> list[Config]:
    return [Config(f"S-{s}@{t}", "SPLIT", ssrc=s, st=t) for s in ("E73", "EM2")
            for t in SPLIT_GRID]


def headline_parts() -> tuple[Config, Config]:
    """(join part, split part) of the chosen settings; either may be inactive."""
    ch = read_chosen()
    j = ch.get("join")
    s = ch.get("split")
    jc = Config("j", "JOIN", j["rule"], j["src"], j["t"]) if j else Config("j", "JOIN")
    sc = Config("s", "SPLIT", ssrc=s["src"], st=s["t"]) if s else Config("s", "SPLIT")
    return jc, sc


def make(order: str, name: str | None = None) -> Config | None:
    jc, sc = headline_parts()
    if order == "FIX" and jc.jrule == "bf" and sc.st is not None and sc.st <= -jc.jt:
        return None
    return Config(name or order, order, jc.jrule, jc.jsrc, jc.jt, sc.ssrc, sc.st)


def orders() -> list[Config]:
    return [c for o in ORDERS if (c := make(o)) is not None]


def test_set() -> list[Config]:
    """HEAD, the other join rules at their TRAIN threshold, and the split alone and after the
    join at its TRAIN-best threshold (fixed ablations, EXPERIMENT.md "Deviations")."""
    ch = read_chosen()
    jt = ch["join_train"]
    sp = ch["split_train"]
    jc, _ = headline_parts()
    head = make(ch["order"], "HEAD")
    out = [head] if head is not None else []
    out += [Config("BF73", "JOIN", "bf", "E73", jt["bf-E73"]),
            Config("BFM2", "JOIN", "bf", "EM2", jt["bf-EM2"]),
            Config("CTRL", "JOIN", "ctrl", "E73", jt["ctrl"]),
            Config("SPLIT", "SPLIT", ssrc=sp["src"], st=sp["t"]),
            Config("JS", "JS", jc.jrule, jc.jsrc, jc.jt, sp["src"], sp["t"])]
    return out


def no_configs() -> list[Config]:
    return []


def stage(name: str) -> list[Config]:
    table = {"joingrid": join_grid, "val4": join_chosen, "splitgrid": split_grid,
             "orders": orders, "test": test_set, "base": no_configs}
    return table[name]()
