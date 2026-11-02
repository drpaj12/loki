"""Equivalence of an assembled design with its netlist (designs without a testbench).

Yosys reads the netlist with the cell models (``q10_check.CELLS_V``) and the assembled RTL,
flattens both, maps to gates, turns asynchronous set and reset into synchronous logic on both sides
(the same transform), and writes BLIF; ABC ``dsec`` (sequential equivalence, register init 0) then
compares them. Result: ``equiv``, ``neq``, ``error`` or ``timeout``. Read only on the designs.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import q10_check as ck
import q10_env as env

BIN = Path(os.environ.get("QL10_YOSYS_BIN",
                          str(env.WS / "external" / "vtr-verilog-to-routing" / "build" / "bin")))
TIMEOUT_S = 600
PREP = "proc; flatten; opt; techmap; async2sync; opt; clean"


def script(netlist: Path, module: str, sample: Path) -> str:
    return "\n".join([
        "read_verilog -sv cells.v", f"read_verilog -sv {netlist}", f"rename {module} gold",
        f"read_verilog -sv {sample}", "hierarchy -top gold", PREP, "write_blif gold.blif",
        "design -reset", "read_verilog -sv cells.v", f"read_verilog -sv {sample}",
        "hierarchy -top TopModule", PREP, "write_blif gate.blif", ""])


def design_equiv(netlist: Path, module: str, sample: Path, work: Path) -> str:
    """``equiv`` | ``neq`` | ``error`` | ``timeout``: the assembled sample against the netlist."""
    work.mkdir(parents=True, exist_ok=True)
    (work / "cells.v").write_text(ck.CELLS_V, encoding="utf-8", newline="\n")
    (work / "eq.ys").write_text(script(netlist, module, sample), encoding="utf-8", newline="\n")
    try:
        y = subprocess.run([str(BIN / "yosys"), "-q", "eq.ys"], capture_output=True, text=True,
                           check=False, cwd=str(work), timeout=TIMEOUT_S)
        if y.returncode != 0:
            return "error"
        a = subprocess.run([str(BIN / "yosys-abc"), "-c", "read_blif gold.blif; dsec gate.blif"],
                           capture_output=True, text=True, check=False, cwd=str(work),
                           timeout=TIMEOUT_S)
    except subprocess.TimeoutExpired:
        return "timeout"
    out = a.stdout + a.stderr
    if "are equivalent" in out and "NOT" not in out:
        return "equiv"
    return "neq" if "NOT EQUIVALENT" in out.upper() else "error"
