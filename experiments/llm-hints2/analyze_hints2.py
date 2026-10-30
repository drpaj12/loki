"""Analysis of the hints-v2 run from ``results.csv``: pass@1, MAJ tests, Holm, verdicts, use.

Usage: ``python -I analyze_hints2.py --results run/results.csv [--kinds claim_kinds.json]
[--out summary.md]``. Strict reading: a call without a pass is a fail; 3 draws per (arm, problem).
Unit: the problem; c = passing draws; MAJ = c >= 2 (primary), ANY = c >= 1 (secondary).
Comparisons (planned, Holm family of 9 per outcome = 3 comparisons x (Q3, Q4, stratified)):
B2 vs A2 (primary), B2 vs B1p, W vs A2. Stratified test = exact binomial on the discordant
problems pooled over Q3 and Q4. Bootstrap interval: problem-level, 2000 resamples, seed 20261030.
Verdict rule for B2 vs A2 (EXPERIMENT.md): USEFUL when the stratified Holm p < 0.05, the 95%
interval excludes 0 and its lower end is at least the minimum gain; POSSIBLY GOOD when only the
first two hold; DISMISSED when the interval's upper end is below the minimum gain; else
INCONCLUSIVE. LLM6 (the model uses the claims) is supported when W minus A2 is negative with
stratified Holm p < 0.05 and more than half of the B2 calls name a claim.
"""

from __future__ import annotations

import argparse
import csv
import importlib
import json
import random
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
hintscfg: Any = importlib.import_module("hintscfg")
stats: Any = importlib.import_module("pilot_stats")

ARMS = ("A2", "B1p", "B2", "W")
STRATA = ("Q3", "Q4")
COMPARISONS = (("B2", "A2"), ("B2", "B1p"), ("W", "A2"))
N_DRAWS = 3
MIN_GAIN = 0.05
SEED = 20261030
HINT_ARMS = ("B1p", "B2", "W")


def holm(pvals: list[float]) -> list[float]:
    order = sorted(range(len(pvals)), key=lambda i: pvals[i])
    adj = [0.0] * len(pvals)
    running = 0.0
    for rank, i in enumerate(order):
        running = max(running, min(1.0, (len(pvals) - rank) * pvals[i]))
        adj[i] = running
    return adj


def load(path: Path) -> tuple[dict[tuple[str, str], int], dict[str, str], list[dict[str, str]]]:
    counts: dict[tuple[str, str], int] = {}
    quart: dict[str, str] = {}
    rows: list[dict[str, str]] = []
    with path.open(encoding="utf-8", newline="") as fh:
        for r in csv.DictReader(fh):
            key = (r["arm"], r["problem"])
            counts[key] = counts.get(key, 0) + int(r["pass"])
            quart[r["problem"]] = r["quartile"]
            rows.append(r)
    return counts, quart, rows


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


def tests(counts: dict[tuple[str, str], int], quart: dict[str, str], kind: str,
          skip_w: frozenset[str] = frozenset()) -> list[TestRow]:
    """The 9 planned tests. Comparisons with W leave out the problems in ``skip_w`` (those whose
    wrong linking still overlaps the true one by more than half; ``wrong_overlap.csv``)."""
    rows: list[TestRow] = []
    for x, y in COMPARISONS:
        pool = [0, 0]
        drop = skip_w if "W" in (x, y) else frozenset()
        for q in STRATA:
            probs = sorted(p for p in quart if quart[p] == q and p not in drop)
            b, c = discordant(counts, probs, x, y, kind)
            pool[0] += b
            pool[1] += c
            rows.append(TestRow(f"{x} vs {y}", q, len(probs), b, c, stats.mcnemar(b, c)))
        rows.append(TestRow(f"{x} vs {y}", "all (stratified)", len(quart) - len(drop & set(quart)),
                            pool[0], pool[1],
                            stats.mcnemar(pool[0], pool[1])))
    for r, adj in zip(rows, holm([r.p for r in rows]), strict=True):
        r.p_holm = adj
    return rows


def boot_ci(counts: dict[tuple[str, str], int], probs: list[str], x: str, y: str,
            reps: int = 2000, seed: int = SEED) -> tuple[float, float, float]:
    d = [(counts[(x, p)] - counts[(y, p)]) / N_DRAWS for p in probs]
    rng = random.Random(seed)
    means = sorted(sum(rng.choices(d, k=len(d))) / len(d) for _ in range(reps))
    return sum(d) / len(d), means[int(0.025 * reps)], means[int(0.975 * reps) - 1]


