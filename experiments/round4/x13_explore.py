"""Exploratory entry 2026-10-25-c, items 1, 2, 4 of the round-4 fix brief (RQ-L13).

Not part of the registered analysis; every number it writes is labelled exploratory.

``repeat`` writes ``x13_repeat.csv`` (per design, f3): the registered repeat key (K0) next to a
null (the same words with cells replaced by random cells that carry the same cell labels, five
draws), a context key (K1: K0 plus the multiset of full-graph WL_2 colours of the footprint cells,
so fan-in and fan-out outside the word count) and the number of words in K0 groups that span at
least two module paths. ``summary`` pools it into ``x13_summary.csv`` (big, small, small without
the synthetic corpus, VerilogEval only) with the H13a/H13b status each baseline gives.
``h13c`` writes ``x13_h13c.csv``: the H13c share for V0 (4 leaves, r from H12b), V1, V2, with the
share from random groups of the same sizes next to it.
"""

from __future__ import annotations

import random
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import dictlib
import l13_measure
import r4lib

DRAWS = 5
Item = tuple[Path, str, str]  # dataset, design, set


def elig_words(g: dictlib.FG, words: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for w in words:
        fp = w["footprint"]
        if len(fp) >= 2 and l13_measure.width_of(w["params"]) >= 2 \
                and not str(w["type"]).startswith("$_CONST") and set(fp) <= set(g.kind):
            out.append(w)
    return out


def label_of(g: dictlib.FG, n: str) -> tuple[Any, ...]:
    return (g.kind[n], g.ctype[n], g.table.get(n, (0, 0)))


def n_edges(g: dictlib.FG, fp: frozenset[str]) -> int:
    return sum(1 for c in fp for _, s, _ in g.fin[c] if s in fp)


def sample_like(g: dictlib.FG, pools: dict[tuple[Any, ...], list[str]], fp: list[str],
                rnd: random.Random) -> frozenset[str]:
    """Random cells with the same multiset of cell labels as ``fp`` (distinct cells)."""
    need = Counter(label_of(g, c) for c in fp)
    out: list[str] = []
    for lab in sorted(need, key=repr):
        out += rnd.sample(pools[lab], need[lab])
    return frozenset(out)


def count_repeated(keys: list[tuple[Any, ...]]) -> int:
    cnt = Counter(keys)
    return sum(v for v in cnt.values() if v >= 2)


def ctx_of(col: dict[str, int], fp: frozenset[str]) -> int:
    return dictlib.h64(sorted(col[c] for c in fp))


def module_paths(fdir: Path) -> dict[str, str]:
    return {r["node_id"]: r["module_path"] for r in
            r4lib.read_csv(fdir / "labels.csv")}


def repeat_row(ds: Path, design: str, floor: str, sets: str) -> list[Any]:
    fdir = ds / design / floor
    g = dictlib.load_fg(fdir / "graph.json")
    words = elig_words(g, l13_measure.words_of(fdir))
    col = dictlib.wl_colors(g, 2)[2]
    mods = module_paths(fdir)
    pools: dict[tuple[Any, ...], list[str]] = defaultdict(list)
    for n in sorted(g.kind):
        pools[label_of(g, n)].append(n)
    k0: list[tuple[Any, ...]] = []
    k1: list[tuple[Any, ...]] = []
    struct: list[bool] = []
    wmod: list[str] = []
    for w in words:
        fp = frozenset(w["footprint"])
        base = (w["type"], l13_measure.width_of(w["params"]), len(fp),
                l13_measure.induced_hash(g, fp))
        k0.append(base)
        k1.append((*base, ctx_of(col, fp)))
        struct.append(n_edges(g, fp) > 0)
        wmod.append(Counter(mods.get(c, "") for c in fp).most_common(1)[0][0])
    cnt0 = Counter(k0)
    rep0 = [cnt0[k] >= 2 for k in k0]
    cnt1 = Counter(k1)
    rep1 = [cnt1[k] >= 2 for k in k1]
    span: dict[tuple[Any, ...], set[str]] = defaultdict(set)
    for k, m in zip(k0, wmod, strict=True):
        span[k].add(m)
    cross = sum(1 for k, r in zip(k0, rep0, strict=True) if r and len(span[k]) >= 2)
    null0 = null1 = null_struct = 0
    rnd = random.Random(f"{design}:{floor}:null")
    for _ in range(DRAWS):
        n0: list[tuple[Any, ...]] = []
        n1: list[tuple[Any, ...]] = []
        for w in words:
            fp2 = sample_like(g, pools, w["footprint"], rnd)
            b = (w["type"], l13_measure.width_of(w["params"]), len(fp2),
                 l13_measure.induced_hash(g, fp2))
            n0.append(b)
            n1.append((*b, ctx_of(col, fp2)))
            null_struct += int(n_edges(g, fp2) > 0)
        null0 += count_repeated(n0)
        null1 += count_repeated(n1)
    return [sets, design, floor, len(words), sum(struct),
            sum(1 for r, s in zip(rep0, struct, strict=True) if r and s), sum(rep0), sum(rep1),
            cross, null0, null1, null_struct, DRAWS, len(set(mods.values()))]


REP_HEAD = ["set", "design", "floor", "eligible", "eligible_struct", "rep_k0_struct", "rep_k0",
            "rep_k1", "cross_module_k0", "null_k0_sum", "null_k1_sum", "null_struct_sum",
            "draws", "modules"]


def big_items(floor: str) -> list[Item]:
    big = r4lib.DATA / "big"
    out = []
    for d in sorted(p.name for p in big.iterdir() if (p / "metrics.json").is_file()):
        ds = big / d / "dataset"
        if (ds / f"vtr_{d}" / floor / "graph.json").is_file():
            out.append((ds, f"vtr_{d}", "big"))
    return out


def run_repeat() -> int:
    rows = [repeat_row(ds, d, "f3", s) for ds, d, s in big_items("f3")]
    rows += [repeat_row(ds, d, "f3", s) for ds, d, s in l13_measure.small_items("f3")]
    r4lib.write_csv(r4lib.OUT / "x13_repeat.csv", REP_HEAD, rows)
    print(len(rows), "rows")
    return 0


def share(num: float, den: float) -> float:
    return num / den if den else 0.0


def summary() -> int:
    rep = r4lib.read_csv(r4lib.OUT / "x13_repeat.csv")
    sel: dict[str, tuple[str, ...]] = {
        "big": ("big",), "small": ("micro", "ve", "corpus"), "small_real": ("micro", "ve"),
        "small_ve": ("ve",), "small_micro": ("micro",), "small_corpus": ("corpus",)}
    out: list[list[Any]] = []
    for name, sets in sel.items():
        rr = [r for r in rep if r["set"] in sets]

        def t(k: str, rr: list[dict[str, str]] = rr) -> int:
            return sum(int(r[k]) for r in rr)

        e, d = t("eligible"), (t("draws") // len(rr) if rr else 0)
        es = t("eligible_struct")
        out.append([name, len(rr), e, round(share(t("rep_k0"), e), 6),
                    round(share(t("null_k0_sum"), e * d), 6),
                    round(share(t("rep_k0"), e) - share(t("null_k0_sum"), e * d), 6),
                    round(share(t("rep_k1"), e), 6),
                    round(share(t("null_k1_sum"), e * d), 6),
                    round(share(t("rep_k1"), e) - share(t("null_k1_sum"), e * d), 6),
                    round(share(es, e), 6), round(share(t("null_struct_sum"), e * d), 6),
                    round(share(t("rep_k0_struct"), es), 6),
                    round(share(t("cross_module_k0"), e), 6)])
    r4lib.write_csv(r4lib.OUT / "x13_summary.csv",
                    ["set", "designs", "eligible", "share_k0", "null_k0", "k0_minus_null",
                     "share_k1", "null_k1", "k1_minus_null", "share_edges", "null_share_edges",
                     "share_k0_among_edges", "cross_module_k0"], out)
    return 0


# -- H13c ------------------------------------------------------------------------------------
VARIANT_SIG = {"V0": 4, "V1": 6, "V2": 6}


def variant_radius(var: str) -> int:
    for r in r4lib.read_csv(r4lib.OUT / "l12b_radius.csv"):
        if r["floor"] == "f2" and r["variant"] == var and r["selected"] == "1":
            return int(r["radius"])
    raise SystemExit(f"no selected radius for {var}")


def group_rows(ds: Path, design: str, var: str) -> list[list[Any]]:
    fdir = ds / design / "f2"
    g = dictlib.load_fg(fdir / "graph.json")
    groups, _ = l13_measure.repeat_groups(g, l13_measure.words_of(fdir))
    if not groups:
        return []
    radius = variant_radius(var)
    sg = dictlib.signatures(g, VARIANT_SIG[var], radius)
    pools: dict[tuple[Any, ...], list[str]] = defaultdict(list)
    for n in sorted(g.kind):
        pools[label_of(g, n)].append(n)
    rnd = random.Random(f"{design}:{var}:h13c")
    out = []
    for gi, grp in enumerate(groups):
        ms = {tuple(sorted(sg.key(c, radius) for c in w["footprint"])) for w in grp}
        fp0 = frozenset(grp[0]["footprint"])
        nulls = []
        for _ in range(DRAWS):
            rs = set()
            for _m in grp:
                fp2 = sample_like(g, pools, grp[0]["footprint"], rnd)
                rs.add(tuple(sorted(sg.key(c, radius) for c in fp2)))
            nulls.append(int(len(rs) == 1))
        out.append([var, design, gi, grp[0]["type"], len(grp), len(fp0),
                    int(n_edges(g, fp0) > 0), int(len(ms) == 1), sum(nulls), DRAWS])
    return out


def run_h13c() -> int:
    rows: list[list[Any]] = []
    for var in VARIANT_SIG:
        for ds, d, _ in big_items("f2"):
            rows += group_rows(ds, d, var)
    r4lib.write_csv(r4lib.OUT / "x13_h13c.csv",
                    ["variant", "design", "group", "type", "members", "cells", "has_edges",
                     "same_signature", "null_same_sum", "draws"], rows)
    print(len(rows), "rows")
    return 0


def main() -> int:
    which = sys.argv[1] if len(sys.argv) > 1 else ""
    if which == "repeat":
        return run_repeat()
    if which == "summary":
        return summary()
    if which == "h13c":
        return run_h13c()
    raise SystemExit(__doc__)


if __name__ == "__main__":
    raise SystemExit(main())
