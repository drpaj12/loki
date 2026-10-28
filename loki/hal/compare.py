"""Statistics and report of the Loki vs HAL/DANA comparison (``docs/plan/hal-compare-prereg.md``).

Input: the per-design count files of ``experiments/hal/run_hal.py score`` (``scores-hal<N>.csv``).
Output: the decision of the pre-registered rule (original text + Amendment 1, A2 and A3), the
headline tables and the generated files for the results document and the paper. Every number
printed comes from these counts; nothing is typed by hand.

    python -m loki.hal.compare DATA --md results.md --tex hal-tables.tex

Needs scipy (the pinned Wilcoxon call); the other parts are standard library.
"""

from __future__ import annotations

import argparse
import csv
import importlib
import json
import random
import re
import statistics
import sys
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from loki.hal.wordscore import WordScore

SEED = 20261026
RESAMPLES = 10000
MARGIN = 0.05
ALPHA = 0.05
MIN_NONZERO = 8
STOP_SHARE = 0.2
INT_FIELDS = ("n_pred", "n_gt", "exact_pred", "exact_gt", "matched", "pur_num", "pur_den",
              "comp_num", "comp_den", "cov_num", "cov_den")


@dataclass(frozen=True)
class Run:
    tool: str
    set: str
    floor: str
    design: str
    score: WordScore
    r5: tuple[int, int, int]  # counted, matched, gt under the round-5 scorer (Loki rows)


def load_scores(path: Path) -> list[Run]:
    out: list[Run] = []
    with path.open(encoding="utf-8", newline="") as fh:
        for r in csv.DictReader(fh):
            ws = WordScore(**{f: int(r[f]) for f in INT_FIELDS})
            out.append(Run(r["tool"], r["set"], r["floor"], r["design"], ws,
                           (int(r["r5_counted"]), int(r["r5_matched"]), int(r["r5_gt"]))))
    return out


def cluster_of(set_name: str, design: str) -> str:
    """A2: one VT design is a cluster; an MI family is the first two ``_`` tokens of the name
    after ``micro_``, digits removed, lower case."""
    if set_name != "MI":
        return f"{set_name}:{design}"
    body = design.removeprefix("micro_")
    toks = [re.sub(r"\d+", "", t) for t in body.split("_")[:2]]
    return "MI:" + "_".join(t for t in toks if t).lower()


def f1(matched: float, n_pred: float, n_gt: float) -> float:
    den = n_pred + n_gt
    return 2 * matched / den if den else 0.0


@dataclass(frozen=True)
class Pair:
    """One design in both arms: (matched, predicted) of HAL, Loki, Loki round-5; GT counts.

    ``g`` is the GT word count of the comparison scorer (HAL and Loki alike); ``g5`` is the
    round-5 GT word count (full footprints). The round-5 D therefore sets Loki's round-5 F1
    (counted, matched, ``g5``) against HAL's comparison F1 (``h``, ``g``): the HAL counts are
    never rescored with the round-5 scorer (Amendment 1 A1)."""

    cluster: str
    design: str
    h: tuple[int, int]
    k: tuple[int, int]
    k5: tuple[int, int]
    g: int
    g5: int

    def f1_h(self) -> float:
        return f1(self.h[0], self.h[1], self.g)

    def f1_k(self) -> float:
        return f1(self.k[0], self.k[1], self.g)

    def f1_k5(self) -> float:
        return f1(self.k5[0], self.k5[1], self.g5)


def make_pairs(runs: Sequence[Run], hal: str, floor: str, sets: Sequence[str]) -> list[Pair]:
    by: dict[tuple[str, str, str], Run] = {(r.tool, r.set, r.design): r for r in runs
                                           if r.floor == floor}
    out = []
    for (tool, s, d), h in sorted(by.items()):
        k = by.get(("lokiW", s, d))
        if tool != hal or s not in sets or k is None:
            continue
        out.append(Pair(cluster_of(s, d), d, (h.score.matched, h.score.n_pred),
                        (k.score.matched, k.score.n_pred), (k.r5[1], k.r5[0]), h.score.n_gt,
                        k.r5[2]))
    return out


def pooled_d(pairs: Sequence[Pair]) -> tuple[float, float, float, float]:
    """(F1_J Loki, F1_J HAL, D, D under Loki's round-5 counts)."""
    g = sum(p.g for p in pairs)
    g5 = sum(p.g5 for p in pairs)
    fh = f1(sum(p.h[0] for p in pairs), sum(p.h[1] for p in pairs), g)
    fk = f1(sum(p.k[0] for p in pairs), sum(p.k[1] for p in pairs), g)
    fk5 = f1(sum(p.k5[0] for p in pairs), sum(p.k5[1] for p in pairs), g5)
    return fk, fh, fk - fh, fk5 - fh


def bootstrap(pairs: Sequence[Pair], seed: int = SEED, n: int = RESAMPLES) -> list[list[float]]:
    """Cluster bootstrap of D and D5; returns the two sorted lists of ``n`` resampled values."""
    groups: dict[str, list[Pair]] = defaultdict(list)
    for p in pairs:
        groups[p.cluster].append(p)
    names = sorted(groups)
    sums = {c: _sums(groups[c]) for c in names}
    rng = random.Random(seed)
    d, d5 = [], []
    for _ in range(n):
        tot = [0] * 8
        for c in rng.choices(names, k=len(names)):
            tot = [a + b for a, b in zip(tot, sums[c], strict=True)]
        hm, hp, km, kp, k5m, k5p, g, g5 = tot
        fh = f1(hm, hp, g)
        d.append(f1(km, kp, g) - fh)
        d5.append(f1(k5m, k5p, g5) - fh)
    return [sorted(d), sorted(d5)]


