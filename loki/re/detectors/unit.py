"""``unit``: datapath and control units over committed pieces (L1 spec 7.9).

A datapath unit is a connected component of committed datapath pieces, joined directly or through
uncommitted cells whose role is datapath; a net that feeds a control port of a piece does not
join. Free cells that touch only one other member are left out (only cells *between* pieces
count). A control unit is a committed ``fsm`` piece with the control-role cells it reaches and
the pieces whose control ports those cells drive. A piece belongs to one unit only: datapath
units are formed first and a control unit skips pieces already in one.
"""

from __future__ import annotations

from collections import deque
from collections.abc import Iterable

from loki.re.detectors import Candidate, RoundContext, sorted_candidates
from loki.re.detectors.role import control_ports, predict_role
from loki.re.view import Piece

DATAPATH_KINDS = (
    "adder", "subtractor", "adder_cin", "comparator", "eq_const", "mux", "mux_tree", "register",
    "counter", "hard_add", "hard_mul", "hard_mem", "hard_group",
)
RATIO_HI = 0.7
RATIO_LO = 0.4
Node = tuple[str, int]  # ("p", piece index) or ("c", cell id)


def _ratio_bin(internal: int, touched: int) -> str:
    ratio = internal / touched if touched else 0.0
    if ratio >= RATIO_HI:
        return ">=0.7"
    return "<0.4" if ratio < RATIO_LO else "0.4-0.7"


class _Net:
    """Who reads and who drives each net of a set of nodes."""

    def __init__(self, ctx: RoundContext) -> None:
        g = ctx.graph
        self.pieces = ctx.view.pieces
        self.drivers: dict[int, Node] = {}
        self.readers: dict[int, list[Node]] = {}
        self.ctrl: dict[int, frozenset[int]] = {}
        for i, p in enumerate(self.pieces):
            self.ctrl[i] = control_ports(ctx.overlay.get(p.hid))
            for n in p.outs:
                self.drivers[n] = ("p", i)
            for n in p.ins:
                if n not in self.ctrl[i]:
                    self.readers.setdefault(n, []).append(("p", i))
        for cid in ctx.view.free_cells:
            cell = g.cells[cid]
            for n in cell.outs:
                self.drivers.setdefault(n, ("c", cid))
            for n in cell.ins:
                if n:
                    self.readers.setdefault(n, []).append(("c", cid))

    def nets_of(self, node: Node, ctx: RoundContext) -> tuple[tuple[int, ...], tuple[int, ...]]:
        if node[0] == "p":
            p = self.pieces[node[1]]
            return p.ins, p.outs
        cell = ctx.graph.cells[node[1]]
        return cell.ins, cell.outs


def _internal(nodes: Iterable[Node], nets: _Net, ctx: RoundContext) -> tuple[int, int]:
    """``(internal nets, touched nets)``: a net is internal when a member drives it and another
    reads it."""
    members = set(nodes)
    touched: set[int] = set()
    internal: set[int] = set()
    for node in members:
        ins, outs = nets.nets_of(node, ctx)
        for n in (*ins, *outs):
            if not n:
                continue
            touched.add(n)
            drv = nets.drivers.get(n)
            if drv in members and any(r in members and r != drv for r in nets.readers.get(n, ())):
                internal.add(n)
    return len(internal), len(touched)


def _footprint(nodes: Iterable[Node], nets: _Net, ctx: RoundContext) -> frozenset[int]:
    cells: set[int] = set()
    for kind, i in nodes:
        if kind == "p":
            cells |= nets.pieces[i].cells
        else:
            cells.add(i)
    return frozenset(cells)


