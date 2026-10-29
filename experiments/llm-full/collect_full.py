"""Place replies, collect and score per draw. No model call.

Usage: ``python -I collect_full.py [--status status.csv]``. Steps:
1. every ``run/outbox/resp-NNNN.txt`` (and ``.meta.json``) is copied to the call's ``reply_path``
   ``run/responses/<arm>/<draw>/<problem>.txt`` (the subagent never sees the problem id);
2. per draw, a staging tree ``run/stage/<draw>/<arm>/<problem>.txt`` and the pilot's ``collect.py``
   write ``run/records/<draw>/<arm>/<problem>/``;
3. the pilot's ``score.py`` scores every record;
4. ``run/results.csv`` (one row per call; a call without a reply is ``not_run`` or the status the
   controller gives in ``--status``, columns call,status: ok, api_refused, no_file, not_run).
"""

from __future__ import annotations

import argparse
import csv
import importlib
import json
import shutil
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
fullcfg: Any = importlib.import_module("fullcfg")
collect: Any = importlib.import_module("collect")
score: Any = importlib.import_module("score")

RUN: Path = fullcfg.RUN
FIELDS = ["call", "draw", "arm", "problem", "quartile", "status", "outcome", "pass", "gb_pass",
          "mismatches", "samples"]


def load_calls() -> list[dict[str, Any]]:
    return list(collect.load_calls(RUN / "calls.jsonl"))


def place_replies(calls: list[dict[str, Any]]) -> int:
    n = 0
    for c in calls:
        src = RUN / c["outbox_file"]
        if not src.exists():
            continue
        dst = RUN / c["reply_path"]
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dst)
        meta = src.with_suffix(".meta.json")
        if meta.exists():
            shutil.copyfile(meta, dst.with_suffix(".meta.json"))
        n += 1
    return n


def stage_draw(calls: list[dict[str, Any]], draw: int) -> Path:
    stage = RUN / "stage" / str(draw)
    sub = [c for c in calls if c["draw"] == draw]
    (RUN / f"calls-draw{draw}.jsonl").write_text(
        "".join(json.dumps(c, sort_keys=True) + "\n" for c in sub), encoding="utf-8", newline="\n")
    for c in sub:
        src = RUN / c["reply_path"]
        if src.exists():
            dst = stage / c["arm"] / f"{c['problem']}.txt"
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src, dst)
            meta = src.with_suffix(".meta.json")
            if meta.exists():
                shutil.copyfile(meta, dst.with_suffix(".meta.json"))
    stage.mkdir(parents=True, exist_ok=True)
    return stage


def read_status(path: Path | None) -> dict[int, str]:
    if path is None:
        return {}
    with path.open(encoding="utf-8", newline="") as fh:
        return {int(r["call"]): r["status"] for r in csv.DictReader(fh)}


def run_all(status: dict[int, str]) -> list[dict[str, Any]]:
    calls = load_calls()
    place_replies(calls)
    rows: list[dict[str, Any]] = []
    for d in fullcfg.DRAWS:
        stage = stage_draw(calls, d)
        out = RUN / "records" / str(d)
        collect.collect(RUN / f"calls-draw{d}.jsonl", stage, out)
        res = {(r["arm"], r["problem"]): r for r in score.score_all(out, [])}
        for c in (x for x in calls if x["draw"] == d):
            r = res.get((c["arm"], c["problem"]))
            base = {"call": c["call"], "draw": d, "arm": c["arm"], "problem": c["problem"],
                    "quartile": c["quartile"]}
            if r is None:
                rows.append({**base, "status": status.get(c["call"], "not_run"), "outcome": "",
                             "pass": 0, "gb_pass": 0, "mismatches": -1, "samples": 0})
            else:
                rows.append({**base, "status": "ok", "outcome": r["outcome"],
                             "pass": int(r["pass"]), "gb_pass": int(r["gb_pass"]),
                             "mismatches": r["mismatches"], "samples": r["samples"]})
    return rows


def write_results(rows: list[dict[str, Any]], path: Path) -> None:
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, FIELDS, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--status", type=Path, default=None)
    ap.add_argument("--out", type=Path, default=RUN / "results.csv")
    a = ap.parse_args(argv)
    rows = run_all(read_status(a.status))
    write_results(rows, a.out)
    outcomes: dict[str, int] = {}
    for r in rows:
        key = r["outcome"] or r["status"]
        outcomes[key] = outcomes.get(key, 0) + 1
    timeouts = outcomes.get("timeout", 0) + outcomes.get("compile-timeout", 0)
    print(json.dumps({"calls": len(rows), "outcomes": outcomes, "timeouts": timeouts},
                     sort_keys=True))
    return 0 if timeouts == 0 else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