def _sums(ps: Sequence[Pair]) -> list[int]:
    return [sum(p.h[0] for p in ps), sum(p.h[1] for p in ps), sum(p.k[0] for p in ps),
            sum(p.k[1] for p in ps), sum(p.k5[0] for p in ps), sum(p.k5[1] for p in ps),
            sum(p.g for p in ps), sum(p.g5 for p in ps)]


def interval(sorted_vals: Sequence[float], level: float) -> tuple[float, float]:
    """Percentile interval of the given level (0.95 means the 2.5th to the 97.5th percentile)."""
    n = len(sorted_vals)
    lo = int(n * (1 - level) / 2 + 1e-9)
    return sorted_vals[lo], sorted_vals[n - lo - 1]


def wilcoxon_p(x: Sequence[float], y: Sequence[float], alternative: str) -> float | None:
    """The pinned A2 call; None when every difference is zero (the test is undefined)."""
    stats = importlib.import_module("scipy.stats")
    try:
        res = stats.wilcoxon(list(x), list(y), zero_method="wilcox", alternative=alternative,
                             method="approx", correction=False)
    except ValueError:
        return None
    return float(res.pvalue)


def _verdict(arm: dict[str, object]) -> str:
    """The pre-registered rule (A2, A3) on the statistics of one scorer, without the A1 condition
    that ties the two scorers together."""
    d = float(str(arm["d"]))
    ci95, ci90 = arm["ci95"], arm["ci90"]
    assert isinstance(ci95, tuple) and isinstance(ci90, tuple)
    p_k, p_h = arm["p_loki_greater"], arm["p_hal_greater"]
    if int(str(arm["nonzero_pairs"])) < MIN_NONZERO:
        return "inconclusive"
    if d >= MARGIN and ci95[0] > MARGIN and p_k is not None and float(str(p_k)) < ALPHA:
        return "Loki ahead"
    if d <= -MARGIN and ci95[1] < -MARGIN and p_h is not None and float(str(p_h)) < ALPHA:
        return "HAL ahead"
    if ci90[0] > -MARGIN and ci90[1] < MARGIN:
        return "comparable"
    return "inconclusive"


def _arm_stats(d: float, boot: Sequence[float], xk: Sequence[float],
               xh: Sequence[float]) -> dict[str, object]:
    arm: dict[str, object] = {
        "d": d, "ci95": interval(boot, 0.95), "ci90": interval(boot, 0.90),
        "p_loki_greater": wilcoxon_p(xk, xh, "greater"),
        "p_hal_greater": wilcoxon_p(xh, xk, "greater"),
        "nonzero_pairs": sum(a != b for a, b in zip(xk, xh, strict=True))}
    arm["outcome"] = _verdict(arm)
    return arm


def _combine(cmp_: dict[str, object], r5: dict[str, object]) -> tuple[str, str]:
    """Outcome of the pre-registered rule with Amendment 1 A1: Loki ahead needs both scorers."""
    vc, v5 = str(cmp_["outcome"]), str(r5["outcome"])
    if int(str(cmp_["nonzero_pairs"])) < MIN_NONZERO:
        return "inconclusive", f"fewer than {MIN_NONZERO} non-zero paired differences"
    if vc == "Loki ahead":
        if v5 == "Loki ahead":
            return vc, ""
        return "inconclusive", ("Loki ahead under the comparison scorer only (A1 round-5 "
                                "condition fails)")
    if vc == "inconclusive" and abs(float(str(cmp_["d"]))) < MARGIN:
        return vc, "no difference shown"
    return vc, ""


def decide(pairs: Sequence[Pair]) -> dict[str, object]:
    """The pre-registered rule with Amendments A1 to A3 on the pairs of E_real at f2: D and its
    bootstrap are pooled over every design in both arms (predictions on a design with no GT word
    are false positives); the Wilcoxon runs on the designs with at least one GT word.

    ``scorers`` holds the statistics under each scorer alone (comparison scorer, and Loki's
    round-5 counts against HAL's unchanged counts) and the outcome of the rule on each; the
    top-level ``outcome`` is the pre-registered one (Loki ahead needs both)."""
    fk, fh, d, d5 = pooled_d(pairs)
    bd, bd5 = bootstrap(pairs)
    gtp = [p for p in pairs if p.g >= 1]
    xk, xh, xk5 = ([f(p) for p in gtp] for f in (Pair.f1_k, Pair.f1_h, Pair.f1_k5))
    cmp_ = _arm_stats(d, bd, xk, xh)
    r5 = _arm_stats(d5, bd5, xk5, xh)
    outcome, note = _combine(cmp_, r5)
    return {
        "outcome": outcome, "note": note, "designs": len(pairs), "designs_gt": len(gtp),
        "clusters": len({p.cluster for p in pairs}), "nonzero_pairs": cmp_["nonzero_pairs"],
        "f1_loki": fk, "f1_hal": fh, "d": d, "d_round5": d5,
        "ci95": cmp_["ci95"], "ci90": cmp_["ci90"], "ci95_round5": r5["ci95"],
        "ci90_round5": r5["ci90"],
        "p_loki_greater": cmp_["p_loki_greater"], "p_hal_greater": cmp_["p_hal_greater"],
        "p_loki_greater_round5": r5["p_loki_greater"],
        "scorers": {"comparison": cmp_, "round5": r5},
    }


