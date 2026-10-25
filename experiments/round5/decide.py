"""Decisions H16a to H16f (rules: EXPERIMENT.md). Reads the ``l16_*.csv`` files; writes
``r5_status.csv`` (hypothesis, status) and ``r5_numbers.csv`` (hypothesis, key, value), plus the
pooled per-kind table ``l16_summary.csv``. Deterministic.
"""

from __future__ import annotations

import random
from collections import defaultdict
from collections.abc import Callable, Sequence
from typing import Any

import r5lib
from scipy import stats

OUT = r5lib.OUT
ARMS = ("R2N", "R2C", "W", "WB")
E_REAL = ("MI", "VT")
E_ALL = ("MI", "VT", "CI", "CO")
DATAPATH = ("register", "mux", "mux_tree", "adder", "subtractor", "comparator", "counter")
CONTROL = ("eq_const", "fsm")
B = 2000


def load(name: str) -> list[dict[str, str]]:
    return r5lib.read_csv(OUT / name)


def kinds_table() -> dict[tuple[str, str, str, str, str], tuple[int, int, int]]:
    """(arm, set, floor, design, kind) -> (counted, matched, gt)."""
    return {(r["arm"], r["set"], r["floor"], r["design"], r["kind"]):
            (int(r["counted"]), int(r["matched"]), int(r["gt"])) for r in load("l16_kinds.csv")}


def avail() -> dict[tuple[str, str, str], set[str]]:
    out: dict[tuple[str, str, str], set[str]] = defaultdict(set)
    for r in load("l16_designs.csv"):
        out[(r["arm"], r["set"], r["floor"])].add(r["design"])
    return out


def common(av: dict[tuple[str, str, str], set[str]], arms: Sequence[str], sets: Sequence[str],
           floor: str) -> list[tuple[str, str]]:
    out = []
    for s in sets:
        ds = set.intersection(*(av.get((a, s, floor), set()) for a in arms))
        out += [(s, d) for d in sorted(ds)]
    return out


def pooled(kt: dict[Any, Any], arm: str, floor: str, units: list[tuple[str, str]],
           kind: str) -> tuple[int, int, int]:
    c = m = g = 0
    for s, d in units:
        v = kt.get((arm, s, floor, d, kind))
        if v:
            c, m, g = c + v[0], m + v[1], g + v[2]
    return c, m, g


def f1(c: int, m: int, g: int) -> float:
    return 2 * m / (c + g) if c + g else 0.0


def prf(c: int, m: int, g: int) -> tuple[float, float, float]:
    return (m / c if c else 0.0, m / g if g else 0.0, f1(c, m, g))


def wilcoxon(diffs: list[float]) -> tuple[float, int]:
    nz = [d for d in diffs if d != 0]
    if len(nz) < 8:
        return 1.0, len(nz)
    return float(stats.wilcoxon(nz, alternative="greater").pvalue), len(nz)


def boot(units: list[Any], fn: Callable[[list[Any]], float]) -> tuple[float, float]:
    rng = random.Random(5)
    vals = sorted(fn([units[rng.randrange(len(units))] for _ in units]) for _ in range(B))
    import math
    return vals[max(0, math.ceil(0.025 * B) - 1)], vals[math.ceil(0.975 * B) - 1]


class Book:
    def __init__(self) -> None:
        self.status: list[list[Any]] = []
        self.numbers: list[list[Any]] = []

    def put(self, h: str, key: str, val: Any) -> None:
        self.numbers.append([h, key, r5lib.r6(val) if isinstance(val, float) else val])

    def decide(self, h: str, status: str, note: str) -> None:
        self.status.append([h, status, note])


def best_base(kt: dict[Any, Any], floor: str, units: list[tuple[str, str]], kind: str) -> str:
    fs = {a: f1(*pooled(kt, a, floor, units, kind)) for a in ("R2N", "R2C")}
    return "R2N" if fs["R2N"] >= fs["R2C"] else "R2C"