def verdict(p_holm: float, mean: float, lo: float, hi: float) -> str:
    """Verdict word for the primary comparison (see the module docstring)."""
    if p_holm < 0.05 and lo > 0 and mean > 0:
        return "USEFUL" if lo >= MIN_GAIN else "POSSIBLY GOOD"
    if hi < MIN_GAIN:
        return "DISMISSED"
    return "INCONCLUSIVE"


def llm6(w_row: TestRow, use_rate: float) -> bool:
    """W minus A2 is negative on MAJ (W-only problems fewer than A2-only, the same counts as p)."""
    return w_row.p_holm < 0.05 and w_row.x_only < w_row.y_only and use_rate > 0.5


def excluded_w(path: Path) -> frozenset[str]:
    """Problems marked ``excluded`` in ``wrong_overlap.csv`` (empty set when the file is absent)."""
    if not path.exists():
        return frozenset()
    with path.open(encoding="utf-8", newline="") as fh:
        return frozenset(r["problem"] for r in csv.DictReader(fh) if r["status"] == "excluded")


def with_claims(kinds: dict[str, dict[str, dict[str, str]]]) -> set[str]:
    """Problems that have at least one v2 claim (B2 differs from A2 by more than its text)."""
    return {p for p, k in kinds.get("B2", {}).items() if k}


def rate_table(counts: dict[tuple[str, str], int], quart: dict[str, str]) -> list[str]:
    out = ["| stratum | arm | problems | pass@1 | pass@3 | MAJ (>=2 of 3) |",
           "| --- | --- | --- | --- | --- | --- |"]
    for label, qs in (*[(q, (q,)) for q in STRATA], ("all", STRATA)):
        probs = sorted(p for p in quart if quart[p] in qs)
        for a in ARMS:
            cs = [counts[(a, p)] for p in probs]
            p1 = sum(c / N_DRAWS for c in cs) / len(cs)
            p3 = sum(1 for c in cs if c >= 1) / len(cs)
            maj = sum(1 for c in cs if c >= 2)
            out.append(f"| {label} | {a} | {len(cs)} | {p1:.3f} | {p3:.3f} | "
                       f"{maj}/{len(cs)} ({maj / len(cs):.2f}) |")
    return out


def use_rates(rows: list[dict[str, str]]) -> dict[str, tuple[int, int, int]]:
    """Per hint arm: (calls with a CLAIMS-USED line naming a claim, with the line, all calls)."""
    out = {a: (0, 0, 0) for a in HINT_ARMS}
    for r in rows:
        if r["arm"] not in HINT_ARMS:
            continue
        u, line, n = out[r["arm"]]
        out[r["arm"]] = (u + (r["used"] == "1"), line + (r["used"] != ""), n + 1)
    return out


def kind_table(rows: list[dict[str, str]], kinds: dict[str, dict[str, dict[str, str]]],
               arm: str) -> list[str]:
    """Pass rate of the calls of ``arm`` that named a claim of a kind, per kind, against the calls
    of the arm that named no claim of that kind (counts, not tested)."""
    per: dict[str, list[tuple[bool, bool]]] = {}
    for r in rows:
        if r["arm"] != arm or r["used"] == "":
            continue
        named = {kinds[arm].get(r["problem"], {}).get(i) for i in r["claims_used"].split(";") if i}
        offered = set(kinds[arm].get(r["problem"], {}).values())
        for kind in offered:
            per.setdefault(kind, []).append((kind in named, r["pass"] == "1"))
    out = [f"| kind ({arm}) | calls using it | pass | calls offered it, not using | pass |",
           "| --- | --- | --- | --- | --- |"]
    for kind in sorted(per):
        used = [p for u, p in per[kind] if u]
        unused = [p for u, p in per[kind] if not u]
        out.append(f"| {kind} | {len(used)} | {sum(used)} | {len(unused)} | {sum(unused)} |")
    return out


