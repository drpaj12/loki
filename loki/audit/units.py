"""Objects of a v2 name map as unit sets (experiments/round6/EXPERIMENT.md, Definitions).

``view_map`` turns a parsed map (``odin3.read_name_map``, or any object with the same fields)
into ``ObjView`` values: the reduced unit set of every logic object, and the units that a
labelled join record of the snapshot's own pass names. Everything after it is pure.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

UnitKey = tuple[str, str, str, str]  # (file, kind, span, name)
ANCHOR_LEVELS = frozenset({"stmt", "branch", "block", "module", "instance"})
SKIP_TYPES = frozenset({"$const", "$port_in", "$port_out"})
_CTX = re.compile(r"^ctx=(\d+)$")


@dataclass(frozen=True)
class ObjView:
    """A logic object: its type, reduced units, units named by a same-pass join, capped flag.

    ``parents`` holds the reduced unit set of each frontier record of the snapshot's own pass
    (the records the pass derived this object from; the object itself when the pass did not
    touch it), for the descent test of an inherited blend."""

    name: str
    type: str
    units: frozenset[UnitKey]
    joined: frozenset[UnitKey]
    capped: bool
    instance_join: frozenset[UnitKey] = frozenset()
    anchors: frozenset[UnitKey] = frozenset()
    parents: tuple[frozenset[UnitKey], ...] = ()


def construct_key(nm: Any, number: int) -> UnitKey:
    """File-stable key of construct ``number`` (ids are renumbered per file)."""
    c = nm.constructs[number - 1]
    path = nm.files[c.file - 1] if c.file else ""
    return (path, str(c.kind), str(c.span), str(c.name))


def _level(nm: Any, number: int) -> str:
    return str(nm.constructs[number - 1].level)


def _parent(nm: Any, number: int) -> int:
    return int(nm.constructs[number - 1].parent)


def anchor(nm: Any, number: int) -> int:
    """V1.2.0 3.3: the construct itself at level stmt or coarser, else its nearest such ancestor."""
    cur = number
    for _ in range(len(nm.constructs) + 1):
        if cur == 0 or _level(nm, cur) in ANCHOR_LEVELS:
            return cur
        cur = _parent(nm, cur)
    return cur


def branch_unit(nm: Any, number: int) -> int:
    """Level ``branch``: the nearest branch ancestor-or-self of the anchor, else the anchor."""
    a = anchor(nm, number)
    cur = a
    for _ in range(len(nm.constructs) + 1):
        if cur == 0:
            return a
        if _level(nm, cur) == "branch":
            return cur
        cur = _parent(nm, cur)
    return a


def _ancestors(nm: Any, number: int) -> set[int]:
    out: set[int] = set()
    cur = _parent(nm, number)
    while cur and cur not in out:
        out.add(cur)
        cur = _parent(nm, cur)
    return out


def reduce_units(nm: Any, members: set[int]) -> set[int]:
    """Drop every member that is an ancestor of another member."""
    drop: set[int] = set()
    for m in members:
        drop |= _ancestors(nm, m) & members
    return members - drop


def leaf_constructs(nm: Any, records: Mapping[int, Any], start: int) -> set[int]:
    """Construct leaves behind record ``start``: each record once, the last ``ctx=n`` parents of a
    record skipped (flatten's instance record)."""
    seen: set[int] = set()
    out: set[int] = set()
    stack = [start]
    while stack:
        n = stack.pop()
        rec = records.get(n)
        if rec is None or n in seen:
            continue
        seen.add(n)
        if rec.kind == "S" and rec.constructs and rec.constructs[0]:
            out.add(int(rec.constructs[0]))
        stack.extend(_walk_parents(rec))
    return out


def _walk_parents(rec: Any) -> Sequence[int]:
    tail = 0
    for f in rec.flags:
        m = _CTX.match(f)
        if m:
            tail = int(m.group(1))
    parents = list(rec.parents)
    return parents[: len(parents) - tail] if tail else parents


def provenance_records(nm: Any, records: Mapping[int, Any], start: int) -> list[Any]:
    """Records reachable from ``start`` through every parent (context parents too)."""
    seen: set[int] = set()
    out: list[Any] = []
    stack = [start]
    while stack:
        n = stack.pop()
        rec = records.get(n)
        if rec is None or n in seen:
            continue
        seen.add(n)
        out.append(rec)
        stack.extend(rec.parents)
    return out


def run_matches(nm: Any, step: str, pass_name: str, args: str) -> bool:
    """True when the pass run named by ``step`` (``t<n>.<op>``) is ``pass_name`` with ``args``."""
    m = re.match(r"^t(\d+)\.", step)
    if not m or not 1 <= int(m.group(1)) <= len(nm.runs):
        return False
    name, rargs = nm.runs[int(m.group(1)) - 1][0], nm.runs[int(m.group(1)) - 1][1]
    return bool(name == pass_name and rargs.strip() == args.strip())


def pass_frontier(
    nm: Any, records: Mapping[int, Any], start: int, pass_name: str, args: str
) -> list[int]:
    """The first records, walking back from ``start``, that are not derived records of the pass
    run (``pass_name`` with ``args``). A start record that is not such a record is its own
    frontier. Context parents of a record are not followed (as in ``leaf_constructs``)."""
    seen: set[int] = set()
    out: list[int] = []
    stack = [start]
    while stack:
        n = stack.pop()
        rec = records.get(n)
        if rec is None or n in seen:
            continue
        seen.add(n)
        if rec.kind == "D" and run_matches(nm, rec.step, pass_name, args):
            stack.extend(_walk_parents(rec))
        else:
            out.append(n)
    return sorted(out)


def _join_units(nm: Any, rec: Any, level: str) -> set[UnitKey]:
    return {construct_key(nm, c) for c in rec.constructs if c}


def view_map(
    nm: Any, types: Mapping[str, str], level: str, pass_name: str, args: str
) -> list[ObjView]:
    """The logic objects of a v2 map. ``types`` maps a hash name to its Odin III cell type;
    ``level`` is ``stmt`` or ``branch``. Wires, ports and constants are not objects. Only
    ``obj.records[0]`` is read: Odin III writes one record per object (checked on the 214,157
    objects of all 1,768 round-6 maps: none has a second record)."""
    records = {r.number: r for r in nm.records}
    unit_of = anchor if level == "stmt" else branch_unit
    out: list[ObjView] = []
    memo: dict[int, frozenset[UnitKey]] = {}

    def reduced(rec_no: int) -> frozenset[UnitKey]:
        if rec_no not in memo:
            ls = leaf_constructs(nm, records, rec_no)
            memo[rec_no] = frozenset(
                construct_key(nm, c) for c in reduce_units(nm, {unit_of(nm, c) for c in ls if c})
                if c)
        return memo[rec_no]

    for obj in nm.objects:
        typ = types.get(obj.name)
        if obj.kind != "node" or typ is None or typ in SKIP_TYPES or not obj.records:
            continue
        leaves = leaf_constructs(nm, records, obj.records[0])
        full = {unit_of(nm, c) for c in leaves if c}
        units = reduce_units(nm, full)
        joined: set[UnitKey] = set()
        inst: set[UnitKey] = set()
        capped = False
        for rec in provenance_records(nm, records, obj.records[0]):
            if rec.kind != "D" or not run_matches(nm, rec.step, pass_name, args):
                continue
            if "join=instance" in rec.flags:
                inst |= _join_units(nm, rec, level)
            if "join" in rec.flags:
                joined |= _join_units(nm, rec, level)
            capped = capped or "lossy=cap" in rec.flags
        out.append(ObjView(obj.name, typ, frozenset(construct_key(nm, u) for u in units if u),
                           frozenset(joined), capped, frozenset(inst),
                           frozenset(construct_key(nm, u) for u in full if u),
                           tuple(reduced(f) for f in pass_frontier(
                               nm, records, obj.records[0], pass_name, args))))
    return out
