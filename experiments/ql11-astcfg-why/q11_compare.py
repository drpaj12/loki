"""Paired comparison of every LLM arm against arm A: pass@1, AST, CFG (no model call).

Inputs: the re-scored AST/CFG rows ($QL11_OUT/rescore/shard*.csv, written by q11_rescore.py; arms of
llm-full and llm-hints2), the Q-L10 rows of arms D and Dh (results/astcfg_rows.csv of ql10-blocks,
scored with the same Scorer), and the results.csv of each experiment (pass per arm, problem, draw).
Pairing: same problem and same draw. Per problem the difference is the mean over the common draws;
the bootstrap (seed 20261103, 2000 resamples) resamples problems. W/L/T counts draws and problems
(a tie is a difference under 1e-9). Label: BETTER or WORSE when the 95 percent CI excludes zero,
else INCONCLUSIVE. Writes results/paired.csv.
Variants: ``flat`` = both sides written by the same Odin III writer (headline); ``raw`` = as the
model wrote it (D: ``asm``, the assembled design, top module only).
Usage: python -B q11_compare.py
"""

from __future__ import annotations

import csv
import random
from collections import defaultdict
from pathlib import Path
from typing import Any

import q11_env as env

Vals = dict[tuple[str, str], dict[int, float]]  # (arm, problem) -> draw -> value
# (experiment, arm, reference arm, reference experiment, comparison)
PAIRS = (("llm-full", "B", "A", "llm-full", "B (Loki hints v1) vs A"),
         ("llm-full", "C", "A", "llm-full", "C (interface only) vs A"),
         ("llm-hints2", "B1p", "A2", "llm-hints2", "B1p (v1 hints, new prompt) vs A2"),
         ("llm-hints2", "B2", "A2", "llm-hints2", "B2 (Loki hints v2) vs A2"),
         ("llm-hints2", "W", "A2", "llm-hints2", "W (wrong hints) vs A2"),
         ("ql10", "D", "A", "llm-full", "D (Loki blocks) vs A"),
         ("ql10", "Dh", "A", "llm-full", "D+h (Loki blocks + kind guess) vs A"))
METRICS = ("pass", "ast", "cfg")


def read(p: Path) -> list[dict[str, str]]:
    with p.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def load_scores() -> dict[tuple[str, str, str], Vals]:
    """(exp, variant, metric) -> Vals for ast and cfg."""
    out: dict[tuple[str, str, str], Vals] = defaultdict(lambda: defaultdict(dict))
    rows = [r for p in sorted((env.OUT11 / "rescore").glob("shard*.csv")) for r in read(p)]
    for r in rows:
        for m in ("ast", "cfg"):
            if r[m] != "":
                out[(r["exp"], r["variant"], m)][(r["arm"], r["problem"])][int(r["draw"])] = \
                    float(r[m])
    for r in read(env.EXP / "ql10-blocks" / "results" / "astcfg_rows.csv"):
        if r["arm"] not in ("D", "Dh"):
            continue
        var = "raw" if r["variant"] == "asm" else r["variant"]
        for m in ("ast", "cfg"):
            if r[m] != "":
                out[("ql10", var, m)][(r["arm"], r["problem"])][int(r["draw"])] = float(r[m])
    return out


def load_pass() -> dict[str, Vals]:
    out: dict[str, Vals] = {}
    for exp, p in (("llm-full", env.EXP / "llm-full" / "results" / "results.csv"),
                   ("llm-hints2", env.EXP / "llm-hints2" / "results" / "results.csv"),
                   ("ql10", env.EXP / "ql10-blocks" / "results" / "results.csv")):
        v: Vals = defaultdict(dict)
        for r in read(p):
            if r.get("outcome") == "not_run":
                continue
            v[(r["arm"], r["problem"])][int(r["draw"])] = float(r["pass"])
        out[exp] = v
    return out


def paired(a: Vals, b: Vals, arm_a: str, arm_b: str) -> dict[str, dict[int, float]]:
    """problem -> draw -> difference a minus b, over the common draws."""
    out: dict[str, dict[int, float]] = {}
    for (arm, prob), da in a.items():
        if arm != arm_a:
            continue
        db = b.get((arm_b, prob))
        if not db:
            continue
        common = sorted(set(da) & set(db))
        if common:
            out[prob] = {d: da[d] - db[d] for d in common}
    return out


def summarise(diffs: dict[str, dict[int, float]], a: Vals, b: Vals, arm_a: str,
              arm_b: str) -> dict[str, Any]:
    probs = sorted(diffs)
    per = [sum(diffs[p].values()) / len(diffs[p]) for p in probs]
    dl = [v for p in probs for v in diffs[p].values()]
    rng = random.Random(env.SEED)
    boots = sorted(sum(per[rng.randrange(len(per))] for _ in per) / len(per)
                   for _ in range(env.BOOT))
    lo, hi = boots[int(0.025 * env.BOOT)], boots[int(0.975 * env.BOOT) - 1]

    def wlt(xs: list[float]) -> str:
        return f"{sum(x > 1e-9 for x in xs)}/{sum(x < -1e-9 for x in xs)}/" \
               f"{sum(abs(x) <= 1e-9 for x in xs)}"

    def mean(v: Vals, arm: str) -> float:
        xs = [sum(v[(arm, p)][d] for d in diffs[p]) / len(diffs[p]) for p in probs]
        return sum(xs) / len(xs)

    return {"problems": len(probs), "draws": len(dl), "mean_arm": round(mean(a, arm_a), 4),
            "mean_ref": round(mean(b, arm_b), 4), "diff": round(sum(per) / len(per), 4),
            "ci_lo": round(lo, 4), "ci_hi": round(hi, 4), "draws_WLT": wlt(dl),
            "problems_WLT": wlt(per),
            "label": "BETTER" if lo > 0 else ("WORSE" if hi < 0 else "INCONCLUSIVE")}


def main() -> int:
    scores, passes = load_scores(), load_pass()
    rows: list[dict[str, Any]] = []
    for exp, arm, ref, refexp, name in PAIRS:
        for variant in ("flat", "raw"):
            for m in METRICS:
                if m == "pass":
                    if variant == "raw":
                        continue
                    a, b = passes[exp], passes[refexp]
                    note = "pass (strict scorer)"
                else:
                    a, b = scores[(exp, variant, m)], scores[(refexp, variant, m)]
                    note = m.upper()
                d = paired(a, b, arm, ref)
                if not d:
                    continue
                rows.append({"endpoint": "gates", "comparison": name, "metric": note,
                             "writer": "n/a" if m == "pass" else
                             ("same writer (flat)" if variant == "flat" else "as written"),
                             **summarise(d, a, b, arm, ref)})
    with (env.RES / "paired.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, list(rows[0]), lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
