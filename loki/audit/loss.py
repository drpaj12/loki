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
    inherited_subset: bool = False


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
    subset = merged and all(any(o.units <= b for b in before) for o in hit)
    inherited = merged and all(
        any(u in ps and len(ps) > 1 for ps in o.parents) for o in hit)
    return Loss(k, name, tuple(partners), reason_of(name, merged, explained, instance, sub),
                explained and merged, capped, transient, inherited, subset)


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


def _size_hist(sizes: Sequence[int]) -> dict[int, int]:
    hist: dict[int, int] = {}
    for n in sizes:
        hist[n] = hist.get(n, 0) + 1
    return hist


def _count_ge(hist: dict[int, int], n: int) -> int:
    return sum(c for size, c in hist.items() if size >= n)


PERSIST_DRAWS = 50
PERSIST_TRIES = 30


def persistence_draw(prev: Sequence[frozenset[UnitKey]], target_sizes: Sequence[int],
                     rng: random.Random) -> list[frozenset[UnitKey]]:
    """One persistence-null draw (EXPERIMENT.md, Amendment A): start from the real unit sets of
    S_{k-1}, apply ``max(0, len(prev) - len(target_sizes))`` random merges (unions of two
    objects), each accepted when it keeps the count of objects of its size or larger within the
    real S_k (or S_{k-1}) count; after ``PERSIST_TRIES`` tries the smallest union is taken."""
    cur = list(prev)
    merges = min(max(0, len(cur) - len(target_sizes)), len(cur) - 1)
    hist = _size_hist([len(s) for s in cur])
    budget_k = _size_hist(list(target_sizes))
    budget_p = _size_hist([len(s) for s in prev])
    for _ in range(merges):
        best: tuple[int, int, int] | None = None
        pick: tuple[int, int] | None = None
        for _t in range(PERSIST_TRIES):
            i = rng.randrange(len(cur))
            j = rng.randrange(len(cur) - 1)
            j += int(j >= i)
            a, b = len(cur[i]), len(cur[j])
            m = len(cur[i] | cur[j])
            hist[a] -= 1
            hist[b] -= 1
            hist[m] = hist.get(m, 0) + 1
            fits = _count_ge(hist, m) <= max(_count_ge(budget_k, m), _count_ge(budget_p, m))
            hist[m] -= 1
            hist[a] += 1
            hist[b] += 1
            if fits:
                pick = (i, j)
                break
            if best is None or m < best[0]:
                best = (m, i, j)
        if pick is None:
            assert best is not None
            pick = (best[1], best[2])
        i, j = pick
        a, b, m = len(cur[i]), len(cur[j]), len(cur[i] | cur[j])
        hist[a] -= 1
        hist[b] -= 1
        hist[m] = hist.get(m, 0) + 1
        cur[i] = cur[i] | cur[j]
        last = cur.pop()
        if j < len(cur):
            cur[j] = last
    return cur


def persistence_losses(snaps: Sequence[tuple[str, Sequence[ObjView]]], design: str,
                       draws: int = PERSIST_DRAWS
                       ) -> tuple[list[dict[UnitKey, int]], list[float]]:
    """Persistence null (Amendment A). Per snapshot index k >= 1: for each unit separable at
    S_{k-1}, a bit mask over the draws (bit d set: not null-separable at S_k in draw d), and the
    mean absolute deviation between the sorted null and real S_k object-size vectors (0.0 when
    no merge is drawn). Index 0 is empty."""
    masks: list[dict[UnitKey, int]] = [{}]
    mads: list[float] = [0.0]
    for k in range(1, len(snaps)):
        prev_objs = snaps[k - 1][1]
        prev = separable(prev_objs)
        sets = [o.units for o in prev_objs]
        target = sorted(len(o.units) for o in snaps[k][1])
        bits = dict.fromkeys(prev, 0)
        dev = 0.0
        for d in range(draws):
            seed = hashlib.sha256(f"{design}:{k}:{d}:persist".encode()).hexdigest()
            cur = persistence_draw(sets, target, random.Random(int(seed[:16], 16)))
            pure = {next(iter(s)) for s in cur if len(s) == 1}
            for u in prev:
                if u not in pure:
                    bits[u] |= 1 << d
            if len(sets) > len(target) and len(cur) == len(target):
                got = sorted(len(s) for s in cur)
                dev += sum(abs(x - y) for x, y in zip(got, target, strict=True)) / len(target)
        masks.append(bits)
        mads.append(dev / draws)
    return masks, mads
