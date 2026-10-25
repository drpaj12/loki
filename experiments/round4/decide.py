"""Decisions of round 4: applies the numeric rules of EXPERIMENT.md to the result CSVs.

Reads the CSVs written by the stage scripts, writes ``r4_status.csv`` (one row per hypothesis and
variant: status plus the deciding numbers), ``l12b_kinds.csv``, ``l12b_h12b2.csv`` and
``l12c_slope.csv``. Every threshold is a constant below, copied from the Stage-0 text.
"""

from __future__ import annotations

import json
import math
import random
from collections import defaultdict
from pathlib import Path
from typing import Any

import l12c_gnn
import r4lib
from scipy import stats

ELIGIBLE = ("adder", "subtractor", "comparator", "eq_const", "mux", "register", "ff_srst")
VARIANTS = ("V0", "V1", "V2")
MARGIN, ALPHA, MIN_PAIRED = 0.05, 0.05, 8
Row = tuple[int, int, int]  # counted, matched, gt


def status(supported: bool, not_supported: bool) -> str:
    if supported:
        return "supported"
    return "not supported" if not_supported else "inconclusive"


def f1_of(c: int, m: int, g: int) -> float:
    return 2 * m / (c + g) if c + g else 0.0


def load_rows(path: Path) -> dict[tuple[str, str, str, str], dict[str, Row]]:
    """(arm, floor, set, design) -> kind -> (counted, matched, gt)."""
    out: dict[tuple[str, str, str, str], dict[str, Row]] = defaultdict(dict)
    for r in r4lib.read_csv(path):
        out[(r["arm"], r["floor"], r["set"], r["design"])][r["kind"]] = (
            int(r["counted"]), int(r["matched"]), int(r["gt"]))
    return out


def pooled(rows: list[Row]) -> Row:
    return (sum(r[0] for r in rows), sum(r[1] for r in rows), sum(r[2] for r in rows))


# -- H12a --------------------------------------------------------------------------------------
def h12a() -> list[list[Any]]:
    rep = r4lib.read_csv(r4lib.OUT / "corpus_report.csv")
    gen = sum(int(r["generated"]) for r in rep)
    ok = sum(int(r["all_floors_ok"]) for r in rep)

    def share(split: str) -> float:
        g = sum(int(r["generated"]) for r in rep if r["split"] == split)
        o = sum(int(r["all_floors_ok"]) for r in rep if r["split"] == split)
        return o / g if g else 0.0

    fam: dict[str, int] = defaultdict(int)
    for r in rep:
        fam[r["family"]] += int(r["all_floors_ok"])
    p_ok = ok / gen
    sup = p_ok >= 0.95 and min(fam.values()) >= 60 and share("ood") >= share("train") - 0.05
    nsup = p_ok < 0.80 or min(fam.values()) < 30
    return [["H12a", "-", status(sup, nsup), f"P_ok={p_ok:.4f} generated={gen} ok={ok} "
             f"min_family_ok={min(fam.values())} ood={share('ood'):.4f} train={share('train'):.4f}"]]


# -- H12b / H12b2 ------------------------------------------------------------------------------
def det_designs() -> dict[tuple[str, str, str], set[str]]:
    out: dict[tuple[str, str, str], set[str]] = defaultdict(set)
    for r in r4lib.read_csv(r4lib.OUT / "l12b_det_designs.csv"):
        out[(r["arm"], r["floor"], r["set"])].add(r["design"])
    return out


