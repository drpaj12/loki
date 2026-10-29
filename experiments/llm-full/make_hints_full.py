"""Arm B hints for the full population (the pilot's make_hints, unchanged, per problem).

Usage: ``python -I make_hints_full.py``. Needs ``ODIN3_ROOT`` (default ``<workspace>/odin3``) and
cffi. Writes ``run/hints/<problem>/hints.md`` and ``hints_stats.csv``. A problem whose hints fail
(Loki or Odin III raises) is logged in ``hint_failures.csv`` with the error; it is not retried.
Problems with a ``hints.md`` already are skipped, so a rerun resumes.
"""

from __future__ import annotations

import csv
import importlib
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
fullcfg: Any = importlib.import_module("fullcfg")
make_hints: Any = importlib.import_module("make_hints")


def rebuild_stats() -> None:
    """hints_stats.csv from the per-problem json files (covers resumed runs)."""
    rows = []
    for p in make_hints.selected():
        j = fullcfg.RUN / "hints" / p / "hints_stats.json"
        if j.exists():
            rows.append(json.loads(j.read_text(encoding="utf-8")))
    with (fullcfg.FULL / "hints_stats.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, make_hints.FIELDS, lineterminator="\n")
        w.writeheader()
        w.writerows({k: r.get(k, "") for k in make_hints.FIELDS} for r in rows)


def main() -> int:
    fails: list[tuple[str, str]] = []
    for p in make_hints.selected():
        if (fullcfg.RUN / "hints" / p / "hints.md").exists():
            continue
        try:
            make_hints.main(["--problems", p])
        except (RuntimeError, ValueError) as exc:
            fails.append((p, str(exc).replace("\n", " ")[:300]))
            print(f"{p}: FAILED", flush=True)
    path = fullcfg.FULL / "hint_failures.csv"
    old = []
    if path.exists():
        with path.open(encoding="utf-8", newline="") as fh:
            old = [(r["problem"], r["error"]) for r in csv.DictReader(fh)]
    merged = dict(old) | dict(fails)
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(["problem", "error"])
        w.writerows(sorted(merged.items()))
    rebuild_stats()
    print(f"{len(fails)} failures")
    return 0


if __name__ == "__main__":
    sys.exit(main())
