"""Directed signatures of the TRUE blocks of composite parts: ``python -B tsig.py [JOBS]``.

For every TEST composite on an Odin III cell, the cells of each part (labels ``module_path``
``u<idx>``) plus the primary-input ports that feed them are counted with the Odin III ``graphlets``
pass (``--cells``, Odin III global rule, directed). Output: $QL4_OUT/tsig/<cell>/<name>.json with
{part index: group or {"error": ...}}. Singles need no pass run: the whole design is the true block
and its signature is the one #68 stored (sig_l3).
"""

from __future__ import annotations

import json
import os
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "graphlets"))
sys.path.insert(0, str(HERE.parent / "l3-detector"))
import blocks as bl  # noqa: E402
import l3dlib  # noqa: E402
import live  # noqa: E402
import sigs  # noqa: E402

OUT = Path(os.environ.get("QL4_OUT", str(live.WS / "work" / "ql4-out")))
O_CELLS = ("O-gate", "O-lut", "O-hard")
MAX_WORK = 3e8


def tsig_path(cell: str, name: str) -> Path:
    return OUT / "tsig" / cell / f"{name}.json"


def one(job: tuple[str, str]) -> str:
    import odin3

    cell, name = job
    dest = tsig_path(cell, name)
    if dest.is_file():
        return ""
    net = l3dlib.netlist_path(l3dlib.OUT, cell, name)
    b = bl.Blif.read(net)
    truth = json.loads((l3dlib.OUT / "composites" / name / "truth.json").read_text(encoding="utf-8"))
    ranges = bl.module_ranges(l3dlib.OUT / "composites" / name / f"{name}.sv",
                              {p["idx"]: p["problem"] for p in truth["parts"]})
    parts, by_line = bl.part_blocks(b, net.parent / "labels.csv", ranges)
    res: dict[str, Any] = {}
    for idx in range(len(truth["parts"])):  # parts with no cell at all are recorded too
        parts.setdefault(idx, set())
    cells = OUT / "tmp" / f"cells_{os.getpid()}.txt"
    cells.parent.mkdir(parents=True, exist_ok=True)
    with odin3.Design.read_blif(net, techlibs=[sigs.VTR_LIB]) as d:
        mod = d.top()
        for idx, blk in sorted(parts.items()):
            outs, pis = bl.block_nodes(b, blk)
            ids = set()
            for n in [*outs, *pis]:
                netobj = mod.net(n)
                pin = netobj.driver() if netobj is not None else None
                if pin is not None:
                    ids.add(pin.node().id)
            if not ids:
                res[str(idx)] = {"error": "empty block", "n_latches": 0, "n_cells": len(blk),
                                 "n_by_line": by_line.get(idx, 0)}
                continue
            try:
                cells.write_text("@p\n" + "\n".join(str(i) for i in sorted(ids)) + "\n",
                                 encoding="utf-8")
                r = d.graphlets(exclude_global=True, directed=True, cells=cells,
                                max_work=int(MAX_WORK))
                g = r["groups"][0]
                g["mode"] = r["mode"]
                g["n_latches"] = b.n_latches(blk)
                g["n_cells"] = len(blk)
                g["n_by_line"] = by_line.get(idx, 0)
                res[str(idx)] = g
            except Exception as exc:  # work cap: recorded
                res[str(idx)] = {"error": str(exc)[:80], "n_latches": b.n_latches(blk),
                                 "n_cells": len(blk), "n_by_line": by_line.get(idx, 0)}
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(res, sort_keys=True), encoding="utf-8")
    return ""


def jobs() -> list[tuple[str, str]]:
    names = [r["name"] for r in l3dlib.read_csv(l3dlib.RES / "composites.csv")
             if r["split"] == "TEST"]
    return [(c, n) for n in names for c in O_CELLS
            if l3dlib.netlist_path(l3dlib.OUT, c, n).is_file()]


def main(argv: list[str]) -> int:
    n = int(argv[0]) if argv else 4
    todo = jobs()
    with ProcessPoolExecutor(n) as pool:
        list(pool.map(one, todo, chunksize=2))
    print(len(todo), "composite x cell jobs")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
