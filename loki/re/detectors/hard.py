"""``hard``: ``unmap``'s recovered cells as pieces of probability 1 (L1 spec 7.2).

The facts are read from the working level after ``unmap`` (spec 9.1): a node with string
attribute ``unmap`` is a recovered word cell, ``unmap_note`` marks the cells the pass declined,
and ``unmap_cand`` names an ambiguous group. Hard blocks are never equivalence-checked, so the
recovered facts carry ``+inf`` (spec 6.2): the loop records the ``hard`` evidence and confirms
the hypothesis.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from loki.re.detectors import Candidate, RoundContext, k_bin, sorted_candidates
from loki.re.overlay import Evidence, Overlay

if TYPE_CHECKING:
    from loki.re.fngraph import FnGraph

RECOVERED = {"$add": "hard_add", "$sub": "hard_add", "$mul": "hard_mul", "$mem": "hard_mem"}
CONFIRMED = ("hard_add", "hard_mul", "hard_mem")
CLK = ("RD_CLK", "WR_CLK")
ADDR = ("RD_ADDR", "WR_ADDR")
WE = ("WR_EN",)
WIDTH_PORTS = ("Y", "RD_DATA")


@dataclass(frozen=True)
class UnmapRecord:
    """One ``unmap`` fact: a recovered node (``rule``), a declined one (``note``) or a member
    of an ambiguous group (``cand``); ``cells`` are the level-0 hard cells of its sources."""

    node_type: str
    rule: str
    note: str
    cand: str
    cells: frozenset[int]
    ports: dict[str, tuple[int, ...]]


def width_of(record: UnmapRecord) -> int:
    """The word width of a recovered node: its ``Y`` or ``RD_DATA`` port width, else 1."""
    for name in WIDTH_PORTS:
        nets = record.ports.get(name, ())
        if nets:
            return len(nets)
    return 1


def _nets(record: UnmapRecord, ports: tuple[str, ...]) -> tuple[int, ...]:
    return tuple(net for name in ports for net in record.ports.get(name, ()))


def shared_ctrl(members: list[UnmapRecord]) -> str:
    """``all`` when every member carries its clock, address and write-enable nets and shares them,
    ``addr_only`` when only the address nets are shared, else ``none`` (spec 7.2)."""

    def shared(ports: tuple[str, ...]) -> bool:
        nets = _nets(members[0], ports)
        return bool(nets) and all(_nets(member, ports) == nets for member in members[1:])

    if shared(CLK) and shared(ADDR) and shared(WE):
        return "all"
    return "addr_only" if shared(ADDR) else "none"


class HardDetector:
    name = "hard"
    kinds = ("hard_add", "hard_mul", "hard_mem", "hard_group")

    def propose(self, ctx: RoundContext) -> list[Candidate]:
        """Round 1 only: a recovered node is a ``hard_*`` candidate, a declined adder an open
        ``hard_add`` and the members of one ``unmap_cand`` value one ``hard_group``."""
        if ctx.round != 1 or not ctx.unmap:
            return []
        out: list[Candidate] = []
        groups: dict[str, list[UnmapRecord]] = {}
        for record in ctx.unmap:
            kind = RECOVERED.get(record.node_type)
            if record.rule and kind is not None:
                out.append(Candidate(
                    kind, record.cells, dict(record.ports),
                    {"rule": record.rule, "width": width_of(record)}, {},
                ))
                if record.cand:
                    groups.setdefault(record.cand, []).append(record)
            elif record.note.startswith("adder:"):
                out.append(Candidate(
                    "hard_add", record.cells, dict(record.ports),
                    {"reason": record.note.split(":", 1)[1]}, {"declined_chain": "yes"},
                ))
        for key in sorted(groups, key=lambda k: min(min(r.cells, default=0) for r in groups[k])):
            members = groups[key]
            if len(members) < 2:
                continue
            cells = frozenset(cell for record in members for cell in record.cells)
            out.append(Candidate(
                "hard_group", cells, {},
                {"kind": key.split(":", 1)[0], "members": len(members),
                 "width": sum(width_of(record) for record in members)},
                {"shared_ctrl": shared_ctrl(members), "k": k_bin(len(members))},
            ))
        return sorted_candidates(out)

    @staticmethod
    def confirm(overlay: Overlay, round: int) -> None:
        """Record the ``hard`` evidence (log-odds ``+inf``) on every recovered candidate and
        confirm it; a declined or grouped candidate stays open (spec 7.2)."""
        for h in overlay.all():
            rule = h.params.get("rule")
            if h.kind not in CONFIRMED or not isinstance(rule, str) or h.status not in (
                    "open", "confirmed"):
                continue
            if not any(e.source == "hard" and e.name == "unmap" for e in h.evidence):
                h.evidence.append(Evidence(round, "hard", "unmap", rule, math.inf))
            h.status = "confirmed"

    @staticmethod
    def read_unmap(working: Any, graph: FnGraph) -> list[UnmapRecord]:
        """The ``unmap``/``unmap_note``/``unmap_cand`` attributes of ``working``'s top module,
        with the level-0 cells of each node's sources and its ports as level-0 net ids."""
        by_name = {name: net for net, name in graph.names.items()}
        out: list[UnmapRecord] = []
        for node in working.top().nodes():
            if str(node.type_name).startswith("$port_"):
                continue
            rule = node.attr("unmap") or ""
            note = node.attr("unmap_note") or ""
            cand = node.attr("unmap_cand") or ""
            if not (rule or note or cand):
                continue
            cells = frozenset(
                graph.line_to_cell[int(src.line)] for src in node.sources()
                if int(src.line) in graph.line_to_cell
            )
            ports: dict[str, tuple[int, ...]] = {}
            for port in node.ports():
                nets: list[int] = []
                for pin in port.pins:
                    net = pin.net()
                    if net is None:
                        nets.append(0)
                        continue
                    nid = int(net.id)
                    nets.append(nid if nid in graph.names else by_name.get(str(net.name), nid))
                ports[str(port.name)] = tuple(nets)
            out.append(UnmapRecord(str(node.type_name), rule, note, cand, cells, ports))
        out.sort(key=lambda r: (min(r.cells, default=0), r.node_type, r.rule, r.note, r.cand))
        return out
