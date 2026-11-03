"""Block ports, the BLIF text of a block, the frozen prompts, a faithful Verilog of the cells, and
the assembly of the decoded blocks into one ``TopModule`` (a deterministic text join, no model).

Prompts are the committed files ``block_prompt_lut.txt`` (arm D, one call per block) and
``a_prompt_lut.txt`` (arm A, the Gate-Breaker prompt with the LUT netlist); their sha256 is in
EXPERIMENT.md. A block's ports are single-bit identifiers (``in[3]`` is ``in_3_``, any other net
``w<k>``).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import q12_env as env
from q12_nl import Cell, Netlist

common: Any = env.mod("common")
bp: Any = env.mod("build_prompts")
GATE_WORD = "Gate-level netlist:"


def template(name: str) -> str:
    return (env.HERE / name).read_text(encoding="utf-8")


@dataclass
class Ports:
    inputs: list[str]  # net names, sorted by identifier
    outputs: list[str]
    internal: list[str]


def module_name(bid: int) -> str:
    return f"Block_{bid}"


def block_ports(nl: Netlist, blocks: list[Any]) -> list[Ports]:
    """Boundary of every block: nets read inside and driven outside are inputs; nets driven inside
    and read outside (or a primary output) are outputs. A clock net is an input."""
    owner = {c: b.bid for b in blocks for c in b.cells}
    drv = nl.driver()
    top_out = set(nl.outputs)
    reads: dict[str, set[int]] = {}
    for c in nl.cells:
        for n in c.reads:
            reads.setdefault(n, set()).add(owner.get(c.idx, -1))  # -1: glue, outside every block
    res: list[Ports] = []
    for b in blocks:
        mine = set(b.cells)
        ins: set[str] = set()
        outs: set[str] = set()
        inner: set[str] = set()
        for ci in b.cells:
            c = nl.cells[ci]
            for n in c.reads:
                (inner if drv.get(n) in mine else ins).add(n)
            for o in c.outs:
                if o in top_out or (reads.get(o, set()) - {b.bid}):
                    outs.add(o)
                else:
                    inner.add(o)
        inner -= ins | outs
        key = nl.ident.__getitem__
        res.append(Ports(sorted(ins, key=key), sorted(outs, key=key), sorted(inner, key=key)))
    return res


def cell_blif(nl: Netlist, c: Cell) -> str:
    s = nl.ident
    if c.kind == "lut":
        head = ".names " + " ".join(s[n] for n in [*c.ins, *c.outs])
        return "\n".join([head, *c.cover])
    if c.kind == "ff":
        return f".latch {s[c.ins[0]]} {s[c.outs[0]]} re {s[c.clock]} 3"
    pins = " ".join(f"{p}={s[n]}" for p, n in c.pins)
    return f".subckt {c.model} {pins}"


def fragment(nl: Netlist, bid: int, cells: list[int], ports: Ports) -> str:
    """The block as BLIF: model name, boundary nets, its cells in the netlist's order."""
    s = nl.ident
    lines = [f".model {module_name(bid)}", ".inputs " + " ".join(s[n] for n in ports.inputs),
             ".outputs " + " ".join(s[n] for n in ports.outputs)]
    lines += [cell_blif(nl, nl.cells[ci]) for ci in cells]
    lines.append(".end")
    return "\n".join(lines)


def prompt_text(nl: Netlist, bid: int, cells: list[int], ports: Ports) -> str:
    """The user message of a block call (exact file text): arm D."""
    s = nl.ident
    body = (template("block_prompt_lut.txt").replace("{NAME}", module_name(bid))
            .replace("{INPUTS}", ", ".join(s[n] for n in ports.inputs) or "(none)")
            .replace("{OUTPUTS}", ", ".join(s[n] for n in ports.outputs) or "(none)")
            .replace("{NETLIST}", fragment(nl, bid, cells, ports)))
    return str(body.rstrip("\n") + "\n" + common.SUFFIX + "\nAnswer:\n")


def whole_blif(nl: Netlist) -> str:
    """The whole netlist as BLIF with the prompt's identifiers (arm A)."""
    s = nl.ident
    lines = [".model RefModule", ".inputs " + " ".join(s[n] for n in nl.inputs),
             ".outputs " + " ".join(s[n] for n in nl.outputs)]
    lines += [cell_blif(nl, c) for c in nl.cells]
    lines.append(".end")
    return "\n".join(lines)


def a_prompt(nl: Netlist, dataset_prompt: str, prefix: str) -> str:
    """The user message of arm A: the Gate-Breaker 2-shot prompt, its netlist section replaced."""
    cut = dataset_prompt.find(GATE_WORD)
    if cut < 0:
        raise ValueError("no netlist section in the dataset prompt")
    intro = dataset_prompt[:cut].replace("gate-level netlist", "LUT-level netlist (BLIF)").strip()
    body = template("a_prompt_lut.txt").replace("{INTRO}", intro).replace(
        "{NETLIST}", whole_blif(nl))
    return str(bp.user_message(prefix, body, "A"))


