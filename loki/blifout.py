"""BLIF writer for a Netlist under a naming scheme, and the inverse for port signals (spec 6.2)."""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass

from loki.anon import Numbering, logic_cells
from loki.model import FinalCell, Netlist, Port

# How a $lut's LUT string indexes input patterns. "index_lsb_first": string position i is the
# output for the pattern where A[k] is bit k of i. Task 4 step 6 checks this against Odin III.
LUT_ROW_ORDER = "index_lsb_first"

_CONSTS = ("$_CONST0_", "$_CONST1_", "$_CONSTX_")
_LATCH = {"$_DFF_P_": "re", "$_DFF_N_": "fe", "$_DLATCH_P_": "ah", "$_DLATCH_N_": "al"}
_CLOCK_PORTS = ("C", "CLK", "E", "EN")


@dataclass(frozen=True)
class Naming:
    """Names used in the BLIF: net by id, cell by value, output buffer by port-bit name."""

    net: Callable[[int], str]
    cell: Callable[[FinalCell], str]
    po_buffer: Callable[[str], str]


def _port_owners(nl: Netlist) -> dict[int, str]:
    """Port bit whose name a net carries: its input bit, else the first output bit on it."""
    owners: dict[int, str] = {}
    for pb in nl.port_bits:
        if pb.direction == "in":
            owners[pb.net] = pb.name
    for pb in nl.port_bits:
        if pb.direction == "out" and pb.net not in owners:
            owners[pb.net] = pb.name
    return owners


def identity_naming(nl: Netlist) -> Naming:
    """Original port-bit names on port nets, ``w<id>`` on other nets, ``c<id>`` on cells."""
    owners = _port_owners(nl)
    return Naming(
        net=lambda i: owners.get(i, f"w{i}"),
        cell=lambda c: f"c{c.id}",
        po_buffer=lambda name: name,
    )


def anon_naming(num: Numbering, nl: Netlist) -> Naming:
    """The ``n<k>`` names of a Numbering."""
    return Naming(
        net=lambda i: num.net[i],
        cell=lambda c: num.cell[c.id],
        po_buffer=lambda name: num.po[name],
    )


def _outputs(nl: Netlist, naming: Naming) -> tuple[list[str], list[tuple[str, str]]]:
    """Output signal names and the (net, buffer) pairs for output bits that need a buffer."""
    pi_nets = {pb.net for pb in nl.port_bits if pb.direction == "in"}
    seen: set[int] = set()
    signals: list[str] = []
    buffers: list[tuple[str, str]] = []
    for pb in nl.port_bits:
        if pb.direction != "out":
            continue
        if pb.net in pi_nets or pb.net in seen:
            buf = naming.po_buffer(pb.name)
            buffers.append((naming.net(pb.net), buf))
            signals.append(buf)
        else:
            signals.append(naming.net(pb.net))
        seen.add(pb.net)
    return signals, buffers


def _port(cell: FinalCell, names: tuple[str, ...]) -> Port:
    for p in (*cell.inputs, *cell.outputs):
        if p.name in names:
            return p
    raise ValueError(f"cell {cell.id} ({cell.type}) has no port among {names}")


def _single(port: Port, naming: Naming) -> str:
    if len(port.nets) != 1 or not port.nets[0]:
        raise ValueError(f"port {port.name} is not one connected bit")
    return naming.net(port.nets[0])


def _lut_lines(cell: FinalCell, naming: Naming) -> list[str]:
    a = _port(cell, ("A",))
    if not all(a.nets):
        raise ValueError(f"LUT cell {cell.id} has an unconnected input")
    ins = [naming.net(n) for n in a.nets]
    out = _single(_port(cell, ("Y",)), naming)
    table = str(cell.params["LUT"])
    width = len(ins)
    if len(table) != 1 << width:
        raise ValueError(f"LUT cell {cell.id}: table length {len(table)} for width {width}")
    lines = [".names " + " ".join([*ins, out])]
    for i, bit in enumerate(table):
        if bit == "1":
            pattern = "".join("1" if (i >> k) & 1 else "0" for k in range(width))
            lines.append(f"{pattern} 1" if pattern else "1")
    return lines