def _fmt(v: float | None, nd: int = 3) -> str:
    return "-" if v is None else f"{v:.{nd}f}"


def pooled_rows(runs: Sequence[Run], tool: str, floor: str, sets: Sequence[str]) -> WordScore:
    total = WordScore()
    for r in runs:
        if r.tool == tool and r.floor == floor and r.set in sets:
            total = total + r.score
    return total


def r5_pooled(runs: Sequence[Run], floor: str, sets: Sequence[str]) -> tuple[int, int, int]:
    rs = [r.r5 for r in runs if r.tool == "lokiW" and r.floor == floor and r.set in sets]
    return sum(c for c, _, _ in rs), sum(m for _, m, _ in rs), sum(g for _, _, g in rs)


def count_designs(runs: Sequence[Run], tool: str, floor: str, sets: Sequence[str]) -> int:
    return sum(1 for r in runs if r.tool == tool and r.floor == floor and r.set in sets)


def same_designs(runs: Sequence[Run], tool: str, other: str, floor: str,
                 sets: Sequence[str]) -> WordScore:
    """Pooled counts of ``tool`` over the designs on which ``other`` also has a row."""
    keep = {(r.set, r.design) for r in runs if r.tool == other and r.floor == floor
            and r.set in sets}
    total = WordScore()
    for r in runs:
        if r.tool == tool and r.floor == floor and (r.set, r.design) in keep:
            total = total + r.score
    return total


TABLE_HEAD = ("| arm | designs | P | G | exact P | exact R | P_J | R_J | F1_J | purity | "
              "completeness | FF coverage |")


def table_row(label: str, n: int, ws: WordScore) -> str:
    r = ws.ratios()
    cells = [label, str(n), str(ws.n_pred), str(ws.n_gt)] + [
        _fmt(r[k]) for k in ("precision_exact", "recall_exact", "precision_j", "recall_j", "f1_j",
                             "purity", "completeness", "ff_coverage")]
    return "| " + " | ".join(cells) + " |"


def r5_row(label: str, n: int, r5: tuple[int, int, int]) -> str:
    c, m, g = r5
    p = round(m / c, 3) if c else None
    rc = round(m / g, 3) if g else None
    fv = round(2 * m / (c + g), 3) if c + g else None
    cells = [label, str(n), str(c), str(g), "-", "-", _fmt(p), _fmt(rc), _fmt(fv), "-", "-", "-"]
    return "| " + " | ".join(cells) + " |"


def headline_table(runs8: Sequence[Run], runs2: Sequence[Run], floor: str,
                   sets: Sequence[str], title: str) -> list[str]:
    lines = [f"**{title}**", "", TABLE_HEAD, "|" + "---|" * 12]
    n8 = count_designs(runs8, "hal8", floor, sets)
    lines.append(table_row("Loki W (comparison scorer)", n8, pooled_rows(runs8, "lokiW", floor,
                                                                          sets)))
    lines.append(r5_row("Loki W (round-5 scorer)", n8, r5_pooled(runs8, floor, sets)))
    nwb = count_designs(runs8, "lokiWB", floor, sets)
    lines.append(table_row("Loki WB (comparison scorer)", nwb,
                           pooled_rows(runs8, "lokiWB", floor, sets)))
    if nwb != n8:
        lines.append(table_row("Loki W (comparison scorer, only the designs WB has)", nwb,
                               same_designs(runs8, "lokiW", "lokiWB", floor, sets)))
    lines.append(table_row("HAL DANA min_group_size 8 (headline)", n8,
                           pooled_rows(runs8, "hal8", floor, sets)))
    lines.append(table_row("HAL DANA min_group_size 2 (sensitivity)",
                           count_designs(runs2, "hal2", floor, sets),
                           pooled_rows(runs2, "hal2", floor, sets)))
    if nwb != n8:
        lines += ["", f"(Loki WB has a run on {nwb} of the {n8} designs of the other arms; the "
                  "designs without a WB run are listed under \"Dropped\". The extra W row pools W "
                  "over WB's designs only.)"]
    return [*lines, ""]


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        return []
    with path.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


@dataclass(frozen=True)
class Shape:
    """Pooled shape of the predicted words of one tool at one floor over a set of designs."""

    groups: int
    median: float
    mean: float
    merging: int

    @property
    def share(self) -> float:
        return self.merging / self.groups if self.groups else 0.0


def shape_of(rows: Sequence[dict[str, str]], tool: str, floor: str,
             sets: Sequence[str]) -> Shape:
    sizes: list[int] = []
    merging = 0
    for r in rows:
        if r["tool"] == tool and r["floor"] == floor and r["set"] in sets:
            sizes += [int(x) for x in r["sizes"].split()]
            merging += int(r["merging"])
    return Shape(len(sizes), statistics.median(sizes) if sizes else 0.0,
                 statistics.fmean(sizes) if sizes else 0.0, merging)


SHAPE_ARMS = (("Loki W", "lokiW", 8), ("Loki WB", "lokiWB", 8),
              ("DANA, size 8 (headline)", "hal8", 8), ("DANA, size 2", "hal2", 2))


