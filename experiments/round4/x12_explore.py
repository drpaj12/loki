"""Exploratory entry 2026-10-25-c, items 9, 10, 14, 15 of the round-4 fix brief (RQ-L12).

Not part of the registered analysis; no status changes. Subcommands:

``dup``    netlist-level duplicates of the corpus test designs (``x12_dup.csv``, per design, floor)
           and the H12b2 / GNN results restricted to test designs absent from train
           (``x12_dup_summary.csv``).
``gnn``    the GNN slope on the actual train sizes and with B = 20000 bootstrap draws
           (``x12_gnn.csv``); test-set sizes after the has-logic filter (``x12_ntrain.csv``).
"""

from __future__ import annotations

import json
import math
import random
import sys
from collections import defaultdict
from typing import Any

import decide
import dictlib
import l12c_gnn
import l14_ident
import r4lib


def netlist_keys(floor: str, design: str) -> tuple[int, int]:
    """(multiset hash of cell labels and edges, 1-WL class) of a corpus netlist."""
    g = dictlib.load_fg(r4lib.CORPUS / design / floor / "graph.json")
    lab = {n: (g.kind[n], g.ctype[n] if g.kind[n] not in ("pi", "po") else "",
               g.table.get(n, (0, 0))) for n in g.kind}
    cells = sorted(map(repr, lab.values()))
    edges = sorted(repr((lab[s], lab[d], p)) for d in g.fin for p, s, _ in g.fin[d])
    mset = dictlib.h64((cells, edges))
    l14_ident.TIE_CAP = 24
    wl = l14_ident.class_of(g, {})[0]
    return mset, wl


def dup_rows() -> list[list[Any]]:
    cs = r4lib.corpus_split()
    out: list[list[Any]] = []
    for fl in r4lib.FLOORS:
        keys = {d: netlist_keys(fl, d) for d in r4lib.ok_designs(r4lib.CORPUS, fl) if d in cs}
        train: dict[tuple[str, int], set[str]] = defaultdict(set)
        trainwl: dict[tuple[str, int], set[str]] = defaultdict(set)
        for d, (m, w) in keys.items():
            if cs[d][1] == "train":
                train[(cs[d][0], m)].add(d)
                trainwl[(cs[d][0], w)].add(d)
        for d, (m, w) in sorted(keys.items()):
            fam, sp = cs[d]
            if sp == "train":
                continue
            out.append([fl, d, fam, sp, int((fam, m) in train), int((fam, w) in trainwl)])
    return out


def load_dup() -> dict[tuple[str, str], tuple[int, int]]:
    return {(r["floor"], r["design"]): (int(r["dup_multiset"]), int(r["dup_wl"]))
            for r in r4lib.read_csv(r4lib.OUT / "x12_dup.csv")}


def micro_f1(dic: dict[tuple[str, str, str, str], dict[str, decide.Row]], var: str,
             split: str, keep: set[str] | None) -> float:
    rows = [v for (arm, fl, ss, d), kinds in dic.items()
            if arm == f"dict-{var}" and fl == "f2" and ss == split and (keep is None or d in keep)
            for v in kinds.values()]
    return decide.f1_of(*decide.pooled(rows))


def gnn_restricted(conf: dict[str, Any], floor: str, which: str, keep: set[str] | None
                   ) -> tuple[list[float], list[float]]:
    """(n_train mean, macro-F1 mean over seeds) per corpus size for the designs in ``keep``."""
    xs, ys = [], []
    for m in l12c_gnn.PER_FAMILY:
        runs = [conf[f"{floor}/c{m}-s{s}"] for s in l12c_gnn.SEEDS if f"{floor}/c{m}-s{s}" in conf]
        if not runs:
            continue
        vals = []
        for run in runs:
            des = [d for d, w in run["which"].items() if w == which and (keep is None or d in keep)]
            vals.append(l12c_gnn.macro_f1(l12c_gnn.pooled(run["conf"], des)))
        xs.append(sum(r["n_train"] for r in runs) / len(runs))
        ys.append(sum(vals) / len(vals))
    return xs, ys


def dup_summary() -> list[list[Any]]:
    dup = load_dup()
    cs = r4lib.corpus_split()
    out: list[list[Any]] = []
    for fl in r4lib.FLOORS:
        for sp in ("iid", "ood"):
            ds = [d for (f, d) in dup if f == fl and cs[d][1] == sp]
            n = len(ds)
            out.append(["dup_rate", fl, sp, "multiset", n, sum(dup[(fl, d)][0] for d in ds), ""])
            out.append(["dup_rate", fl, sp, "wl", n, sum(dup[(fl, d)][1] for d in ds), ""])
    dic = decide.load_rows(r4lib.OUT / "l12b_dict_rows.csv")
    for kidx, kname in ((0, "multiset"), (1, "wl")):
        keep = {d for (f, d), v in dup.items() if f == "f2" and v[kidx] == 0}
        for var in decide.VARIANTS:
            fi = micro_f1(dic, var, "iid", None)
            fo = micro_f1(dic, var, "ood", None)
            ki = micro_f1(dic, var, "iid", keep)
            ko = micro_f1(dic, var, "ood", keep)
            n_i = len([d for d in keep if cs[d][1] == "iid"])
            n_o = len([d for d in keep if cs[d][1] == "ood"])
            out.append(["h12b2_all", "f2", var, kname, "", round(fi, 6), round(fo, 6)])
            out.append(["h12b2_restricted", "f2", var, kname, f"{n_i}/{n_o}",
                        round(ki, 6), round(ko, 6)])
    conf = json.loads((l12c_gnn.GNN / "conf.json").read_text(encoding="utf-8"))
    for fl in r4lib.FLOORS:
        for kidx, kname in ((0, "multiset"), (1, "wl")):
            keep = {d for (f, d), v in dup.items() if f == fl and v[kidx] == 0}
            for sp in ("iid", "ood"):
                for tag, kp in (("all", None), ("restricted", keep)):
                    xs, ys = gnn_restricted(conf, fl, sp, kp)
                    sl = decide.ols_slope([math.log2(x) for x in xs], ys)
                    out.append([f"gnn_{tag}", fl, sp, kname,
                                "" if kp is None else len(kp & {d for d, w in
                                                         conf[f"{fl}/c70-s0"]["which"].items()
                                                         if w == sp}),
                                " ".join(f"{y:.4f}" for y in ys), round(sl, 6)])
    return out


