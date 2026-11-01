"""Per design x cell context: the parsed netlist, the L1 state groups and the partition blocks."""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import blocks as bl  # noqa: E402
import l3dlib  # noqa: E402

from loki.l3.netlist import Netlist  # noqa: E402


@dataclass
class Ctx:
    key: tuple[str, str, str]  # (set, design, cell)
    blif: bl.Blif
    groups: list[list[str]]
    unb: list[set[int]]  # unbounded cone blocks (#69)
    bnd: list[set[int]]  # bounded cone blocks (#70, #71)
    labels: Path


def build(kind: str, design: str, cell: str) -> Ctx:
    root = l3dlib.CENSUS if kind == "single" else l3dlib.OUT
    net = l3dlib.netlist_path(root, cell, design)
    claims = json.loads(l3dlib.intent_path(root, cell, design).read_text(
        encoding="utf-8"))["claims"]
    groups = bl.pt.state_groups(claims)
    b = bl.Blif.read(net)
    nl = Netlist.read(net)
    return Ctx((kind, design, cell), b, groups,
               [bl.unbounded_block(b, qs) for qs in groups],
               [bl.bounded_block(b, nl, groups, gi) for gi in range(len(groups))],
               net.parent / "labels.csv")
