"""``role``: control or datapath, one hypothesis per level-0 logic cell (L1 spec 7.10).

The fixpoint is L0's (L0 spec 7.5) on the level-0 graph: a worklist over monotone sets of
``control`` and ``data``. A cell takes the kinds of every cell that reads its outputs (all level-0
cells are neutral readers), ``data`` from a primary output or a hard-cell reader, and ``control``
from a control sink net. The reads of a sink net inside the footprint of the hypothesis that owns
it carry nothing back (a mux LUT passes its data role to its data inputs, not to its select).
"""

from __future__ import annotations

from collections import deque

from loki.re.detectors import Candidate, RoundContext, sorted_candidates
from loki.re.overlay import Hypothesis

CONTROL, DATA = "control", "data"
LIVE = ("confirmed", "committed")
SINK_KINDS = ("mux", "mux_tree", "mux_bit", "ff_en", "ff_srst", "register", "counter", "shift_reg")
SINK_PORTS = ("S", "en", "rst", "EN", "RST")
DATA_KINDS = ("adder", "subtractor", "adder_cin", "comparator", "eq_const", "register")
ROLE_CELLS = ("lut", "ff", "latch")
BUS_MIN = 4


def predict_role(h: Hypothesis) -> str:
    """``mixed`` when ``role_prop`` is mixed, else ``control`` when ``p >= 0.5``, else
    ``datapath``."""
    if h.features.get("role_prop") == "mixed":
        return "mixed"
    return "control" if h.log_odds >= 0.0 else "datapath"


def control_ports(h: Hypothesis) -> frozenset[int]:
    """The nets of ``h`` that drive its select, enable or reset ports."""
    return frozenset(n for key in SINK_PORTS for n in h.nets.get(key, ()))


def _prop(kinds: set[str]) -> str:
    if kinds == {CONTROL}:
        return "control"
    if kinds == {DATA}:
        return "data"
    return "mixed" if kinds else "none"


def _bus4(h: Hypothesis) -> bool:
    k = h.params.get("k", 0)
    return isinstance(k, int) and k >= BUS_MIN


def _seeds(
    ctx: RoundContext,
) -> tuple[dict[int, set[str]], dict[int, set[int]]]:
    """Initial kinds per cell and, per control sink net, the cells whose reads it ignores."""
    kinds: dict[int, set[str]] = {cid: set() for cid in ctx.graph.cells}
    sinks: dict[int, set[int]] = {}
    for h in ctx.overlay.by_kind("fsm"):
        if h.status in LIVE:
            for c in h.cells:
                kinds.setdefault(c, set()).add(CONTROL)
    for kind in SINK_KINDS:
        for h in ctx.overlay.by_kind(kind):
            if h.status in LIVE:
                for net in control_ports(h):
                    sinks.setdefault(net, set()).update(h.cells)
    for h in ctx.overlay.committed():
        if h.kind in DATA_KINDS or (h.kind == "bus" and _bus4(h)):
            for c in h.cells:
                kinds.setdefault(c, set()).add(DATA)
    return kinds, sinks


def role_kinds(ctx: RoundContext) -> dict[int, set[str]]:
    """The ``control`` / ``data`` sets of every level-0 cell after the fixpoint."""
    g = ctx.graph
    kinds, sinks = _seeds(ctx)
    pos = set(g.pos)
    work = deque(sorted(g.cells))
    queued = set(work)
    while work:
        y = work.popleft()
        queued.discard(y)
        new = set(kinds[y])
        for net in g.cells[y].outs:
            if net in pos:
                new.add(DATA)
            if net in sinks:
                new.add(CONTROL)
            for r, _ in g.readers.get(net, ()):
                if r in sinks.get(net, ()):
                    continue
                if g.cells[r].kind == "hard":
                    new.add(DATA)
                else:
                    new |= kinds[r]
        if new == kinds[y]:
            continue
        kinds[y] = new
        for net in g.cells[y].ins:
            d = g.driver.get(net)
            if d is not None and d not in queued:
                queued.add(d)
                work.append(d)
    return kinds


class RoleDetector:
    name = "role"
    kinds = ("role",)

    def propose(self, ctx: RoundContext) -> list[Candidate]:
        g = ctx.graph
        roles = role_kinds(ctx)
        in_bus4: set[int] = set()
        for h in ctx.overlay.by_kind("bus"):
            if h.status != "rejected" and _bus4(h):
                in_bus4 |= h.cells
        out: list[Candidate] = []
        for cid in sorted(g.cells):
            cell = g.cells[cid]
            if cell.kind not in ROLE_CELLS:
                continue
            feats = {
                "role_prop": _prop(roles[cid]),
                "in_bus4": "yes" if cid in in_bus4 else "no",
            }
            out.append(Candidate("role", frozenset({cid}), {"Y": cell.outs}, {}, feats))
        return sorted_candidates(out)