def shape_rows(data: Path) -> dict[int, list[dict[str, str]]]:
    return {n: read_csv_rows(data / f"groups-hal{n}.csv") for n in (8, 2)}


def shape_section(data: Path) -> list[str]:
    """Pooled size of the predicted words and the share that overlap more than one scored GT
    word, per tool (Fix 2 M4). Predicted words are the distinct sets of 2 FFs or more that the
    scorer scores. A predicted word merges words when its FFs that lie in a scored GT word (WIDTH
    >= 2, 2 FFs or more) are not all inside one such word (`loki.hal.wordscore.group_shape`)."""
    rows = shape_rows(data)
    lines = ["**Predicted words: size and merging (E_real = MI + VT, pooled over designs)**", "",
             "| floor | arm | words | median size | mean size | words merging GT words | share |",
             "|---|---|---|---|---|---|---|"]
    for floor in ("f2", "f3"):
        for label, tool, n in SHAPE_ARMS:
            sh = shape_of(rows[n], tool, floor, ("MI", "VT"))
            lines.append(f"| {floor} | {label} | {sh.groups} | {sh.median:.1f} | {sh.mean:.2f} | "
                         f"{sh.merging} | {sh.share:.3f} |")
    return [*lines, ""]


def stop_rule_table(data: Path) -> list[str]:
    """Per set and floor: designs run, dropped, share (stop rule: more than 20 percent stops)."""
    tot: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for r in read_csv_rows(data / "run-hal8.csv"):
        row = tot[r["key"].split("/")[0]]
        row[0] += 1
        row[1] += r["status"] != "ok"
    for r in read_csv_rows(data / "big-summary-hal8.csv"):
        row = tot["BIG-f2"]
        row[0] += 1
        row[1] += r["status"] != "ok"
    lines = ["| set-floor | designs | dropped | share | stop rule (more than 20 percent) |",
             "|---|---|---|---|---|"]
    for k, (n, d) in sorted(tot.items()):
        verdict = "STOP, not scored" if d / n > STOP_SHARE else "scored"
        lines.append(f"| {k} | {n} | {d} | {d / n:.3f} | {verdict} |")
    return [*lines, ""]


def dropped_list(data: Path) -> list[str]:
    rows = read_csv_rows(data / "dropped-hal8.csv")
    return [f"- {r['key']} ({r['arm']}): {r['status']} ({r['detail']})" for r in rows] + [""]


def big_table(data: Path) -> list[str]:
    """Descriptive only (Amendment 2 B4): no answer-key score is computed on BIG."""
    lines = ["| design | status | flip-flops | DANA groups | groups of 2+ | largest | HAL s |",
             "|---|---|---|---|---|---|---|"]
    for r in read_csv_rows(data / "big-summary-hal8.csv"):
        lines.append("| " + " | ".join([r["design"], r["status"], r["ffs"], r["groups"],
                                        r["groups_ge2"], r["largest"], r["seconds"]]) + " |")
    return [*lines, ""]


def time_line(data: Path) -> list[str]:
    secs = [float(r["seconds"]) for r in read_csv_rows(data / "run-hal8.csv")]
    if not secs:
        return []
    return [f"HAL setting 8 on MI and VT: {len(secs)} runs, {sum(secs):.1f} s in total, "
            f"longest {max(secs):.2f} s (900 s limit).", ""]


def lut_count_bad(rows: Sequence[dict[str, str]]) -> list[dict[str, str]]:
    return [r for r in rows if r["count_mismatch"] != "0"]


def checks_section(data: Path) -> list[str]:
    out: list[str] = []
    for name, title in (("determinism.csv", "A7 determinism (DANA twice, smallest 5 of E_real f2)"),
                        ("determinism-fresh.csv", "A7 determinism, both runs uncached (`--fresh`)"),
                        ("permutation.csv", "A6 name and order permutation (6 designs, seed 7)")):
        rows = read_csv_rows(data / name)
        out += [f"**{title}**", ""]
        if not rows and name == "determinism-fresh.csv":
            continue
        out += [f"- {r['key']}: {r['partitions']}" for r in rows] or ["- not run"]
        out.append("")
    rt = read_csv_rows(data / "roundtrip.csv")
    lc = read_csv_rows(data / "lutcheck.csv")
    ld = read_csv_rows(data / "loadcheck.csv")
    ff = read_csv_rows(data / "f2f3.csv")
    dsr = read_csv_rows(data / "dffsr.csv")
    out += ["**Load and function checks**", "",
            f"- A8 round trip (BLIF vs iverilog, VT and BIG): "
            f"{sum(r['status'] == 'ok' for r in rt)} ok, "
            f"{sum(r['status'] == 'FAIL' for r in rt)} fail, "
            f"{sum(r['status'] == 'not_convertible' for r in rt)} not convertible",
            f"- lut6.hgl bit order in HAL: {len(lc)} designs, "
            f"{sum(int(r['luts_hal']) for r in lc)} LUTs in HAL, "
            f"{sum(int(r['mismatches']) for r in lc)} truth-table mismatches",
            f"- LUT counts, BLIF against HAL: {len(lc) - len(lut_count_bad(lc))} of {len(lc)} "
            "designs equal" + "".join(
                f"; {r['key']}: BLIF {r['luts_blif_named']} named + {r['luts_blif_unnamed']} "
                f"unnamed, HAL {r['luts_hal']}" for r in lut_count_bad(lc)),
            f"- DANA f2 and f3 partitions equal on {sum(r['partitions'] == 'equal' for r in ff)} "
            f"of {len(ff)} designs (`f2f3.csv`)" + "".join(
                f"; {r['key']}: {r['partitions']}" for r in ff if r["partitions"] != "equal"),
            f"- DFFSR cells in the MI and VT netlists: {sum(int(r['dffsr_cells']) for r in dsr)} "
            f"in {sum(int(r['dffsr_cells']) > 0 for r in dsr)} of {len(dsr)} (`dffsr.csv`)",
            f"- corpus-train load checks: {sum(r['status'] == 'ok' for r in ld)} of {len(ld)} ok",
            ""]
    return out


