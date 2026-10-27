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
import sys
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from loki.hal.wordscore import WordScore

SEED = 20261026
RESAMPLES = 10000
MARGIN = 0.05
ALPHA = 0.05
MIN_NONZERO = 8
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
    """One design in both arms: (matched, predicted) of HAL, Loki, Loki round-5; GT counts."""

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
        if tool != hal or s not in sets or k is None or h.score.n_gt < 1:
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


def decide(pairs: Sequence[Pair]) -> dict[str, object]:
    """The pre-registered rule with Amendments A1 to A3 on the pairs of E_real at f2."""
    fk, fh, d, d5 = pooled_d(pairs)
    bd, bd5 = bootstrap(pairs)
    ci95, ci90, ci95_5 = interval(bd, 0.95), interval(bd, 0.90), interval(bd5, 0.95)
    xk, xh, xk5 = ([f(p) for p in pairs] for f in (Pair.f1_k, Pair.f1_h, Pair.f1_k5))
    nonzero = sum(a != b for a, b in zip(xk, xh, strict=True))
    p_k = wilcoxon_p(xk, xh, "greater")
    p_h = wilcoxon_p(xh, xk, "greater")
    p_k5 = wilcoxon_p(xk5, xh, "greater")
    ahead_k = (d >= MARGIN and ci95[0] > MARGIN and p_k is not None and p_k < ALPHA)
    ahead_k5 = (d5 >= MARGIN and ci95_5[0] > MARGIN and p_k5 is not None and p_k5 < ALPHA)
    ahead_h = (d <= -MARGIN and ci95[1] < -MARGIN and p_h is not None and p_h < ALPHA)
    comparable = ci90[0] > -MARGIN and ci90[1] < MARGIN
    outcome = "inconclusive"
    if nonzero < MIN_NONZERO:
        note = f"fewer than {MIN_NONZERO} non-zero paired differences"
    elif ahead_k and ahead_k5:
        outcome, note = "Loki ahead", ""
    elif ahead_k:
        note = "Loki ahead under the comparison scorer only (A1 round-5 condition fails)"
    elif ahead_h:
        outcome, note = "HAL ahead", ""
    elif comparable:
        outcome, note = "comparable", ""
    else:
        note = "no difference shown" if abs(d) < MARGIN else ""
    return {
        "outcome": outcome, "note": note, "designs": len(pairs), "clusters": len(
            {p.cluster for p in pairs}), "nonzero_pairs": nonzero,
        "f1_loki": fk, "f1_hal": fh, "d": d, "d_round5": d5,
        "ci95": ci95, "ci90": ci90, "ci95_round5": ci95_5,
        "p_loki_greater": p_k, "p_hal_greater": p_h, "p_loki_greater_round5": p_k5,
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
    lines.append(table_row("Loki WB (comparison scorer)", count_designs(runs8, "lokiWB", floor,
                                                                         sets),
                           pooled_rows(runs8, "lokiWB", floor, sets)))
    lines.append(table_row("HAL DANA min_group_size 8 (headline)", n8,
                           pooled_rows(runs8, "hal8", floor, sets)))
    lines.append(table_row("HAL DANA min_group_size 2 (sensitivity)",
                           count_designs(runs2, "hal2", floor, sets),
                           pooled_rows(runs2, "hal2", floor, sets)))
    return [*lines, ""]


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        return []
    with path.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def drops_line(data: Path, setting: int, runs: Sequence[Run]) -> list[str]:
    rows = read_csv_rows(data / f"dropped-hal{setting}.csv")
    lines = [f"Dropped from both arms (HAL setting {setting}): {len(rows)}", ""]
    per: dict[tuple[str, str], int] = defaultdict(int)
    for r in rows:
        key = r["key"].split("/")[0]
        per[(key, r["status"])] += 1
    lines += [f"- {k[0]}: {k[1]} x {v}" for k, v in sorted(per.items())]
    return [*lines, ""]


def big_table(runs: Sequence[Run], data: Path) -> list[str]:
    secs = {r["key"]: r["seconds"] for r in read_csv_rows(data / "run-hal8.csv")}
    lines = ["| design | GT words | HAL groups | HAL matched | HAL F1_J | HAL s | Loki W words | "
             "Loki matched | Loki F1_J |", "|" + "---|" * 9]
    by = {(r.tool, r.design): r for r in runs if r.set == "BIG" and r.floor == "f2"}
    for (tool, d), h in sorted(by.items(), key=lambda kv: (kv[1].score.n_gt, kv[0][1])):
        if tool != "hal8":
            continue
        k = by.get(("lokiW", d))
        kk = k.score if k else WordScore()
        lines.append("| " + " | ".join([
            d, str(h.score.n_gt), str(h.score.n_pred), str(h.score.matched),
            _fmt(h.score.ratios()["f1_j"]), secs.get(f"BIG-f2/{d}", "-"), str(kk.n_pred),
            str(kk.matched), _fmt(kk.ratios()["f1_j"])]) + " |")
    return [*lines, ""]


def checks_section(data: Path) -> list[str]:
    out: list[str] = []
    for name, title in (("determinism.csv", "A7 determinism (DANA twice, smallest 5)"),
                        ("permutation.csv", "A6 name/order permutation (6 designs)")):
        rows = read_csv_rows(data / name)
        out += [f"**{title}**", ""]
        out += [f"- {r['key']}: {r['partitions']}" for r in rows] or ["- not run"]
        out.append("")
    return out


def decision_section(dec: dict[str, object]) -> list[str]:
    ci95, ci90, ci5 = dec["ci95"], dec["ci90"], dec["ci95_round5"]
    assert isinstance(ci95, tuple) and isinstance(ci90, tuple) and isinstance(ci5, tuple)

    def p(v: object) -> str:
        return "undefined" if v is None else f"{float(str(v)):.4f}"
    return [
        "**Decision (E_real = MI + VT at f2, HAL headline = min_group_size 8)**", "",
        f"- outcome: **{dec['outcome']}** {dec['note']}".rstrip(),
        f"- designs with a GT word in both arms: {dec['designs']} ({dec['clusters']} clusters), "
        f"non-zero paired differences: {dec['nonzero_pairs']}",
        f"- pooled F1_J: Loki W {_fmt(float(str(dec['f1_loki'])))}, HAL "
        f"{_fmt(float(str(dec['f1_hal'])))}; D = {_fmt(float(str(dec['d'])))}; D with Loki's "
        f"round-5 counts = {_fmt(float(str(dec['d_round5'])))}",
        f"- bootstrap CI of D: 95% [{_fmt(ci95[0])}, {_fmt(ci95[1])}], 90% "
        f"[{_fmt(ci90[0])}, {_fmt(ci90[1])}]; round-5 D 95% [{_fmt(ci5[0])}, {_fmt(ci5[1])}] "
        f"({RESAMPLES} cluster resamples, seed {SEED})",
        f"- Wilcoxon (approx, no continuity correction): p(Loki greater) = "
        f"{p(dec['p_loki_greater'])}, p(HAL greater) = {p(dec['p_hal_greater'])}, "
        f"p(Loki greater, round-5 counts) = {p(dec['p_loki_greater_round5'])}", ""]


def build(data: Path) -> tuple[list[str], dict[str, object], dict[str, dict[str, object]]]:
    runs8 = load_scores(data / "scores-hal8.csv")
    runs2 = load_scores(data / "scores-hal2.csv") if (data / "scores-hal2.csv").is_file() else []
    real = ("MI", "VT")
    lines = ["# Loki word-first detector vs HAL/DANA: results (generated)", "",
             "Generated by `python -m loki.hal.compare`; do not edit. Rule and amendments: "
             "`docs/plan/hal-compare-prereg.md`.", ""]
    dec = decide(make_pairs(runs8, "hal8", "f2", real))
    lines += decision_section(dec)
    for floor in ("f2", "f3"):
        lines += headline_table(runs8, runs2, floor, real, f"E_real (MI + VT), floor {floor}")
        for s in real:
            lines += headline_table(runs8, runs2, floor, (s,), f"{s}, floor {floor}")
    lines += ["**BIG (f2), smallest first, no test**", ""] + big_table(runs8, data)
    lines += drops_line(data, 8, runs8)
    if runs2:
        lines += drops_line(data, 2, runs2)
    lines += checks_section(data)
    sens: dict[str, dict[str, object]] = {}
    if runs2:
        sens["setting2"] = decide(make_pairs(runs2, "hal2", "f2", real))
        lines += ["**Sensitivity: HAL min_group_size 2 (not the headline)**", ""]
        lines += decision_section(sens["setting2"])
    return lines, dec, sens


def tex_macros(dec: dict[str, object], sens: dict[str, dict[str, object]], runs8: list[Run],
               runs2: list[Run]) -> list[str]:
    def num(v: object) -> str:
        return "undefined" if v is None else f"{float(str(v)):.3f}"
    ci95, ci90 = dec["ci95"], dec["ci90"]
    assert isinstance(ci95, tuple) and isinstance(ci90, tuple)
    out = ["% Generated by loki.hal.compare; do not edit.",
           f"\\newcommand{{\\halOutcome}}{{{dec['outcome']}}}",
           f"\\newcommand{{\\halDesigns}}{{{dec['designs']}}}",
           f"\\newcommand{{\\halFoneLoki}}{{{num(dec['f1_loki'])}}}",
           f"\\newcommand{{\\halFoneHal}}{{{num(dec['f1_hal'])}}}",
           f"\\newcommand{{\\halD}}{{{num(dec['d'])}}}",
           f"\\newcommand{{\\halDfive}}{{{num(dec['d_round5'])}}}",
           f"\\newcommand{{\\halCiLo}}{{{num(ci95[0])}}}",
           f"\\newcommand{{\\halCiHi}}{{{num(ci95[1])}}}",
           f"\\newcommand{{\\halPLoki}}{{{num(dec['p_loki_greater'])}}}",
           f"\\newcommand{{\\halPHal}}{{{num(dec['p_hal_greater'])}}}"]
    for floor in ("f2", "f3"):
        for tool, runs in (("lokiW", runs8), ("hal8", runs8), ("hal2", runs2)):
            ws = pooled_rows(runs, tool, floor, ("MI", "VT"))
            for key, val in ws.ratios().items():
                name = "".join(w.title() for w in key.split("_"))
                out.append(f"\\newcommand{{\\hal{tool.title()}{floor.title()}{name}}}"
                           f"{{{num(val)}}}")
            out.append(f"\\newcommand{{\\hal{tool.title()}{floor.title()}Groups}}{{{ws.n_pred}}}")
            out.append(f"\\newcommand{{\\hal{tool.title()}{floor.title()}Words}}{{{ws.n_gt}}}")
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
        args.tex.write_text("\n".join(tex_macros(
            dec, sens, runs8, load_scores(p2) if p2.is_file() else [])) + "\n", encoding="utf-8")
    if args.json:
        args.json.write_text(json.dumps({"decision": dec, "sensitivity": sens}, indent=1,
                                        sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