def kind_table(floor: str, var: str, sets: tuple[str, ...]
               ) -> tuple[list[list[Any]], int]:
    dic = load_rows(r4lib.OUT / "l12b_dict_rows.csv")
    det = load_rows(r4lib.OUT / "l12b_det_rows.csv")
    have = det_designs()
    designs = [(s, d) for s in sets for d in sorted(
        have[("det-N", floor, s)] & have[("det-C", floor, s)])]
    rows: list[list[Any]] = []
    wins = 0
    for k in ELIGIBLE + ("ff_en", "counter", "fsm", "mux_tree"):
        per: dict[str, list[Row]] = {"dict": [], "det-N": [], "det-C": []}
        gts: list[tuple[str, str]] = []
        for s, d in designs:
            for arm, store, key in (("dict", dic, f"dict-{var}"), ("det-N", det, "det-N"),
                                    ("det-C", det, "det-C")):
                per[arm].append(store.get((key, floor, s, d), {}).get(k, (0, 0, 0)))
            if per["dict"][-1][2] > 0:
                gts.append((s, d))
        fd = f1_of(*pooled(per["dict"]))
        fn_, fc = f1_of(*pooled(per["det-N"])), f1_of(*pooled(per["det-C"]))
        best = "det-N" if fn_ >= fc else "det-C"
        fb = max(fn_, fc)
        idx = [i for i, r in enumerate(per["dict"]) if r[2] > 0]
        diffs = [f1_of(*per["dict"][i]) - f1_of(*per[best][i]) for i in idx]
        p = float("nan")
        if len(idx) >= MIN_PAIRED and any(x != 0 for x in diffs):
            p = float(stats.wilcoxon(diffs, zero_method="wilcox", alternative="greater").pvalue)
        won = (k in ELIGIBLE and len(idx) >= MIN_PAIRED and fd >= fb + MARGIN
               and not math.isnan(p) and p < ALPHA)
        wins += int(won)
        c, m, g = pooled(per["dict"])
        rows.append([floor, var, k, "eligible" if k in ELIGIBLE else "report", len(designs),
                     len(idx), c, m, g, round(fd, 6), best, round(fb, 6), round(fn_, 6),
                     round(fc, 6), "" if math.isnan(p) else round(p, 6), int(won)])
    return rows, wins


KIND_HEAD = ["floor", "variant", "kind", "role", "designs", "designs_with_gt", "dict_counted",
             "dict_matched", "gt", "f1_dict", "best_det", "f1_det", "f1_det_N", "f1_det_C",
             "wilcoxon_p", "won"]


def h12b() -> tuple[list[list[Any]], list[list[Any]]]:
    status_rows: list[list[Any]] = []
    detail: list[list[Any]] = []
    for floor in r4lib.FLOORS:
        for var in VARIANTS:
            rows, wins = kind_table(floor, var, ("micro", "vetest"))
            detail += rows
            n_el = len(ELIGIBLE)
            st = status(wins >= 4, wins <= 1)
            tag = "H12b" if floor == "f2" else "H12b-f3(report)"
            status_rows.append([tag, f"{var}", st if floor == "f2" else f"{st} (report only)",
                                f"won={wins}/{n_el} floor={floor}"])
    return status_rows, detail


def h12b2() -> tuple[list[list[Any]], list[list[Any]]]:
    dic = load_rows(r4lib.OUT / "l12b_dict_rows.csv")
    out: list[list[Any]] = []
    detail: list[list[Any]] = []
    for var in VARIANTS:
        f: dict[str, float] = {}
        for s in ("iid", "ood"):
            rows = [v for (arm, fl, ss, _), kinds in dic.items()
                    if arm == f"dict-{var}" and fl == "f2" and ss == s for v in kinds.values()]
            c, m, g = pooled(rows)
            f[s] = f1_of(c, m, g)
            detail.append([var, s, c, m, g, round(f[s], 6)])
        ratio = f["ood"] / f["iid"] if f["iid"] > 0 else float("nan")
        dep_ok = f["iid"] >= 0.20
        st = "inconclusive" if not dep_ok else status(ratio >= 0.80, ratio < 0.50)
        out.append(["H12b2", var, st, f"R={ratio:.4f} iid={f['iid']:.4f} ood={f['ood']:.4f}"
                    + ("" if dep_ok else " (iid < 0.20: ratio uninformative)")])
    return out, detail


