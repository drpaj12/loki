"""Per-construct and per-endpoint tables for Q-L11 (no model call, no Odin III run).

Reads the Q-L9 TEST result (``$QL9_OUT/res_test_TEST.pkl``, config HEAD = the Q-L10 block builder's
rules), the answer key of the benchmark units and the Odin III ``labels.csv`` next to each netlist.
Writes (results/): ``construct_loss.csv`` (one row per answer-key construct: set, design, cell,
endpoint, kind, n_cells, right, failure class, provenance-mixing shares of its cells),
``endpoint_size.csv`` (size of the units per endpoint) and ``ve_endpoint_size.csv`` (the Gate-Breaker
VerilogEval designs at the three endpoints).
Endpoint of a cell class: gate = O-gate, Y-gate; k4 = O-lut, Y-lut; k6 = O-hard (hard-block map).
Provenance exists on the O cells only (Y cells have no labels.csv).
Usage: python -B q11_struct.py
"""

from __future__ import annotations

import csv
import pickle
import statistics as st
from pathlib import Path
from typing import Any

import q11_env as env
import q9_env as e9

qt = e9.mod("q6_truth")
qn = e9.mod("q6_net")
q7e = e9.mod("q7_eval")
l3dlib = e9.mod("l3dlib")
ENDPOINT = {"O-gate": "gate", "Y-gate": "gate", "O-lut": "k4", "Y-lut": "k4", "O-hard": "k6"}


def label_rows(u: Any) -> dict[str, dict[str, str]]:
    p = u.net.parent / "labels.csv"
    if not p.is_file():
        return {}
    with p.open(encoding="utf-8", newline="") as fh:
        return {r["node_id"]: r for r in csv.DictReader(fh)}


def mix_shares(cells: frozenset[int], g: Any, lab: dict[str, dict[str, str]]) -> dict[str, float]:
    """Share of the cells with a label that carry provenance of more than one construct."""
    rows = [lab[g.b.cname[i]] for i in cells if g.b.cname[i] in lab]
    if not rows:
        return {"labelled": 0, "star": float("nan"), "pipe": float("nan"), "span": float("nan"),
                "ctypes": float("nan")}
    n = len(rows)
    return {"labelled": n,
            "star": sum("*" in r["module_path"] for r in rows) / n,
            "pipe": sum("|" in r["construct_types"] for r in rows) / n,
            "span": sum(int(r["n_spans"] or 0) > 1 for r in rows) / n,
            "ctypes": sum(len([t for t in r["construct_types"].split("|") if t]) for r in rows) / n}


def construct_rows() -> list[dict[str, Any]]:
    res = pickle.loads((e9.OUT9 / "res_test_TEST.pkl").read_bytes())
    head = {x["key"]: x["cfg"]["HEAD"]["rows"] for x in res}
    refs = q7e.ref_rows()  # the constructs Q-L9 scores (its 1141); the others have no D70 row
    out: list[dict[str, Any]] = []
    for u in qt.units("TEST"):
        rows = head.get(u.key)
        if not rows:
            continue
        g = qn.Graph.read(u.net)
        lab = label_rows(u)
        cons = {(c.idx, c.kind): c for c in qt.constructs(u, g) if c.kind != "glue" and c.cells}
        for r in rows:
            if refs.get(q7e.key_of(r)) is None:
                continue
            c = cons.get((r["part"], r["kind"]))
            m = mix_shares(c.cells, g, lab) if c is not None and lab else {}
            out.append({"set": r["set"], "design": r["design"], "cell": r["cell"],
                        "endpoint": ENDPOINT[r["cell"]], "part": r["part"], "kind": r["kind"],
                        "n_true": r["n_true"], "right": r["right"], "cls": r["cls"],
                        "labelled": m.get("labelled", 0), "star": m.get("star", ""),
                        "pipe": m.get("pipe", ""), "span": m.get("span", ""),
                        "ctypes": m.get("ctypes", "")})
    return out


def unit_stats(net: Path, lab_path: Path) -> dict[str, float]:
    g = qn.Graph.read(net)
    nets = set()
    for i in range(g.b.n):
        nets.update(g.b.ins[i])
        nets.update(g.b.outs[i])
    luts = [len(g.b.ins[i]) for i in range(g.b.n) if not g.b.latch[i] and i not in g.hard]
    out: dict[str, float] = {"cells": g.b.n, "nets": len(nets),
                             "ffs": sum(g.b.latch), "hard": len(g.hard),
                             "lut_inputs_sum": sum(luts), "luts": len(luts)}
    if lab_path.is_file():
        with lab_path.open(encoding="utf-8", newline="") as fh:
            rows = [r for r in csv.DictReader(fh) if r["kind"] not in ("pi", "po")]
        if rows:
            out["lab_cells"] = len(rows)
            out["ctypes_sum"] = sum(len([t for t in r["construct_types"].split("|") if t])
                                    for r in rows)
            out["pipe"] = sum("|" in r["construct_types"] for r in rows)
            out["star"] = sum("*" in r["module_path"] for r in rows)
            out["span"] = sum(int(r["n_spans"] or 0) > 1 for r in rows)
    return out


def summarise(rows: list[dict[str, float]]) -> dict[str, Any]:
    cells = [r["cells"] for r in rows]
    s: dict[str, Any] = {"units": len(rows), "cells_total": int(sum(cells)),
                         "cells_median": st.median(cells), "cells_mean": round(st.mean(cells), 1),
                         "nets_mean": round(st.mean(r["nets"] for r in rows), 1)}
    luts, ins = sum(r["luts"] for r in rows), sum(r["lut_inputs_sum"] for r in rows)
    s["mean_inputs_per_logic_cell"] = round(ins / luts, 2) if luts else ""
    lab = [r for r in rows if "lab_cells" in r]
    n = sum(r["lab_cells"] for r in lab)
    if n:
        s["labelled_cells"] = int(n)
        s["ctypes_per_cell"] = round(sum(r["ctypes_sum"] for r in lab) / n, 3)
        s["share_pipe"] = round(sum(r["pipe"] for r in lab) / n, 4)
        s["share_star"] = round(sum(r["star"] for r in lab) / n, 4)
        s["share_span_gt1"] = round(sum(r["span"] for r in lab) / n, 4)
    return s


def write(name: str, rows: list[dict[str, Any]]) -> None:
    keys: list[str] = []
    for r in rows:
        keys += [k for k in r if k not in keys]
    with (env.RES / name).open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, keys, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


def endpoint_size() -> None:
    per: dict[str, list[dict[str, float]]] = {c: [] for c in ENDPOINT}
    for u in qt.units("TEST"):
        per[u.cell].append(unit_stats(u.net, u.net.parent / "labels.csv"))
    write("endpoint_size.csv", [{"cell": c, "endpoint": ENDPOINT[c], **summarise(v)}
                                for c, v in per.items() if v])
    ve: dict[str, list[dict[str, float]]] = {c: [] for c in ENDPOINT}
    names = sorted(p.name for p in (l3dlib.CENSUS / "build" / "O-gate").glob("ve_*"))
    for c in ENDPOINT:
        for d in names:
            p = l3dlib.netlist_path(l3dlib.CENSUS, c, d)
            if p.is_file():
                ve[c].append(unit_stats(p, p.parent / "labels.csv"))
    write("ve_endpoint_size.csv", [{"cell": c, "endpoint": ENDPOINT[c], **summarise(v)}
                                   for c, v in ve.items() if v])


def main() -> int:
    env.RES.mkdir(parents=True, exist_ok=True)
    write("construct_loss.csv", construct_rows())
    endpoint_size()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
