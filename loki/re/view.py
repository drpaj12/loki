"""The current level as detectors see it: free cells, pieces, absorbed cells (spec 9.2)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from loki.re.sim import Support

if TYPE_CHECKING:
    from loki.re.fngraph import FnGraph
    from loki.re.overlay import Overlay


@dataclass(frozen=True)
class Piece:
    """An instance of a committed hypothesis at this level."""

    hid: str
    kind: str
    ins: tuple[int, ...]
    outs: tuple[int, ...]
    cells: frozenset[int]


@dataclass(frozen=True)
class View:
    free_cells: tuple[int, ...]
    pieces: tuple[Piece, ...]
    absorbed: frozenset[int]
    support: Support

    @classmethod
    def level0(cls, graph: FnGraph) -> View:
        """Round 1: every cell is free, no pieces."""
        return cls(tuple(sorted(graph.cells)), (), frozenset(), Support(graph))

    @classmethod
    def build(cls, working: Any, graph: FnGraph, overlay: Overlay) -> View:
        """Walk the top module of ``working``: a node with ``loki_hid`` is a committed piece
        (footprint from the overlay); the cells in pieces are absorbed and the piece outputs
        that leave it become supports' sources. Net IDs are mapped through net names when an
        ID is unknown to ``graph``."""
        by_name = {name: net for net, name in graph.names.items()}

        def net_of(pin: Any) -> int:
            net = pin.net()
            if net is None:
                return 0
            nid = int(net.id)
            return nid if nid in graph.names else by_name.get(str(net.name), nid)

        pieces: list[Piece] = []
        for node in working.top().nodes():
            hid = node.attr("loki_hid")
            if hid is None:
                continue
            ins: list[int] = []
            outs: list[int] = []
            for port in node.ports():
                nets = [n for n in (net_of(p) for p in port.pins) if n]
                (outs if port.direction == "out" else ins).extend(nets)
            hyp = overlay.get(hid)
            pieces.append(Piece(hid, hyp.kind, tuple(ins), tuple(outs), hyp.cells))
        pieces.sort(key=lambda p: (min(p.cells, default=0), p.hid))
        absorbed = frozenset(c for p in pieces for c in p.cells)
        extra = frozenset(n for p in pieces for n in p.outs)
        free = tuple(c for c in sorted(graph.cells) if c not in absorbed)
        return cls(free, tuple(pieces), absorbed, Support(graph, extra))