# -- H12c --------------------------------------------------------------------------------------
def ols_slope(xs: list[float], ys: list[float]) -> float:
    mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
    den = sum((x - mx) ** 2 for x in xs)
    return sum((x - mx) * (y - my) for x, y in zip(xs, ys, strict=True)) / den if den else 0.0


def curve_slope(conf: dict[str, Any], floor: str, which: str, picks: list[str]) -> float:
    """Slope of mean-over-seeds macro-F1 on log2 n for the designs ``picks`` (with repeats)."""
    xs: list[float] = []
    ys: list[float] = []
    for m in l12c_gnn.PER_FAMILY:
        vals = []
        for s in l12c_gnn.SEEDS:
            run = conf.get(f"{floor}/c{m}-s{s}")
            if run is None:
                continue
            tot: dict[str, int] = defaultdict(int)
            for d in picks:
                for k, n in run["conf"].get(d, {}).items():
                    tot[k] += n
            vals.append(l12c_gnn.macro_f1(dict(tot)))
        if vals:
            xs.append(math.log2(m * 12))
            ys.append(sum(vals) / len(vals))
    return ols_slope(xs, ys) if len(xs) >= 2 else float("nan")


def h12c() -> tuple[list[list[Any]], list[list[Any]]]:
    conf = json.loads((l12c_gnn.GNN / "conf.json").read_text(encoding="utf-8"))
    out: list[list[Any]] = []
    detail: list[list[Any]] = []
    for floor in r4lib.FLOORS:
        ref = conf.get(f"{floor}/c70-s0")
        if ref is None:
            continue
        for which in l12c_gnn.SETNAMES:
            des = sorted(d for d, w in ref["which"].items() if w == which)
            b = curve_slope(conf, floor, which, des)
            rnd = random.Random(4)
            boots = sorted(curve_slope(conf, floor, which, [rnd.choice(des) for _ in des])
                           for _ in range(2000))
            lo, hi = boots[int(0.025 * len(boots))], boots[int(0.975 * len(boots)) - 1]
            detail.append([floor, which, len(des), round(b, 6), round(lo, 6), round(hi, 6)])
            if floor == "f2" and which == "vetest":
                st = status(b >= 0.020 and lo > 0, hi < 0.010)
                out.append(["H12c", "-", st,
                            f"slope={b:.4f}/doubling CI=[{lo:.4f},{hi:.4f}] n_designs={len(des)}"])
    return out, detail


# -- H13 ---------------------------------------------------------------------------------------
def share_rep(rows: list[dict[str, str]]) -> tuple[float, int, int]:
    e = sum(int(r["eligible_words"]) for r in rows)
    n = sum(int(r["repeated_words"]) for r in rows)
    return (n / e if e else 0.0), n, e


def h13() -> list[list[Any]]:
    big = [r for r in r4lib.read_csv(r4lib.OUT / "l13_big.csv") if r["floor"] == "f3"]
    small = [r for r in r4lib.read_csv(r4lib.OUT / "l13_small.csv") if r["floor"] == "f3"]
    groups = r4lib.read_csv(r4lib.OUT / "l13_groups.csv")
    sb, nb, eb = share_rep(big)
    ss, ns, es = share_rep(small)
    enough = len(big) >= 3
    st_a = status(sb >= 0.50, sb < 0.25) if enough else "inconclusive"
    st_b = status(sb - ss >= 0.15, sb - ss <= 0.05) if enough else "inconclusive"
    out = [
        ["H13a", "-", st_a, f"share_rep(big)={sb:.4f} ({nb}/{eb}) designs={len(big)}"],
        ["H13b", "-", st_b, f"big={sb:.4f} small={ss:.4f} ({ns}/{es}) diff={sb - ss:.4f}"],
    ]
    if groups:
        same = sum(int(g["same_signature"]) for g in groups) / len(groups)
        out.append(["H13c", "-", status(same >= 0.70, same < 0.40),
                    f"same_signature={same:.4f} groups={len(groups)}"])
    else:
        out.append(["H13c", "-", "inconclusive", "no repeat groups"])
    return out


