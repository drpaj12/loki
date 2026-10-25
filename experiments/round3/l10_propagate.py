"""RQ-L10: how far from the I/O port words do the ground-truth word constructs lie?

Definitions: ``EXPERIMENT.md`` (round 3). Pure ground-truth analysis of the L0 floors; no run is
read. Writes ``l10_reach.csv`` and ``l10_ports.csv``.
"""

from __future__ import annotations

import json
import math
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import r3lib

from loki.score.gt import COMPARE, GtInstance, derive_instances, label_buses, read_labels

NOT_CELLS = frozenset({"pi", "po", "const"})
MAX_LEVEL = 4
GROUP_CAP = 20000
TAUS = {"relaxed": 0.75, "strict": 1.0}
DATAPATH = ("register", "mux", "mux_tree", "adder", "subtractor", "comparator", "counter")
CONTROL = ("eq_const", "fsm")
WIDTH_KEYS = ("WIDTH", "Y_WIDTH", "A_WIDTH", "B_WIDTH")

Sig = tuple[str, str, str, int]
Group = tuple[str, ...]


@dataclass(frozen=True)
class Graph:
    sig: dict[str, Sig]
    out: dict[str, list[tuple[str, str]]]  # src -> (reader, pin)
    inn: dict[str, list[tuple[str, str]]]  # dst -> (driver, pin)


def load_graph(floor_dir: Path) -> Graph:
    obj = json.loads((floor_dir / "graph.json").read_text(encoding="utf-8"))
    sig: dict[str, Sig] = {}
    for n in obj["nodes"]:
        f = n["features"]
        sig[str(n["id"])] = (str(n["kind"]), str(n["labels"]["cell_type"]),
                             str(f.get("lut_table", "")), int(f.get("lut_width", 0)))
    out: dict[str, list[tuple[str, str]]] = defaultdict(list)
    inn: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for e in obj["edges"]:
        out[str(e["src"])].append((str(e["dst"]), str(e["pin"])))
        inn[str(e["dst"])].append((str(e["src"]), str(e["pin"])))
    return Graph(sig, dict(out), dict(inn))


def step(g: Graph, word: Group, tau: float, forward: bool) -> list[Group]:
    """Groups one hop from ``word`` (forward: readers; backward: drivers), per EXPERIMENT.md."""
    k = len(word)
    need = max(2, math.ceil(tau * k))
    adj = g.out if forward else g.inn
    by_sig: dict[tuple[Sig, str], dict[int, list[str]]] = defaultdict(lambda: defaultdict(list))
    for i, x in enumerate(word):
        for cell, pin in adj.get(x, ()):
            if g.sig[cell][0] in NOT_CELLS:
                continue
            by_sig[(g.sig[cell], pin)][i].append(cell)
    groups: list[Group] = []
    for _s, bits in sorted(by_sig.items()):
        cells = [c[0] for _i, c in sorted(bits.items()) if len(c) == 1]
        if len(cells) >= need and len(set(cells)) == len(cells):
            groups.append(tuple(cells))
    return groups


def port_words(floor_dir: Path, g: Graph) -> list[Group]:
    words: list[Group] = []
    for b in label_buses(read_labels(floor_dir)):
        kinds = {g.sig[n][0] for n in b.members if n in g.sig}
        if len(b.members) >= 2 and kinds in ({"pi"}, {"po"}):
            words.append(tuple(n for n, _bit in sorted(b.bits, key=lambda t: t[1])))
    return sorted(set(words))


def propagate(g: Graph, ports: list[Group], tau: float) -> tuple[dict[frozenset[str], int], bool]:
    """Cell set of every group to its lowest level (1..MAX_LEVEL); True when the cap was hit."""
    seen: dict[frozenset[str], int] = {frozenset(w): 0 for w in ports}
    frontier = list(ports)
    for level in range(1, MAX_LEVEL + 1):
        nxt: list[Group] = []
        for w in frontier:
            for fwd in (True, False):
                for y in step(g, w, tau, fwd):
                    key = frozenset(y)
                    if key not in seen:
                        seen[key] = level
                        nxt.append(y)
        if len(seen) > GROUP_CAP:
            return seen, True
        frontier = nxt
    return seen, False


