"""``ff_pattern``: enable and synchronous reset on a flip-flop's D cone, and registers
(L1 spec 7.3)."""

from __future__ import annotations

from dataclasses import dataclass, field

from loki.re.detectors import (
    Candidate,
    RoundContext,
    bin_count,
    k_bin,
    params_json,
    sorted_candidates,
)
from loki.re.fnfacts import cofactor
from loki.re.sim import simulate

CONE_DEPTH = 3
CONE_INPUTS = 12
RST_EDGES = (1, 2, 4, 8)
RST_LABELS = ("1", "2-3", "4-7", "8+")
_FF_TYPES = ("$_DFF_P_", "$_DFF_N_", "$_FF_")


@dataclass
class _Ff:
    cell: int
    q: int
    d: int
    clock: int
    cone: tuple[int, ...] = ()
    reads: frozenset[int] = frozenset()
    en: list[tuple[int, int]] = field(default_factory=list)  # (net, active)
    rst: list[tuple[int, int, int]] = field(default_factory=list)  # (net, active, value)
    cells: frozenset[int] = frozenset()


def _column(i: int, m: int) -> int:
    """Vector over the ``2^m`` patterns whose bit ``x`` is bit ``i`` of ``x``."""
    block = ((1 << (1 << i)) - 1) << (1 << i)
    out = 0
    for x in range(0, 1 << m, 1 << (i + 1)):
        out |= block << x
    return out


def _cut(ctx: RoundContext, cells: set[int]) -> list[int]:
    g = ctx.graph
    driven = {n for c in cells for n in g.cells[c].outs}
    nets: set[int] = set()
    for c in cells:
        for n in g.cells[c].ins:
            d = g.driver.get(n)
            if n and n not in driven and not (d is not None and g.cells[d].kind == "const"):
                nets.add(n)
    return sorted(nets)


def _d_cone(ctx: RoundContext, d: int) -> tuple[int, ...]:
    """Cells of the D cone (spec 7.3): the driver of ``d`` and cells whose only reader is the
    cone, to depth ``CONE_DEPTH`` and at most ``CONE_INPUTS`` cut inputs."""
    g = ctx.graph
    free = set(ctx.view.free_cells)
    drv = g.driver.get(d)
    if not d or drv is None or drv not in free or g.cells[drv].kind != "lut":
        return ()
    cells = {drv}
    depth = {drv: 1}
    queue = [drv]
    pos = set(g.pos)
    while queue:
        cid = queue.pop(0)
        if depth[cid] >= CONE_DEPTH:
            continue
        for net in g.cells[cid].ins:
            sub = g.driver.get(net)
            if (net == 0 or sub is None or sub in cells or sub not in free or net in pos
                    or g.cells[sub].kind != "lut"):
                continue
            if any(r not in cells for r, _ in g.readers.get(net, ())):
                continue
            trial = cells | {sub}
            if len(_cut(ctx, trial)) > CONE_INPUTS:
                continue
            cells = trial
            depth[sub] = depth[cid] + 1
            queue.append(sub)
    return tuple(sorted(cells))


def _function(
    ctx: RoundContext, cone: tuple[int, ...], d: int
) -> tuple[list[int], int] | None:
    """Cut inputs and the composed table of ``d`` over them (``2^m`` patterns, ``m <= 12``)."""
    g = ctx.graph
    cuts = _cut(ctx, set(cone))
    m = len(cuts)
    if m == 0 or m > CONE_INPUTS:
        return None
    n = 1 << m
    values = {net: _column(i, m) for i, net in enumerate(cuts)}
    for c in cone:
        for net in g.cells[c].ins:
            drv = g.driver.get(net)
            if drv is not None and g.cells[drv].kind == "const":
                values[net] = (1 << n) - 1 if g.cells[drv].table & 1 else 0
    return cuts, simulate(g, cone, values, n)[d]


def _analyse(ctx: RoundContext, ff: _Ff) -> None:
    ff.cone = _d_cone(ctx, ff.d)
    cells = {ff.cell, *ff.cone}
    if not ff.cone:
        ff.reads = frozenset({ff.d}) if ff.d else frozenset()
        ff.cells = frozenset(cells)
        return
    fn = _function(ctx, ff.cone, ff.d)
    ff.reads = frozenset(_cut(ctx, set(ff.cone)))
    ff.cells = frozenset(cells)
    if fn is None:
        return
    cuts, table = fn
    m = len(cuts)
    full = (1 << (1 << m)) - 1
    qt = _column(cuts.index(ff.q), m) if ff.q in cuts else None
    reduced = [table]
    for i, net in enumerate(cuts):
        if net == ff.q:
            continue
        for v in (0, 1):
            c = cofactor(table, m, i, v)
            if c in (0, full) and cofactor(table, m, i, 1 - v) not in (0, full):
                ff.rst.append((net, v, 1 if c else 0))
                reduced.append(cofactor(table, m, i, 1 - v))
                break
    if qt is None:
        return
    for f in reduced:
        for i, net in enumerate(cuts):
            if net == ff.q:
                continue
            for v in (0, 1):
                held = cofactor(f, m, i, v) == qt and cofactor(f, m, i, 1 - v) != qt
                if held and (net, 1 - v) not in ff.en:
                    ff.en.append((net, 1 - v))


def _lookup(ctx: RoundContext, kind: str) -> dict[tuple[frozenset[int], str], str]:
    return {(h.cells, params_json(h.params)): h.id for h in ctx.overlay.by_kind(kind)
            if h.status != "rejected"}


