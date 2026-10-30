"""A3 numbers: v1 claims per problem (reverse-provenance elements, status committed or candidate)
and how many remain after ``loki.intent.dedupe.merge_duplicates``.

Usage: ``python -I dedupe_stats.py`` (reads ``run/hints/<problem>/out/reverse-provenance.json``,
the v1 runs made by ``make_hints.py``). Writes ``dedupe_stats.csv``.
"""

from __future__ import annotations

import csv
import importlib
import json
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))
merge_duplicates = importlib.import_module("loki.intent.dedupe").merge_duplicates


def as_claims(rp: dict[str, Any]) -> list[dict[str, Any]]:
    keep = ("committed", "candidate")
    return [{"id": e["id"], "kind": e["kind"], "nets": e["nets"], "p": e["p_comp"],
             "params": e["params"], "wires": []} for e in rp["elements"] if e["status"] in keep]


def main() -> int:
    rows: list[dict[str, Any]] = []
    with (HERE / "selection.csv").open(encoding="utf-8", newline="") as fh:
        problems = [r["problem"] for r in csv.DictReader(fh)]
    for p in problems:
        rp = json.loads((HERE / "run" / "hints" / p / "out" / "reverse-provenance.json")
                        .read_text(encoding="utf-8"))
        claims = as_claims(rp)
        merged = merge_duplicates(claims)
        rows.append({"problem": p, "v1_claims": len(claims), "v2_claims": len(merged),
                     "merged_away": len(claims) - len(merged)})
    with (HERE / "dedupe_stats.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, list(rows[0]), lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    tot1 = sum(int(r["v1_claims"]) for r in rows)
    tot2 = sum(int(r["v2_claims"]) for r in rows)
    print(f"{len(rows)} problems: {tot1} v1 claims -> {tot2} after dedupe "
          f"({tot1 - tot2} merged away)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
