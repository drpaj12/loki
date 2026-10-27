"""Separability, first loss, join partner, reason class and the random-set null (pure)."""

from __future__ import annotations

import hashlib
import random
from collections.abc import Sequence
from dataclasses import dataclass, field

from loki.audit.units import ObjView, UnitKey

ARITH = frozenset({"$add", "$sub", "$mul", "$alu"})
MUX = frozenset({"$mux", "$pmux"})
COMPARE = frozenset({"$eq", "$ne", "$lt", "$le", "$gt", "$ge"})
STORAGE_PREFIX = ("$dff", "$adff", "$sdff", "$aldff", "$dlatch", "$adlatch")
PARTNER_SHOWN = 5
REASONS = ("removed", "subsumed", "fsm-recode", "instance-join", "opt-merge", "width-reduce",
           "lower-share", "lut-cone", "unlabelled-merge")


@dataclass(frozen=True)
class Loss:
    """The first loss of a unit: snapshot index, partners, reason class, labelled or not."""

    index: int
    pass_name: str
    partners: tuple[UnitKey, ...]
    reason: str
    explained: bool
    capped: bool
    transient: bool
    inherited: bool = False


@dataclass
class UnitRow:
    key: UnitKey
    hw: str = "logic"
    first: int = 0
    status: str = "kept"
    loss: Loss | None = None
    pure_at: list[int] = field(default_factory=list)


def hw_kind(types: Sequence[str]) -> str:
    """Hardware kind of a unit from the types of its pure objects (fixed precedence)."""
    ts = set(types)
    if "$fsm" in ts:
        return "fsm"
    if any(t.startswith(STORAGE_PREFIX) for t in ts):
        return "register"
    for name, group in (("arith", ARITH), ("mux", MUX), ("compare", COMPARE)):
        if ts & group:
            return name
    return "logic"


def separable(objs: Sequence[ObjView]) -> dict[UnitKey, list[ObjView]]:
    """Units with a pure object, and those objects."""
    out: dict[UnitKey, list[ObjView]] = {}
    for o in objs:
        if len(o.units) == 1:
            out.setdefault(next(iter(o.units)), []).append(o)
    return out


def reached(objs: Sequence[ObjView]) -> dict[UnitKey, list[ObjView]]:
    out: dict[UnitKey, list[ObjView]] = {}
    for o in objs:
        for u in o.units:
            out.setdefault(u, []).append(o)
    return out


def _sort_key(u: UnitKey) -> tuple[str, int, int, str, str]:
    file, kind, span, _name = u
    head = span.split("-")[0].split(".")
    line = int(head[0]) if head[0].isdigit() else 0
    col = int(head[1]) if len(head) > 1 and head[1].isdigit() else 0
    return (file, line, col, kind, span)


def reason_of(pass_name: str, merged: bool, explained: bool, instance: bool,
              subsumed: bool = False) -> str:
    """The reason class of a loss (first matching rule of the protocol; ``subsumed`` is the
    dated split of ``removed``: u is only the enclosing statement of a finer unit)."""
    if not merged:
        if pass_name == "fsm":
            return "fsm-recode"
        return "subsumed" if subsumed else "removed"
    if pass_name == "fsm":
        return "fsm-recode"
    if instance:
        return "instance-join"
    if not explained:
        return "unlabelled-merge"
    return {"opt": "opt-merge", "wreduce": "width-reduce", "lower": "lower-share",
            "abc": "lut-cone"}.get(pass_name, "unlabelled-merge")


def _loss_at(u: UnitKey, k: int, snaps: Sequence[tuple[str, Sequence[ObjView]]],
             transient: bool) -> Loss:
    name, objs = snaps[k]
    hit = reached(objs).get(u, [])
    merged = bool(hit)
    partners = sorted({p for o in hit for p in o.units if p != u}, key=_sort_key)
    explained = any(u in o.joined for o in hit)
    instance = any(u in o.instance_join for o in hit)
    capped = any(o.capped for o in hit) and not explained
    sub = any(u in o.anchors for o in objs)
    before = [p.units for p in snaps[k - 1][1] if len(p.units) > 1]
    inherited = merged and all(any(o.units <= b for b in before) for o in hit)
    return Loss(k, name, tuple(partners), reason_of(name, merged, explained, instance, sub),
                explained and merged, capped, transient, inherited)


def audit(snaps: Sequence[tuple[str, Sequence[ObjView]]]) -> dict[UnitKey, UnitRow]:
    """Per unit: hardware kind, first separable snapshot, first loss. ``snaps`` is the ordered
    list of (pass name, objects) for S1..Sn; index 0 is S1."""
    seps = [separable(objs) for _, objs in snaps]
    rows: dict[UnitKey, UnitRow] = {}
    for _, objs in snaps:
        for u in reached(objs):
            rows.setdefault(u, UnitRow(u))
    for u, row in rows.items():
        row.pure_at = [k for k, s in enumerate(seps) if u in s]
        if not row.pure_at:
            row.status = "never"
            continue
        row.first = row.pure_at[0]
        row.hw = hw_kind([o.type for o in seps[row.first][u]])
        if row.first > 0:
            row.status = "late"
        lost = next((k for k in range(row.first + 1, len(snaps)) if u not in seps[k]), None)
        if lost is not None:
            later = any(k > lost for k in row.pure_at)
            row.status = "lost"
            row.loss = _loss_at(u, lost, snaps, later)
        elif row.first == 0:
            row.status = "kept"
    for row in rows.values():
        if row.status == "never":
            row.status = "born-joined"
    return rows


def null_losses(snaps: Sequence[tuple[str, Sequence[ObjView]]], design: str,
                draws: int = 5) -> list[dict[UnitKey, float]]:
    """Per snapshot k >= 1: for each real separable-at-(k-1) unit the fraction of null draws
    in which it is not null-separable at k. Index 0 is empty (no S0)."""
    out: list[dict[UnitKey, float]] = [{}]
    for k in range(1, len(snaps)):
        prev = separable(snaps[k - 1][1])
        pool = sorted(set(prev) | set(reached(snaps[k][1])))
        sizes = [len(o.units) for o in snaps[k][1]]
        lost = dict.fromkeys(prev, 0.0)
        for d in range(draws):
            seed = hashlib.sha256(f"{design}:{k}:{d}".encode()).hexdigest()
            rng = random.Random(int(seed[:16], 16))
            # an object of size >= 2 is never pure, so only the size-1 objects are drawn
            pure = {pool[rng.randrange(len(pool))] for s in sizes if s == 1 and pool}
            for u in prev:
                if u not in pure:
                    lost[u] += 1.0 / draws
        out.append(lost)
    return out
