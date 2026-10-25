"""Round-3 `loki re` runs on the micro dataset: M3N, M3C (f3) and M1N (f1-k6), then score.

Run under the heavy lock. Restartable (a run with a report.json is skipped). Smallest first.
"""

from __future__ import annotations

import json
import sys

import r2lib
import r3lib

from loki.schemas import dump_json
from loki.score.metrics import score_run

REPO = r3lib.HERE.parents[1]
PLAN = {"M3N": None, "M3C": REPO / "calib" / "f3.json", "M1N": None}


def main() -> int:
    workers = int(sys.argv[1]) if len(sys.argv) > 1 else 3
    for name, calib in PLAN.items():
        rs = r3lib.SETS[name]
        todo = r2lib.test_designs(r3lib.MICRO, rs.floor, None)
        jobs = [(f"{name} {d} {n}", r3lib.floor_dir(rs, d) / "netlist.blif", rs.floor, calib,
                 r3lib.run_dir(rs, d)) for d, n in todo]
        r2lib.run_many(jobs, workers, 900)
        done = 0
        for d, _n in todo:
            rd = r3lib.run_dir(rs, d)
            if (rd / "overlay.json").is_file():
                (rd / "score.json").write_text(
                    dump_json(score_run(rd, r3lib.floor_dir(rs, d), 0.5)), encoding="utf-8")
                done += 1
        print(json.dumps({"set": name, "designs": len(todo), "scored": done}), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
