"""Dry run without a model: references and negative controls go through collect.py and score.py.

Usage: ``python -I dryrun.py``. Arm A answers are the 40 references renamed to ``TopModule`` (all
must pass). Arm B answers are negative controls: an empty-bodied ``TopModule`` for one problem per
quartile (must fail with ``runtime``), a syntax error, a reply without ``[BEGIN]``, and a fenced
reply without markers. Everything goes under ``run/dryrun``; exit 1 when any expectation fails.
"""

from __future__ import annotations

import csv
import importlib
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
common = importlib.import_module("common")
collect = importlib.import_module("collect")
score = importlib.import_module("score")

WRONG = {"Q1": "Prob024_hadd", "Q2": "Prob100_fsm3comb", "Q3": "Prob023_vector100r",
         "Q4": "Prob082_lfsr32"}
SYNTAX, NOOUT, FENCED = "Prob014_andgate", "Prob013_m2014_q4e", "Prob005_notgate"


def top_of(problem: str) -> str:
    ref = (common.dataset_dir() / f"{problem}_ref.sv").read_text(encoding="utf-8")
    return re.sub(r"\bRefModule\b", "TopModule", ref)


def wrapped(code: str) -> str:
    return "// Step 1\n// Step 2\n// Step 3\n// Step 4\n[BEGIN]\n```verilog\n" + code.rstrip() \
        + "\n```\n[DONE]\n"


def wrong_module(problem: str) -> str:
    """The reference's port header with an empty body: outputs undriven, so it must mismatch."""
    code = top_of(problem)
    end = code.find(");")
    if end < 0 or "input" not in code[:end]:
        raise ValueError(f"{problem}: header is not ANSI style")
    return code[: end + 2] + "\nendmodule\n"


def put(root: Path, arm: str, problem: str, text: str) -> None:
    path = root / "responses" / arm / f"{problem}.txt"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def build_responses(root: Path, problems: list[str]) -> dict[tuple[str, str], str]:
    expect: dict[tuple[str, str], str] = {}
    for p in problems:
        put(root, "A", p, wrapped(top_of(p)))
        expect[("A", p)] = "pass"
    for p in WRONG.values():
        put(root, "B", p, wrapped(wrong_module(p)))
        expect[("B", p)] = "runtime"
    put(root, "B", SYNTAX, wrapped("module TopModule(input a; output y)\nassign y = ;\nendmodule"))
    expect[("B", SYNTAX)] = "syntax"
    put(root, "B", NOOUT, "I think the circuit is an inverter.\n")
    expect[("B", NOOUT)] = "no-output"
    put(root, "B", FENCED, "```verilog\n" + top_of(FENCED).rstrip() + "\n```\n")
    expect[("B", FENCED)] = "no-output"
    return expect


def main() -> int:
    root = common.run_dir() / "dryrun"
    with (common.HERE / "selection.csv").open(encoding="utf-8", newline="") as fh:
        problems = [r["problem"] for r in csv.DictReader(fh)]
    expect = build_responses(root, problems)
    info = collect.collect(common.run_dir() / "calls.jsonl", root / "responses", root / "records")
    results = {(r["arm"], r["problem"]): r for r in score.score_all(root / "records", [])}
    bad = [(k, v, results[k]["outcome"]) for k, v in expect.items() if results[k]["outcome"] != v]
    fenced = results[("B", FENCED)].get("fallback_outcome")
    passed = sum(1 for p in problems if results[("A", p)]["pass"])
    wrong_fail = sum(1 for p in WRONG.values() if not results[("B", p)]["pass"])
    report = {"collected": info["collected"], "refs_pass": passed, "refs_total": len(problems),
              "wrong_fail": wrong_fail, "wrong_total": len(WRONG), "unexpected": bad,
              "fenced_fallback_outcome": fenced}
    (root / "dryrun.json").write_text(json.dumps(report, sort_keys=True, indent=1) + "\n",
                                      encoding="utf-8", newline="\n")
    (common.HERE / "dryrun_result.json").write_text(
        json.dumps(report, sort_keys=True, indent=1) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(report, sort_keys=True))
    return 0 if not bad and passed == len(problems) and fenced == "pass" else 1


if __name__ == "__main__":
    sys.exit(main())