def scorer_table(dec: dict[str, object]) -> list[str]:
    """The decision under both scorers side by side (Fix 2 M1). HAL's counts are the same in both
    rows; only Loki's counts and GT differ (Amendment 1 A1)."""
    sc = dec["scorers"]
    assert isinstance(sc, dict)
    a: dict[str, Any]
    lines = ["| scorer for Loki | D | CI95 | CI90 | Wilcoxon p (Loki greater) | "
             "Wilcoxon p (HAL greater) | non-zero pairs | rule applied to this scorer alone |",
             "|---|---|---|---|---|---|---|---|"]
    for key, label in (("comparison", "comparison scorer (dedup, FF cuts)"),
                       ("round5", "round-5 scorer")):
        a = sc[key]
        lo95, hi95 = a["ci95"]
        lo90, hi90 = a["ci90"]
        lines.append(
            f"| {label} | {_fmt(a['d'])} | [{_fmt(lo95)}, {_fmt(hi95)}] | "
            f"[{_fmt(lo90)}, {_fmt(hi90)}] | {_fmt(a['p_loki_greater'], 4)} | "
            f"{_fmt(a['p_hal_greater'], 4)} | {a['nonzero_pairs']} | {a['outcome']} |")
    return lines


def decision_section(dec: dict[str, object], title: str = "") -> list[str]:
    ci95, ci90, ci5 = dec["ci95"], dec["ci90"], dec["ci95_round5"]
    assert isinstance(ci95, tuple) and isinstance(ci90, tuple) and isinstance(ci5, tuple)

    def p(v: object) -> str:
        return "undefined" if v is None else f"{float(str(v)):.4f}"
    return [
        title or "**Decision (E_real = MI + VT at f2, HAL headline = min_group_size 8)**", "",
        f"- outcome: **{dec['outcome']}** {dec['note']}".rstrip(),
        f"- designs in both arms: {dec['designs']} ({dec['clusters']} clusters), of which with a "
        f"GT word: {dec['designs_gt']}; non-zero paired differences (Wilcoxon): "
        f"{dec['nonzero_pairs']}",
        f"- pooled F1_J: Loki W {_fmt(float(str(dec['f1_loki'])))}, HAL "
        f"{_fmt(float(str(dec['f1_hal'])))}; D = {_fmt(float(str(dec['d'])))}; D with Loki's "
        f"round-5 counts = {_fmt(float(str(dec['d_round5'])))}",
        f"- bootstrap CI of D: 95% [{_fmt(ci95[0])}, {_fmt(ci95[1])}], 90% "
        f"[{_fmt(ci90[0])}, {_fmt(ci90[1])}]; round-5 D 95% [{_fmt(ci5[0])}, {_fmt(ci5[1])}] "
        f"({RESAMPLES} cluster resamples, seed {SEED})",
        f"- Wilcoxon (approx, no continuity correction): p(Loki greater) = "
        f"{p(dec['p_loki_greater'])}, p(HAL greater) = {p(dec['p_hal_greater'])}, "
        f"p(Loki greater, round-5 counts) = {p(dec['p_loki_greater_round5'])}", "",
        "Both scorers side by side (HAL counts identical in both rows):", "",
        *scorer_table(dec), "",
        "The pre-registered outcome above needs Loki ahead under both scorers (Amendment 1 A1); "
        "no scorer is the headline.", ""]


def order_of_events(f1_cmp: float, f1_r5: float) -> list[str]:
    return [
        "Order of events (git commit times, UTC-4, branch `exp/hal`).", "",
        "- 2026-10-25 19:08 `92b5493`: round 5 merged; Loki's W and WB counts under the round-5 "
        "scorer exist from this point.",
        "- 2026-10-26 17:27 `363187f`: pre-registration. Its text already cuts Loki's cells and "
        "the GT footprints to flip-flops; it says nothing on duplicate predictions.",
        "- 2026-10-26 17:37 `ca4cbac`: first comparison scorer (deduplicates predicted sets). "
        "Committed after Loki's round-5 counts were known, before any HAL run.",
        "- 2026-10-26 17:45 `1214dab`: round-5 switches added; WIDTH >= 2 GT words only.",
        "- 2026-10-26 17:50 `4a71877`: Amendment 1 (states the four scorer differences, adds the "
        "round-5 condition, the bootstrap CI and the equivalence rule).",
        "- 2026-10-26 22:50 `373049e`: Amendment 2; the lut6 bit-order check had loaded HAL on "
        "the 100 MI and VT f2 designs (no DANA grouping, no score; see the erratum).",
        "- 2026-10-26 22:57 `ae66d9d`: first DANA scores on MI and VT.", "",
        "The scorer therefore was fixed after Loki's round-5 counts were seen and before any DANA "
        "grouping was scored. It moves Loki's pooled f2 F1_J from " + _fmt(f1_r5) + " (round-5 "
        "scorer) to " + _fmt(f1_cmp) + " (comparison scorer). Both decisions are shown; neither "
        "scorer is chosen as the headline by its result.", ""]

