"""Function check of the converted netlist: a BLIF simulator and an iverilog testbench.

``BlifSim`` evaluates the BLIF itself (the reference). ``sim_library`` is a behavioural Verilog
model of every cell of the two ``.hgl`` libraries, so iverilog can run the converted instance
netlist. ``compare_traces`` drives random vectors through both and returns the first mismatch.
All flip-flops are clocked together once per cycle, start at their ``init`` (unknown: 0), and
the primary outputs are sampled before the clock edge.
"""

from __future__ import annotations

import random
import subprocess
from pathlib import Path

from loki.hal.blif import Blif, Gate, Latch, Subckt


class SimError(RuntimeError):
    """A combinational loop, an unsupported cell or a tool failure."""


class BlifSim:
    def __init__(self, b: Blif) -> None:
        self.b = b
        self.gates = {c.output: c for c in b.cells if isinstance(c, Gate)}
        self.latches = [c for c in b.cells if isinstance(c, Latch)]
        self.srffs = [c for c in b.cells if isinstance(c, Subckt)]
        for s in self.srffs:
            if s.model != "DFFSR":
                raise SimError(f"cannot simulate .subckt {s.model}")
        self.clocks = {c.clock for c in self.latches} | {
            dict(s.pins)["C"] for s in self.srffs}
        self.state: dict[str, int] = {c.q: 1 if c.init == "1" else 0 for c in self.latches}
        self.state.update({dict(s.pins)["Q"]: 0 for s in self.srffs})

    def _eval(self, inputs: dict[str, int]) -> dict[str, int]:
        val: dict[str, int] = {**self.state}
        for n in self.b.inputs:
            val[n] = 0 if n in self.clocks else inputs[n]
        busy: set[str] = set()

        def get(net: str) -> int:
            if net in val:
                return val[net]
            g = self.gates.get(net)
            if g is None:
                raise SimError(f"undriven net {net}")
            if net in busy:
                raise SimError(f"combinational loop at {net}")
            busy.add(net)
            idx = sum(get(n) << j for j, n in enumerate(g.inputs))
            val[net] = (g.table() >> idx) & 1
            busy.discard(net)
            return val[net]

        for net in [*self.gates, *self.b.outputs]:
            get(net)
        return val

    def _async(self, val: dict[str, int]) -> bool:
        changed = False
        for s in self.srffs:
            p = dict(s.pins)
            want = 1 if val[p["S"]] else 0 if val[p["R"]] else self.state[p["Q"]]
            if want != self.state[p["Q"]]:
                self.state[p["Q"]] = want
                changed = True
        return changed

    def step(self, inputs: dict[str, int]) -> list[int]:
        """Apply ``inputs``, return the outputs, then take one clock edge."""
        val = self._eval(inputs)
        for _ in range(8):
            if not self._async(val):
                break
            val = self._eval(inputs)
        outs = [val[n] for n in self.b.outputs]
        nxt = {c.q: val[c.d] for c in self.latches}
        for s in self.srffs:
            p = dict(s.pins)
            nxt[p["Q"]] = 1 if val[p["S"]] else 0 if val[p["R"]] else val[p["D"]]
        self.state.update(nxt)
        return outs


def _lut_model(k: int) -> str:
    width = 1 << k
    pins = ", ".join(f"I{j}" for j in range(k))
    idx = ", ".join(f"I{j}" for j in reversed(range(k)))
    sel = f"{{{idx}}}"
    return (f"module LUT{k} #(parameter [{width - 1}:0] INIT = 0) (input {pins}, output O);\n"
            f"  assign O = INIT[{sel}];\nendmodule\n")


