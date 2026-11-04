"""Netlist check of the lut4 build: largest LUT input count and LUT / FF counts beside k4 and k6.

For every design of the set, read the lut4 BLIF (this lane's census) and the Q-L12 "k4" (f2, six-input
mapper) and "k6" (f1-k6) BLIFs (read only), count LUTs (``.names`` with at least one input,
constants and buffers counted apart), flip-flops and hard adders, and the largest number of inputs
of a ``.names``. Fails (exit 1) when a lut4 netlist has a LUT above 4 inputs. Writes
``results/netcheck.csv``. No model call. Usage: ``python -B l4_netcheck.py``.
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path
from typing import Any

import l4_env as l4

env = l4.env
nlm: Any = env.mod("q12_nl")
bk: Any = env.mod("q12_build")
OLD_RUN = env.WS / "work" / "ql12-out"
OLD_CENSUS = env.WS / "work" / "l3-out" / "build"
FIELDS = ["problem", "tier"] + [f"{e}_{k}" for e in ("lut4", "k4", "k6")
                                for k in ("luts", "glue", "ffs", "adders", "maxin")]


def dirs(problem: str) -> dict[str, Path]:
    if nlm.is_ext(problem):
        return {"lut4": env.RUN / "census" / "O-lut" / problem / "f2",
                "k4": OLD_RUN / "census" / "O-lut" / problem / "f2",
                "k6": OLD_RUN / "census" / "O-hard" / problem / "f1-k6"}
    return {"lut4": env.CENSUS / "O-lut" / f"ve_{problem}" / "f2",
            "k4": OLD_CENSUS / "O-lut" / f"ve_{problem}" / "f2",
            "k6": OLD_CENSUS / "O-hard" / f"ve_{problem}" / "f1-k6"}


def stats(d: Path) -> dict[str, int] | None:
    import json
    if not (d / "netlist.blif").is_file():
        return None
    key = json.loads((d / "key.json").read_text(encoding="utf-8"))
    nl = nlm.parse((d / "netlist.blif").read_text(encoding="utf-8"), key["ports"])
    luts = [c for c in nl.cells if c.kind == "lut"]
    return {"luts": sum(1 for c in luts if not c.glue), "glue": sum(1 for c in luts if c.glue),
            "ffs": sum(1 for c in nl.cells if c.kind == "ff"),
            "adders": sum(1 for c in nl.cells if c.kind == "hard"),
            "maxin": max((len(c.ins) for c in luts), default=0)}


def main() -> int:
    rows = []
    bad = 0
    for r in bk.problems():
        row: dict[str, Any] = {"problem": r["problem"], "tier": r["tier"]}
        for ep, d in dirs(r["problem"]).items():
            s = stats(d)
            for k in ("luts", "glue", "ffs", "adders", "maxin"):
                row[f"{ep}_{k}"] = "" if s is None else s[k]
            if ep == "lut4" and s is not None and s["maxin"] > 4:
                bad += 1
        rows.append(row)
    env.RES.mkdir(exist_ok=True)
    with (env.RES / "netcheck.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, FIELDS, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    have = [r for r in rows if r["lut4_maxin"] != ""]
    print(f"lut4 netlists {len(have)}; max LUT inputs {max(int(r['lut4_maxin']) for r in have)}; "
          f"over 4: {bad}")
    for ep in ("lut4", "k4", "k6"):
        sub = [r for r in rows if r[f"{ep}_luts"] != ""]
        print(ep, "designs", len(sub), "LUTs", sum(int(r[f"{ep}_luts"]) for r in sub),
              "FFs", sum(int(r[f"{ep}_ffs"]) for r in sub),
              "max inputs", max(int(r[f"{ep}_maxin"]) for r in sub))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