READING = [
    "How to read the tables. One scorer (`loki.hal.wordscore`) scores both tools against the L0",
    "storage words of at least two flip-flops. DANA reads only the flip-flop graph and the clock,",
    "enable, set and reset nets of the flip-flop pins; the f2 and f3 netlists of a design hold",
    "the same flip-flops and the same flip-flop to flip-flop connectivity, and neither floor's",
    "flip-flop carries an enable or reset pin in the evaluation sets (no DFFSR cell; checked), so",
    "DANA's f2 and f3 rows are equal by construction (checked per design: equal partitions under",
    "the original flip-flop names, see the checks) and the f2 to f3 difference in the tables is",
    "Loki's (Amendment 2 B3).",
    "The decision rule is the pre-registered one (Amendments A1 to A3); `inconclusive` means no",
    "difference was shown, not that the tools are equal. BIG is not scored (stop rule).", ""]


def build(data: Path) -> tuple[list[str], dict[str, object], dict[str, dict[str, object]]]:
    runs8 = load_scores(data / "scores-hal8.csv")
    runs2 = load_scores(data / "scores-hal2.csv") if (data / "scores-hal2.csv").is_file() else []
    real = ("MI", "VT")
    lines = ["# Loki word-first detector vs HAL/DANA: results (generated)", "",
             "Generated by `python -m loki.hal.compare`; do not edit. Rule and amendments: "
             "`docs/plan/hal-compare-prereg.md`.", ""]
    dec = decide(make_pairs(runs8, "hal8", "f2", real))
    r5c, r5m, r5g = r5_pooled(runs8, "f2", real)
    lines += order_of_events(float(str(dec["f1_loki"])), 2 * r5m / (r5c + r5g)) + READING
    lines += decision_section(dec)
    for floor in ("f2", "f3"):
        lines += headline_table(runs8, runs2, floor, real, f"E_real (MI + VT), floor {floor}")
        for s in real:
            lines += headline_table(runs8, runs2, floor, (s,), f"{s}, floor {floor}")
    lines += ["**Stop rule per set and floor (HAL setting 8)**", ""] + stop_rule_table(data)
    lines += ["Dropped from both arms:", ""] + dropped_list(data) + time_line(data)
    lines += ["**BIG (f2), descriptive only, not scored (Amendment 2 B4)**", ""] + big_table(data)
    lines += shape_section(data) + checks_section(data)
    sens: dict[str, dict[str, object]] = {}
    if runs2:
        sens["setting2"] = decide(make_pairs(runs2, "hal2", "f2", real))
        lines += decision_section(
            sens["setting2"], "**Sensitivity: the same rule with HAL min_group_size 2 "
            "(not the headline)**")
    return lines, dec, sens


TEX_TOOL = {"lokiW": "LokiW", "lokiWB": "LokiWB", "hal8": "HalEight", "hal2": "HalTwo"}
TEX_FLOOR = {"f2": "FTwo", "f3": "FThree"}
TEX_KEY = {"precision_exact": "PrecExact", "recall_exact": "RecExact", "precision_j": "PrecJ",
           "recall_j": "RecJ", "f1_j": "FJ", "purity": "Purity", "completeness": "Compl",
           "ff_coverage": "Cover"}


def _num(v: object) -> str:
    return "undefined" if v is None else f"{float(str(v)):.3f}"


def _identical(rows: Sequence[dict[str, str]]) -> int:
    return sum(r["partitions"] == "identical" for r in rows)


def tex_checks(data: Path) -> list[str]:
    """Macros for the counts the prose quotes: stop-rule counts, large designs, load checks."""
    big = read_csv_rows(data / "big-summary-hal8.csv")
    ok = [r for r in big if r["status"] == "ok"]
    lut = read_csv_rows(data / "lutcheck.csv")
    perm = read_csv_rows(data / "permutation.csv")
    rep = read_csv_rows(data / "determinism.csv")
    fresh = read_csv_rows(data / "determinism-fresh.csv")
    ff = read_csv_rows(data / "f2f3.csv")
    dsr = read_csv_rows(data / "dffsr.csv")
    vals = {
        "BigTotal": len(big), "BigDropped": len(big) - len(ok), "BigRun": len(ok),
        "BigMaxSeconds": f"{max((float(r['seconds']) for r in ok), default=0.0):.0f}",
        "StopLimit": f"{int(STOP_SHARE * 100)}\\%", "LutCount": sum(
            int(r["luts_hal"]) for r in lut), "LutMismatch": sum(
            int(r["mismatches"]) for r in lut), "LutDesigns": len(lut),
        "LutCountBad": len(lut_count_bad(lut)), "PermDesigns": len(perm),
        "PermIdentical": _identical(perm), "RepDesigns": len(rep), "RepIdentical": _identical(rep),
        "FreshDesigns": len(fresh), "FreshIdentical": _identical(fresh),
        "FFDesigns": len(ff), "FFEqual": sum(r["partitions"] == "equal" for r in ff),
        "DffsrNetlists": len(dsr), "DffsrCells": sum(int(r["dffsr_cells"]) for r in dsr)}
    return [f"\\newcommand{{\\hal{k}}}{{{v}}}" for k, v in vals.items()]


