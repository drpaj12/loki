"""L3 v0 composite detector: wires between detected single-pattern instances (spec 6, 7)."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from loki.l3.detect import Detection, Instance
from loki.l3.netlist import Netlist

FAMILY = {"fsm": "fsm", "counter": "counter", "timer": "counter", "shift": "shift",
          "lfsr": "shift"}
PART_ENTRIES = ("timer", "lfsr", "counter", "shift", "fsm")  # a timer/lfsr claims its state first


@dataclass(frozen=True)
class Part:
    idx: int
    family: str
    entry: str
    inst: Instance


@dataclass(frozen=True)
class Wire:
    src: int
    dst: int
    depth: int
    via: str  # "direct" (depth 0) or "comb"


@dataclass
class Composite:
    pattern: str
    parts: list[int]
    wires: list[Wire]
    p: float


def parts_of(det: Detection) -> list[Part]:
    """One part per state-disjoint instance; a timer or LFSR replaces its counter or shift."""
    parts: list[Part] = []
    taken: dict[str, set[str]] = {}
    for entry in PART_ENTRIES:
        fam = FAMILY[entry]
        for inst in det.instances.get(entry, []):
            if inst.q & taken.get(fam, set()):
                continue
            taken.setdefault(fam, set()).update(inst.q)
            parts.append(Part(len(parts), fam, entry, inst))
    return parts


def wires_of(parts: list[Part], net: Netlist, max_depth: int) -> list[Wire]:
    """A wire a -> b: a forward walk from a's state nets, through at most ``max_depth``
    combinational cells (stopping at flip-flops), reaches an input net of b."""
    out: list[Wire] = []
    for a in parts:
        reach = net.forward(a.inst.q, max_depth)
        for b in parts:
            if a.idx == b.idx or a.inst.q & b.inst.q:
                continue
            hits = [reach[n] for n in b.inst.inputs if n in reach]
            if hits:
                d = min(hits)
                out.append(Wire(a.idx, b.idx, d, "direct" if d == 0 else "comb"))
    return out


def _logit(p: float) -> float:
    p = min(max(p, 1e-4), 1 - 1e-4)
    return math.log(p / (1 - p))


def composites_of(parts: list[Part], wires: list[Wire]) -> list[Composite]:
    """Connected components (over wires, either direction) with at least two parts. Posterior:
    log-odds sum of the part posteriors (capped) and wire terms (direct +2, comb +2 - depth/2)."""
    adj: dict[int, set[int]] = {p.idx: set() for p in parts}
    for w in wires:
        adj[w.src].add(w.dst)
        adj[w.dst].add(w.src)
    seen: set[int] = set()
    out: list[Composite] = []
    for p in parts:
        if p.idx in seen:
            continue
        comp, todo = {p.idx}, [p.idx]
        while todo:
            for n in adj[todo.pop()]:
                if n not in comp:
                    comp.add(n)
                    todo.append(n)
        seen |= comp
        if len(comp) < 2:
            continue
        ws = [w for w in wires if w.src in comp]
        score = sum(min(_logit(q.inst.p), 4.0) for q in parts if q.idx in comp)
        score += sum(2.0 - 0.5 * w.depth for w in ws)
        name = "+".join(sorted(q.family for q in parts if q.idx in comp))
        out.append(Composite(name, sorted(comp), ws, 1 / (1 + math.exp(-score))))
    return out


def as_dict(c: Composite, parts: list[Part]) -> dict[str, Any]:
    return {"kind": "pattern", "pattern": c.pattern, "p": round(c.p, 6), "parts": {
        str(i): parts[i].inst.claims for i in c.parts}, "wires": [
        {"from": w.src, "to": w.dst, "depth": w.depth, "via": w.via} for w in c.wires]}
