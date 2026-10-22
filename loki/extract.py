"""Read the final top module of an Odin III design into a Netlist (spec 4 step 4, 5.1)."""

from __future__ import annotations

from typing import Any

from loki.model import FinalCell, Net, Netlist, PortBit
from loki.snapshot import node_ports, node_spans

_CONSTS = ("$_CONST0_", "$_CONST1_", "$_CONSTX_")


class Unsupported(Exception):
    """The final design holds something L0 does not label (instances, tristates, inout)."""


def _kind(design: Any, node: Any) -> str:
    typ = str(node.type_name)
    if typ == "$lut":
        return "lut"
    if typ.startswith(("$_DFF", "$_DLATCH")):
        return "ff"
    if typ in _CONSTS:
        return "const"
    if "tribuf" in typ.lower() or typ.startswith("$_TBUF"):
        raise Unsupported(f"tristate cell {typ}")
    if design.module(typ) is not None:
        raise Unsupported(f"instance of module {typ}")
    gran = str(node.granularity)
    if gran == "hard":
        return "hard"
    raise Unsupported(f"unmapped {gran} cell {typ}")


def _cell(design: Any, node: Any) -> FinalCell:
    if any(p.direction == "inout" for p in node.ports()):
        raise Unsupported(f"inout port on {node.type_name}")
    return FinalCell(
        id=int(node.id),
        kind=_kind(design, node),
        type=str(node.type_name),
        name=str(node.name),
        params=dict(node.params()),
        spans=node_spans(node),
        inputs=node_ports(node, "in"),
        outputs=node_ports(node, "out"),
    )


def _net_names(net: Any) -> tuple[str, ...]:
    return tuple(n for n in [net.name, *net.aliases()] if n)


def _port_bits(
    module: Any, extra: list[int], next_net: int
) -> tuple[list[PortBit], int]:
    bits: list[PortBit] = []
    for mp in module.ports():
        typ = str(mp.node.type_name)
        if typ == "$port_inout":
            raise Unsupported(f"inout port {mp.wire.name}")
        direction = "in" if typ == "$port_in" else "out"
        pins = mp.node.pins()
        spans = node_spans(mp.node)
        for bit, pin in enumerate(pins):
            net = pin.net()
            if net is None:
                net_id = next_net
                next_net += 1
                extra.append(net_id)
            else:
                net_id = int(net.id)
            name = f"{mp.wire.name}[{bit}]" if len(pins) > 1 else str(mp.wire.name)
            bits.append(PortBit(name, direction, net_id, spans))
    return bits, next_net


def extract_netlist(design: Any, top_name: str) -> Netlist:
    """The final top module as a Netlist; Unsupported when it holds more than L0 handles."""
    module = design.top()
    cells = tuple(
        _cell(design, n) for n in module.nodes() if not str(n.type_name).startswith("$port_")
    )
    all_nets = {int(n.id): Net(int(n.id), _net_names(n)) for n in module.nets()}
    extra: list[int] = []
    bits, _ = _port_bits(module, extra, max(all_nets, default=0) + 1)
    used = {n for c in cells for p in (*c.inputs, *c.outputs) for n in p.nets if n}
    used.update(pb.net for pb in bits)
    nets = {i: all_nets.get(i, Net(i, ())) for i in sorted(used)}
    return Netlist(top_name, nets, cells, tuple(bits))
