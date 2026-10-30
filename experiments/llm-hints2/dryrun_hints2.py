"""Dry run without a model: fake replies go through outbox, collect, score and the analysis.

Usage: ``python -I dryrun_hints2.py`` (after ``build_hints2.py``). Works in ``run-dry/``
(``calls.jsonl`` copied, ``prompts`` linked from ``run/``). Six problems (three of Q3, three of Q4)
get the reference solution as ``TopModule`` or a deliberately bad reply by a fixed pattern over
the arms and draws; hint-arm replies carry a CLAIMS-USED line (ids, ``none`` or none at all).
Every other call has no reply (``not_run``). Checks: outcomes as expected, 0 timeouts, pass counts
per (arm, problem), the CLAIMS-USED fields, the paired tests and the verdict run. Writes
``dryrun_result.json``; exit 1 on any mismatch.
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
os.environ["LLM_HINTS2_RUN"] = str(DRY)
sys.path.insert(0, str(HERE))
hintscfg: Any = importlib.import_module("hintscfg")
pilot_dry: Any = importlib.import_module("dryrun")
collect_h2: Any = importlib.import_module("collect_hints2")
analyze_h2: Any = importlib.import_module("analyze_hints2")

ARMS = ("A2", "B1p", "B2", "W")
# pass pattern over draws 1..3 per problem index; arms B2 and A2 follow it, W passes one draw less
PATTERNS = [(1, 1, 1), (1, 1, 0), (1, 0, 0), (0, 0, 0), (1, 1, 1), (0, 0, 1)]
BAD = ("runtime", "syntax", "no-output")
USED = {"B1p": "CLAIMS-USED: h1", "B2": "CLAIMS-USED: h2,h4", "W": "CLAIMS-USED: none"}


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
    for q in ("Q3", "Q4", "Q3", "Q4", "Q3", "Q4"):
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
    return ok and (arm != "W" or draw != 3)


def reply_for(ok: bool, arm: str, problem: str, kind: str) -> str:
    text = str(pilot_dry.wrapped(pilot_dry.top_of(problem))) if ok else bad_reply(problem, kind)
    if arm in USED and "[DONE]" in text:
        text += USED[arm] + "\n"
    return text


def main() -> int:
    DRY.mkdir(exist_ok=True)
    shutil.copyfile(HERE / "run" / "calls.jsonl", DRY / "calls.jsonl")
    link = DRY / "prompts"
    if not link.exists():
        link.symlink_to(HERE / "run" / "prompts")
    probs = pick_problems()
    expect: dict[int, tuple[str, str]] = {}
    for c in collect_h2.load_calls():
        if c["problem"] not in probs:
            continue
        idx = probs.index(c["problem"])
        ok = expected_pass(idx, c["arm"], c["draw"])
        kind = BAD[c["call"] % 3]
        out = DRY / c["outbox_file"]
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(reply_for(ok, c["arm"], c["problem"], kind), encoding="utf-8", newline="\n")
        expect[c["call"]] = ("pass" if ok else kind, c["problem"])
    rows = collect_h2.run_all({})
    collect_h2.write_results(rows, DRY / "results.csv")
    got = {r["call"]: r for r in rows}
    bad = [(k, v[0], got[k]["outcome"]) for k, v in expect.items() if got[k]["outcome"] != v[0]]
    used_bad = [k for k in expect if got[k]["arm"] in USED and got[k]["outcome"] == "pass"
                and got[k]["used"] != (0 if got[k]["arm"] == "W" else 1)]
    timeouts = sum(1 for r in rows if r["outcome"] in ("timeout", "compile-timeout"))
    counts, quart, res_rows = analyze_h2.load(DRY / "results.csv")
    wrong_counts = [(a, p) for i, p in enumerate(probs) for a in ARMS
                    if counts[(a, p)] != sum(expected_pass(i, a, d) for d in (1, 2, 3))]
    kinds = json.loads((HERE / "claim_kinds.json").read_text(encoding="utf-8"))
    summary = analyze_h2.render(counts, quart, res_rows, kinds)
    (DRY / "summary.md").write_text(summary, encoding="utf-8", newline="\n")
    p1 = {a: sum(counts[(a, p)] / 3 for p in probs) / len(probs) for a in ARMS}
    report = {"calls": len(rows), "replies": len(expect),
              "not_run": sum(1 for r in rows if r["status"] == "not_run"),
              "unexpected_outcomes": bad, "wrong_counts": wrong_counts,
              "wrong_used_fields": used_bad, "timeouts": timeouts, "problems": probs,
              "pass_at_1_dry_set": {a: round(v, 4) for a, v in p1.items()}}
    (HERE / "dryrun_result.json").write_text(json.dumps(report, sort_keys=True, indent=1) + "\n",
                                             encoding="utf-8", newline="\n")
    print(json.dumps(report, sort_keys=True))
    return 0 if not bad and not wrong_counts and not used_bad and timeouts == 0 and \
        len(expect) == 4 * 6 * 3 and quart else 1


if __name__ == "__main__":
    sys.exit(main())