def width_of(params: dict[str, Any]) -> int:
    return max((int(params[k]) for k in WIDTH_KEYS
                if isinstance(params.get(k), int) and not isinstance(params.get(k), bool)),
               default=1)


def kinds_of(words: dict[str, Any], insts: list[GtInstance]) -> dict[str, str]:
    """gid to counted construct kind (width >= 2 and >= 2 cells), others left out."""
    by_id = {int(w["id"]): w for w in words["words"]}
    out: dict[str, str] = {}
    for i in insts:
        if len(i.footprint) < 2:
            continue
        if i.gid[0] in "rcmf":
            out[i.gid] = {"r": "register", "c": "counter", "m": "mux_tree", "f": "fsm"}[i.gid[0]]
            continue
        w = by_id[int(i.gid[1:])]
        if width_of(w.get("params", {})) < 2:
            continue
        t = str(w["type"])
        if t in ("$mux", "$pmux"):
            out[i.gid] = "mux"
        elif t == "$add":
            out[i.gid] = "adder"
        elif t == "$sub":
            out[i.gid] = "subtractor"
        elif t in COMPARE:
            const = bool(w.get("const_ports")) and t in ("$eq", "$ne")
            out[i.gid] = "eq_const" if const else "comparator"
    return out


RELATIONAL = ("$lt", "$le", "$gt", "$ge")
SUBSUMED_BY = {"mux": "mux_tree", "register": "counter"}


def relconst_gids(words: dict[str, Any], kinds: dict[str, str]) -> set[str]:
    """Exploratory: ``comparator`` gids whose word is $lt/$le/$gt/$ge with a constant port (the
    protocol says a comparator has none; the deciding count keeps them)."""
    by_id = {int(w["id"]): w for w in words["words"]}
    return {g for g, k in kinds.items()
            if k == "comparator" and g[0] == "w" and by_id[int(g[1:])]["type"] in RELATIONAL
            and by_id[int(g[1:])].get("const_ports")}


def subsumed_gids(insts: list[GtInstance], kinds: dict[str, str]) -> set[str]:
    """Exploratory: counted mux (register) constructs whose footprint lies inside a counted
    mux_tree (counter) footprint of the design, so the same cells are not counted twice."""
    foot = {i.gid: i.footprint for i in insts}
    out: set[str] = set()
    for gid, kind in kinds.items():
        outer = SUBSUMED_BY.get(kind)
        if outer and any(foot[gid] <= foot[o] for o, k in kinds.items() if k == outer):
            out.add(gid)
    return out


def reach_levels(groups: dict[frozenset[str], int], insts: list[GtInstance],
                 kinds: dict[str, str]) -> dict[str, tuple[int, int]]:
    """gid to (seed level, full level), 99 when never reached."""
    by_cell: dict[str, list[frozenset[str]]] = defaultdict(list)
    for y, lvl in groups.items():
        if lvl >= 1 and len(y) >= 2:
            for c in y:
                by_cell[c].append(y)
    res: dict[str, tuple[int, int]] = {}
    for i in insts:
        if i.gid not in kinds:
            continue
        near = {y for c in i.footprint for y in by_cell.get(c, ())}
        seed = full = 99
        for y in near:
            k = len(y & i.footprint)
            lvl = groups[y]
            if k >= 2 and k / len(y) >= 0.5:
                seed = min(seed, lvl)
            if k / len(y | i.footprint) >= 0.5:
                full = min(full, lvl)
        res[i.gid] = (seed, full)
    return res


