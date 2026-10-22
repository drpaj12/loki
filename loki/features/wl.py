"""Directed colour refinement (1-WL) with stable string colours, and the coarsest equitable
partition by partition refinement (L1 spec 6.7 A)."""

from __future__ import annotations

import hashlib
from collections import deque
from dataclasses import dataclass

from loki.features import WL_ROUNDS
from loki.features.graph import FeatureGraph
from loki.features.npn import npn_class
from loki.features.roles import NetRoles

_STARTS = ("table", "npn")
_DIRECTIONS = ("in", "out", "both")
_TABLE_KINDS = ("lut", "gate", "const")


@dataclass(frozen=True)
class WLConfig:
    start: str = "npn"
    direction: str = "both"
    rounds: int = WL_ROUNDS

    def __post_init__(self) -> None:
        if self.start not in _STARTS:
            raise ValueError(f"start must be one of {_STARTS}")
        if self.direction not in _DIRECTIONS:
            raise ValueError(f"direction must be one of {_DIRECTIONS}")

    @property
    def name(self) -> str:
        return f"{self.start}/{self.direction}"


@dataclass(frozen=True)
class WLResult:
    config: WLConfig
    colours: tuple[tuple[str, ...], ...]
    stable_round: int | None


@dataclass(frozen=True)
class Partition:
    class_of: tuple[int, ...]
    n_classes: int


@dataclass(frozen=True)
class Quotient:
    size: tuple[int, ...]
    label: tuple[str, ...]
    edges: tuple[tuple[int, int, str, int], ...]


