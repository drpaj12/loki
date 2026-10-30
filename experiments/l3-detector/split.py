"""Fixed TUNE/TEST split of the labelled census designs: ``python -B split.py``.

Rule: rare patterns are stratified (in the order lfsr, fsm_counter, fsm_shift, timer, shift the
still-unassigned designs of that pattern, sorted by name, alternate TEST, TUNE, TEST, ...), so each
rare pattern has designs on both sides; all other designs: sha256(design name) first 8 hex digits
as an integer, even = TUNE, odd = TEST. Writes results/split_single.csv
(the fixed list; committed with the plan, before any detector run).
"""

from __future__ import annotations

import csv
import hashlib
from pathlib import Path

HERE = Path(__file__).resolve().parent
CENSUS = HERE.parent / "l3-census" / "results" / "labels_rtl.csv"


def side(design: str) -> str:
    return "TUNE" if int(hashlib.sha256(design.encode()).hexdigest()[:8], 16) % 2 == 0 else "TEST"


RARE = ("lfsr", "fsm_counter", "fsm_shift", "timer", "shift")


def assign(rows: list[dict[str, str]]) -> dict[str, str]:
    out: dict[str, str] = {}
    for pat in RARE:
        todo = sorted(r["design"] for r in rows
                      if r[pat] not in ("", "0") and r["design"] not in out)
        for i, d in enumerate(todo):
            out[d] = "TEST" if i % 2 == 0 else "TUNE"
    for r in rows:
        out.setdefault(r["design"], side(r["design"]))
    return out


def main() -> int:
    with CENSUS.open(encoding="utf-8", newline="") as fh:
        rows = [r for r in csv.DictReader(fh) if r["status"] in ("ok", "manual")]
    sp = assign(rows)
    with (HERE / "results" / "split_single.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(["design", "corpus", "split"])
        for r in sorted(rows, key=lambda r: r["design"]):
            w.writerow([r["design"], r["corpus"], sp[r["design"]]])
    print(len(rows), "designs")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
