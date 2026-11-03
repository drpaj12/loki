"""The block check by random simulation, and the equivalence check of a design with its netlist.

Block check (as ``q10_check.block_check``): the decoded block is simulated against the faithful
Verilog of its own cells (``q12_render.stub_module`` without register initialisation) on 400
random cycles with Icarus Verilog; ``ok`` / ``mismatch`` / ``compile`` / ``inconclusive`` /
``timeout``. Design equivalence (designs without a testbench, tier ext): Yosys flattens the
faithful Verilog of the whole netlist (``gold``) and the assembled sample, ABC ``dsec``
(sequential equivalence, register init 0) compares them (``q10_equiv`` machinery).
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

import q12_env as env
import q12_render as rn
from q12_nl import Netlist

q10_equiv: Any = env.mod("q10_equiv")
CYCLES = 400
TIMEOUT_S = 30


def _tb(nl: Netlist, bid: int, cells: list[int], ports: rn.Ports) -> str:
    s = nl.ident
    name = rn.module_name(bid)
    ins_set = set(ports.inputs)
    clocks = sorted({s[nl.cells[c].clock] for c in cells
                     if nl.cells[c].kind == "ff" and nl.cells[c].clock in ins_set})
    ins = [s[n] for n in ports.inputs]
    outs = [s[n] for n in ports.outputs]
    decl = "".join(f"  reg {i};\n" for i in ins) + "".join(f"  wire {o}_r, {o}_d;\n" for o in outs)

    def conn(suf: str) -> str:
        return ", ".join([f".{i}({i})" for i in ins] + [f".{o}({o}{suf})" for o in outs])

    free = [i for i in ins if i not in clocks]
    rnd = "".join(f"      {i} = $urandom;\n" for i in free)
    cmp_ = " && ".join(f"({o}_r !== 1'bx ? {o}_d === {o}_r : 1'b1)" for o in outs) or "1'b1"
    known = " || ".join(f"({o}_r !== 1'bx)" for o in outs) or "1'b0"
    clk0 = "".join(f"  initial {c} = 0;\n" for c in clocks)
    tog = "".join(f"      {c} = ~{c};\n" for c in clocks)
    return f"""`timescale 1ns/1ps
module tbblk;
{decl}{clk0}  integer k, bad, seen;
  {name}_r r({conn('_r')});
  {name} d({conn('_d')});
  initial begin
    bad = 0; seen = 0;
    for (k = 0; k < {CYCLES}; k = k + 1) begin
{rnd}      #1;
{tog}      #1;
      if ({known}) begin seen = seen + 1; if (!({cmp_})) bad = bad + 1; end
    end
    $display("BLOCKEQ %0d %0d", bad, seen);
    $finish;
  end
endmodule
"""


def block_check(nl: Netlist, bid: int, cells: list[int], ports: rn.Ports, code: str,
                work: Path) -> str:
    iverilog, vvp = shutil.which("iverilog"), shutil.which("vvp")
    if not iverilog or not vvp:
        raise FileNotFoundError("iverilog and vvp are required")
    work.mkdir(parents=True, exist_ok=True)
    ref = re.sub(rf"\bmodule {rn.module_name(bid)}\b", f"module {rn.module_name(bid)}_r",
                 rn.stub_module(nl, bid, cells, ports, init=False))
    (work / "ref.v").write_text(ref, encoding="utf-8", newline="\n")
    (work / "dut.v").write_text(code, encoding="utf-8", newline="\n")
    (work / "tb.v").write_text(_tb(nl, bid, cells, ports), encoding="utf-8", newline="\n")
    comp = subprocess.run([iverilog, "-g2012", "-s", "tbblk", "-o", str(work / "sim.bin"),
                           str(work / "ref.v"), str(work / "dut.v"), str(work / "tb.v")],
                          capture_output=True, text=True, check=False, cwd=str(work))
    if comp.returncode != 0:
        return "compile"
    try:
        sim = subprocess.run([vvp, str(work / "sim.bin")], capture_output=True, text=True,
                             check=False, cwd=str(work), timeout=TIMEOUT_S)
    except subprocess.TimeoutExpired:
        return "timeout"
    m = re.search(r"BLOCKEQ (\d+) (\d+)", sim.stdout)
    if not m or int(m.group(2)) == 0:
        return "inconclusive"
    return "ok" if int(m.group(1)) == 0 else "mismatch"


def gold_module(nl: Netlist, gate: Any) -> str:
    """The whole netlist as one module of the interface of the design, named ``gold`` (the
    faithful Verilog of its cells; one block of every cell, with the original port bits)."""
    one = type("One", (), {"bid": 0, "cells": list(range(len(nl.cells)))})()
    ports = rn.block_ports(nl, [one])[0]
    code = rn.assemble(nl, gate, [one], [ports],
                       {0: rn.stub_module(nl, 0, one.cells, ports)})
    return code.replace("module TopModule(", "module gold(")


def design_equiv(nl: Netlist, gate: Any, sample: Path, work: Path) -> str:
    """``equiv`` | ``neq`` | ``error`` | ``timeout``: the assembled sample against the netlist."""
    work.mkdir(parents=True, exist_ok=True)
    gold = work / "gold.v"
    gold.write_text(gold_module(nl, gate), encoding="utf-8", newline="\n")
    script = "\n".join([
        f"read_verilog -sv {gold}", "hierarchy -top gold", q10_equiv.PREP, "write_blif gold.blif",
        "design -reset", f"read_verilog -sv {sample}", "hierarchy -top TopModule",
        q10_equiv.PREP, "write_blif gate.blif", ""])
    (work / "eq.ys").write_text(script, encoding="utf-8", newline="\n")
    bin_ = q10_equiv.BIN
    try:
        y = subprocess.run([str(bin_ / "yosys"), "-q", "eq.ys"], capture_output=True, text=True,
                           check=False, cwd=str(work), timeout=q10_equiv.TIMEOUT_S)
        if y.returncode != 0:
            return "error"
        a = subprocess.run([str(bin_ / "yosys-abc"), "-c", "read_blif gold.blif; dsec gate.blif"],
                           capture_output=True, text=True, check=False, cwd=str(work),
                           timeout=q10_equiv.TIMEOUT_S)
    except subprocess.TimeoutExpired:
        return "timeout"
    out = a.stdout + a.stderr
    if "are equivalent" in out and "NOT" not in out:
        return "equiv"
    return "neq" if "NOT EQUIVALENT" in out.upper() else "error"
