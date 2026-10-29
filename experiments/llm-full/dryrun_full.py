"""Dry run without a model: fake replies go through outbox, collect, score and the analysis.

Usage: ``python -I dryrun_full.py``. Works in ``run-dry/`` (calls.jsonl copied, ``prompts`` linked
from ``run/``). Six problems get reference replies (as TopModule) or deliberately bad ones in the
three draws and three arms by a fixed pattern; every other call has no reply (status not_run).
Checks: outcomes as expected, 0 timeouts, per-problem pass counts, pass@1 and pass@3 means, the
paired tests run. Writes ``dryrun_result.json``; exit 1 on any mismatch.
"""

from __future__ import annotations

import csv
import importlib
import json
import os
import shutil
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
DRY = HERE / "run-dry"
os.environ["LLM_FULL_RUN"] = str(DRY)
sys.path.insert(0, str(HERE))
fullcfg: Any = importlib.import_module("fullcfg")
pilot_dry: Any = importlib.import_module("dryrun")
collect_full: Any = importlib.import_module("collect_full")
analyze_full: Any = importlib.import_module("analyze_full")

# pass pattern over draws 1..3 for arms A and B; arm C passes in draw 1 only where A does
PATTERNS = [(1, 1, 1), (1, 1, 0), (1, 0, 0), (0, 0, 0), (1, 1, 1), (0, 0, 1)]
BAD = ("runtime", "syntax", "no-output")


def bad_reply(problem: str, kind: str) -> str:
    if kind == "runtime":
        return str(pilot_dry.wrapped(pilot_dry.wrong_module(problem)))
    if kind == "syntax":
        broken = "module TopModule(input a; output y)\nassign y = ;\nendmodule"
        return str(pilot_dry.wrapped(broken))
    return "I think the circuit is a gate.\n"


def pick_problems() -> list[str]:
    with (HERE / "selection.csv").open(encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))
    chosen: list[str] = []
    for q in ("Q1", "Q2", "Q3", "Q4", "Q1", "Q2"):
        for r in rows:
            if r["quartile"] == q and r["problem"] not in chosen:
                try:
                    pilot_dry.wrong_module(r["problem"])
                except ValueError:
                    continue
                chosen.append(r["problem"])
                break
    return chosen


def expected_pass(idx: int, arm: str, draw: int) -> bool:
    ok = bool(PATTERNS[idx][draw - 1])
    return ok and (arm != "C" or draw == 1)


def main() -> int:
    DRY.mkdir(exist_ok=True)
    shutil.copyfile(HERE / "run" / "calls.jsonl", DRY / "calls.jsonl")
    link = DRY / "prompts"
    if not link.exists():
        link.symlink_to(HERE / "run" / "prompts")
    probs = pick_problems()
    expect: dict[int, tuple[str, str]] = {}
    for c in collect_full.load_calls():
        if c["problem"] not in probs:
            continue
        idx = probs.index(c["problem"])
        ok = expected_pass(idx, c["arm"], c["draw"])
        kind = BAD[(c["call"]) % 3]
        text = pilot_dry.wrapped(pilot_dry.top_of(c["problem"])) if ok \
            else bad_reply(c["problem"], kind)
        out = DRY / c["outbox_file"]
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding="utf-8", newline="\n")
        expect[c["call"]] = ("pass" if ok else kind, c["problem"])
    rows = collect_full.run_all({})
    collect_full.write_results(rows, DRY / "results.csv")
    got = {r["call"]: r for r in rows}
    bad = [(k, v[0], got[k]["outcome"]) for k, v in expect.items() if got[k]["outcome"] != v[0]]
    not_run = sum(1 for r in rows if r["status"] == "not_run")
    timeouts = sum(1 for r in rows if r["outcome"] in ("timeout", "compile-timeout"))
    counts, quart = analyze_full.load(DRY / "results.csv")
    wrong_counts = [(a, p) for i, p in enumerate(probs) for a in ("A", "B", "C")
                    if counts[(a, p)] != sum(expected_pass(i, a, d) for d in (1, 2, 3))]
    p1 = {a: sum(analyze_full.pass_at_k(3, counts[(a, p)], 1) for p in probs) / len(probs)
          for a in "ABC"}
    p3 = {a: sum(analyze_full.pass_at_k(3, counts[(a, p)], 3) for p in probs) / len(probs)
          for a in "ABC"}
    summary = analyze_full.render(counts, quart)
    (DRY / "summary.md").write_text(summary, encoding="utf-8", newline="\n")
    report = {"calls": len(rows), "replies": len(expect), "not_run": not_run,
              "unexpected_outcomes": bad, "wrong_counts": wrong_counts, "timeouts": timeouts,
              "problems": probs, "pass_at_1_dry_set": {a: round(v, 4) for a, v in p1.items()},
              "pass_at_3_dry_set": {a: round(v, 4) for a, v in p3.items()}}
    (HERE / "dryrun_result.json").write_text(json.dumps(report, sort_keys=True, indent=1) + "\n",
                                             encoding="utf-8", newline="\n")
    print(json.dumps(report, sort_keys=True))
    return 0 if not bad and not wrong_counts and timeouts == 0 and \
        len(expect) == 9 * 6 and quart else 1


if __name__ == "__main__":
    sys.exit(main())
