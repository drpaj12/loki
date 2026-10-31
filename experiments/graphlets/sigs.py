"""Signatures from the Odin III ``graphlets`` pass: ``python -B sigs.py [JOBS]``.

For every library netlist (precomputed and live entries) and mode (undirected size 5, directed)
runs ``Design.graphlets(exclude_global=True)`` (Odin III's global rule: a net that reaches a clock pin
or has >= 16 readers), writes the group JSON to $GLET_OUT/sig/<mode>/<cell>/<name>.json (orbit totals
and GDD, integers) and stores the orbit totals in the database. Typed mode: the pass has none.
"""

from __future__ import annotations

import json
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
import db  # noqa: E402
import gen  # noqa: E402
import live  # noqa: E402

VTR_LIB = live.ODIN / "lib" / "vtr.o3lib"
MODES = {"undirected": False, "directed": True}


def signature(netlist: Path, mode: str) -> dict[str, Any]:
    """The first group of the pass JSON for one netlist (orbit_totals, gdd, nodes, edges, ...)."""
    import odin3

    with odin3.Design.read_blif(netlist, techlibs=[VTR_LIB]) as design:
        res = design.graphlets(exclude_global=True, directed=MODES[mode])
    group: dict[str, Any] = res["groups"][0]
    group["mode"] = res["mode"]
    return group


def sig_path(mode: str, cell: str, name: str) -> Path:
    return live.OUT / "sig" / mode / cell / f"{name}.json"


def one(job: tuple[str, str, int, int, str, str, str]) -> tuple[str, int]:
    pattern, variant, width, depth, cell, mode, _ = job
    inst = gen.Inst(pattern, variant, width, depth)
    p = sig_path(mode, cell, inst.name)
    if p.is_file():
        return inst.name, 0
    try:
        grp = signature(live.netlist_of(inst, cell), mode)
    except Exception as exc:  # recorded, not hidden
        return f"{inst.name} {cell} {mode}: {exc}"[:200], 1
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(grp, sort_keys=True), encoding="utf-8")
    return inst.name, 0


def jobs(widths: tuple[int, ...] | None = None) -> list[tuple[str, str, int, int, str, str, str]]:
    out = []
    for inst in gen.instances(widths or gen.WIDTHS):
        for cell in live.CELLS:
            for mode in MODES:
                out.append((inst.pattern, inst.variant, inst.width, inst.depth, cell, mode, ""))
    return out


def load_into_db(con: Any, provenance: str = "precomputed", insts: list[gen.Inst] | None = None
                 ) -> int:
    ver = live.tool_versions()
    n = 0
    for inst in insts or list(gen.instances()):
        for cell in live.CELLS:
            for mode in MODES:
                p = sig_path(mode, cell, inst.name)
                if not p.is_file():
                    continue
                grp = json.loads(p.read_text(encoding="utf-8"))
                db.put_signature(con, live.key_of(inst, cell), provenance, mode,
                                 dict(enumerate(grp["orbit_totals"])),
                                 input_sha256=db.sha256_file(live.netlist_of(inst, cell)),
                                 tool_commit=ver["odin3_commit"], script_hash=ver["gen_hash"],
                                 measurer_version="graphlets-pass-v1",
                                 origin=f"sig/{mode}/{cell}/{inst.name}.json")
                n += 1
    return n


def main(argv: list[str]) -> int:
    n_jobs = int(argv[0]) if argv else 6
    todo = jobs()
    with ProcessPoolExecutor(n_jobs) as pool:
        res = list(pool.map(one, todo, chunksize=20))
    bad = [r[0] for r in res if r[1]]
    (live.OUT / "sig").mkdir(exist_ok=True)
    (live.OUT / "sig" / "failures.txt").write_text("\n".join(bad) + "\n", encoding="utf-8")
    con = db.open_db(live.DB_PATH)
    print(len(todo), "jobs,", len(bad), "failed;", load_into_db(con), "rows stored")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