def _h(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def _table_label(fg: FeatureGraph, v: int, cfg: WLConfig) -> str:
    if cfg.start == "table":
        return f"T{fg.width[v]}:{fg.table[v]:x}"
    try:
        return "N" + npn_class(fg.table[v], fg.width[v]).key
    except ValueError:
        return f"X{fg.width[v]}:{fg.table[v]:x}"


def start_label(fg: FeatureGraph, roles: NetRoles, v: int, cfg: WLConfig) -> str:
    """The text hashed into the round-0 colour of node ``v`` (L1 spec 6.7 A)."""
    role = roles.nodes[v]
    parts = [fg.kind[v], fg.type[v]]
    if fg.table[v] >= 0 and fg.kind[v] in _TABLE_KINDS:
        parts.append(_table_label(fg, v, cfg))
    parts.append(f"clk={int(role.clock_domain > 0)}")
    parts.append(f"rst={role.has_reset}")
    parts.append(f"en={role.enable}")
    if cfg.start == "npn":
        parts.append(f"c={min(role.const_inputs, 3)}")
    else:
        pairs = sorted(
            f"{fg.pin[e]}={fg.table[fg.src[e]] if fg.table[fg.src[e]] >= 0 else '?'}"
            for e in fg.adjacency()[0][v] if fg.kind[fg.src[e]] == "const"
        )
        parts.append("c=" + ",".join(pairs))
    return "|".join(parts)


def _pin_labels(fg: FeatureGraph, cfg: WLConfig) -> list[str]:
    """Edge pin labels: LUT inputs all share ``I`` in the ``npn`` variant."""
    if cfg.start != "npn":
        return list(fg.pin)
    return ["I" if fg.kind[fg.dst[e]] in ("lut", "gate") else fg.pin[e]
            for e in range(fg.n_edges)]


def _signal_adjacency(
    fg: FeatureGraph, roles: NetRoles
) -> tuple[list[list[int]], list[list[int]]]:
    ins: list[list[int]] = [[] for _ in range(fg.n_nodes)]
    outs: list[list[int]] = [[] for _ in range(fg.n_nodes)]
    for e in range(fg.n_edges):
        if roles.edge_class[e] == "signal":
            ins[fg.dst[e]].append(e)
            outs[fg.src[e]].append(e)
    return ins, outs


def refine(fg: FeatureGraph, roles: NetRoles, cfg: WLConfig) -> WLResult:
    """Colour refinement for ``cfg.rounds`` rounds; edges of non-signal nets are not followed."""
    n = fg.n_nodes
    ins, outs = _signal_adjacency(fg, roles)
    label = _pin_labels(fg, cfg)
    cur = [_h(start_label(fg, roles, v, cfg)) for v in range(n)]
    rounds = [tuple(cur)]
    use_in = cfg.direction in ("in", "both")
    use_out = cfg.direction in ("out", "both")
    for _ in range(cfg.rounds):
        nxt: list[str] = []
        for v in range(n):
            ip = op = ""
            if use_in:
                ip = ",".join(sorted(f"{label[e]}:{cur[fg.src[e]]}" for e in ins[v]))
            if use_out:
                op = ",".join(sorted(f"{label[e]}:{cur[fg.dst[e]]}" for e in outs[v]))
            nxt.append(_h(f"{cur[v]}|{ip}|{op}"))
        cur = nxt
        rounds.append(tuple(cur))
    counts = [len(set(c)) for c in rounds]
    stable = next((r for r in range(1, len(rounds)) if counts[r] == counts[r - 1]), None)
    return WLResult(cfg, tuple(rounds), stable)


def classes(res: WLResult, r: int) -> dict[str, tuple[int, ...]]:
    """Colour to sorted node indices at round ``r``."""
    out: dict[str, list[int]] = {}
    for v, c in enumerate(res.colours[r]):
        out.setdefault(c, []).append(v)
    return {c: tuple(out[c]) for c in sorted(out)}


def stable_partition(fg: FeatureGraph, roles: NetRoles, cfg: WLConfig) -> Partition:
    """The coarsest partition that refines the start colours and is equitable for the pin
    labelled signal edges in ``cfg.direction``; classes are numbered by lowest node index.

    Partition refinement with splitter classes; every class that splits keeps its largest part
    under the old id and queues the other parts (Berkholz, Bonsma and Grohe 2017)."""
    n = fg.n_nodes
    ins, outs = _signal_adjacency(fg, roles)
    label_id: dict[str, int] = {}
    pl = _pin_labels(fg, cfg)
    elab = [label_id.setdefault(p, len(label_id)) for p in pl]
    first: dict[str, int] = {}
    class_of = [0] * n
    members: list[set[int]] = []
    for v in range(n):
        cid = first.setdefault(_h(start_label(fg, roles, v, cfg)), len(first))
        if cid == len(members):
            members.append(set())
        members[cid].add(v)
        class_of[v] = cid
    use_in = cfg.direction in ("in", "both")
    use_out = cfg.direction in ("out", "both")
    queue = deque(range(len(members)))
    while queue:
        s = queue.popleft()
        sigs: dict[int, dict[tuple[int, int], int]] = {}
        for u in members[s]:
            if use_in:
                for e in outs[u]:
                    d = sigs.setdefault(fg.dst[e], {})
                    d[(0, elab[e])] = d.get((0, elab[e]), 0) + 1
            if use_out:
                for e in ins[u]:
                    d = sigs.setdefault(fg.src[e], {})
                    d[(1, elab[e])] = d.get((1, elab[e]), 0) + 1
        by_class: dict[int, dict[tuple[tuple[tuple[int, int], int], ...], list[int]]] = {}
        for v, cnt in sigs.items():
            by_class.setdefault(class_of[v], {}).setdefault(
                tuple(sorted(cnt.items())), []
            ).append(v)
        for x in sorted(by_class):
            groups = list(by_class[x].values())
            touched = sum(len(g) for g in groups)
            rest = len(members[x]) - touched
            largest = max(len(g) for g in groups)
            if rest == 0 and len(groups) == 1:
                continue
            moving: list[list[int]]
            if rest >= largest:
                moving = groups
            else:
                seen = {v for g in groups for v in g}
                remainder = [v for v in members[x] if v not in seen]
                keep = max(range(len(groups)), key=lambda i: len(groups[i]))
                moving = [g for i, g in enumerate(groups) if i != keep]
                if remainder:
                    moving.append(remainder)
            for g in moving:
                nid = len(members)
                members.append(set(g))
                queue.append(nid)
                members[x].difference_update(g)
                for v in g:
                    class_of[v] = nid
    renumber: dict[int, int] = {}
    out = tuple(renumber.setdefault(class_of[v], len(renumber)) for v in range(n))
    return Partition(out, len(renumber))


def quotient(fg: FeatureGraph, roles: NetRoles, part: Partition, cfg: WLConfig) -> Quotient:
    """Class sizes, start labels and, per ``(C, D, pin label)``, the edges each node of ``D``
    receives from ``C``; needs direction ``in`` or ``both`` (the partition is then equitable)."""
    if cfg.direction == "out":
        raise ValueError("quotient needs direction 'in' or 'both'")
    n_classes = part.n_classes
    rep: list[int] = [-1] * n_classes
    size = [0] * n_classes
    for v, c in enumerate(part.class_of):
        size[c] += 1
        if rep[c] < 0:
            rep[c] = v
    ins, _ = _signal_adjacency(fg, roles)
    label = _pin_labels(fg, cfg)
    edges: list[tuple[int, int, str, int]] = []
    for d in range(n_classes):
        counts: dict[tuple[int, str], int] = {}
        for e in ins[rep[d]]:
            key = (part.class_of[fg.src[e]], label[e])
            counts[key] = counts.get(key, 0) + 1
        edges.extend((c, d, lab, k) for (c, lab), k in counts.items())
    edges.sort()
    labels = tuple(start_label(fg, roles, rep[c], cfg) for c in range(n_classes))
    return Quotient(tuple(size), labels, tuple(edges))
