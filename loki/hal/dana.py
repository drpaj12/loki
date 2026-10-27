"""Reader of HAL's dataflow output (``groups.txt`` of the dataflow plugin, HAL v4.5.0).

Format (``Result::write_txt``): per group a header line
``ID:<n>, Size:<k>, CLK: {<net ids>}, EN: {..}, R: {..}, S: {..}``, then ``  Successors:   {..}``
and ``  Predecessors: {..}`` (group ids), then one line per gate ``<name>, type: <t>, id: <n>,
RS:``, then an empty line. HAL gate names are the instance names of the converted Verilog, which
are the L0 node ids (``loki.hal.blif2hal``). The net lists are HAL net ids, not names.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass

HEADER = re.compile(
    r"^ID:(\d+),\s*Size:(\d+),\s*CLK:\s*\{([^}]*)\},\s*EN:\s*\{([^}]*)\},\s*"
    r"R:\s*\{([^}]*)\},\s*S:\s*\{([^}]*)\}\s*$")
LINKS = re.compile(r"^\s*(Successors|Predecessors):\s*\{([^}]*)\}\s*$")
GATE = re.compile(r"^(\S+?)\s*,\s*type:\s*(\S+?)\s*,\s*id:\s*(\d+)\s*,")


class DanaError(ValueError):
    """The text is not a dataflow ``groups.txt``."""


@dataclass(frozen=True)
class DanaGroup:
    gid: int
    size: int
    gates: tuple[str, ...]
    gate_types: tuple[str, ...]
    clk: tuple[int, ...]
    en: tuple[int, ...]
    reset: tuple[int, ...]
    set: tuple[int, ...]
    successors: tuple[int, ...]
    predecessors: tuple[int, ...]


def _ints(text: str) -> tuple[int, ...]:
    return tuple(int(x) for x in text.replace(",", " ").split())


@dataclass
class _Acc:
    gid: int
    size: int
    nets: tuple[tuple[int, ...], ...]
    succ: tuple[int, ...] = ()
    pred: tuple[int, ...] = ()

    def __post_init__(self) -> None:
        self.gates: list[tuple[str, str]] = []

    def done(self) -> DanaGroup:
        if len(self.gates) != self.size:
            raise DanaError(f"group {self.gid}: Size {self.size} but {len(self.gates)} gates")
        clk, en, rst, st = self.nets
        return DanaGroup(
            self.gid, self.size, tuple(g for g, _ in self.gates),
            tuple(t for _, t in self.gates), clk, en, rst, st, self.succ, self.pred)


def parse_groups_txt(text: str) -> list[DanaGroup]:
    groups: list[DanaGroup] = []
    cur: _Acc | None = None
    for line in text.splitlines():
        h = HEADER.match(line)
        if h:
            if cur:
                groups.append(cur.done())
            cur = _Acc(int(h[1]), int(h[2]), tuple(_ints(h[i]) for i in (3, 4, 5, 6)))
            continue
        if cur is None:
            continue
        link = LINKS.match(line)
        if link:
            if link[1] == "Successors":
                cur.succ = _ints(link[2])
            else:
                cur.pred = _ints(link[2])
            continue
        g = GATE.match(line)
        if g:
            cur.gates.append((g[1], g[2]))
    if cur:
        groups.append(cur.done())
    return groups


def hal_words(groups: Iterable[DanaGroup], ffs: frozenset[str]) -> list[frozenset[str]]:
    """The FF sets of the groups (gate names are L0 node ids); other gates are dropped."""
    return [frozenset(g.gates) & ffs for g in groups]
