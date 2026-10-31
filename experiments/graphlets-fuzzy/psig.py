"""Dump full partition signatures (bounded cones, both modes): ``python -B psig.py [JOBS]``.

Reuses graphlets/partitions.py (bounded cones). Output: $GLET_OUT/fuzzy/part_sigs.jsonl, one
line per
(set, design, cell, mode, group) with orbit_totals and gdd, the flip-flop count and the links.
"""

from __future__ import annotations

import json
import os
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "graphlets"))
os.environ["GLET_BOUNDED"] = "1"
import partitions as pt  # noqa: E402

OUT = pt.OUT / "fuzzy"


def one(job: tuple[str, str, str, str, str]) -> list[dict[str, Any]]:
    kind, name, cell, net, intent = job
    claims = json.loads(Path(intent).read_text(encoding="utf-8"))["claims"]
    qgroups = pt.state_groups(claims)
    rows: list[dict[str, Any]] = []
    for rec in pt.partitions_of(Path(net), qgroups, True):
        for mode in ("undirected", "directed"):
            row: dict[str, Any] = {"set": kind, "design": name, "cell": cell, "mode": mode,
                                   "gi": rec["gi"], "ff": rec["ff"], "n_groups": len(qgroups),
                                   "links": rec.get("links", [])}
            if "error" in rec or mode not in rec:
                row["error"] = rec.get("error", "")
            else:
                g = rec[mode]
                row.update(nodes=g["nodes"], edges=g["edges"], orbit_totals=g["orbit_totals"],
                           gdd=g["gdd"])
            rows.append(row)
    if not qgroups:
        rows.append({"set": kind, "design": name, "cell": cell, "mode": "none", "n_groups": 0})
    return rows


def main(argv: list[str]) -> int:
    n = int(argv[0]) if argv else 10
    todo = pt.jobs()
    OUT.mkdir(exist_ok=True)
    dest = OUT / "part_sigs.jsonl"
    with ProcessPoolExecutor(n) as pool, dest.open("w", encoding="utf-8") as fh:
        for rows in pool.map(one, todo, chunksize=2):
            for r in rows:
                fh.write(json.dumps(r, sort_keys=True) + "\n")
    print(len(todo), "designs done")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
