"""Item 9 proof: rerun arms W and WB on CI, CO (corpus test split) and VT (VerilogEval held-out)
at f2 with the current code into a scratch directory and compare every output file except
``timing.json`` byte for byte with the stored run of ``loki-exp5-data``.

Usage: check_identical.py <scratch-dir> [arm ...]     (default arms: W WB; prints one line per
mismatch and a final count; exit status 1 when anything differs)
"""

from __future__ import annotations

import sys
from pathlib import Path

import r5lib

SETS = ("CI", "CO", "VT")
SKIP = {"timing.json"}


def main() -> int:
    scratch = Path(sys.argv[1])
    arms = sys.argv[2:] or ["W", "WB"]
    jobs = []
    pairs = []
    for arm in arms:
        for name in SETS:
            for ds, d in r5lib.eval_sets("f2")[name]:
                out = scratch / f"{arm}-{name}-f2" / d / "re"
                ref = r5lib.run_dir(arm, name, "f2", d)
                if not (ref / "score.json").is_file():
                    continue
                jobs.append((f"{arm} {name} {d}", ds / d / "f2" / "netlist.blif", "f2",
                             r5lib.ARMS[arm], out, ds, d, 900, "all"))
                pairs.append((arm, name, d, ref, out))
    r5lib.run_jobs(jobs, 8)
    bad = same = 0
    for arm, name, d, ref, out in pairs:
        names = sorted(p.name for p in ref.iterdir() if p.name not in SKIP)
        for fn in names:
            a, b = ref / fn, out / fn
            if not b.is_file() or a.read_bytes() != b.read_bytes():
                print("DIFF", arm, name, d, fn)
                bad += 1
            else:
                same += 1
    print(f"files identical {same} different {bad} runs {len(pairs)}")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