def kind_hyp(bk: Book, h: str, kt: dict[Any, Any], av: dict[Any, Any], kind: str,
             sets: Sequence[str], need_recall: bool) -> None:
    units = common(av, ("WB", "R2N", "R2C"), sets, "f2")
    base = best_base(kt, "f2", units, kind)
    pw = prf(*pooled(kt, "WB", "f2", units, kind))
    pb = prf(*pooled(kt, base, "f2", units, kind))
    bk.put(h, "n_designs", len(units))
    bk.put(h, "baseline_arm", base)
    for tag, v in (("WB", pw), ("base", pb)):
        for i, nm in enumerate(("precision", "recall", "f1")):
            bk.put(h, f"{nm}_{tag}", v[i])
    pw_w = prf(*pooled(kt, "W", "f2", units, kind))
    bk.put(h, "f1_W", pw_w[2])
    diffs = []
    for s, d in units:
        gw = kt.get(("WB", s, "f2", d, kind))
        gb = kt.get((base, s, "f2", d, kind))
        if gw and gw[2] > 0:
            fw = f1(*gw)
            fb = f1(*gb) if gb else 0.0
            diffs.append(fw - fb)
    p, nnz = wilcoxon(diffs)
    bk.put(h, "wilcoxon_p", p)
    bk.put(h, "designs_with_gt", len(diffs))
    bk.put(h, "nonzero_diffs", nnz)
    dr, df = pw[1] - pb[1], pw[2] - pb[2]
    bk.put(h, "delta_recall", dr)
    bk.put(h, "delta_f1", df)
    if need_recall:
        sup = dr >= 0.20 and df >= 0.10 and p < 0.05
        notsup = dr < 0.05
    else:
        sup = df >= 0.10 and p < 0.05
        notsup = df < 0.03
    bk.decide(h, "supported" if sup else "not supported" if notsup else "inconclusive",
              f"dR {dr:.3f} dF1 {df:.3f} p {p:.4f} n {len(diffs)}")


def tiling_hyp(bk: Book, av: dict[Any, Any]) -> None:
    rows = load("l16_tiling.csv")
    q: dict[tuple[str, str, str], list[float]] = defaultdict(lambda: [0.0, 0.0])
    for r in rows:
        v = q[(r["arm"], r["set"], r["design"])]
        v[0] += float(r["instances"])
        v[1] += float(r["covered"])

    def pool(arm: str, sets: Sequence[str]) -> float:
        n = sum(v[0] for k, v in q.items() if k[0] == arm and k[1] in sets)
        c = sum(v[1] for k, v in q.items() if k[0] == arm and k[1] in sets)
        return c / n if n else 0.0

    for arm in ("R2N", "R2C", "W", "WB", "null-W", "null-WB"):
        for s in E_ALL:
            bk.put("H16a", f"q_{arm}_{s}", pool(arm, (s,)))
    units = [d for s, d in common(av, ("WB", "R2N", "R2C"), ("VT",), "f2")]
    base = max(("R2N", "R2C"), key=lambda a: sum(
        v[1] for k, v in q.items() if k[0] == a and k[1] == "VT" and k[2] in units))
    n = sum(q[("WB", "VT", d)][0] for d in units if ("WB", "VT", d) in q)
    cw = sum(q[("WB", "VT", d)][1] for d in units if ("WB", "VT", d) in q)
    cb = sum(q[(base, "VT", d)][1] for d in units if (base, "VT", d) in q)
    cn = sum(q[("null-WB", "VT", d)][1] for d in units if ("null-WB", "VT", d) in q)
    qw, qb, qn = cw / n if n else 0.0, cb / n if n else 0.0, cn / n if n else 0.0
    diffs = []
    for d in units:
        if ("WB", "VT", d) in q and q[("WB", "VT", d)][0] > 0:
            a, b = q[("WB", "VT", d)], q.get((base, "VT", d), [1.0, 0.0])
            diffs.append(a[1] / a[0] - (b[1] / b[0] if b[0] else 0.0))
    p, nnz = wilcoxon(diffs)
    dq = qw - qb
    pairs = [(q[("WB", "VT", d)], q.get((base, "VT", d), [1.0, 0.0])) for d in units
             if ("WB", "VT", d) in q]
    lo, hi = boot(pairs, lambda ps: (sum(a[1] for a, _ in ps) - sum(b[1] for _, b in ps))
                  / max(1.0, sum(a[0] for a, _ in ps)))
    for k, v in (("n_instances", n), ("q_WB", qw), ("q_base", qb), ("q_null", qn), ("delta_q", dq),
                 ("delta_q_lo", lo), ("delta_q_hi", hi), ("wilcoxon_p", p),
                 ("designs", len(diffs)), ("nonzero", nnz), ("baseline_arm", base)):
        bk.put("H16a", k, v)
    sup = dq >= 0.15 and qw - qn >= 0.10 and p < 0.05
    bk.decide("H16a", "supported" if sup else "not supported" if dq < 0.05 else "inconclusive",
              f"dq {dq:.3f} q_WB {qw:.3f} q_base {qb:.3f} q_null {qn:.3f} p {p:.4f}")


