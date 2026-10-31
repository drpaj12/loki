"""Width inference from L1 claims, scored on the library (width known by construction).

``python -B width_infer.py``: reads $GLET_OUT/re/<cell>/<name>/intent.json for every library
instance, writes results/width_infer.csv (per pattern x cell x method: exact-match counts) and
prints the table. Methods: M1 widest word-level claim (counter, register, lfsr, shift_reg, ff_en,
timer-like) width; M2 widest bus; M3 distinct flip-flop output nets; each compared with the width
the state register has by construction (fsm: state bits; regfile: word width; M3 on regfile
against depth x width).
"""

from __future__ import annotations

import csv
import json
import os
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
WS = Path(os.environ.get("L3_WS", str(HERE.parent.parent.parent.parent)))
OUT = Path(os.environ.get("GLET_OUT", str(WS / "work" / "glet-out")))

import gen  # noqa: E402

CELLS = ("O-gate", "O-lut", "O-hard", "Y-gate", "Y-lut")
WORD = ("counter", "register", "lfsr", "shift_reg", "ff_en", "ff_srst", "ff_sen", "ff_arst")


def state_bits(i: gen.Inst) -> int:
    if i.pattern == "fsm":
        return i.width if i.variant == "onehot" else max(1, (i.width - 1).bit_length())
    return i.width


def ff_truth(i: gen.Inst) -> int:
    return i.width * i.depth if i.pattern == "regfile" else state_bits(i)


def infer(d: dict[str, Any]) -> dict[str, int]:
    words = [int(c["params"]["width"]) for c in d["claims"]
             if c["kind"] in WORD and "width" in c.get("params", {})]
    buses = [int(b["width"]) for b in d["buses"]]
    qnets: set[str] = set()
    for c in d["claims"]:
        nets = c.get("nets", {})
        for key in ("q", "Q"):
            if key in nets:
                qnets.update(nets[key])
    return {"M1": max(words, default=0), "M2": max(buses, default=0), "M3": len(qnets)}


def main() -> int:
    tally: dict[tuple[str, str, str], list[int]] = defaultdict(lambda: [0, 0, 0])
    for i in gen.instances():
        for cell in CELLS:
            p = OUT / "re" / cell / i.name / "intent.json"
            if not p.is_file():
                continue
            got = infer(json.loads(p.read_text(encoding="utf-8")))
            for m, v in got.items():
                truth = ff_truth(i) if m == "M3" else state_bits(i)
                t = tally[(i.pattern, cell, m)]
                t[0] += 1
                t[1] += int(v == truth)
                t[2] += int(v == 0)
    rows = [{"pattern": k[0], "cell": k[1], "method": k[2], "n": v[0], "exact": v[1],
             "none": v[2], "exact_rate": round(v[1] / v[0], 3)} for k, v in sorted(tally.items())]
    path = HERE / "results" / "width_infer.csv"
    path.parent.mkdir(exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, list(rows[0]), lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    by: dict[tuple[str, str], list[int]] = defaultdict(lambda: [0, 0])
    for r in rows:
        by[(r["pattern"], r["method"])][0] += r["n"]
        by[(r["pattern"], r["method"])][1] += r["exact"]
    for (pat, m), (n, e) in sorted(by.items()):
        print(f"{pat:9s} {m} {e}/{n} = {e / n:.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
