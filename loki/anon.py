"""Anonymisation: one shared counter names every net, cell and port pseudo-cell (spec 6.1, 6.6)."""

from __future__ import annotations

from dataclasses import dataclass

from loki.model import FinalCell, Netlist
from loki.schemas import SCHEMA

PORT_KINDS = ("pi", "po")


@dataclass(frozen=True)
class Numbering:
    """Anonymised names: nets and cells by id, port-bit pseudo-cells by original port-bit name."""

    net: dict[int, str]
    cell: dict[int, str]
    pi: dict[str, str]
    po: dict[str, str]


def logic_cells(nl: Netlist) -> list[FinalCell]:
    """The non-port cells in id order."""
    return sorted((c for c in nl.cells if c.kind not in PORT_KINDS), key=lambda c: c.id)


def number(nl: Netlist) -> Numbering:
    """Spec 6.1 order: nets by id, then non-port cells by id, then port pseudo-cells."""
    k = 0
    net: dict[int, str] = {}
    for nid in sorted(nl.nets):
        net[nid] = f"n{k}"
        k += 1
    cell: dict[int, str] = {}
    for c in logic_cells(nl):
        cell[c.id] = f"n{k}"
        k += 1
    pi: dict[str, str] = {}
    po: dict[str, str] = {}
    for pb in nl.port_bits:
        (pi if pb.direction == "in" else po)[pb.name] = f"n{k}"
        k += 1
    return Numbering(net, cell, pi, po)


def _port_name(num: Numbering, name: str, direction: str) -> str:
    return (num.pi if direction == "in" else num.po)[name]


def build_key(
    nl: Netlist,
    num: Numbering,
    design: str,
    floor: str,
    word_ids: dict[int, tuple[int, ...]],
) -> dict[str, object]:
    """The key.json object (spec 6.6): the only place original names live."""
    nets = {
        num.net[i]: {"odin_id": i, "names": list(n.names)} for i, n in sorted(nl.nets.items())
    }
    cells = {
        num.cell[c.id]: {
            "odin_id": c.id,
            "type": c.type,
            "name": c.name,
            "word_ids": list(word_ids.get(c.id, ())),
        }
        for c in logic_cells(nl)
    }
    ports = [
        {
            "anon": _port_name(num, pb.name, pb.direction),
            "orig": pb.name,
            "dir": pb.direction,
            "net": num.net[pb.net],
        }
        for pb in nl.port_bits
    ]
    return {
        "schema": SCHEMA,
        "design": design,
        "floor": floor,
        "top": nl.top,
        "nets": nets,
        "cells": cells,
        "ports": ports,
    }
