"""Development harness: arm W/WB on a prefix of the corpus TRAIN split (never an evaluation set)."""
from __future__ import annotations

import json
import sys

import r5lib

N = int(sys.argv[2]) if len(sys.argv) > 2 else 150
ARM = sys.argv[1] if len(sys.argv) > 1 else "W"
FLOOR = sys.argv[3] if len(sys.argv) > 3 else "f2"
cs = r5lib.corpus_split()
train = [d for d in r5lib.ok_designs(r5lib.CORPUS, FLOOR) if cs[d][1] == "train"]
# fixed spread: every k-th design by name
step = max(1, len(train) // N)
sel = train[::step][:N]
root = r5lib.DATA / "dev" / f"{ARM}-{FLOOR}"
jobs = [(d, r5lib.CORPUS / d / FLOOR / "netlist.blif", FLOOR, r5lib.ARMS[ARM], root / f"{d}",
         r5lib.CORPUS, d, 300, "all") for d in sel]
r5lib.run_jobs(jobs, 8) if "--noscore" not in sys.argv else None
scores = []
fam: dict[str, dict[str, list[int]]] = {}
for d in sel:
    p = root / d / "score.json"
    if p.is_file():
        s = json.loads(p.read_text())
        scores.append(s)
        for k, v in s["constructs"].items():
            f = fam.setdefault(cs[d][0], {}).setdefault(k, [0, 0, 0])
            f[0] += v["counted"]
            f[1] += v["matched"]
            f[2] += v["gt"]
tab = r5lib.summarise(scores)
print("designs", len(scores), "of", len(sel))
for k in r5lib.KDICT:
    v = tab.get(k)
    if v:
        p = v["matched"] / v["counted"] if v["counted"] else 0
        r = v["matched"] / v["gt"] if v["gt"] else 0
        print(f"{k:12s} counted {v['counted']:5d} matched {v['matched']:5d} "
              f"gt {v['gt']:5d} P {p:.2f} R {r:.2f}")
if "--fam" in sys.argv:
    for kk in sys.argv[sys.argv.index("--fam") + 1:]:
        print("family breakdown", kk)
        for f in sorted(fam):
            v = fam[f].get(kk)
            if v and (v[0] or v[2]):
                print(f"  {f:12s} counted {v[0]:4d} matched {v[1]:4d} gt {v[2]:4d}")
