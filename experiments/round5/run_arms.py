"""Stage 2 runs: arms W and WB over the evaluation sets (smallest design first).

Usage: run_arms.py sets | big     (``sets``: MI VT CI CO at f2, MI VT at f3, MI at f1-k6)
Runs are restartable (a run with ``score.json`` is skipped); ``seconds.txt`` holds the wall time of
a run (up to 8 runs share the machine, so times are indicative; BIG runs one at a time).
"""

from __future__ import annotations

import sys

import r5lib

PLAN = (("f2", ("MI", "VT", "CI", "CO")), ("f3", ("MI", "VT")), ("f1-k6", ("MI",)))
WORKERS = 8


def nodes(dataset: r5lib.Path, design: str, floor: str) -> int:
    for e in r5lib.manifest(dataset)["designs"]:
        if e["design"] == design:
            return int(e["floors"][floor].get("nodes", 0))
    return 0


def sets_run() -> int:
    for floor, names in PLAN:
        for arm in ("W", "WB"):
            jobs = []
            for name in names:
                pairs = r5lib.eval_sets(floor)[name] if floor != "f1-k6" else [
                    (r5lib.MICRO, d) for d in r5lib.ok_designs(r5lib.MICRO, floor)]
                sized = sorted(((nodes(ds, d, floor), ds, d) for ds, d in pairs),
                               key=lambda t: (t[0], t[2]))
                for _n, ds, d in sized:
                    out = r5lib.run_dir(arm, name, floor, d)
                    jobs.append((f"{arm} {name} {floor} {d}", ds / d / floor / "netlist.blif",
                                 floor, r5lib.ARMS[arm], out, ds, d, 900, "all"))
            r5lib.run_jobs(jobs, WORKERS)
    return 0


def big_run() -> int:
    import json
    rows = []
    for d in sorted(p.name for p in r5lib.BIGDIR.iterdir() if (p / "dataset").is_dir()):
        ds = r5lib.BIGDIR / d / "dataset"
        sub = next(ds.iterdir())
        g = sub / "f2" / "graph.json"
        if g.is_file():
            rows.append((g.stat().st_size, d, ds, sub.name))
    rows.sort()
    (r5lib.DATA / "big_order.json").write_text(json.dumps([r[1] for r in rows]))
    for _size, d, ds, sub in rows:
        out = r5lib.run_dir("W", "BIG", "f2", d)
        job = (f"W BIG f2 {d}", ds / sub / "f2" / "netlist.blif", "f2", r5lib.ARMS["W"], out, ds,
               sub, 1800, "none")
        r5lib.run_jobs([job], 1)
    return 0


if __name__ == "__main__":
    what = sys.argv[1] if len(sys.argv) > 1 else ""
    raise SystemExit({"sets": sets_run, "big": big_run}.get(what, lambda: print(__doc__) or 2)())
