"""RQ-L14 identifiability: canonical netlist classes of the twin set, style-recovery ceiling and
the Bayes ceiling of the signature classifier on the corpus.

Writes ``l14_twins.csv`` (per base position and floor), ``l14_ident.csv`` (per family and floor,
pooled) and ``l14_bayes.csv``. See EXPERIMENT.md, Stage 4.
"""

from __future__ import annotations

import importlib
import itertools
import json
from collections import Counter
from typing import Any

import dictlib
import r4lib

nx: Any = importlib.import_module("networkx")
EXACT_MAX_NODES = 400
ROUNDS = 6
FLOORS3 = ("f1-k6", "f2", "f3")


def p_canonical(tab: int, w: int) -> int:
    """Smallest table over input permutations that respect the cofactor-count order."""
    sig = [(sum(1 for i in range(1 << w) if ((i >> v) & 1) == 0 and (tab >> i) & 1),
            sum(1 for i in range(1 << w) if ((i >> v) & 1) == 1 and (tab >> i) & 1))
           for v in range(w)]
    order = sorted(range(w), key=lambda v: sig[v])
    groups = [list(g) for _, g in itertools.groupby(order, key=lambda v: sig[v])]
    best: int | None = None
    for combo in itertools.product(*[itertools.permutations(g) for g in groups]):
        perm = [v for g in combo for v in g]
        out = 0
        for i in range(1 << w):
            j = 0
            for new_pos, old_pos in enumerate(perm):
                j |= ((i >> new_pos) & 1) << old_pos
            if (tab >> j) & 1:
                out |= 1 << i
        best = out if best is None else min(best, out)
    return best if best is not None else tab


def node_colour(g: dictlib.FG, n: str, cache: dict[tuple[int, int], int]) -> int:
    if n in g.table:
        tab, w = g.table[n]
        key = (tab, w)
        if key not in cache:
            cache[key] = p_canonical(tab, w)
        return dictlib.h64((g.kind[n], w, cache[key]))
    return dictlib.h64((g.kind[n], g.ctype[n] if g.kind[n] not in ("pi", "po") else ""))


def class_of(g: dictlib.FG, cache: dict[tuple[int, int], int]) -> tuple[int, dict[str, int]]:
    cur = {n: node_colour(g, n, cache) for n in g.kind}
    for _ in range(ROUNDS):
        cur = {n: dictlib.h64((cur[n], sorted((g.pin_of(n, p), cur[s]) for p, s, _ in g.fin[n])))
               for n in g.kind}
    return dictlib.h64(sorted(cur.values())), cur


def to_nx(g: dictlib.FG, col: dict[str, int]) -> Any:
    G = nx.DiGraph()
    for n in g.kind:
        G.add_node(n, c=col[n])
    for n, ins in g.fin.items():
        for p, s, _ in ins:
            G.add_edge(s, n, p=g.pin_of(n, p))
    return G


def exact_classes(items: list[tuple[str, dictlib.FG]], cache: dict[tuple[int, int], int]
                  ) -> int | None:
    """Number of isomorphism classes among ``items`` (None when a graph is too large)."""
    if any(len(g.kind) > EXACT_MAX_NODES for _, g in items):
        return None
    graphs = []
    for _, g in items:
        col = {n: node_colour(g, n, cache) for n in g.kind}
        graphs.append(to_nx(g, col))
    reps: list[Any] = []
    for G in graphs:
        for R in reps:
            if nx.is_isomorphic(G, R, node_match=lambda a, b: a["c"] == b["c"],
                                edge_match=lambda a, b: a["p"] == b["p"]):
                break
        else:
            reps.append(G)
    return len(reps)


def twins() -> list[list[Any]]:
    rows = r4lib.read_csv(r4lib.DATA / "twins-project" / "corpus.csv")
    groups: dict[tuple[str, str], list[str]] = {}
    for r in rows:
        groups.setdefault((r["family"], r["split"]), []).append(r["design"])
    cache: dict[tuple[int, int], int] = {}
    man = r4lib.manifest(r4lib.TWINS)
    ok = {e["design"]: {f for f, i in e["floors"].items() if i["status"] == "ok"}
          for e in man["designs"]}
    out: list[list[Any]] = []
    for (fam, base), des in sorted(groups.items()):
        for fl in FLOORS3:
            have = [d for d in des if fl in ok.get(d, set())]
            if len(have) < 2:
                continue
            fgs = [(d, dictlib.load_fg(r4lib.TWINS / d / fl / "graph.json")) for d in have]
            cls = Counter(class_of(g, cache)[0] for _, g in fgs)
            ex = exact_classes(fgs, cache)
            out.append([fam, base, fl, len(have), len(cls), "" if ex is None else ex,
                        round(len(cls) / len(have), 6),
                        "" if ex is None else round(ex / len(have), 6)])
    return out