def chain_hyp(bk: Book) -> None:
    rows = [r for r in load("l16_chain.csv") if not r["item"].startswith("fsm_")]
    comp: dict[tuple[str, str, str, str], int] = {
        (r["arm"], r["set"], r["design"], r["item"]): int(r["complete"]) for r in rows}
    items = sorted({k[1:] for k in comp if k[0] == "WB"} & {k[1:] for k in comp if k[0] == "R2N"})
    cw = sum(comp[("WB", *i)] for i in items)
    cb = sum(comp[("R2N", *i)] for i in items)
    b = sum(1 for i in items if comp[("WB", *i)] and not comp[("R2N", *i)])
    c = sum(1 for i in items if comp[("R2N", *i)] and not comp[("WB", *i)])
    p = float(stats.binomtest(b, b + c, 0.5, alternative="greater").pvalue) if b + c else 1.0
    for arm in ARMS:
        n = sum(1 for k in comp if k[0] == arm)
        bk.put("H16d", f"chains_{arm}", n)
        bk.put("H16d", f"complete_{arm}", sum(v for k, v in comp.items() if k[0] == arm))
    fsm = [r for r in load("l16_chain.csv") if r["item"].startswith("fsm_")]
    for arm in ARMS:
        bk.put("H16d", f"fsm_hit_{arm}", sum(int(r["complete"]) for r in fsm if r["arm"] == arm))
        bk.put("H16d", f"fsm_gt_{arm}", sum(1 for r in fsm if r["arm"] == arm))
    for k, v in (("paired_chains", len(items)), ("complete_WB", cw), ("complete_R2N", cb),
                 ("WB_only", b), ("R2N_only", c), ("sign_p", p)):
        bk.put("H16d", k, v)
    gain = cw - cb
    if b + c < 8:
        st = "not supported" if gain <= 1 else "inconclusive"
    else:
        st = ("supported" if gain >= 5 and p < 0.05
              else "not supported" if gain <= 1 else "inconclusive")
    bk.decide("H16d", st, f"gain {gain} WB {cw} R2N {cb} discordant {b}/{c} p {p:.4f}")


