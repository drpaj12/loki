"""Block ports, the block netlist text, the frozen block prompt, and the assembly of the decoded
blocks into one ``TopModule`` (a deterministic text join: no model call).

The prompt is two committed files, ``block_prompt.txt`` and ``block_hint.txt`` (frozen in the plan
commit; their sha256 is in EXPERIMENT.md). Every net is a single-bit identifier (``in[3]`` becomes
``in_3_``); constants stay ``1'h0`` / ``1'h1``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import q10_env as env
from q10_blocks import Block
from q10_nl import Netlist, is_const

common: Any = env.mod("common")
bp: Any = env.mod("build_prompts")
KIND_NAMES = {"fsm": "a finite state machine", "counter": "a counter",
              "shift": "a shift register", "regfile": "a register file",
              "register": "a bank of registers"}


def template(name: str) -> str:
    return (env.HERE / name).read_text(encoding="utf-8")


@dataclass
class Ports:
    inputs: list[str]  # net bit keys, sorted by identifier
    outputs: list[str]
    internal: list[str]


def block_ports(nl: Netlist, blocks: list[Block]) -> list[Ports]:
    """Boundary of every block: nets read inside and driven outside are inputs; nets driven
    inside and read outside (or by an assign, or a top output bit) are outputs."""
    owner = {c: b.bid for b in blocks for c in b.cells}
    drv = {c.out: c.idx for c in nl.cells}
    outs_top = set(nl.port_bits("output")) | {r for _, r in nl.assigns}
    reads: dict[str, set[int]] = {}
    for c in nl.cells:
        for n in c.ins:
            if not is_const(n):
                reads.setdefault(n, set()).add(owner[c.idx])
    res: list[Ports] = []
    for b in blocks:
        mine = set(b.cells)
        ins: set[str] = set()
        outs: set[str] = set()
        inner: set[str] = set()
        for ci in b.cells:
            c = nl.cells[ci]
            for n in c.ins:
                if is_const(n):
                    continue
                (inner if drv.get(n) in mine else ins).add(n)
            o = c.out
            if o in outs_top or (reads.get(o, set()) - {b.bid}):
                outs.add(o)
            else:
                inner.add(o)
        inner -= ins | outs
        key = nl.san.__getitem__
        res.append(Ports(sorted(ins, key=key), sorted(outs, key=key), sorted(inner, key=key)))
    return res


def cell_text(nl: Netlist, ci: int) -> str:
    c = nl.cells[ci]
    pins = ",\n".join(f"    .{p}({'1' + chr(39) + 'h' + v[1:] if is_const(v) else nl.san[v]})"
                      for p, v in c.pins.items())
    return f"  {c.typ} {c.name} (\n{pins}\n  );"


def fragment(nl: Netlist, b: Block, ports: Ports) -> str:
    """The block as a Verilog module of single-bit ports and its cells, in the netlist's order."""
    name = module_name(b)
    s = nl.san
    head = ", ".join(s[n] for n in ports.inputs + ports.outputs)
    lines = [f"module {name}({head});"]
    lines += [f"  input {s[n]};" for n in ports.inputs]
    lines += [f"  output {s[n]};" for n in ports.outputs]
    lines += [f"  wire {s[n]};" for n in ports.internal]
    lines += [cell_text(nl, ci) for ci in b.cells]
    lines.append("endmodule")
    return "\n".join(lines)


def module_name(b: Block) -> str:
    return f"Block_{b.bid}"


def prompt_text(nl: Netlist, b: Block, ports: Ports, hint: bool) -> str:
    """The user message of a block call (exact file text); ``hint`` adds Loki's kind guess."""
    s = nl.san
    h = ""
    if hint and b.guess:
        h = template("block_hint.txt").replace("{KIND}", KIND_NAMES[b.guess]).rstrip("\n")
        h = "\n\n" + h.lstrip("\n")
    body = (template("block_prompt.txt").replace("{NAME}", module_name(b))
            .replace("{INPUTS}", ", ".join(s[n] for n in ports.inputs) or "(none)")
            .replace("{OUTPUTS}", ", ".join(s[n] for n in ports.outputs) or "(none)")
            .replace("{HINT}", h).replace("{NETLIST}", fragment(nl, b, ports)))
    return str(body.rstrip("\n") + "\n" + common.SUFFIX + "\nAnswer:\n")


def top_ports(nl: Netlist) -> list[str]:
    """Port declarations of TopModule (widths from the netlist), header order."""
    out = []
    for n in nl.header:
        kind, hi, lo = nl.decl[n]
        rng = f" [{hi}:{lo}]" if hi is not None else ""
        out.append(f"  {kind}{rng} {n};")
    return out


def _const(key: str) -> str:
    return {"#0": "1'b0", "#1": "1'b1"}.get(key, "1'bx")


def assemble(nl: Netlist, blocks: list[Block], ports: list[Ports], codes: dict[int, str]) -> str:
    """One text: the decoded block modules (``codes``: block id to code) and a TopModule that
    instantiates every block on the netlist wires. A top port bit is connected directly (no extra
    delta delay against a testbench); other nets are wires ``t_<identifier>``."""
    s = nl.san

    def net(key: str) -> str:
        if is_const(key):
            return _const(key)
        return key if nl.bits.get(key) in ("input", "output") else "t_" + s[key]

    body = ["\n".join(codes[b.bid].rstrip("\n").split("\n")) for b in blocks]
    top = [f"module TopModule({', '.join(nl.header)});", *top_ports(nl)]
    inner = sorted({s[k] for k in s if nl.bits.get(k) not in ("input", "output")})
    top += [f"  wire t_{w};" for w in inner]
    for lhs, rhs in nl.assigns:
        top.append(f"  assign {net(lhs)} = {net(rhs)};")
    for b, p in zip(blocks, ports, strict=True):
        conn = ", ".join(f".{s[n]}({net(n)})" for n in p.inputs + p.outputs)
        top.append(f"  {module_name(b)} u_{b.bid}({conn});")
    top.append("endmodule")
    return "\n\n".join([*body, "\n".join(top)]) + "\n"
