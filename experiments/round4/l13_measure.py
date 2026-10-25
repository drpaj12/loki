"""RQ-L13: structure measures of designs (repeat groups, memories, depth, buses, fan-out, FSMs).

Usage: l13_measure.py big | small   (writes ``l13_big.csv`` or ``l13_small.csv``, and for ``big``
also ``l13_groups.csv`` with the signature test of H13c)
Definitions are those of EXPERIMENT.md, Stage 3: a *repeat group* is a set of at least two GT
words (at least 2 cells, width >= 2) with equal (type, width, cell count, WL-2 hash of the
footprint-induced subgraph); `share_rep` is the share of such words in a group.
"""

from __future__ import annotations

import csv
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

import dictlib
import r4lib

from loki.score.gt import label_buses

HIGH_FANOUT = 8
WIDTH_KEYS = ("WIDTH", "Y_WIDTH", "A_WIDTH", "B_WIDTH")
WIDE_BUS = 8


def width_of(params: dict[str, Any]) -> int:
    ws = [v for k, v in params.items() if k in WIDTH_KEYS and isinstance(v, int)]
    return max(ws) if ws else 1


def induced_hash(g: dictlib.FG, cells: frozenset[str], rounds: int = 2) -> int:
    cur = {c: dictlib.h64((g.kind[c], g.ctype[c], g.table.get(c, (0, 0)))) for c in cells}
    for _ in range(rounds):
        cur = {c: dictlib.h64((cur[c], sorted(
            (g.pin_of(c, p), cur[s]) for p, s, _ in g.fin[c] if s in cells))) for c in cells}
    return dictlib.h64(sorted(cur.values()))


def words_of(fdir: Path) -> list[dict[str, Any]]:
    obj = json.loads((fdir / "words.json").read_text(encoding="utf-8"))
    return list(obj["words"])


def repeat_groups(g: dictlib.FG, words: list[dict[str, Any]]
                  ) -> tuple[list[list[dict[str, Any]]], int]:
    """(groups of size >= 2, number of eligible words)."""
    elig = [w for w in words
            if len(w["footprint"]) >= 2 and width_of(w["params"]) >= 2
            and not str(w["type"]).startswith("$_CONST")]
    keyed: dict[tuple[Any, ...], list[dict[str, Any]]] = {}
    for w in elig:
        fp = frozenset(w["footprint"])
        if not fp <= set(g.kind):
            continue
        key = (w["type"], width_of(w["params"]), len(fp), induced_hash(g, fp))
        keyed.setdefault(key, []).append(w)
    return [v for _, v in sorted(keyed.items(), key=lambda kv: repr(kv[0])) if len(v) >= 2], \
        len(elig)


def measure(dataset: Path, design: str, floor: str, sets: str) -> dict[str, Any]:
    fdir = dataset / design / floor
    g = dictlib.load_fg(fdir / "graph.json")
    words = words_of(fdir)
    groups, n_elig = repeat_groups(g, words)
    n_rep = sum(len(v) for v in groups)
    with (fdir / "labels.csv").open(encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))
    buses = label_buses(rows)
    modules = Counter(r["module_path"] for r in rows if r["kind"] not in ("pi", "po"))
    readers: Counter[str] = Counter()
    nets: dict[str, set[str]] = {}
    for n in g.kind:
        for p, d, net in g.fout[n]:
            if p != "CLK" and g.kind[n] != "const":
                readers[net] += 1
                nets.setdefault(net, set()).add(d)
    high = {n for n, c in readers.items() if c >= HIGH_FANOUT}
    word_of: dict[str, set[int]] = {}
    for w in words:
        for c in w["footprint"]:
            word_of.setdefault(c, set()).add(int(w["id"]))
    shared = sum(1 for n in high if len({i for d in nets[n] for i in word_of.get(d, ())}) >= 2)
    ffs = [c for c in g.cells if g.kind[c] == "ff"]
    lvl = _levels(fdir)
    d_levels = []
    for c in ffs:
        src = [s for p, s, _ in g.fin[c] if p == "D"]
        d_levels.append(lvl.get(src[0], 0) if src else 0)
    mems = [w for w in words if str(w["type"]) in ("$mem", "$memrd", "$memwr")]
    return {
        "design": design, "floor": floor, "set": sets, "cells": len(g.cells),
        "words": len(words), "eligible_words": n_elig, "repeated_words": n_rep,
        "repeat_groups": len(groups), "max_group": max((len(v) for v in groups), default=0),
        "modules": len(modules), "memories": len(mems),
        "wide_buses": sum(1 for b in buses if len(b.bits) >= WIDE_BUS),
        "max_bus": max((len(b.bits) for b in buses), default=0),
        "ffs": len(ffs), "ff_shallow": sum(1 for x in d_levels if x <= 1),
        "ff_dlevel_max": max(d_levels, default=0),
        "high_fanout_nets": len(high), "shared_ctrl_nets": shared,
        "max_fanout": max(readers.values(), default=0),
        "fsm_words": sum(1 for w in words if w.get("fsm")),
    }


