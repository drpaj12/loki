"""Structure-only block recovery of the stored runs at gates, lut4, k4 and k6, per design
(no model).

For each design of the Q-L13 set and each earlier endpoint, with the block files stored by that run:
the key constructs (>= 2 flip-flops with the same construct type, HDL line and column in the census
labels, as that run's ``*_key.py``), and how many have a right block (the right-block rule). Reuses
the Q-L10 (gates) and Q-L12 (k4, k6, lut4) code unchanged. One process per mode (the q10 and q12
modules share short names): ``--mode gates|k46|lut4`` prints CSV rows ``endpoint,design,...``.
Needs ``work/ql13-out/env.sh``. Output to ``results/prior_key.csv`` via ``--write``.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from typing import Any

import ql13_env as env

FIELDS = ["endpoint", "design", "cells", "ffs", "blocks", "key_total", "key_right",
          "coarse_total", "coarse_right"]


def coarse_q12(nl: Any, ep: str, n: str, qnl: Any) -> list[frozenset[int]]:
    """Key without the construct type: flip-flops with the same HDL line and column (the key the
    gds endpoint can give from the chain). Census labels, cell name join, as ``q12_key``."""
    import csv
    from collections import defaultdict
    path = qnl.census_dir(ep, n) / "labels.csv"
    if not path.is_file():
        return []
    cell_of = {c.cname: c.idx for c in nl.cells if c.kind == "ff" and c.cname}
    groups: dict[tuple[str, str], set[int]] = defaultdict(set)
    with path.open(encoding="utf-8", newline="") as fh:
        for r in csv.DictReader(fh):
            if r["kind"] == "ff" and r["node_id"] in cell_of:
                groups[(r["hdl_line"], r["hdl_col"])].add(cell_of[r["node_id"]])
    return [frozenset(g) for _k, g in sorted(groups.items()) if len(g) >= 2]


def coarse_gates(nl: Any, n: str, qk: Any) -> list[frozenset[int]]:
    import csv
    from collections import defaultdict
    path = qk.labels_path(n)
    if not path.is_file():
        return []
    ff_of = {c.out: c.idx for c in nl.cells if c.typ.startswith("DFF")}
    groups: dict[tuple[str, str], set[int]] = defaultdict(set)
    with path.open(encoding="utf-8", newline="") as fh:
        for r in csv.DictReader(fh):
            if r["kind"] in qk.SKIP_KINDS or not r["bus_name"]:
                continue
            bus, bit = r["bus_name"], int(r["bit_index"])
            for name in ((f"{bus}[{bit}]", bus) if bit == 0 else (f"{bus}[{bit}]",)):
                if name in ff_of:
                    groups[(r["hdl_line"], r["hdl_col"])].add(ff_of[name])
                    break
    return [frozenset(g) for _k, g in sorted(groups.items()) if len(g) >= 2]


def rows_gates(names: list[str]) -> list[dict[str, Any]]:
    import q10_build as qbd
    import q10_key as qk
    import q10_pop as pop
    out: list[dict[str, Any]] = []
    for n in names:
        if not qbd.blocks_file(n).is_file():
            continue
        nl = pop.read(n)
        blocks = qbd.load_blocks(n)
        cons = qk.key_constructs(nl, n)
        rb = qk.right_blocks(nl, blocks, cons)
        cc = coarse_gates(nl, n, qk)
        crb = qk.right_blocks(nl, blocks, cc)
        out.append({"endpoint": "gates", "design": n, "cells": len(nl.cells),
                    "ffs": sum(1 for c in nl.cells if c.typ.startswith("DFF")),
                    "blocks": len(blocks), "key_total": len(cons),
                    "key_right": sum(1 for x in rb if x), "coarse_total": len(cc),
                    "coarse_right": sum(1 for x in crb if x)})
    return out


def rows_q12(names: list[str], eps: list[str]) -> list[dict[str, Any]]:
    import q12_build as qbd
    import q12_key as qk
    import q12_nl as nlm
    out: list[dict[str, Any]] = []
    for ep in eps:
        for n in names:
            if not qbd.blocks_file(ep, n).is_file():
                continue
            nl = nlm.read(ep, n)
            blocks = qbd.load_blocks(ep, n)
            cons = qk.key_constructs(nl, ep, n)
            rb = qk.right_blocks(nl, blocks, cons)
            cc = coarse_q12(nl, ep, n, nlm)
            crb = qk.right_blocks(nl, blocks, cc)
            out.append({"endpoint": ep, "design": n, "cells": len(nl.cells),
                        "ffs": sum(1 for c in nl.cells if c.kind == "ff"),
                        "blocks": len(blocks), "key_total": len(cons),
                        "key_right": sum(1 for x in rb if x), "coarse_total": len(cc),
                        "coarse_right": sum(1 for x in crb if x)})
    return out


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["gates", "k46", "lut4"])
    ap.add_argument("--write", action="store_true")
    ns = ap.parse_args(argv)
    names = [d["name"] for d in env.designs()]
    if ns.write:
        rows: list[dict[str, Any]] = []
        for mode in ("gates", "k46", "lut4"):
            e = dict(os.environ)
            if mode == "lut4":  # l4_env sets these with setdefault; the shell env.sh sets Q-L12's
                e["QL12_OUT"] = str(env.WS / "work" / "ql12l4-out")
                e.pop("QL12_CENSUS", None)
            p = subprocess.run([sys.executable, "-B", __file__, "--mode", mode],
                               capture_output=True, text=True, check=True, env=e)
            for line in p.stdout.splitlines():
                if line.startswith("ROW "):
                    rows.append(dict(zip(FIELDS, line[4:].split(","), strict=True)))
        env.write_csv(env.RES / "prior_key.csv", FIELDS, rows)
        print(len(rows), "rows")
        return 0
    if ns.mode == "gates":
        rows = rows_gates(names)
    elif ns.mode == "k46":
        rows = rows_q12(names, ["k4", "k6"])
    else:
        import l4_env  # noqa: F401  (sets the q12 modules to the lut4 endpoint; must come first)
        rows = rows_q12(names, ["lut4"])
    for r in rows:
        print("ROW " + ",".join(str(r[f]) for f in FIELDS))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
