"""Stub decoder (dry run only), cell models, and the block equivalence check by simulation.

``stub_decode`` writes a faithful RTL of a block (one ``assign`` per gate, one ``always`` per
flip-flop): the dry run uses it as a perfect reply. ``block_check`` simulates a decoded block
against the block's own netlist fragment (cell models below) on random inputs with Icarus Verilog
and reports ``ok`` / ``mismatch`` / ``compile`` / ``inconclusive``; it is a diagnostic per block,
the pass of a design is always the VerilogEval testbench (or the equivalence check of the design).
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import q10_render as rn
from q10_blocks import Block
from q10_nl import Netlist, is_const

CELLS_V = """module NOT(input A, output Y); assign Y = ~A; endmodule
module BUF(input A, output Y); assign Y = A; endmodule
module NAND(input A, input B, output Y); assign Y = ~(A & B); endmodule
module NOR(input A, input B, output Y); assign Y = ~(A | B); endmodule
module DFF(input C, input D, output reg Q); always @(posedge C) Q <= D; endmodule
module DFFSR(input C, input D, input R, input S, output reg Q);
  always @(posedge C or posedge R or posedge S) if (R) Q <= 1'b0; else if (S) Q <= 1'b1;
    else Q <= D;
endmodule
"""
CYCLES = 400
TIMEOUT_S = 30


def _pin(nl: Netlist, v: str) -> str:
    return "1'b" + v[1] if is_const(v) and v != "#x" else "1'bx" if is_const(v) else nl.san[v]


def stub_decode(nl: Netlist, b: Block, ports: rn.Ports) -> str:
    """Behavioural RTL of the block, equivalent to its cells, with the block's port names. Each
    flip-flop starts at 0 (some references initialise their registers; X in a reference matches
    anything in the testbench, so 0 is safe)."""
    s = nl.san
    seq = {nl.cells[c].out for c in b.cells if nl.cells[c].typ.startswith("DFF")}
    names = ports.inputs + ports.outputs
    lines = [f"module {rn.module_name(b)}({', '.join(s[n] for n in names)});"]
    lines += [f"  input {s[n]};" for n in ports.inputs]
    lines += [f"  output {s[n]};" for n in ports.outputs]
    lines += [f"  reg {s[n]};" for n in ports.outputs if n in seq]
    lines += [f"  {'reg' if n in seq else 'wire'} {s[n]};" for n in ports.internal]
    lines += [f"  initial {s[nl.cells[c].out]} = 1'b0;" for c in b.cells
              if nl.cells[c].typ.startswith("DFF")]
    for ci in b.cells:
        c = nl.cells[ci]
        p = {k: _pin(nl, v) for k, v in c.pins.items()}
        if c.typ == "NOT":
            lines.append(f"  assign {p['Y']} = ~{p['A']};")
        elif c.typ == "BUF":
            lines.append(f"  assign {p['Y']} = {p['A']};")
        elif c.typ == "NAND":
            lines.append(f"  assign {p['Y']} = ~({p['A']} & {p['B']});")
        elif c.typ == "NOR":
            lines.append(f"  assign {p['Y']} = ~({p['A']} | {p['B']});")
        elif c.typ == "DFF":
            lines.append(f"  always @(posedge {p['C']}) {p['Q']} <= {p['D']};")
        else:
            lines.append(f"  always @(posedge {p['C']} or posedge {p['R']} or posedge {p['S']})"
                         f" if ({p['R']}) {p['Q']} <= 1'b0; else if ({p['S']}) {p['Q']} <= 1'b1;"
                         f" else {p['Q']} <= {p['D']};")
    lines.append("endmodule")
    return "\n".join(lines) + "\n"


def _tb(nl: Netlist, b: Block, ports: rn.Ports) -> str:
    s = nl.san
    name = rn.module_name(b)
    clocks = sorted({s[nl.cells[c].pins["C"]] for c in b.cells
                     if nl.cells[c].typ.startswith("DFF") and not is_const(nl.cells[c].pins["C"])})
    ins = [s[n] for n in ports.inputs]
    outs = [s[n] for n in ports.outputs]
    decl = "".join(f"  reg {i};\n" for i in ins) + "".join(f"  wire {o}_r, {o}_d;\n" for o in outs)

    def conn(suf: str) -> str:
        parts = [f".{i}({i})" for i in ins] + [f".{o}({o}{suf})" for o in outs]
        return ", ".join(parts)

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


def block_check(nl: Netlist, b: Block, ports: rn.Ports, code: str, work: Path) -> str:
    """ok | mismatch | compile | inconclusive | timeout for a decoded block against its cells."""
    iverilog, vvp = shutil.which("iverilog"), shutil.which("vvp")
    if not iverilog or not vvp:
        raise FileNotFoundError("iverilog and vvp are required")
    work.mkdir(parents=True, exist_ok=True)
    frag = re.sub(rf"\bmodule {rn.module_name(b)}\b", f"module {rn.module_name(b)}_r",
                  rn.fragment(nl, b, ports))
    (work / "ref.v").write_text(CELLS_V + frag + "\n", encoding="utf-8", newline="\n")
    (work / "dut.v").write_text(code, encoding="utf-8", newline="\n")
    (work / "tb.v").write_text(_tb(nl, b, ports), encoding="utf-8", newline="\n")
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