def main() -> int:
    plan = [("micro", r3lib.MICRO, f) for f in ("f2", "f3", "f1-k6")] + \
           [("veval", r3lib.VEVAL, f) for f in ("f2", "f3")]
    reach_rows: list[list[object]] = []
    port_rows: list[list[object]] = []
    design_rows: list[list[object]] = []
    expl_rows: list[list[object]] = []
    for ds, root, floor in plan:
        designs = r3lib.designs_of(root, floor)
        for tname, tau in TAUS.items():
            cnt: dict[str, list[int]] = defaultdict(lambda: [0] * 11)
            n_port = n_with = n_pi = n_po = capped = 0
            ex: dict[tuple[str, str], list[int]] = defaultdict(lambda: [0, 0, 0])
            for d in designs:
                fd = root / d / floor
                g = load_graph(fd)
                ports = port_words(fd, g)
                groups, hit = propagate(g, ports, tau)
                words = json.loads((fd / "words.json").read_text(encoding="utf-8"))
                insts = derive_instances(words)
                kinds = kinds_of(words, insts)
                lv = reach_levels(groups, insts, kinds)
                capped += 1 if hit else 0
                rel = relconst_gids(words, kinds)
                sub = subsumed_gids(insts, kinds)
                ex[("footprint_io_cells", "all")][2] += sum(
                    1 for i in insts if i.gid in kinds for c in i.footprint
                    if g.sig[c][0] in ("pi", "po"))
                for gid, (seed, _full) in lv.items():
                    cl = "datapath" if kinds[gid] in DATAPATH else "control"
                    for var, drop in (("deciding", False), ("no_relconst", gid in rel),
                                      ("dedup_footprint", gid in sub),
                                      ("no_relconst_dedup", gid in rel or gid in sub)):
                        if not drop:
                            row = ex[(var, cl)]
                            row[0] += 1
                            row[1] += 1 if seed <= 2 else 0
                    ex[("relconst_count", cl)][2] += 1 if gid in rel else 0
                    ex[("subsumed_count", cl)][2] += 1 if gid in sub else 0
                n_port += len(ports)
                n_with += 1 if ports else 0
                n_pi += sum(1 for w in ports if g.sig[w[0]][0] == "pi")
                n_po += sum(1 for w in ports if g.sig[w[0]][0] == "po")
                dcl: dict[str, list[int]] = defaultdict(lambda: [0, 0])
                for gid, (seed, _full) in lv.items():
                    cl = "datapath" if kinds[gid] in DATAPATH else "control"
                    dcl[cl][0] += 1
                    dcl[cl][1] += 1 if seed <= 2 else 0
                for cl, (n_cl, n_h2) in sorted(dcl.items()):
                    design_rows.append([ds, floor, tname, d, cl, n_cl, n_h2])
                for gid, (seed, full) in lv.items():
                    row = cnt[kinds[gid]]
                    row[0] += 1
                    for h in range(1, MAX_LEVEL + 1):
                        row[h] += 1 if seed <= h else 0
                        row[4 + h] += 1 if full <= h else 0
                    row[9] += 1 if seed == 99 else 0
                    row[10] += 1 if full == 99 else 0
            for kind in (*DATAPATH, *CONTROL):
                r = cnt.get(kind, [0] * 11)
                cls = "datapath" if kind in DATAPATH else "control"
                reach_rows.append([ds, floor, tname, kind, cls, *r])
            for (var, cl), (n_v, h2_v, extra) in sorted(ex.items()):
                expl_rows.append([ds, floor, tname, var, cl, n_v, h2_v, extra])
            port_rows.append([ds, floor, tname, len(designs), n_with, n_pi, n_po, capped])
        print("done", ds, floor, len(designs), flush=True)
    r3lib.write_csv(r3lib.HERE / "l10_reach.csv",
                    ["dataset", "floor", "rule", "kind", "class", "n_gt", "seed_h1", "seed_h2",
                     "seed_h3", "seed_h4", "full_h1", "full_h2", "full_h3", "full_h4",
                     "never_seed", "never_full"], reach_rows)
    r3lib.write_csv(r3lib.HERE / "l10_design.csv",
                    ["dataset", "floor", "rule", "design", "class", "n_gt", "seed_h2"], design_rows)
    r3lib.write_csv(r3lib.HERE / "l10_exploratory.csv",
                    ["dataset", "floor", "rule", "variant", "class", "n_gt", "seed_h2",
                     "count"], expl_rows)
    r3lib.write_csv(r3lib.HERE / "l10_ports.csv",
                    ["dataset", "floor", "rule", "designs", "designs_with_port_word",
                     "input_words", "output_words", "designs_capped"], port_rows)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
