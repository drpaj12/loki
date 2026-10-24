"""RQ-L2: AST and CFG similarity of Loki's output Verilog against the VerilogEval reference.

For every VerilogEval design and variant, the candidate is the output Verilog and the reference
is ``<Prob>_ref.sv``. Variants:
  f3-l0      the f3 gate netlist (L0-stop, ``netlist.v`` of the dataset)
  f2-l0      the f2 LUT netlist (``netlist.v``)
  f3-calib   ``design.v`` of the calibrated f3 run (L1-stop); f3-none, f2-calib, f2-none likewise
AST: pyverilog depth-3 best-Jaccard (Algorithm 2). CFG: the odin3 probe (Algorithm 3), skipped
above 12,000 CFG nodes. Writes ``<data>/l2/astcfg.json`` and ``l2_astcfg.csv``.

Usage: l2_astcfg.py [--max-nodes N]   (run under the heavy lock; the CFG side loads Odin III)
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

import metrics_ext
import r2lib

REFS = Path(os.environ.get("VERILOG_EVAL", str(r2lib.WS / "external" / "verilog-eval"))) \
    / "dataset_spec-to-rtl"
OUT = r2lib.DATA / "l2" / "astcfg.json"
RUNS = r2lib.DATA / "l2" / "runs"
VARIANTS = ("f3-l0", "f2-l0", "f3-calib", "f3-none", "f2-calib", "f2-none")


def candidate(variant: str, design: str) -> Path:
    if variant.endswith("-l0"):
        floor = variant.split("-")[0]
        return r2lib.VEVAL / design / floor / "netlist.v"
    floor, cond = variant.split("-")
    return RUNS / f"{floor}-{cond}" / f"{design}__{floor}" / "re" / "design.v"


def score_design(binding: Any, design: str, ref: Path, variants: tuple[str, ...]) -> dict[str, Any]:
    row: dict[str, Any] = {"design": design}
    try:
        ref_mod = metrics_ext.parse_clean(ref)
    except Exception as err:
        ref_mod, row["ref_ast_error"] = None, f"{type(err).__name__}: {str(err)[:100]}"
    try:
        ref_cfg = metrics_ext.cfg_of(binding, ref)
    except Exception as err:
        ref_cfg, row["ref_cfg_error"] = None, f"{type(err).__name__}: {str(err)[:100]}"
    for v in variants:
        path = candidate(v, design)
        if not path.is_file():
            continue
        if ref_mod is not None:
            try:
                row[f"{v}:ast"] = round(metrics_ext.ast_similarity(ref_mod, path), 6)
            except Exception as err:
                row[f"{v}:ast_error"] = f"{type(err).__name__}: {str(err)[:100]}"
        if ref_cfg is not None:
            try:
                cfg = metrics_ext.cfg_of(binding, path)
                row[f"{v}:cfg"] = round(metrics_ext.cfg_similarity(ref_cfg, cfg), 6)
            except Exception as err:
                row[f"{v}:cfg_error"] = f"{type(err).__name__}: {str(err)[:100]}"
    return row


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-nodes", type=int, default=10**9)
    ap.add_argument("--variants", default=",".join(VARIANTS))
    args = ap.parse_args()
    variants = tuple(args.variants.split(","))
    probe = metrics_ext.cfg_probe()
    binding = probe.load_binding()
    probe.ensure_sanitizer_preload(binding)
    done: dict[str, Any] = {}
    if OUT.is_file():
        done = {r["design"]: r for r in json.loads(OUT.read_text(encoding="utf-8"))}
    for design, nodes in r2lib.test_designs(r2lib.VEVAL, "f3", None):
        if nodes > args.max_nodes or design in done:
            continue
        stem = design.removeprefix("ve_")
        row = score_design(binding, design, REFS / f"{stem}_ref.sv", variants)
        row["f3_nodes"] = nodes
        done[design] = row
        OUT.write_text(json.dumps(list(done.values()), sort_keys=True, indent=1) + "\n",
                       encoding="utf-8")
        print(design, nodes, {k: v for k, v in row.items() if k.endswith(("ast", "cfg"))},
              flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