def run_dup() -> int:
    rows = dup_rows()
    r4lib.write_csv(r4lib.OUT / "x12_dup.csv",
                    ["floor", "design", "family", "split", "dup_multiset", "dup_wl"], rows)
    r4lib.write_csv(r4lib.OUT / "x12_dup_summary.csv",
                    ["what", "floor", "set_or_variant", "key", "n", "a", "b"], dup_summary())
    return 0


# -- GNN: actual n_train, larger B ------------------------------------------------------------
def boot_ci(conf: dict[str, Any], floor: str, des: list[str], b: int, actual: bool
            ) -> tuple[float, float, float]:
    def slope(picks: list[str]) -> float:
        xs, ys = [], []
        for m in l12c_gnn.PER_FAMILY:
            runs = [conf[f"{floor}/c{m}-s{s}"] for s in l12c_gnn.SEEDS
                    if f"{floor}/c{m}-s{s}" in conf]
            vals = []
            for run in runs:
                tot: dict[str, int] = defaultdict(int)
                for d in picks:
                    for k, n in run["conf"].get(d, {}).items():
                        tot[k] += n
                vals.append(l12c_gnn.macro_f1(dict(tot)))
            n_tr = sum(r["n_train"] for r in runs) / len(runs) if actual else m * 12
            xs.append(math.log2(n_tr))
            ys.append(sum(vals) / len(vals))
        return decide.ols_slope(xs, ys)

    rnd = random.Random(4)
    boots = sorted(slope([rnd.choice(des) for _ in des]) for _ in range(b))
    lo = boots[max(0, math.ceil(0.025 * b) - 1)]
    hi = boots[math.ceil(0.975 * b) - 1]
    return slope(des), lo, hi


def mean_train(conf: dict[str, Any], floor: str, m: int) -> float:
    """Mean actual number of train designs over the seeds of the size ``m`` per family."""
    return float(sum(conf[f"{floor}/c{m}-s{s}"]["n_train"] for s in l12c_gnn.SEEDS)) / 3


def run_gnn() -> int:
    conf = json.loads((l12c_gnn.GNN / "conf.json").read_text(encoding="utf-8"))
    rows: list[list[Any]] = []
    sets: list[list[Any]] = []
    for fl in r4lib.FLOORS:
        ref = conf[f"{fl}/c70-s0"]
        for which in l12c_gnn.SETNAMES:
            des = sorted(d for d, w in ref["which"].items() if w == which)
            sets.append([fl, which, len(des), "|".join(
                f"{m}:{mean_train(conf, fl, m):.1f}" for m in l12c_gnn.PER_FAMILY)])
            if fl == "f2" and which == "vetest":
                for actual in (False, True):
                    for b in (2000, 20000):
                        s, lo, hi = boot_ci(conf, fl, des, b, actual)
                        rows.append([fl, which, "actual" if actual else "nominal", b, len(des),
                                     round(s, 6), round(lo, 6), round(hi, 6)])
    r4lib.write_csv(r4lib.OUT / "x12_gnn.csv",
                    ["floor", "set", "x_axis", "B", "n_designs", "slope", "ci_lo", "ci_hi"], rows)
    r4lib.write_csv(r4lib.OUT / "x12_ntrain.csv",
                    ["floor", "set", "n_designs_with_logic", "mean_n_train_by_per_family"], sets)
    return 0


def run_sets() -> int:
    """Designs per set before and after the has-logic filter (item 9)."""
    out: list[list[Any]] = []
    for fl in r4lib.FLOORS:
        for name, items in r4lib.eval_sets(fl).items():
            kept = sum(1 for ds, d in items if l12c_gnn.has_logic(ds, d, fl))
            out.append([fl, name, len(items), kept])
        tr = [d for d in r4lib.ok_designs(r4lib.CORPUS, fl)
              if r4lib.corpus_split()[d][1] == "train"]
        out.append([fl, "corpus_train", len(tr),
                    sum(1 for d in tr if l12c_gnn.has_logic(r4lib.CORPUS, d, fl))])
        ve = r4lib.ok_designs(r4lib.VEVAL, fl, "train")
        out.append([fl, "ve_train", len(ve),
                    sum(1 for d in ve if l12c_gnn.has_logic(r4lib.VEVAL, d, fl))])
    r4lib.write_csv(r4lib.OUT / "x12_filter.csv", ["floor", "set", "designs", "with_logic"], out)
    return 0


def main() -> int:
    which = sys.argv[1] if len(sys.argv) > 1 else ""
    if which == "dup":
        return run_dup()
    if which == "gnn":
        return run_gnn()
    if which == "sets":
        return run_sets()
    raise SystemExit(__doc__)


if __name__ == "__main__":
    raise SystemExit(main())