def _levels(fdir: Path) -> dict[str, int]:
    obj = json.loads((fdir / "graph.json").read_text(encoding="utf-8"))
    return {str(n["id"]): int(n["features"]["level"]) for n in obj["nodes"]}


def group_signature_test(dataset: Path, design: str, radius: int) -> list[list[Any]]:
    """H13c rows at f2: per repeat group, whether all members have equal signature multisets."""
    fdir = dataset / design / "f2"
    g = dictlib.load_fg(fdir / "graph.json")
    groups, _ = repeat_groups(g, words_of(fdir))
    if not groups:
        return []
    sg = dictlib.signatures(g, 6, max(radius, 0))
    out = []
    for gi, grp in enumerate(groups):
        ms = [tuple(sorted(sg.key(c, radius) for c in w["footprint"])) for w in grp]
        out.append([design, gi, grp[0]["type"], len(grp), len(grp[0]["footprint"]),
                    int(len(set(ms)) == 1), len(set(ms))])
    return out


def selected_radius() -> int:
    for r in r4lib.read_csv(r4lib.OUT / "l12b_radius.csv"):
        if r["floor"] == "f2" and r["variant"] == "V1" and r["selected"] == "1":
            return int(r["radius"])
    raise SystemExit("l12b_radius.csv has no selected V1 radius at f2")


def small_items(floor: str) -> list[tuple[Path, str, str]]:
    cs = r4lib.corpus_split()
    items = [(r4lib.MICRO, d, "micro") for d in r4lib.ok_designs(r4lib.MICRO, floor)]
    items += [(r4lib.VEVAL, d, "ve") for d in r4lib.ok_designs(r4lib.VEVAL, floor)]
    items += [(r4lib.CORPUS, d, "corpus") for d in r4lib.ok_designs(r4lib.CORPUS, floor)
              if cs[d][1] == "train"]
    return items


def main() -> int:
    which = sys.argv[1] if len(sys.argv) > 1 else ""
    out: list[dict[str, Any]] = []
    grp: list[list[Any]] = []
    if which == "small":
        for floor in r4lib.FLOORS:
            out += [measure(ds, d, floor, s) for ds, d, s in small_items(floor)]
        name = "l13_small.csv"
    elif which == "big":
        big = r4lib.DATA / "big"
        radius = selected_radius()
        for d in sorted(p.name for p in big.iterdir() if (p / "metrics.json").is_file()):
            ds = big / d / "dataset"
            for floor in ("f2", "f3"):
                if (ds / f"vtr_{d}" / floor / "graph.json").is_file():
                    out.append(measure(ds, f"vtr_{d}", floor, "big"))
            if (ds / f"vtr_{d}" / "f2" / "graph.json").is_file():
                grp += group_signature_test(ds, f"vtr_{d}", radius)
        name = "l13_big.csv"
        r4lib.write_csv(r4lib.OUT / "l13_groups.csv",
                        ["design", "group", "type", "members", "cells", "same_signature",
                         "distinct_signatures"], grp)
    else:
        raise SystemExit(__doc__)
    keys = list(out[0]) if out else []
    r4lib.write_csv(r4lib.OUT / name, keys, [[r[k] for k in keys] for r in out])
    print(len(out), "rows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
