"""Place replies, collect and score per draw; read the CLAIMS-USED line. No model call.

Usage: ``python -I collect_hints2.py [--status status.csv] [--out results.csv]``. Steps as
``llm-full/collect_full.py``: outbox files are copied to the call's ``reply_path``, each draw is
staged and collected with the pilot's ``collect.py``, scored with the pilot's ``score.py`` (strict
``pass``, unchanged), and ``results.csv`` gets one row per call. Added columns: ``claims_used``
(ids, ``;``-joined) and ``used`` (1 when the last line after [DONE] names at least one claim, 0 for
``none``, empty when the line is missing or the arm has no claims). A call with no reply is
``not_run`` unless ``--status`` gives its status.
"""

from __future__ import annotations

import argparse
import csv
import importlib
import json
import re
import shutil
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
hintscfg: Any = importlib.import_module("hintscfg")
collect: Any = importlib.import_module("collect")
score: Any = importlib.import_module("score")

RUN: Path = hintscfg.RUN
FIELDS = ["call", "draw", "arm", "problem", "quartile", "status", "outcome", "pass", "gb_pass",
          "mismatches", "samples", "claims_used", "used"]
HINT_ARMS = ("B1p", "B2", "W")
_USED = re.compile(r"^\s*CLAIMS-USED:\s*(.*?)\s*$", re.I | re.M)
_ID = re.compile(r"\bh\d+\b")


def claims_used(reply: str) -> list[str] | None:
    """Ids on the last CLAIMS-USED line after the last [DONE]; [] for ``none``; None when the
    line is missing."""
    tail = reply.rsplit("[DONE]", 1)[-1]
    found = _USED.findall(tail)
    if not found:
        return None
    return sorted(set(_ID.findall(found[-1])), key=lambda i: int(i[1:]))


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
    stage.mkdir(parents=True, exist_ok=True)
    return stage


def read_status(path: Path | None) -> dict[int, str]:
    if path is None:
        return {}
    with path.open(encoding="utf-8", newline="") as fh:
        return {int(r["call"]): r["status"] for r in csv.DictReader(fh)}


def used_fields(c: dict[str, Any]) -> dict[str, Any]:
    if c["arm"] not in HINT_ARMS or not (RUN / c["reply_path"]).exists():
        return {"claims_used": "", "used": ""}
    ids = claims_used((RUN / c["reply_path"]).read_text(encoding="utf-8", errors="replace"))
    if ids is None:
        return {"claims_used": "", "used": ""}
    return {"claims_used": ";".join(ids), "used": int(bool(ids))}


def run_all(status: dict[int, str]) -> list[dict[str, Any]]:
    calls = load_calls()
    place_replies(calls)
    rows: list[dict[str, Any]] = []
    for d in hintscfg.DRAWS:
        stage = stage_draw(calls, d)
        out = RUN / "records" / str(d)
        collect.collect(RUN / f"calls-draw{d}.jsonl", stage, out)
        res = {(r["arm"], r["problem"]): r for r in score.score_all(out, [])}
        for c in (x for x in calls if x["draw"] == d):
            r = res.get((c["arm"], c["problem"]))
            base = {"call": c["call"], "draw": d, "arm": c["arm"], "problem": c["problem"],
                    "quartile": c["quartile"], **used_fields(c)}
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
