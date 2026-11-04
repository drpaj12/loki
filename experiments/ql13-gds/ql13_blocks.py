"""Loki L0 block recovery at the "gds" endpoint (structure only, no model call).

For each design whose flow reached the ``extract`` step: write ``$QL13_OUT/<name>/gds/``
(``netlist.blif``, ``labels.csv``, ``ports.json``: ``ql13_gdsnet``), read the BLIF with the Q-L12
reader, cut it with the Q-L12 block builder (cell class ``O-lut``) and apply the Q-L12 right-block
rule to the key constructs (>= 2 flip-flops with the same HDL line and column in the labels).
Writes ``results/gds_blocks.csv`` and ``results/gds_key.csv``. Needs the environment of
``work/ql13-out/env.sh`` (Odin III library for the graphlet pass; q10/q12 modules on the path).
Usage: ``python3 -B ql13_blocks.py [NAME_FILTER]``.
"""

from __future__ import annotations

import csv
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

import q12_blocks as qb  # noqa: E402  (path from env.sh)
import q12_key as key  # noqa: E402
import q12_nl as nlm  # noqa: E402
import ql13_env as env
import ql13_gdsnet as gn

from loki.prov_steps import read_run

MIN_FF = key.MIN_FF


def key_constructs(nl: Any, labels: Path) -> list[frozenset[int]]:
    """Flip-flop sets (cell indices) with the same HDL line and column in the labels."""
    cell_of = {c.cname: c.idx for c in nl.cells if c.kind == "ff" and c.cname}
    groups: dict[tuple[str, str], set[int]] = defaultdict(set)
    with labels.open(encoding="utf-8", newline="") as fh:
        for r in csv.DictReader(fh):
            if r["kind"] == "ff" and r["node_id"] in cell_of and r["hdl_line"]:
                groups[(r["hdl_line"], r["hdl_col"])].add(cell_of[r["node_id"]])
    return [frozenset(g) for _k, g in sorted(groups.items()) if len(g) >= MIN_FF]


def one(name: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    root = env.RUN / name
    out = root / "out"
    gdir = root / "gds"
    gdir.mkdir(exist_ok=True)
    row: dict[str, Any] = {"design": name, "status": "ok", "cells": 0, "ffs": 0, "labelled": 0,
                           "unknown": 0, "blocks": 0, "key_total": 0, "key_right": 0,
                           "partial": int(not (out / "prov" / "index.json").is_file())}
    spice = out / "ext_hier.spice"
    prov = out / "prov"
    if not (prov / "index.json").is_file():  # a run that stopped at LVS: ql13_chain's partial copy
        prov = root / "prov-partial"
    if not spice.is_file() or not (prov / "index.json").is_file():
        row["status"] = "no_extract"
        return row, []
    try:
        text, ports, kinds = gn.convert(spice, gn.read_lib())
    except gn.Unsupported as err:
        row["status"] = f"unsupported: {err}"[:100]
        return row, []
    (gdir / "netlist.blif").write_text(text, encoding="utf-8")
    (gdir / "ports.json").write_text(json.dumps(ports), encoding="utf-8")
    labs = gn.labels(read_run(prov), kinds)
    gn.write_csv(gdir / "labels.csv", labs)
    nl = nlm.parse(text, ports)
    row["cells"] = len(nl.cells)
    row["ffs"] = sum(1 for c in nl.cells if c.kind == "ff")
    row["labelled"] = sum(1 for x in labs if x["construct_type"] == "hdl")
    row["unknown"] = sum(1 for x in labs if x["construct_type"] == "unknown")
    blocks = qb.build(nl, gdir / "netlist.blif", "O-lut") if nl.logic() else []
    cons = key_constructs(nl, gdir / "labels.csv")
    rb = key.right_blocks(nl, blocks, cons)
    row.update({"blocks": len(blocks), "key_total": len(cons),
                "key_right": sum(1 for x in rb if x)})
    keys = [{"design": name, "construct": i, "ffs": len(c), "right_blocks": json.dumps(r)}
            for i, (c, r) in enumerate(zip(cons, rb, strict=True))]
    return row, keys


def main(argv: list[str]) -> int:
    rows: list[dict[str, Any]] = []
    keys: list[dict[str, Any]] = []
    for d in env.designs():
        if argv and not any(a in d["name"] for a in argv):
            continue
        if not (env.RUN / d["name"] / "status.json").is_file():
            continue
        r, k = one(d["name"])
        rows.append(r)
        keys += k
        print(r, flush=True)
    if not argv:
        env.write_csv(env.RES / "gds_blocks.csv", list(rows[0]), rows)
        env.write_csv(env.RES / "gds_key.csv", ["design", "construct", "ffs", "right_blocks"], keys)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