def sim_library(floor: str) -> str:
    """Behavioural Verilog of the cells of the floor's ``.hgl`` library."""
    common = (
        "module GND (output O); assign O = 1'b0; endmodule\n"
        "module VCC (output O); assign O = 1'b1; endmodule\n"
    )
    ff = ("module {n} #(parameter INIT = 1'b0) (input C, input D, output reg Q);\n"
          "  initial Q = INIT;\n  always @(posedge C) Q <= D;\nendmodule\n")
    if floor == "f2":
        return common + "".join(_lut_model(k) for k in range(1, 7)) + ff.format(n="FF")
    if floor == "f3":
        return common + ff.format(n="DFF") + (
            "module BUF (input A, output Y); assign Y = A; endmodule\n"
            "module INV (input A, output Y); assign Y = ~A; endmodule\n"
            "module NAND2 (input A, input B, output Y); assign Y = ~(A & B); endmodule\n"
            "module NOR2 (input A, input B, output Y); assign Y = ~(A | B); endmodule\n"
            "module DFFSR (input C, input D, input S, input R, output reg Q);\n"
            "  initial Q = 1'b0;\n"
            "  always @(S or R) if (S) Q = 1'b1; else if (R) Q = 1'b0;\n"
            "  always @(posedge C) if (!S && !R) Q <= D;\nendmodule\n")
    raise SimError(f"floor {floor!r}")


def vectors(b: Blif, cycles: int, seed: int) -> list[dict[str, int]]:
    rng = random.Random(seed)
    return [{n: rng.getrandbits(1) for n in b.inputs} for _ in range(cycles)]


def testbench(b: Blif, vecs: list[dict[str, int]], clocks: set[str]) -> str:
    ins = [n for n in b.inputs if n not in clocks]
    lines = ["module tb;"]
    lines += [f"  reg {n};" for n in b.inputs] + [f"  wire {n};" for n in b.outputs]
    conn = ", ".join(f".{n}({n})" for n in [*b.inputs, *b.outputs])
    lines.append(f"  {b.model} dut ({conn});")
    outs = ", ".join(b.outputs)
    lines.append("  initial begin")
    lines += [f"    {n} = 0;" for n in clocks]
    for v in vecs:
        lines += [f"    {n} = {v[n]};" for n in ins]
        lines.append("    #1;")
        lines.append(f'    $display("%b", {{{outs}}});')
        lines += [f"    {n} = 1;" for n in sorted(clocks)]
        lines.append("    #1;")
        lines += [f"    {n} = 0;" for n in sorted(clocks)]
        lines.append("    #1;")
    lines += ["    $finish;", "  end", "endmodule"]
    return "\n".join(lines) + "\n"


def run_iverilog(workdir: Path, files: list[str], timeout: int = 120) -> list[str]:
    """Compile ``files`` (names in ``workdir``) and run; returns the ``$display`` lines."""
    out = workdir / "sim.vvp"
    comp = subprocess.run(["iverilog", "-o", str(out), *files], cwd=workdir,
                          capture_output=True, text=True, timeout=timeout)
    if comp.returncode != 0:
        raise SimError(f"iverilog: {comp.stderr.strip()[:500]}")
    run = subprocess.run(["vvp", str(out)], cwd=workdir, capture_output=True, text=True,
                         timeout=timeout)
    if run.returncode != 0:
        raise SimError(f"vvp: {run.stderr.strip()[:500]}")
    return [ln for ln in run.stdout.splitlines() if ln and set(ln) <= set("01xz")]


def compare_traces(
    b: Blif, floor: str, hal_verilog: str, workdir: Path, cycles: int = 64, seed: int = 1
) -> str:
    """Empty string when the converted netlist matches the BLIF on random vectors, else the
    description of the first mismatching cycle."""
    sim = BlifSim(b)
    vecs = vectors(b, cycles, seed)
    expect = ["".join(str(x) for x in sim.step(v)) for v in vecs]
    (workdir / "dut.v").write_text(hal_verilog, encoding="utf-8")
    (workdir / "cells.v").write_text(sim_library(floor), encoding="utf-8")
    (workdir / "tb.v").write_text(testbench(b, vecs, sim.clocks), encoding="utf-8")
    got = run_iverilog(workdir, ["tb.v", "dut.v", "cells.v"])
    if len(got) != len(expect):
        return f"expected {len(expect)} lines, iverilog gave {len(got)}"
    for i, (e, g) in enumerate(zip(expect, got, strict=True)):
        if e != g:
            return f"cycle {i}: BLIF {e} converted {g}"
    return ""