def _const_lines(cell: FinalCell, naming: Naming) -> list[str]:
    out = _single(_port(cell, ("Y",)), naming)
    lines = [f".names {out}"]
    if cell.type == "$_CONST1_":
        lines.append("1")
    return lines


def _latch_lines(cell: FinalCell, naming: Naming) -> list[str]:
    kind = _LATCH.get(cell.type)
    if kind is None:
        raise ValueError(f"unsupported storage cell type {cell.type}")
    d = _single(_port(cell, ("D",)), naming)
    q = _single(_port(cell, ("Q",)), naming)
    clk = _single(_port(cell, _CLOCK_PORTS), naming)
    return [f".latch {d} {q} {kind} {clk} 3"]


def _subckt_lines(cell: FinalCell, naming: Naming) -> list[str]:
    conns: list[str] = []
    for port in (*cell.inputs, *cell.outputs):
        for bit, net in enumerate(port.nets):
            if not net:
                continue
            formal = port.name if port.width == 1 else f"{port.name}[{bit}]"
            conns.append(f"{formal}={naming.net(net)}")
    return [".subckt " + " ".join([cell.type, *conns])]


def _cell_lines(cell: FinalCell, naming: Naming) -> list[str]:
    if cell.type == "$lut":
        lines = _lut_lines(cell, naming)
    elif cell.type in _CONSTS:
        lines = _const_lines(cell, naming)
    elif cell.kind == "ff":
        lines = _latch_lines(cell, naming)
    else:
        lines = _subckt_lines(cell, naming)
    return [*lines, f".cname {naming.cell(cell)}"]


def _group(cell: FinalCell) -> int:
    if cell.type in _CONSTS:
        return 0
    if cell.type == "$lut":
        return 1
    return 2 if cell.kind == "ff" else 3


def write_blif(nl: Netlist, naming: Naming) -> str:
    """The BLIF text of a netlist (deterministic; groups sorted by cell id)."""
    inputs = [naming.net(pb.net) for pb in nl.port_bits if pb.direction == "in"]
    outputs, buffers = _outputs(nl, naming)
    lines = [".model top", ".inputs " + " ".join(inputs), ".outputs " + " ".join(outputs)]
    for cell in sorted(logic_cells(nl), key=lambda c: (_group(c), c.id)):
        lines.extend(_cell_lines(cell, naming))
    for net, buf in buffers:
        lines.extend([f".names {net} {buf}", "1 1"])
    lines.append(".end")
    return "\n".join(lines) + "\n"


def _signal_map(key: dict[str, object], outputs: set[str]) -> dict[str, str]:
    mapping: dict[str, str] = {}
    ports = key["ports"]
    assert isinstance(ports, list)
    for p in ports:
        anon, orig, net = str(p["anon"]), str(p["orig"]), str(p["net"])
        mapping[anon if (p["dir"] == "out" and anon in outputs) else net] = orig
    return mapping


_SPLIT = re.compile(r"(\s+)")


def deanonymise(blif: str, key: dict[str, object]) -> str:
    """Map port signals of an anonymised BLIF back to original port-bit names."""
    outputs: set[str] = set()
    for line in blif.splitlines():
        if line.startswith(".outputs"):
            outputs = set(line.split()[1:])
    mapping = _signal_map(key, outputs)
    out: list[str] = []
    for line in blif.splitlines():
        if line.startswith(".cname") or line.startswith(".model"):
            out.append(line)
            continue
        out.append("".join(_map_token(tok, mapping) for tok in _SPLIT.split(line)))
    return "\n".join(out) + "\n"


def _map_token(tok: str, mapping: dict[str, str]) -> str:
    if tok in mapping:
        return mapping[tok]
    if "=" in tok:
        formal, _, actual = tok.partition("=")
        return f"{formal}={mapping.get(actual, actual)}"
    return tok
