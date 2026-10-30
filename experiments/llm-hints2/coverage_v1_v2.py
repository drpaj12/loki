"""v1 against v2 claims on the 64 problems: coverage per kind, readable FSMs, roles, buses.

Usage: ``python -I coverage_v1_v2.py``. Reads the v1 runs (``run/hints/<p>/out/
reverse-provenance.json``, committed and candidate claims) and the v2 intents
(``run/hints2/<p>/intent.json``). Writes ``coverage_v1_v2.csv``: per row a measure, its v1 and its
v2 value. A problem counts for a kind when it has at least one claim of that kind.
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
KINDS = ("fsm", "counter", "shift_reg", "lfsr", "register", "bus")


def load(root: Path, name: str, p: str) -> dict[str, Any]:
    obj: dict[str, Any] = json.loads((root / p / name).read_text(encoding="utf-8"))
    return obj


def main() -> int:
    with (HERE / "selection.csv").open(encoding="utf-8", newline="") as fh:
        probs = [r["problem"] for r in csv.DictReader(fh)]
    v1 = {p: load(HERE / "run" / "hints", "out/reverse-provenance.json", p) for p in probs}
    v2 = {p: load(HERE / "run" / "hints2", "intent.json", p) for p in probs}
    keep = ("committed", "candidate")
    rows: list[tuple[str, object, object]] = []
    n1 = sum(1 for p in probs for e in v1[p]["elements"] if e["status"] in keep)
    n2 = sum(len(v2[p]["claims"]) for p in probs)
    rows.append(("claims (all kinds)", n1, n2))
    for kind in KINDS:
        a = sum(1 for p in probs if any(e["kind"] == kind and e["status"] in keep
                                       for e in v1[p]["elements"]))
        b = sum(1 for p in probs if any(c["kind"] == kind for c in v2[p]["claims"]))
        rows.append((f"problems with a {kind} claim", a, b))
    fsm_v1 = sum(1 for p in probs for f in v1[p]["fsms"] if f["states"] > 0 and f["transitions"])
    fsm_all = sum(len(v1[p]["fsms"]) for p in probs)
    rows.append(("FSM claims with states and transitions (v1: of "
                 f"{fsm_all} fsm rows)", fsm_v1, sum(
                     1 for p in probs for c in v2[p]["claims"] if c["kind"] == "fsm")))
    rows.append(("problems with an empty-claims hint block",
                 sum(1 for p in probs if not any(e["status"] in keep for e in v1[p]["elements"])),
                 sum(1 for p in probs if not v2[p]["claims"])))
    ctrl1 = sum(1 for p in probs for e in v1[p]["elements"]
                if e["status"] in keep and e["role"] == "control")
    ctrl2 = sum(1 for p in probs for c in v2[p]["claims"] if c.get("role") == "control")
    rows.append(("claims with role control", ctrl1, ctrl2))
    rows.append(("problems with a bus that has a purpose link", 0,
                 sum(1 for p in probs if any(b["links"] for b in v2[p]["buses"]))))
    rows.append(("problems with any bus claim or bus", sum(
        1 for p in probs if v1[p]["buses"]), sum(1 for p in probs if v2[p]["buses"])))
    rows.append(("claims with a calibrated p printed", "0 (calib none)",
                 sum(1 for p in probs for c in v2[p]["claims"] if c["p"] is not None)))
    with (HERE / "coverage_v1_v2.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(["measure", "v1", "v2"])
        w.writerows(rows)
    for r in rows:
        print(r)
    return 0


if __name__ == "__main__":
    sys.exit(main())