def tex_shape(data: Path) -> list[str]:
    """Macros for the group-size statistics quoted in the prose (Fix 2 M4)."""
    rows = shape_rows(data)
    out = []
    for floor in ("f2", "f3"):
        for _label, tool, n in SHAPE_ARMS:
            sh = shape_of(rows[n], tool, floor, ("MI", "VT"))
            base = f"\\hal{TEX_TOOL[tool]}{TEX_FLOOR[floor]}"
            out += [f"\\newcommand{{{base}Median}}{{{sh.median:.1f}}}",
                    f"\\newcommand{{{base}Mean}}{{{sh.mean:.1f}}}",
                    f"\\newcommand{{{base}Merge}}{{{sh.merging}}}",
                    f"\\newcommand{{{base}MergeShare}}{{{sh.share:.2f}}}"]
    return out


def tex_scorers(dec: dict[str, object]) -> list[str]:
    """Macros and table of the decision under both scorers (Fix 2 M1)."""
    sc = dec["scorers"]
    assert isinstance(sc, dict)
    a: dict[str, Any]
    out = []
    names = {"comparison": "Cmp", "round5": "Five"}
    for key, tag in names.items():
        a = sc[key]
        vals = {"D": _num(a["d"]), "CiLo": _num(a["ci95"][0]), "CiHi": _num(a["ci95"][1]),
                "CiNinetyLo": _num(a["ci90"][0]), "CiNinetyHi": _num(a["ci90"][1]),
                "PLoki": _num(a["p_loki_greater"]), "PHal": _num(a["p_hal_greater"]),
                "Nonzero": a["nonzero_pairs"], "Outcome": a["outcome"]}
        out += [f"\\newcommand{{\\halScorer{tag}{k}}}{{{v}}}" for k, v in vals.items()]
    rows = []
    for key, label in (("comparison", "Comparison scorer"), ("round5", "Round-5 scorer")):
        a = sc[key]
        rows.append(f"{label} & {_fmt(a['d'])} & [{_fmt(a['ci95'][0])}, {_fmt(a['ci95'][1])}] & "
                    f"[{_fmt(a['ci90'][0])}, {_fmt(a['ci90'][1])}] & {_fmt(a['p_loki_greater'])} & "
                    f"{_fmt(a['p_hal_greater'])} & {a['outcome']} \\\\")
    return out + ["\\begin{table}[t]",
                  "\\caption{The decision on E\\_real at f2 under the two scorers "
                  "for Loki (HAL counts identical in both rows). $D = F_J(\\text{Loki}) - "
                  "F_J(\\text{DANA})$; $p_L$, $p_H$: one-sided Wilcoxon p, Loki greater and DANA "
                  "greater. The last column applies the rule to that row alone; the "
                  "decision needs Loki ahead under both.}",
                  "\\label{tab:hal-decision}", "\\centering", "\\footnotesize",
                  "\\begin{tabular}{@{}lrrrrrl@{}}", "\\toprule",
                  "Scorer & $D$ & 95\\% CI & 90\\% CI & $p_L$ & $p_H$ & rule alone \\\\",
                  "\\midrule", *rows, "\\bottomrule", "\\end{tabular}", "\\end{table}"]


def tex_macros(dec: dict[str, object], sens: dict[str, dict[str, object]], runs8: list[Run],
               runs2: list[Run]) -> list[str]:
    ci95, ci90 = dec["ci95"], dec["ci90"]
    assert isinstance(ci95, tuple) and isinstance(ci90, tuple)
    out = ["% Generated by loki.hal.compare; do not edit.",
           f"\\newcommand{{\\halOutcome}}{{{dec['outcome']}}}",
           f"\\newcommand{{\\halDesigns}}{{{dec['designs']}}}",
           f"\\newcommand{{\\halDesignsGt}}{{{dec['designs_gt']}}}",
           f"\\newcommand{{\\halClusters}}{{{dec['clusters']}}}",
           f"\\newcommand{{\\halNonzero}}{{{dec['nonzero_pairs']}}}",
           f"\\newcommand{{\\halFoneLoki}}{{{_num(dec['f1_loki'])}}}",
           f"\\newcommand{{\\halFoneHal}}{{{_num(dec['f1_hal'])}}}",
           f"\\newcommand{{\\halD}}{{{_num(dec['d'])}}}",
           f"\\newcommand{{\\halDfive}}{{{_num(dec['d_round5'])}}}",
           f"\\newcommand{{\\halCiLo}}{{{_num(ci95[0])}}}",
           f"\\newcommand{{\\halCiHi}}{{{_num(ci95[1])}}}",
           f"\\newcommand{{\\halCiNinetyLo}}{{{_num(ci90[0])}}}",
           f"\\newcommand{{\\halCiNinetyHi}}{{{_num(ci90[1])}}}",
           f"\\newcommand{{\\halPLoki}}{{{_num(dec['p_loki_greater'])}}}",
           f"\\newcommand{{\\halPHal}}{{{_num(dec['p_hal_greater'])}}}"]
    s2 = sens.get("setting2")
    if s2 is not None:
        sc2 = s2["scorers"]
        assert isinstance(sc2, dict)
        out += [f"\\newcommand{{\\halTwoScorerCmpOutcome}}{{{sc2['comparison']['outcome']}}}",
                f"\\newcommand{{\\halTwoScorerFiveOutcome}}{{{sc2['round5']['outcome']}}}"]
    for floor in ("f2", "f3"):
        cnt, mat, gtn = r5_pooled(runs8, floor, ("MI", "VT"))
        r5v = {"PrecJ": mat / cnt if cnt else None, "RecJ": mat / gtn if gtn else None,
               "FJ": 2 * mat / (cnt + gtn) if cnt + gtn else None}
        out += [f"\\newcommand{{\\halRFive{TEX_FLOOR[floor]}{k}}}{{{_num(v)}}}"
                for k, v in r5v.items()]
    for floor in ("f2", "f3"):
        for tool, runs in (("lokiW", runs8), ("lokiWB", runs8), ("hal8", runs8), ("hal2", runs2)):
            ws = pooled_rows(runs, tool, floor, ("MI", "VT"))
            base = f"\\hal{TEX_TOOL[tool]}{TEX_FLOOR[floor]}"
            for key, val in ws.ratios().items():
                out.append(f"\\newcommand{{{base}{TEX_KEY[key]}}}{{{_num(val)}}}")
            out.append(f"\\newcommand{{{base}Groups}}{{{ws.n_pred}}}")
            out.append(f"\\newcommand{{{base}Words}}{{{ws.n_gt}}}")
    return out