# -- H14 ---------------------------------------------------------------------------------------
def h14ab() -> list[list[Any]]:
    rows = {(r["family"], r["floor"]): r for r in r4lib.read_csv(r4lib.OUT / "l14_ident.csv")}
    c3 = float(rows[("*", "f3")]["ceiling_wl"])
    c2 = float(rows[("*", "f2")]["ceiling_wl"])
    c1 = float(rows[("*", "f1-k6")]["ceiling_wl"])
    return [
        ["H14a", "f3", status(c3 <= 0.60, c3 >= 0.85), f"ceiling_f3={c3:.4f} f2={c2:.4f} f1={c1:.4f}"],
        ["H14b", "-", status(c3 - c2 >= 0.05, c3 - c2 <= 0.0), f"f3-f2={c3 - c2:.4f}"],
    ]


def h14cd() -> list[list[Any]]:
    rows = r4lib.read_csv(r4lib.OUT / "l14_mdl.csv")
    out: list[list[Any]] = []
    shares: dict[str, float] = {}
    for var in ("l0-f2", "l0-f3", "f2-none", "f3-none", "f2-calib", "f3-calib"):
        rr = [r for r in rows if r["variant"] == var]
        shares[var] = sum(1 for r in rr if float(r["ratio"]) > 1.0) / len(rr)
    sup = all(v >= 0.90 for v in shares.values())
    nsup = sum(1 for v in shares.values() if v < 0.70) >= 3
    out.append(["H14c", "-", status(sup, nsup),
                " ".join(f"{k}={v:.3f}" for k, v in shares.items())])
    pairs = [(math.log(float(r["ratio"])), float(r["ast"]), math.log(max(1, int(r["tokens"]))),
              float(r["cfg"]) if r["cfg"] else float("nan"))
             for r in rows if r["variant"] in ("f2-none", "f3-none", "f2-calib", "f3-calib")
             and r["ast"] != ""]
    x = [p[0] for p in pairs]
    y = [p[1] for p in pairs]
    z = [p[2] for p in pairs]
    rho = stats.spearmanr(x, y)
    rx = stats.rankdata(x)
    ry = stats.rankdata(y)
    rz = stats.rankdata(z)

    def resid(a: Any, b: Any) -> Any:
        slope = ols_slope(list(b), list(a))
        mb, ma = sum(b) / len(b), sum(a) / len(a)
        return [ai - (ma + slope * (bi - mb)) for ai, bi in zip(a, b, strict=True)]

    part = stats.spearmanr(resid(rx, rz), resid(ry, rz))
    r_, p_ = float(rho.statistic), float(rho.pvalue)
    pr, pp = float(part.statistic), float(part.pvalue)
    sup2 = r_ <= -0.30 and pr <= -0.15 and pp < 0.05
    out.append(["H14d", "-", status(sup2, r_ > -0.15),
                f"rho={r_:.4f} (p={p_:.2g}) partial={pr:.4f} (p={pp:.2g}) n={len(pairs)}"])
    return out


def main() -> int:
    rows: list[list[Any]] = []
    rows += h12a()
    s, kinds = h12b()
    rows += s
    r2s, r2d = h12b2()
    rows += r2s
    r4lib.write_csv(r4lib.OUT / "l12b_kinds.csv", KIND_HEAD, kinds)
    r4lib.write_csv(r4lib.OUT / "l12b_h12b2.csv",
                    ["variant", "set", "counted", "matched", "gt", "micro_f1"], r2d)
    cs, cd = h12c()
    rows += cs
    r4lib.write_csv(r4lib.OUT / "l12c_slope.csv",
                    ["floor", "set", "n_designs", "slope_per_doubling", "ci_lo", "ci_hi"], cd)
    for fn in (h13, h14ab, h14cd):
        try:
            rows += fn()
        except FileNotFoundError:
            continue
    r4lib.write_csv(r4lib.OUT / "r4_status.csv", ["id", "variant", "status", "numbers"], rows)
    for r in rows:
        print(r)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