def bayes() -> list[list[Any]]:
    cs = r4lib.corpus_split()
    out: list[list[Any]] = []
    for fl in r4lib.FLOORS:
        for kmax in (4, 6):
            bt: list[dict[tuple[int, int], Counter[frozenset[str]]]] = [{} for _ in range(4)]
            for d in r4lib.ok_designs(r4lib.CORPUS, fl):
                if d not in cs:
                    continue
                fdir = r4lib.CORPUS / d / fl
                sg = dictlib.signatures(dictlib.load_fg(fdir / "graph.json"), kmax)
                words = json.loads((fdir / "words.json").read_text(encoding="utf-8"))
                kinds = dictlib.kinds_of_cells(words)
                for cell in sg.g.cells:
                    ks = frozenset(kinds.get(cell, set()))
                    for r in range(4):
                        bt[r].setdefault(sg.key(cell, r), Counter())[ks] += 1
            for r in range(4):
                total = sum(sum(x.values()) for x in bt[r].values())
                acc = sum(max(x.values()) for x in bt[r].values()) / total
                per: dict[str, list[int]] = {k: [0, 0] for k in dictlib.KDICT}
                for cnt in bt[r].values():
                    n = sum(cnt.values())
                    for k in dictlib.KDICT:
                        nk = sum(v for ks, v in cnt.items() if k in ks)
                        per[k][1] += nk
                        if nk / n >= 0.5:
                            per[k][0] += nk
                out.append([fl, kmax, r, total, len(bt[r]), round(acc, 6)]
                           + [round(per[k][0] / per[k][1], 6) if per[k][1] else "" for k in
                              dictlib.KDICT])
    return out


def pooled(rows: list[list[Any]]) -> list[list[Any]]:
    acc: dict[tuple[str, str], list[float]] = {}
    acce: dict[tuple[str, str], list[float]] = {}
    for fam, _b, fl, n, c, ex, ceil, ceil_ex in rows:
        w = n  # weight by the number of style variants
        acc.setdefault((fam, fl), []).append(ceil * w)
        acc.setdefault(("*", fl), []).append(ceil * w)
        acc.setdefault((fam, fl + "#w"), []).append(w)
        acc.setdefault(("*", fl + "#w"), []).append(w)
        if ceil_ex != "":
            acce.setdefault((fam, fl), []).append(ceil_ex * w)
            acce.setdefault(("*", fl), []).append(ceil_ex * w)
            acce.setdefault((fam, fl + "#w"), []).append(w)
            acce.setdefault(("*", fl + "#w"), []).append(w)
        del c, ex
    out = []
    for (fam, fl), v in sorted(acc.items()):
        if fl.endswith("#w"):
            continue
        ceil = sum(v) / sum(acc[(fam, fl + "#w")])
        ve = acce.get((fam, fl))
        cex = round(sum(ve) / sum(acce[(fam, fl + "#w")]), 6) if ve else ""
        out.append([fam, fl, sum(acc[(fam, fl + "#w")]), round(ceil, 6),
                    round(1 - ceil, 6), cex])
    return out


def main() -> int:
    tw = twins()
    r4lib.write_csv(r4lib.OUT / "l14_twins.csv",
                    ["family", "base", "floor", "n_styles", "classes_wl", "classes_exact",
                     "ceiling_wl", "ceiling_exact"], tw)
    r4lib.write_csv(r4lib.OUT / "l14_ident.csv",
                    ["family", "floor", "n_designs", "ceiling_wl", "collapse_wl",
                     "ceiling_exact"], pooled(tw))
    r4lib.write_csv(r4lib.OUT / "l14_bayes.csv",
                    ["floor", "kmax", "radius", "cells", "signatures", "cell_acc",
                     *[f"recall_{k}" for k in dictlib.KDICT]], bayes())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