def wb_note(runs: Sequence[Run]) -> str:
    """Caption sentence on the designs that the WB arm does not cover."""
    parts = []
    for fl in ("f2", "f3"):
        n_w = count_designs(runs, "lokiW", fl, ("MI", "VT"))
        n_wb = count_designs(runs, "lokiWB", fl, ("MI", "VT"))
        if n_wb != n_w:
            parts.append(f"{fl}: {n_wb} of {n_w} designs")
    if not parts:
        return ""
    return ("Loki WB has a run on fewer designs than the other arms (" + "; ".join(parts)
            + "; listed in docs/results-hal.md), so its rows pool a different design set.")


def tex_table(runs8: list[Run], runs2: list[Run]) -> list[str]:
    cols = ("precision_j", "recall_j", "f1_j", "purity", "completeness")
    out = ["\\begin{table*}[t]",
           "\\caption{Loki word-first detector (\\code{W}) against HAL's DANA on MI and VT "
           "(E\\_real), word recovery against the L0 ground truth; one scorer for both tools. "
           "$P_J$, $R_J$, $F_J$: Jaccard-0.5 matching; purity and completeness over flip-flops. "
           "The round-5 scorer row counts Loki as round 5 did (the scorer used for Loki in round 5). "
           + wb_note(runs8) + "}",
           "\\label{tab:hal}", "\\centering", "\\footnotesize",
           "\\begin{tabular}{@{}l" + "rrrrr" * 2 + "@{}}", "\\toprule",
           " & \\multicolumn{5}{c}{f2 (LUT6)} & \\multicolumn{5}{c}{f3 (cmos6)} \\\\",
           "\\cmidrule(lr){2-6}\\cmidrule(lr){7-11}",
           "Arm & $P_J$ & $R_J$ & $F_J$ & pur. & compl. & $P_J$ & $R_J$ & $F_J$ & pur. & compl. "
           "\\\\", "\\midrule"]
    arms = (("Loki W", "lokiW", runs8), ("Loki WB", "lokiWB", runs8),
            ("DANA, size 8 (headline)", "hal8", runs8), ("DANA, size 2", "hal2", runs2))
    r5 = []
    for fl in ("f2", "f3"):
        cnt, mat, gtn = r5_pooled(runs8, fl, ("MI", "VT"))
        pj, rj = (mat / cnt if cnt else None), (mat / gtn if gtn else None)
        fj = 2 * mat / (cnt + gtn) if cnt + gtn else None
        r5 += [_fmt(pj), _fmt(rj), _fmt(fj), "-", "-"]
    for label, tool, runs in arms:
        cells = []
        for fl in ("f2", "f3"):
            r = pooled_rows(runs, tool, fl, ("MI", "VT")).ratios()
            cells += [_fmt(r[k]) for k in cols]
        out.append(label + " & " + " & ".join(cells) + " \\\\")
        if tool == "lokiW":
            out.append("Loki W, round-5 scorer & " + " & ".join(r5) + " \\\\")
    out += ["\\bottomrule", "\\end{tabular}", "\\end{table*}"]
    return out


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="loki.hal.compare", description=__doc__)
    ap.add_argument("data", type=Path)
    ap.add_argument("--md", type=Path)
    ap.add_argument("--tex", type=Path)
    ap.add_argument("--json", type=Path)
    args = ap.parse_args(argv)
    lines, dec, sens = build(args.data)
    text = "\n".join(lines) + "\n"
    if args.md:
        args.md.write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text)
    if args.tex:
        runs8 = load_scores(args.data / "scores-hal8.csv")
        p2 = args.data / "scores-hal2.csv"
        runs2 = load_scores(p2) if p2.is_file() else []
        args.tex.write_text("\n".join(
            tex_macros(dec, sens, runs8, runs2) + tex_checks(args.data) + tex_shape(args.data)
            + tex_scorers(dec) + tex_table(runs8, runs2)) + "\n", encoding="utf-8")
    if args.json:
        args.json.write_text(json.dumps({"decision": dec, "sensitivity": sens}, indent=1,
                                        sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