def render(counts: dict[tuple[str, str], int], quart: dict[str, str],
           rows: list[dict[str, str]], kinds: dict[str, dict[str, dict[str, str]]],
           skip_w: frozenset[str] = frozenset()) -> str:
    probs = sorted(quart)
    out = [f"# Hints v2 summary ({len(probs)} problems, 3 draws, strict: no pass = fail)", "",
           "## pass@k per arm and quartile", "", *rate_table(counts, quart), "",
           "## Mean pass@1 difference (problem-level bootstrap 95% interval, seed fixed)", ""]
    cis = {}
    for x, y in (*COMPARISONS, ("B1p", "A2")):
        cis[(x, y)] = boot_ci(counts, probs, x, y)
        m, lo, hi = cis[(x, y)]
        out.append(f"- {x} minus {y}: {m:+.3f} [{lo:+.3f}, {hi:+.3f}]")
    maj = tests(counts, quart, "MAJ", skip_w)
    sub = {p: q for p, q in quart.items() if p in with_claims(kinds)}
    sec = tests(counts, sub, "MAJ", skip_w) if sub else []
    for title, table in (("primary: at least 2 of 3 draws", maj),
                         ("secondary: any draw passes", tests(counts, quart, "ANY", skip_w)),
                         (f"secondary, pre-stated: the {len(sub)} problems with v2 claims, at "
                          "least 2 of 3 draws (own Holm family)", sec)):
        out += ["", f"## Paired tests, {title} (Holm over {len(table)})", "",
                "| comparison | stratum | problems | first only | second only | p | p (Holm) |",
                "| --- | --- | --- | --- | --- | --- | --- |"]
        out += [f"| {r.cmp} | {r.stratum} | {r.n} | {r.x_only} | {r.y_only} | {r.p:.4f} | "
                f"{r.p_holm:.4f} |" for r in table]
    prim = next(r for r in maj if r.cmp == "B2 vs A2" and r.stratum.startswith("all"))
    wrow = next(r for r in maj if r.cmp == "W vs A2" and r.stratum.startswith("all"))
    m, lo, hi = cis[("B2", "A2")]
    rates = use_rates(rows)
    out += ["", "## Verdicts (rule fixed in EXPERIMENT.md)", "",
            f"- LLM5, B2 vs A2: {verdict(prim.p_holm, m, lo, hi)} (mean {m:+.3f} "
            f"[{lo:+.3f}, {hi:+.3f}], stratified Holm p {prim.p_holm:.4f}, minimum gain "
            f"{MIN_GAIN:+.2f})"]
    u, line, n = rates["B2"]
    wm = cis[("W", "A2")][0]
    word = "supported" if llm6(wrow, u / n if n else 0) else "not supported"
    out.append(f"- LLM6, W vs A2: {word} (MAJ: W only {wrow.x_only}, A2 only {wrow.y_only}; "
               f"stratified Holm p {wrow.p_holm:.4f}; B2 use rate {u}/{n}; pass@1 W minus A2 "
               f"{wm:+.3f} over all problems; {len(skip_w)} problems left out of the W tests)")
    if sec:
        s2 = next(r for r in sec if r.cmp == "B2 vs A2" and r.stratum.startswith("all"))
        out.append(f"- Secondary (problems with claims), B2 vs A2: MAJ B2 only {s2.x_only}, A2 "
                   f"only {s2.y_only}, stratified Holm p {s2.p_holm:.4f} (not a verdict)")
    out += ["", "## Use of the claims (CLAIMS-USED line)", "",
            "| arm | calls naming a claim | calls with the line | calls |",
            "| --- | --- | --- | --- |"]
    out += [f"| {a} | {u} | {line} | {n} |" for a, (u, line, n) in rates.items()]
    for arm in HINT_ARMS:
        out += ["", *kind_table(rows, kinds, arm)]
    return "\n".join(out) + "\n"


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--results", type=Path, required=True)
    ap.add_argument("--kinds", type=Path, default=HERE / "claim_kinds.json")
    ap.add_argument("--excluded", type=Path, default=HERE / "wrong_overlap.csv")
    ap.add_argument("--out", type=Path, default=None)
    a = ap.parse_args(argv)
    counts, quart, rows = load(a.results)
    kinds = json.loads(a.kinds.read_text(encoding="utf-8")) if a.kinds.exists() else {
        arm: {} for arm in HINT_ARMS}
    text = render(counts, quart, rows, kinds, excluded_w(a.excluded))
    if a.out:
        a.out.write_text(text, encoding="utf-8", newline="\n")
    sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
