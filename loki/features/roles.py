"""Role flags: classify nets as const, clock, reset, enable or signal (L2 spec 8.1 and 8.2)."""

from __future__ import annotations

from dataclasses import dataclass

from loki.features.graph import FeatureGraph

CLASS_NAMES = ("signal", "clock", "reset", "enable", "const")
_CLOCK_PREFIX = ("clk", "clock")
_RESET_PREFIX = ("rst", "reset", "clr", "clear")
_ENABLE_PREFIX = ("en", "enable", "ce")


@dataclass(frozen=True)
class SignalConfig:
    min_fanout: int = 16
    dominance: float = 0.8


@dataclass(frozen=True)
class NodeRole:
    clock_domain: int
    has_reset: int
    const_inputs: int
    enable: int


@dataclass(frozen=True)
class NetRoles:
    net_class: dict[int, str]
    edge_class: tuple[str, ...]
    nodes: tuple[NodeRole, ...]
    classified: dict[str, int]
    clock_domains: int


def restrict(table: int, width: int, k: int, value: int) -> int:
    """The table over the other inputs (order kept) once input ``k`` is fixed to ``value``."""
    low = (1 << k) - 1
    out = 0
    for y in range(1 << (width - 1)):
        x = ((y & ~low) << 1) | (value << k) | (y & low)
        out |= ((table >> x) & 1) << y
    return out


def is_forcing(table: int, width: int, k: int) -> bool:
    """True when fixing input ``k`` to some value makes the output constant.

    Needs at least two inputs: with one input the output is always constant once it is fixed."""
    if width < 2:
        return False
    full = (1 << (1 << (width - 1))) - 1
    return any(restrict(table, width, k, v) in (0, full) for v in (0, 1))


def is_hold(table: int, width: int, k: int, q: int) -> bool:
    """True when, for some value of input ``k``, the output equals input ``q`` for every
    other input (the hold path of a clock-enable mux whose flip-flop output is ``q``)."""
    if k == q or not (0 <= k < width and 0 <= q < width):
        return False
    for v in (0, 1):
        if all(
            ((table >> x) & 1) == ((x >> q) & 1) for x in range(1 << width) if (x >> k) & 1 == v
        ):
            return True
    return False


def _pin_index(pin: str) -> int:
    """``k`` of a LUT pin ``I<k>``; -1 for any other pin name."""
    return int(pin[1:]) if len(pin) > 1 and pin[0] == "I" and pin[1:].isdigit() else -1


def _d_luts(fg: FeatureGraph) -> dict[int, tuple[int, ...]]:
    """D-LUTs: LUT nodes whose output feeds only flip-flop ``D`` pins; value = the FFs fed."""
    out_edges = fg.adjacency()[1]
    found: dict[int, tuple[int, ...]] = {}
    for v in range(fg.n_nodes):
        if fg.kind[v] != "lut" or not out_edges[v]:
            continue
        if all(fg.kind[fg.dst[e]] == "ff" and fg.pin[e] == "D" for e in out_edges[v]):
            found[v] = tuple(sorted({fg.dst[e] for e in out_edges[v]}))
    return found


def _is_clock_sink(fg: FeatureGraph, e: int) -> bool:
    d = fg.dst[e]
    if fg.kind[d] == "ff":
        return fg.pin[e] == "CLK"
    return fg.kind[d] == "hard" and fg.pin[e].lower().startswith(_CLOCK_PREFIX)


def _forcing_sink(fg: FeatureGraph, e: int, dl: dict[int, tuple[int, ...]]) -> bool:
    d = fg.dst[e]
    if d in dl:
        k = _pin_index(fg.pin[e])
        return k >= 0 and is_forcing(fg.table[d], fg.width[d], k)
    return fg.kind[d] == "hard" and fg.pin[e].lower().startswith(_RESET_PREFIX)


def _hold_sink(fg: FeatureGraph, e: int, dl: dict[int, tuple[int, ...]]) -> bool:
    d = fg.dst[e]
    if d in dl:
        k = _pin_index(fg.pin[e])
        if k < 0:
            return False
        fed = set(dl[d])
        in_edges = fg.adjacency()[0][d]
        qs = {_pin_index(fg.pin[i]) for i in in_edges if fg.src[i] in fed}
        return any(q >= 0 and is_hold(fg.table[d], fg.width[d], k, q) for q in qs)
    return fg.kind[d] == "hard" and fg.pin[e].lower().startswith(_ENABLE_PREFIX)


def classify_nets(fg: FeatureGraph, cfg: SignalConfig | None = None) -> NetRoles:
    """Classify every net (check order const, clock, reset, enable, else signal) and derive the
    per-node flags of L2 spec 8.2 (``cfg`` defaults to ``SignalConfig()``)."""
    cfg = cfg or SignalConfig()
    by_net: dict[int, list[int]] = {}
    for e in range(fg.n_edges):
        by_net.setdefault(fg.net[e], []).append(e)
    dl = _d_luts(fg)
    net_class: dict[int, str] = {}
    for net in sorted(by_net):
        edges = by_net[net]
        driver = min(fg.src[e] for e in edges)
        fanout = len(edges)
        if fg.kind[driver] == "const":
            net_class[net] = "const"
        elif any(_is_clock_sink(fg, e) for e in edges):
            net_class[net] = "clock"
        elif fanout >= cfg.min_fanout and (
            sum(1 for e in edges if _forcing_sink(fg, e, dl)) / fanout >= cfg.dominance
        ):
            net_class[net] = "reset"
        elif fanout >= cfg.min_fanout and (
            sum(1 for e in edges if _hold_sink(fg, e, dl)) / fanout >= cfg.dominance
        ):
            net_class[net] = "enable"
        else:
            net_class[net] = "signal"
    edge_class = tuple(net_class[fg.net[e]] for e in range(fg.n_edges))
    classified = {name: 0 for name in CLASS_NAMES}
    for cls in net_class.values():
        classified[cls] += 1
    n = fg.n_nodes
    domain = [0] * n
    clock_nets = sorted((n_ for n_, c in net_class.items() if c == "clock"),
                        key=lambda x: (min(fg.src[e] for e in by_net[x]), x))
    for number, net in enumerate(clock_nets, start=1):
        for e in by_net[net]:
            if domain[fg.dst[e]] == 0:
                domain[fg.dst[e]] = number
    reset = [0] * n
    enable = [0] * n
    const_in = [0] * n
    for e in range(fg.n_edges):
        cls = edge_class[e]
        d = fg.dst[e]
        if cls == "reset":
            reset[d] = 1
        elif cls == "enable":
            enable[d] = 1
        elif cls == "const":
            const_in[d] += 1
    in_edges = fg.adjacency()[0]
    for f in range(n):
        if fg.kind[f] != "ff":
            continue
        for e in in_edges[f]:
            if fg.pin[e] == "D":
                reset[f] |= reset[fg.src[e]]
                enable[f] |= enable[fg.src[e]]
    nodes = tuple(NodeRole(domain[v], reset[v], const_in[v], enable[v]) for v in range(n))
    return NetRoles(net_class, edge_class, nodes, classified, len(clock_nets))