def _bus_positions(ctx: RoundContext) -> dict[int, tuple[str, int]]:
    """Net to ``(bus id, bit)`` for the slice outputs of live ``bus`` hypotheses."""
    pos: dict[int, tuple[str, int]] = {}
    for h in ctx.overlay.by_kind("bus"):
        if h.status == "rejected":
            continue
        for name, nets in h.nets.items():
            if name.startswith("slice") and name[5:].isdigit() and nets:
                pos.setdefault(nets[0], (h.id, int(name[5:])))
    return pos


def _order(members: list[_Ff], bus_pos: dict[int, tuple[str, int]]) -> tuple[list[_Ff], str]:
    """Slices ordered as their D-side bus when every D is a slice of one bus, else by Q."""
    spots = [bus_pos.get(f.d) for f in members]
    buses = {sp[0] for sp in spots if sp is not None}
    if None not in spots and len(buses) == 1:
        keyed = sorted(zip(spots, members, strict=True), key=lambda t: (t[0] or ("", 0))[1])
        return [f for _, f in keyed], "bus"
    return sorted(members, key=lambda f: f.q), "net_id"


def _d_source(
    ctx: RoundContext, ff: _Ff, bus_pos: dict[int, tuple[str, int]]
) -> str:
    """Key of the one committed piece or bus that the FF's D cone reads, ``""`` when neither
    (spec 7.3: the register branch without a shared enable or reset)."""
    hit = sorted(p.hid for p in ctx.view.pieces if set(p.outs) & ff.reads)
    if len(hit) == 1:
        return "piece:" + hit[0]
    buses = sorted({sp[0] for n in ff.reads if (sp := bus_pos.get(n)) is not None})
    return "bus:" + buses[0] if len(buses) == 1 else ""


class FfPatternDetector:
    name = "ff_pattern"
    kinds = ("ff_en", "ff_srst", "register")

    def propose(self, ctx: RoundContext) -> list[Candidate]:
        g = ctx.graph
        ffs: list[_Ff] = []
        for cid in ctx.view.free_cells:
            c = g.cells[cid]
            if c.kind == "ff" and c.type in _FF_TYPES and c.ins and c.outs:
                ffs.append(_Ff(cid, c.outs[0], c.ins[0], c.clock))
        for ff in ffs:
            _analyse(ctx, ff)
        fan: dict[tuple[int, int], set[int]] = {}
        for ff in ffs:
            for net, active, _ in ff.rst:
                fan.setdefault((net, active), set()).add(ff.cell)
        out: list[Candidate] = []
        for ff in ffs:
            for net, active in ff.en:
                out.append(Candidate(
                    "ff_en", ff.cells, {"q": (ff.q,), "d": (ff.d,), "en": (net,)},
                    {"en": net, "active": active}, {"en_fn_exact": "yes"},
                ))
            for net, active, value in ff.rst:
                out.append(Candidate(
                    "ff_srst", ff.cells, {"q": (ff.q,), "d": (ff.d,), "rst": (net,)},
                    {"rst": net, "active": active, "value": value},
                    {"rst_fanout": bin_count(len(fan[(net, active)]), RST_EDGES, RST_LABELS)},
                ))
        out.extend(self._registers(ctx, ffs))
        return sorted_candidates(out)

    @staticmethod
    def _registers(ctx: RoundContext, ffs: list[_Ff]) -> list[Candidate]:
        groups: dict[tuple[int, tuple[int, int] | None, tuple[int, int] | None, str], list[_Ff]]
        groups = {}
        bus_pos = _bus_positions(ctx)
        for ff in ffs:
            if not ff.clock:
                continue
            en = min(ff.en) if ff.en else None
            rst = min((n, a) for n, a, _ in ff.rst) if ff.rst else None
            piece = ""
            if en is None and rst is None:
                piece = _d_source(ctx, ff, bus_pos)
                if not piece:
                    continue
            groups.setdefault((ff.clock, en, rst, piece), []).append(ff)
        en_ids = _lookup(ctx, "ff_en")
        rst_ids = _lookup(ctx, "ff_srst")
        cands: list[Candidate] = []
        for key in sorted(groups, key=repr):
            if len(groups[key]) < 2:
                continue
            clock, en, rst, piece = key
            members, source = _order(groups[key], bus_pos)
            children: list[str] = []
            for f in members:
                for net, active in f.en:
                    hid = en_ids.get((f.cells, params_json({"en": net, "active": active})))
                    if hid:
                        children.append(hid)
                for net, active, value in f.rst:
                    hid = rst_ids.get(
                        (f.cells, params_json({"rst": net, "active": active, "value": value}))
                    )
                    if hid:
                        children.append(hid)
            nets: dict[str, tuple[int, ...]] = {
                "q": tuple(f.q for f in members), "d": tuple(f.d for f in members),
                "clk": (clock,),
            }
            feats = {"width": k_bin(len(members))}
            if en is not None:
                nets["en"] = (en[0],)
            if rst is not None:
                nets["rst"] = (rst[0],)
            if en is not None or rst is not None:
                feats["shared_ctrl"] = (
                    "both" if en is not None and rst is not None else "en" if en else "rst"
                )
            if piece:
                feats["d_from_piece"] = "yes"
            cands.append(Candidate(
                "register", frozenset().union(*(f.cells for f in members)), nets,
                {"order_source": source}, feats, children=tuple(children),
            ))
        return cands