class UnitDetector:
    name = "unit"
    kinds = ("datapath_unit", "control_unit")

    def propose(self, ctx: RoundContext) -> list[Candidate]:
        if ctx.round < 2 or not ctx.view.pieces:
            return []
        nets = _Net(ctx)
        roles = {c: predict_role(h) for h in ctx.overlay.by_kind("role") for c in h.cells}
        used: set[int] = set()
        out = self._datapath(ctx, nets, roles, used)
        out.extend(self._control(ctx, nets, roles, used))
        return sorted_candidates(out)

    @staticmethod
    def _make(
        ctx: RoundContext, nets: _Net, kind: str, nodes: list[Node], pieces: list[Piece]
    ) -> Candidate:
        internal, touched = _internal(nodes, nets, ctx)
        members = set(nodes)
        outs: list[int] = []
        ins: list[int] = []
        for node in sorted(members):
            i_nets, o_nets = nets.nets_of(node, ctx)
            ins += [n for n in i_nets if n and nets.drivers.get(n) not in members]
            outs += [
                n for n in o_nets
                if n and (n in ctx.graph.pos
                          or any(r not in members for r in nets.readers.get(n, ())))
            ]
        children = tuple(sorted(p.hid for p in pieces))
        return Candidate(
            kind, _footprint(nodes, nets, ctx),
            {"in": tuple(sorted(set(ins))), "out": tuple(sorted(set(outs)))},
            {"pieces": len(pieces)}, {"internal_ratio": _ratio_bin(internal, touched)},
            children=children,
        )

    def _datapath(
        self, ctx: RoundContext, nets: _Net, roles: dict[int, str], used: set[int]
    ) -> list[Candidate]:
        pieces = nets.pieces
        nodes: set[Node] = {("p", i) for i, p in enumerate(pieces) if p.kind in DATAPATH_KINDS}
        nodes |= {("c", c) for c in ctx.view.free_cells if roles.get(c) == "datapath"}
        adj: dict[Node, set[Node]] = {n: set() for n in nodes}
        for net, drv in nets.drivers.items():
            for r in nets.readers.get(net, ()):
                if drv in nodes and r in nodes and r != drv:
                    adj[drv].add(r)
                    adj[r].add(drv)
        seen: set[Node] = set()
        out: list[Candidate] = []
        for start in sorted(n for n in nodes if n[0] == "p"):
            if start in seen:
                continue
            comp = self._component(start, adj)
            seen |= comp
            kept = self._prune(comp, adj)
            ps = [pieces[i] for kind, i in kept if kind == "p"]
            if len(ps) >= 2:
                used.update(i for kind, i in kept if kind == "p")
                out.append(self._make(ctx, nets, "datapath_unit", sorted(kept), ps))
        return out

    @staticmethod
    def _component(start: Node, adj: dict[Node, set[Node]]) -> set[Node]:
        comp = {start}
        todo = deque([start])
        while todo:
            for m in sorted(adj[todo.popleft()]):
                if m not in comp:
                    comp.add(m)
                    todo.append(m)
        return comp

    @staticmethod
    def _prune(comp: set[Node], adj: dict[Node, set[Node]]) -> set[Node]:
        """Drop free cells with at most one neighbour left, repeatedly."""
        kept = set(comp)
        changed = True
        while changed:
            changed = False
            for n in sorted(kept):
                if n[0] == "c" and len(adj[n] & kept) <= 1:
                    kept.discard(n)
                    changed = True
        return kept

    def _control(
        self, ctx: RoundContext, nets: _Net, roles: dict[int, str], used: set[int]
    ) -> list[Candidate]:
        g = ctx.graph
        out: list[Candidate] = []
        for fi, fsm in enumerate(nets.pieces):
            if fsm.kind != "fsm":
                continue
            reached = set(fsm.outs)
            cells: set[int] = set()
            todo = deque(sorted(reached))
            while todo:
                net = todo.popleft()
                for kind, cid in nets.readers.get(net, ()):
                    if kind != "c" or cid in cells or roles.get(cid) != "control":
                        continue
                    cells.add(cid)
                    for o in g.cells[cid].outs:
                        if o not in reached:
                            reached.add(o)
                            todo.append(o)
            driven = [
                i for i, p in enumerate(nets.pieces)
                if i != fi and i not in used and set(nets.ctrl[i]) & reached
            ]
            if not cells and not driven:
                continue
            used.update(driven)
            nodes: list[Node] = [("p", fi), *(("p", i) for i in driven), *(("c", c) for c in cells)]
            ps = [fsm, *(nets.pieces[i] for i in driven)]
            out.append(self._make(ctx, nets, "control_unit", nodes, ps))
        return out
