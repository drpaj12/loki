"""Pass rates, quartiles, exact McNemar tests and `standard` against `re` from status/results CSVs.

Usage: ``python -I pilot_stats.py --run RUN_DIR --standard STD_DIR`` where each dir holds
``status.csv`` and ``results.csv`` (the tracked ``results/<run>/`` copies). Prints Markdown.
Pass is the strict scorer (``pass`` column); the Gate-Breaker-equivalent count is added as a
cross-check. Tests: exact two-sided McNemar on discordant pairs of the paired problem set.
"""

from __future__ import annotations

import argparse
import csv
import sys
from math import comb
from pathlib import Path

ARMS = "ABC"


def read(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def mcnemar(b: int, c: int) -> float:
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    return min(1.0, 2 * sum(comb(n, i) for i in range(k + 1)) / 2**n)


def load(d: Path) -> tuple[dict[tuple[str, str], str], dict[tuple[str, str], dict[str, str]]]:
    st = {(r["arm"], r["problem"]): r["status"] for r in read(d / "status.csv")}
    res = {(r["arm"], r["problem"]): r for r in read(d / "results.csv")}
    return st, res


def passed(res: dict[tuple[str, str], dict[str, str]], a: str, p: str, col: str = "pass") -> bool:
    r = res.get((a, p))
    return bool(r) and r[col] in ("1", "True", "true")


def frac(n: int, d: int) -> str:
    return f"{n}/{d} ({n / d:.2f})" if d else "n/a"


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--run", type=Path, required=True)
    ap.add_argument("--standard", type=Path, required=True)
    ap.add_argument("--selection", type=Path, default=Path(__file__).with_name("selection.csv"))
    a = ap.parse_args(argv)
    quart = {r["problem"]: r["quartile"] for r in read(a.selection)}
    probs = sorted(quart)
    st, res = load(a.run)
    paired = [p for p in probs if all(st[(x, p)] == "ok" for x in ARMS)]
    out = []
    out += ["### Pass rate per arm", "",
            "| view | arm A | arm B | arm C |", "| --- | --- | --- | --- |"]
    for col, tag in (("pass", "strict"), ("gb_pass", "Gate-Breaker-equivalent")):
        row = [frac(sum(passed(res, x, p, col) for p in probs), len(probs)) for x in ARMS]
        out.append(f"| all calls, no-file = fail ({tag}) | " + " | ".join(row) + " |")
    ans = [[p for p in probs if st[(x, p)] == "ok"] for x in ARMS]
    out.append("| answered only (strict) | " + " | ".join(
        frac(sum(passed(res, x, p) for p in ps), len(ps)) for x, ps in zip(ARMS, ans, strict=True)) + " |")
    for col, tag in (("pass", "strict"), ("gb_pass", "Gate-Breaker-equivalent")):
        row = [frac(sum(passed(res, x, p, col) for p in paired), len(paired)) for x in ARMS]
        out.append(f"| paired set, {len(paired)} problems ({tag}) | " + " | ".join(row) + " |")
    out += ["", "### Pass rate per quartile (strict)", "",
            "| quartile | view | arm A | arm B | arm C |", "| --- | --- | --- | --- | --- |"]
    for q in ("Q1", "Q2", "Q3", "Q4"):
        qp = [p for p in probs if quart[p] == q]
        qpair = [p for p in paired if quart[p] == q]
        out.append(f"| {q} | all calls | " + " | ".join(
            frac(sum(passed(res, x, p) for p in qp), len(qp)) for x in ARMS) + " |")
        out.append(f"| {q} | paired | " + " | ".join(
            frac(sum(passed(res, x, p) for p in qpair), len(qpair)) for x in ARMS) + " |")
    out += ["", f"### Paired tests (exact McNemar, two-sided, paired set n = {len(paired)}, "
            "strict)",
            "", "| comparison | both pass | first only | second only | neither | p |",
            "| --- | --- | --- | --- | --- | --- |"]
    for x, y in (("B", "A"), ("A", "C"), ("B", "C")):
        both = sum(passed(res, x, p) and passed(res, y, p) for p in paired)
        xo = sum(passed(res, x, p) and not passed(res, y, p) for p in paired)
        yo = sum(passed(res, y, p) and not passed(res, x, p) for p in paired)
        out.append(f"| {x} vs {y} | {both} | {xo} | {yo} | {len(paired) - both - xo - yo} | "
                   f"{mcnemar(xo, yo):.4f} |")
    sst, sres = load(a.standard)
    out += ["", "### Refusal and no-file rate", "",
            "| run | arm | calls made | ok | refused | no-file | refused + no-file |",
            "| --- | --- | --- | --- | --- | --- | --- |"]
    for name, s in (("standard", sst), ("re", st)):
        for x in ARMS:
            c = {k: sum(1 for p in probs if s[(x, p)] == k) for k in ("ok", "refused", "no-file")}
            made = sum(c.values())
            bad = c["refused"] + c["no-file"]
            out.append(f"| {name} | {x} | {made} | {c['ok']} | {c['refused']} | {c['no-file']} | "
                       f"{frac(bad, made)} |")
    out += ["", "### `standard` against `re`, problems answered (ok) in both runs "
            "(exploratory; the prompts differ)", "",
            "| arm | problems | pass in standard | pass in re | both | standard only | re only |",
            "| --- | --- | --- | --- | --- | --- | --- |"]
    for x in ARMS:
        both_ok = [p for p in probs if sst[(x, p)] == "ok" and st[(x, p)] == "ok"]
        s = sum(passed(sres, x, p) for p in both_ok)
        r = sum(passed(res, x, p) for p in both_ok)
        bb = sum(passed(sres, x, p) and passed(res, x, p) for p in both_ok)
        out.append(f"| {x} | {len(both_ok)} | {s} | {r} | {bb} | {s - bb} | {r - bb} |")
    sys.stdout.write("\n".join(out) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
