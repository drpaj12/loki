"""Graph building: node features, levels and edges (spec 6.4)."""

from __future__ import annotations

import heapq
from collections.abc import Sequence
from dataclasses import dataclass

from loki.anon import Numbering, logic_cells
from loki.labels import Label
from loki.model import FinalCell, Netlist
from loki.schemas import SCHEMA

_COMB_KINDS = ("lut", "hard", "gate")


def _is_comb(c: FinalCell) -> bool:
    return c.kind in _COMB_KINDS


def _drivers(nl: Netlist) -> dict[int, FinalCell]:
    """Net id -> the cell whose output port carries it."""
    out: dict[int, FinalCell] = {}
    for c in logic_cells(nl):
        for p in c.outputs:
            for n in p.nets:
                if n:
                    out[n] = c
    return out


def _input_nets(c: FinalCell) -> list[int]:
    return [n for p in c.inputs for n in p.nets if n]


def levels(nl: Netlist) -> tuple[dict[int, int], int]:
    """Level per cell id (longest combinational path) and the number of loops cut."""
    cells = {c.id: c for c in logic_cells(nl)}
    drv = _drivers(nl)
    level = {cid: 0 for cid, c in cells.items() if not _is_comb(c)}
    preds: dict[int, set[int]] = {}
    succs: dict[int, set[int]] = {cid: set() for cid in cells}
    for cid, c in cells.items():
        if not _is_comb(c):
            continue
        preds[cid] = {drv[n].id for n in _input_nets(c) if n in drv and _is_comb(drv[n])}
        for p in preds[cid]:
            succs[p].add(cid)
    pending = {cid: len(ps) for cid, ps in preds.items()}
    ready = [cid for cid, n in pending.items() if n == 0]
    heapq.heapify(ready)
    loops = 0
    while len(level) < len(cells):
        if not ready:
            loops += 1
            cut = min(cid for cid in preds if cid not in level)
            pending[cut] = 0
            heapq.heappush(ready, cut)
        cid = heapq.heappop(ready)
        if cid in level:
            continue
        level[cid] = 1 + max(
            (level.get(drv[n].id, 0) for n in _input_nets(cells[cid]) if n in drv), default=0
        )
        for s in succs[cid]:
            pending[s] -= 1
            if pending[s] == 0 and s not in level:
                heapq.heappush(ready, s)
    return level, loops


