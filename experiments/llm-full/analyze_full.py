"""Analysis of the full run from ``results.csv``: pass@1, pass@3, paired tests, Holm.

Usage: ``python -I analyze_full.py --results run/results.csv [--out summary.md]``.
Strict reading: a call without a pass (any status) is a fail; draws = 3 per (arm, problem).
Unit of analysis is the problem. Per problem and arm c = number of passing draws (0..3).
pass@k = 1 - C(n-c, k) / C(n, k) with n = 3 (the unbiased estimator); pass@1 = c / 3 and
pass@3 = 1 when c >= 1. Binary outcomes for tests: MAJ (c >= 2, primary) and ANY (pass@3 = 1,
secondary). Tests: exact two-sided McNemar per quartile; stratified test = exact binomial on the
discordant pairs pooled over the four quartiles (the matched-pairs form of the Cochran-Mantel-
Haenszel test, strata = quartiles); Holm over the 10 tests of each outcome (A vs B and B vs C, each
for 4 quartiles and the stratified test).
"""

from __future__ import annotations

import argparse
import csv
import importlib
import random
import sys
from dataclasses import dataclass
from math import comb
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
fullcfg: Any = importlib.import_module("fullcfg")
stats: Any = importlib.import_module("pilot_stats")

ARMS = ("A", "B", "C")
QUARTS = ("Q1", "Q2", "Q3", "Q4")
COMPARISONS = (("A", "B"), ("B", "C"))
N_DRAWS = 3


def pass_at_k(n: int, c: int, k: int) -> float:
    """Unbiased pass@k estimator for n draws with c passes (Chen et al. 2021; see EXPERIMENT.md)."""
    if n - c < k:
        return 1.0
    return 1.0 - comb(n - c, k) / comb(n, k)


def holm(pvals: list[float]) -> list[float]:
    """Holm step-down adjusted p-values, in the input order."""
    order = sorted(range(len(pvals)), key=lambda i: pvals[i])
    adj = [0.0] * len(pvals)
    running = 0.0
    for rank, i in enumerate(order):
        running = max(running, min(1.0, (len(pvals) - rank) * pvals[i]))
        adj[i] = running
    return adj


def load(path: Path) -> tuple[dict[tuple[str, str], int], dict[str, str]]:
    """({(arm, problem): passing draws}, {problem: quartile}); missing draws count as fails."""
    counts: dict[tuple[str, str], int] = {}
    quart: dict[str, str] = {}
    with path.open(encoding="utf-8", newline="") as fh:
        for r in csv.DictReader(fh):
            key = (r["arm"], r["problem"])
            counts[key] = counts.get(key, 0) + int(r["pass"])
            quart[r["problem"]] = r["quartile"]
    return counts, quart


def binary(c: int, kind: str) -> bool:
    return c >= 2 if kind == "MAJ" else c >= 1


def discordant(counts: dict[tuple[str, str], int], probs: list[str], x: str, y: str,
               kind: str) -> tuple[int, int]:
    xo = sum(1 for p in probs if binary(counts[(x, p)], kind) and not binary(counts[(y, p)], kind))
    yo = sum(1 for p in probs if binary(counts[(y, p)], kind) and not binary(counts[(x, p)], kind))
    return xo, yo


@dataclass
class TestRow:
    cmp: str
    stratum: str
    n: int
    x_only: int
    y_only: int
    p: float
    p_holm: float = 1.0


def tests(counts: dict[tuple[str, str], int], quart: dict[str, str], kind: str) -> list[TestRow]:
    rows: list[TestRow] = []
    for x, y in COMPARISONS:
        pool = [0, 0]
        for q in QUARTS:
            probs = sorted(p for p in quart if quart[p] == q)
            b, c = discordant(counts, probs, x, y, kind)
            pool[0] += b
            pool[1] += c
            rows.append(TestRow(f"{x} vs {y}", q, len(probs), b, c, stats.mcnemar(b, c)))
        rows.append(TestRow(f"{x} vs {y}", "all (stratified)", len(quart), pool[0], pool[1],
                            stats.mcnemar(pool[0], pool[1])))
    for r, adj in zip(rows, holm([r.p for r in rows]), strict=True):
        r.p_holm = adj
    return rows


def rate_table(counts: dict[tuple[str, str], int], quart: dict[str, str]) -> list[str]:
    out = ["| stratum | arm | problems | pass@1 | pass@3 | MAJ (>=2 of 3) |",
           "| --- | --- | --- | --- | --- | --- |"]
    for label, qs in (*[(q, (q,)) for q in QUARTS], ("all", QUARTS)):
        probs = sorted(p for p in quart if quart[p] in qs)
        for a in ARMS:
            cs = [counts[(a, p)] for p in probs]
            p1 = sum(pass_at_k(N_DRAWS, c, 1) for c in cs) / len(cs)
            p3 = sum(pass_at_k(N_DRAWS, c, 3) for c in cs) / len(cs)
            maj = sum(1 for c in cs if c >= 2)
            out.append(f"| {label} | {a} | {len(cs)} | {p1:.3f} | {p3:.3f} | "
                       f"{maj}/{len(cs)} ({maj / len(cs):.2f}) |")
    return out


def boot_ci(counts: dict[tuple[str, str], int], probs: list[str], x: str, y: str,
            reps: int = 2000, seed: int = 20261029) -> tuple[float, float, float]:
    """Mean pass@1 difference x - y with a problem-level bootstrap 95% interval (seeded)."""
    d = [(counts[(x, p)] - counts[(y, p)]) / N_DRAWS for p in probs]
    rng = random.Random(seed)
    means = sorted(sum(rng.choices(d, k=len(d))) / len(d) for _ in range(reps))
    return sum(d) / len(d), means[int(0.025 * reps)], means[int(0.975 * reps) - 1]


def render(counts: dict[tuple[str, str], int], quart: dict[str, str]) -> str:
    probs = sorted(quart)
    out = [f"# Full run summary ({len(probs)} problems, 3 draws, strict: no pass = fail)", "",
           "## pass@k per arm and quartile", "", *rate_table(counts, quart), "",
           "## Mean pass@1 difference (problem-level bootstrap 95% interval, seed fixed)", ""]
    for x, y in (*COMPARISONS, ("A", "C")):
        m, lo, hi = boot_ci(counts, probs, x, y)
        out.append(f"- {x} minus {y}: {m:+.3f} [{lo:+.3f}, {hi:+.3f}]")
    for kind, title in (("MAJ", "primary: problem passes in at least 2 of 3 draws"),
                        ("ANY", "secondary: pass@3 (any draw passes)")):
        out += ["", f"## Paired tests, {title}", "",
                "| comparison | stratum | problems | first only | second only | p | p (Holm) |",
                "| --- | --- | --- | --- | --- | --- | --- |"]
        for r in tests(counts, quart, kind):
            out.append(f"| {r.cmp} | {r.stratum} | {r.n} | {r.x_only} | {r.y_only} | "
                       f"{r.p:.4f} | {r.p_holm:.4f} |")
    return "\n".join(out) + "\n"


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--results", type=Path, required=True)
    ap.add_argument("--out", type=Path, default=None)
    a = ap.parse_args(argv)
    counts, quart = load(a.results)
    text = render(counts, quart)
    if a.out:
        a.out.write_text(text, encoding="utf-8", newline="\n")
    sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