def _lit(nl: Netlist, n: str) -> str:
    return nl.ident[n]


def _tree(tt: list[int], names: list[str]) -> str:
    """Shannon tree of a truth table (first input = most significant index bit) as nested ``?:``
    with equal branches merged: exact three-valued behaviour, an unknown input only gives an
    unknown output when the function depends on it (a sum of minterms would not)."""
    if all(v == tt[0] for v in tt):
        return f"1'b{tt[0]}"
    half = len(tt) // 2
    lo, hi = _tree(tt[:half], names[1:]), _tree(tt[half:], names[1:])
    return lo if lo == hi else f"({names[0]} ? {hi} : {lo})"


def lut_expr(nl: Netlist, c: Cell) -> str:
    """The function of a LUT cover as a Verilog expression on the identifiers of its inputs."""
    k = len(c.ins)
    if k == 0:
        return "1'b1" if c.cover else "1'b0"
    rows = [r.split()[0] for r in c.cover]
    tt = [int(any(all(ch in ("-", bit) for ch, bit in zip(row, f"{m:0{k}b}", strict=True))
                  for row in rows)) for m in range(2**k)]
    return _tree(tt, [_lit(nl, n) for n in c.ins])


def cell_verilog(nl: Netlist, c: Cell, init: bool) -> str:
    """One cell as behavioural Verilog on the block's identifiers (``init``: flip-flop starts 0)."""
    s = nl.ident
    if c.kind == "lut":
        return f"  assign {s[c.outs[0]]} = {lut_expr(nl, c)};"
    if c.kind == "ff":
        q = s[c.outs[0]]
        return ((f"  initial {q} = 1'b0;\n" if init else "")
                + f"  always @(posedge {s[c.clock]}) {q} <= {s[c.ins[0]]};")
    p = dict(c.pins)
    total = f"{s[p['a']]} + {s[p['b']]} + {s[p['cin']]}"
    return f"  assign {{{s[p['cout']]}, {s[p['sumout']]}}} = {total};"


def stub_module(nl: Netlist, bid: int, cells: list[int], ports: Ports, init: bool = True) -> str:
    """Behavioural RTL of the block, equivalent to its cells, with the block's port names (the
    dry run's perfect reply; ``init=False`` is the block check's reference)."""
    s = nl.ident
    seq = {nl.cells[c].outs[0] for c in cells if nl.cells[c].kind == "ff"}
    names = ports.inputs + ports.outputs
    lines = [f"module {module_name(bid)}({', '.join(s[n] for n in names)});"]
    lines += [f"  input {s[n]};" for n in ports.inputs]
    lines += [f"  output {s[n]};" for n in ports.outputs]
    lines += [f"  reg {s[n]};" for n in ports.outputs if n in seq]
    lines += [f"  {'reg' if n in seq else 'wire'} {s[n]};" for n in ports.internal]
    lines += [cell_verilog(nl, nl.cells[ci], init) for ci in cells]
    lines.append("endmodule")
    return "\n".join(lines) + "\n"


def glue_const(c: Cell) -> str:
    return "1'b1" if c.cover else "1'b0"


def top_net(nl: Netlist, n: str) -> str:
    """The expression of a net in TopModule: the original bit of a primary net, else a wire."""
    return nl.orig[n] if n in nl.orig else "t_" + nl.ident[n]


def assemble(nl: Netlist, gate: Any, blocks: list[Any], ports: list[Ports],
             codes: dict[int, str]) -> str:
    """One text: the decoded block modules (``codes``: block id to code) and a TopModule that
    instantiates every block on the netlist wires. ``gate`` is the Gate-Breaker netlist of the
    same design (its header and port declarations are the interface of the testbench)."""
    rn10: Any = env.mod("q10_render")
    top = [f"module TopModule({', '.join(gate.header)});", *rn10.top_ports(gate)]
    inner = sorted({nl.ident[n] for n in nl.ident if n not in nl.orig})
    top += [f"  wire t_{w};" for w in inner]
    for b, p in zip(blocks, ports, strict=True):
        conn = ", ".join(f".{nl.ident[n]}({top_net(nl, n)})" for n in p.inputs + p.outputs)
        top.append(f"  {module_name(b.bid)} u_{b.bid}({conn});")
    top += [f"  assign {top_net(nl, c.outs[0])} = "
            f"{top_net(nl, c.ins[0]) if c.ins else glue_const(c)};" for c in nl.cells if c.glue]
    top.append("endmodule")
    body = [codes[b.bid].rstrip("\n") for b in blocks]
    return "\n\n".join([*body, "\n".join(top)]) + "\n"