def seed_hyp(bk: Book) -> None:
    rows = load("l16_seed.csv")
    acc: dict[tuple[str, str], list[float]] = defaultdict(lambda: [0.0, 0.0])
    for r in rows:
        if r["set"] in E_REAL:
            kind = "datapath" if r["kind"] in DATAPATH else "control"
            v = acc[(r["arm"], kind)]
            v[0] += float(r["constructs"])
            v[1] += float(r["seeded"])
            w = acc[(r["arm"], r["kind"])]
            w[0] += float(r["constructs"])
            w[1] += float(r["seeded"])

    def share(arm: str, kind: str) -> float:
        n, s = acc.get((arm, kind), [0.0, 0.0])
        return s / n if n else 0.0

    for arm in ("R2N", "R2C", "W", "WB", "null-W", "null-WB"):
        for kind in ("datapath", "control", *DATAPATH, *CONTROL):
            if (arm, kind) in acc:
                bk.put("H16e", f"{kind}_{arm}", share(arm, kind))
    d, dn = share("W", "datapath"), share("null-W", "datapath")
    bk.put("H16e", "D", d)
    bk.put("H16e", "D_null", dn)
    bk.put("H16e", "constructs_datapath", acc[("W", "datapath")][0])
    st = ("supported" if d >= 0.50 and d - dn >= 0.25
          else "not supported" if d < 0.25 or d - dn < 0.10 else "inconclusive")
    bk.decide("H16e", st, f"D {d:.3f} null {dn:.3f} gap {d - dn:.3f}")


def big_hyp(bk: Book) -> None:
    rows = load("l16_big.csv")
    designs = {r["design"] for r in rows}
    bk.put("H16f", "designs_finished", len(designs))
    if len(designs) < 3:
        bk.decide("H16f", "inconclusive", f"only {len(designs)} designs finished")
        return
    gt = sum(int(r["gt"]) for r in rows)
    c, m = sum(int(r["counted"]) for r in rows), sum(int(r["matched"]) for r in rows)
    cf, mf = sum(int(r["counted_F"]) for r in rows), sum(int(r["matched_F"]) for r in rows)
    fa, ff = f1(c, m, gt), f1(cf, mf, gt)
    nulls = [float(r["f1"]) for r in load("l16_big_null.csv")]
    share = sum(1 for x in nulls if x >= ff) / len(nulls)
    for k, v in (("counted", c), ("matched", m), ("gt", gt), ("counted_F", cf), ("matched_F", mf),
                 ("f1_all", fa), ("f1_F", ff), ("delta", ff - fa), ("null_share_ge", share),
                 ("null_mean", sum(nulls) / len(nulls))):
        bk.put("H16f", k, v)
    st = ("supported" if ff - fa >= 0.05 and share <= 0.05
          else "not supported" if ff - fa < 0.01 or share > 0.20 else "inconclusive")
    bk.decide("H16f", st, f"dF1 {ff - fa:.4f} null share {share:.3f}")


def summary(kt: dict[Any, Any]) -> None:
    acc: dict[tuple[str, str, str, str], list[int]] = defaultdict(lambda: [0, 0, 0, 0])
    for (arm, s, fl, _d, kind), (c, m, g) in kt.items():
        v = acc[(fl, s, arm, kind)]
        v[0] += c
        v[1] += m
        v[2] += g
    rows = []
    for (fl, s, arm, kind), (c, m, g, _) in sorted(acc.items()):
        p, r, f = prf(c, m, g)
        rows.append([fl, s, arm, kind, c, m, g, r5lib.r6(p), r5lib.r6(r), r5lib.r6(f)])
    r5lib.write_csv(OUT / "l16_summary.csv", ["floor", "set", "arm", "kind", "counted", "matched",
                                              "gt", "precision", "recall", "f1"], rows)


def main() -> int:
    kt, av = kinds_table(), avail()
    bk = Book()
    tiling_hyp(bk, av)
    kind_hyp(bk, "H16b", kt, av, "ff_en", E_ALL, True)
    kind_hyp(bk, "H16c", kt, av, "eq_const", E_REAL, False)
    chain_hyp(bk)
    seed_hyp(bk)
    big_hyp(bk)
    summary(kt)
    r5lib.write_csv(OUT / "r5_status.csv", ["hypothesis", "status", "numbers"],
                    sorted(bk.status))
    r5lib.write_csv(OUT / "r5_numbers.csv", ["hypothesis", "key", "value"], bk.numbers)
    for row in sorted(bk.status):
        print(*row)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
