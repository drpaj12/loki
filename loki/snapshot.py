"""Word-level snapshot and instance sites read from an Odin III design (spec 4 step 2, 5.2)."""

from __future__ import annotations

from typing import Any

from loki.model import InstanceSite, Port, Snapshot, Span, WordCell

# Where the `fsm` pass leaves the state-register marker (probed in tests/test_odin_facts.py):
# the string attribute odin3_fsm_encoding on the state register's node (spec 7.6).
FSM_CARRIER = "node:odin3_fsm_encoding"
FSM_ATTR = "odin3_fsm_encoding"


def to_span(src: Any) -> Span:
    """An odin3.Source as a Span."""
    return Span(str(src.file), int(src.line), int(src.col), int(src.end_line), int(src.end_col))


def node_spans(node: Any) -> tuple[Span, ...]:
    return tuple(to_span(s) for s in node.sources())


def pin_net_id(pin: Any) -> int:
    net = pin.net()
    return int(net.id) if net is not None else 0


def node_ports(node: Any, direction: str) -> tuple[Port, ...]:
    """The node's ports whose direction is ``in`` (inout counts as in) or ``out``."""
    want_out = direction == "out"
    return tuple(
        Port(str(p.name), int(p.width), tuple(pin_net_id(pin) for pin in p.pins))
        for p in node.ports()
        if (p.direction == "out") == want_out
    )


def take_snapshot(design: Any, instances: tuple[InstanceSite, ...] = ()) -> Snapshot:
    """Every live word-level node of the top module, ports skipped."""
    module = design.top()
    words: list[WordCell] = []
    for node in module.nodes():
        typ = str(node.type_name)
        if typ.startswith("$port_"):
            continue
        words.append(
            WordCell(
                id=int(node.id),
                type=typ,
                name=str(node.name),
                params=dict(node.params()),
                spans=node_spans(node),
                inputs=node_ports(node, "in"),
                outputs=node_ports(node, "out"),
                fsm=node.attr(FSM_ATTR) is not None,
            )
        )
    return Snapshot(tuple(words), instances, str(module.name))


def take_instances(design: Any) -> tuple[InstanceSite, ...]:
    """Instance nodes of user modules in every module (call before ``flatten``)."""
    sites: list[InstanceSite] = []
    for module in design.modules():
        for node in module.nodes():
            typ = str(node.type_name)
            if design.module(typ) is None:
                continue
            spans = node_spans(node)
            if spans:
                sites.append(InstanceSite(spans[0], str(node.name), typ, str(module.name)))
    return tuple(sites)
