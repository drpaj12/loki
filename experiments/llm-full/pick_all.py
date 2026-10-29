"""Population of the full run: every problem of the four quartile files, minus the pilot's rules.

Usage: ``python -I pick_all.py``. Writes ``selection.csv`` (same columns as the pilot's) and
``excluded.csv`` (problem, quartile, reason, value). Pilot rule applied: the dataset prompt is at
most ``common.MAX_PROMPT_BYTES`` (40000 B). Reference pre-flight failures and hint failures are
added later by hand to ``EXCLUDED_EXTRA`` in this file, with a reason, and logged in EXPERIMENT.md.
"""

from __future__ import annotations

import csv
import importlib
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
fullcfg: Any = importlib.import_module("fullcfg")
common = fullcfg.common
pick: Any = importlib.import_module("pick_designs")

NO_LATCH = "arm B hints fail: Odin III cmos6 library has no latch cell (loki re error)"
EXCLUDED_EXTRA: dict[str, str] = {
    "Prob099_m2014_q6c": "reference fails its own testbench (ports Y2, Y4 not in the reference)",
    "Prob028_m2014_q4a": NO_LATCH,
    "Prob145_circuit8": NO_LATCH,
}  # problem -> reason


def population() -> tuple[list[tuple[str, str]], list[tuple[str, str, str, str]]]:
    keep: list[tuple[str, str]] = []
    drop: list[tuple[str, str, str, str]] = []
    for q, name in common.QUARTILES.items():
        names = pick.read_list(common.ve_root() / "quartiles" / f"{name}_quartile.txt")
        for p in sorted(names):
            size = (common.dataset_dir() / f"{p}_prompt.txt").stat().st_size
            if size > common.MAX_PROMPT_BYTES:
                drop.append((p, q, "prompt over 40000 B (pilot cap)", str(size)))
            elif p in EXCLUDED_EXTRA:
                drop.append((p, q, EXCLUDED_EXTRA[p], ""))
            else:
                keep.append((q, p))
    keep.sort(key=lambda t: (t[0], pick.lines_of(t[1]), t[1]))
    return keep, drop


def main() -> int:
    veval = common.REPO / "experiments" / "veval-l0"
    bench = pick.load_csv(veval / "benchmark.csv", "problem")
    feats = pick.load_csv(veval / "features.csv", "design")
    keep, drop = population()
    ds = common.dataset_dir()
    with (common.HERE / "selection.csv").open("w", encoding="utf-8", newline="\n") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(["quartile", "problem", "netlist_lines", "prompt_bytes", "bin_quartile",
                    "fsm_gt", "dffsr"])
        for q, p in keep:
            net = (ds / f"{p}_netlist.v").read_text(encoding="utf-8")
            w.writerow([q, p, pick.lines_of(p), (ds / f"{p}_prompt.txt").stat().st_size,
                        bench[p]["quartile"] if p in bench else "-",
                        feats[f"ve_{p}"]["fsm"] if f"ve_{p}" in feats else "-",
                        "y" if "DFFSR" in net else ""])
    with (common.HERE / "excluded.csv").open("w", encoding="utf-8", newline="\n") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(["problem", "quartile", "reason", "value"])
        w.writerows(drop)
    print(f"population {len(keep)}, excluded {len(drop)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