def lut_table_hex(table: str) -> str:
    """Hex of a LUT table, MSB (highest pattern index) first, padded to the table width."""
    digits = max(1, len(table) // 4)
    return format(int(table[::-1], 2), f"0{digits}x")


def _pin_names(c: FinalCell) -> list[tuple[str, int]]:
    """(pin name, net) for every connected input pin of a cell."""
    pins: list[tuple[str, int]] = []
    for p in c.inputs:
        for bit, net in enumerate(p.nets):
            if not net:
                continue
            if c.type == "$lut":
                name = f"I{bit}"
            elif c.kind == "ff":
                name = {"C": "CLK", "D": "D", "E": "EN"}.get(p.name, p.name)
            else:
                name = p.name if p.width == 1 else f"{p.name}[{bit}]"
            pins.append((name, net))
    return pins


@dataclass(frozen=True)
class _Node:
    nid: str
    kind: str
    cell: FinalCell | None
    in_net: int  # for a PO: the net it reads; for a PI: the net it drives


def _nodes(nl: Netlist, num: Numbering) -> list[_Node]:
    nodes = [_Node(num.cell[c.id], c.kind, c, 0) for c in logic_cells(nl)]
    for pb in nl.port_bits:
        if pb.direction == "in":
            nodes.append(_Node(num.pi[pb.name], "pi", None, pb.net))
        else:
            nodes.append(_Node(num.po[pb.name], "po", None, pb.net))
    return nodes


def _sink_counts(nl: Netlist) -> dict[int, int]:
    counts: dict[int, int] = {}
    for c in logic_cells(nl):
        for n in _input_nets(c):
            counts[n] = counts.get(n, 0) + 1
    for pb in nl.port_bits:
        if pb.direction == "out":
            counts[pb.net] = counts.get(pb.net, 0) + 1
    return counts


def _features(
    node: _Node, level: int, sinks: dict[int, int]
) -> dict[str, object]:
    c = node.cell
    feats: dict[str, object] = {
        "fan_in": 0, "fan_out": 0, "level": level, "lut_width": 0, "lut_table": "",
        "is_seq": 0, "is_const": 0, "hard_ports": 0,
    }
    if c is None:
        feats["fan_in"] = 1 if node.kind == "po" else 0
        feats["fan_out"] = sinks.get(node.in_net, 0) if node.kind == "pi" else 0
        return feats
    feats["fan_in"] = len(_input_nets(c))
    feats["fan_out"] = sum(sinks.get(n, 0) for p in c.outputs for n in p.nets if n)
    feats["is_seq"] = 1 if c.kind == "ff" else 0
    feats["is_const"] = 1 if c.kind == "const" else 0
    if c.type == "$lut":
        a = c.inputs[0]
        feats["lut_width"] = a.width
        feats["lut_table"] = lut_table_hex(str(c.params["LUT"]))
    if c.kind == "hard":
        feats["hard_ports"] = len(_input_nets(c)) + sum(n != 0 for p in c.outputs for n in p.nets)
    return feats


def _label_dict(lab: Label) -> dict[str, object]:
    return {
        "construct_type": lab.construct_type,
        "construct_types": lab.construct_types,
        "n_construct_cells": lab.n_construct_cells,
        "module_path": lab.module_path,
        "bus_name": lab.bus_name,
        "bit_index": lab.bit_index,
        "role": lab.role,
        "hdl_file": lab.hdl_file,
        "hdl_line": lab.hdl_line,
        "hdl_col": lab.hdl_col,
        "hdl_end_line": lab.hdl_end_line,
        "hdl_end_col": lab.hdl_end_col,
        "n_spans": lab.n_spans,
    }


def _net_driver_ids(nl: Netlist, num: Numbering) -> dict[int, str]:
    """Net id -> node id of its driver (a cell, or the input port bit that drives it)."""
    out = {n: num.cell[c.id] for n, c in _drivers(nl).items()}
    for pb in nl.port_bits:
        if pb.direction == "in":
            out[pb.net] = num.pi[pb.name]
    return out


def _edges(nl: Netlist, num: Numbering, nodes: list[_Node]) -> list[dict[str, object]]:
    drv = _net_driver_ids(nl, num)
    edges: list[dict[str, object]] = []
    for node in nodes:
        if node.cell is not None:
            pins = _pin_names(node.cell)
        elif node.kind == "po":
            pins = [("I", node.in_net)]
        else:
            continue
        for pin, net in pins:
            if net in drv:
                edges.append({"src": drv[net], "dst": node.nid, "net": num.net[net], "pin": pin})
    edges.sort(key=lambda e: (int(str(e["src"])[1:]), int(str(e["dst"])[1:]), str(e["pin"])))
    return edges


def build_graph(
    nl: Netlist, labels: Sequence[Label], num: Numbering, design: str, floor: str
) -> tuple[dict[str, object], int]:
    """The graph.json object and the number of combinational loops cut by ``levels``."""
    level, loops = levels(nl)
    drivers = _drivers(nl)
    sinks = _sink_counts(nl)
    nodes = _nodes(nl, num)
    if len(labels) != len(nodes):
        raise ValueError("labels do not match the graph nodes")
    out_nodes: list[dict[str, object]] = []
    for node, lab in zip(nodes, labels, strict=True):
        if lab.node_id != node.nid:
            raise ValueError(f"label order differs from node order at {node.nid}")
        if node.cell is not None:
            lv = level[node.cell.id]
        elif node.kind == "po":
            d = drivers.get(node.in_net)
            lv = level[d.id] + 1 if d is not None else 1
        else:
            lv = 0
        out_nodes.append(
            {
                "id": node.nid,
                "kind": node.kind,
                "features": _features(node, lv, sinks),
                "labels": _label_dict(lab),
            }
        )
    graph: dict[str, object] = {
        "schema": SCHEMA,
        "design": design,
        "floor": floor,
        "nodes": out_nodes,
        "edges": _edges(nl, num, nodes),
    }
    return graph, loops
