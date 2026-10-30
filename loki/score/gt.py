"""Ground truth from an L0 floor directory (L1 spec 12.1 to 12.3). Pure except file reading."""

from __future__ import annotations

import csv
import json
from collections import deque
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

STORAGE = frozenset({
    "$dff", "$dffe", "$adff", "$adffe", "$sdff", "$sdffe", "$sdffce", "$dffsr", "$dffsre",
    "$aldff", "$aldffe", "$dlatch", "$adlatch", "$dlatchsr",
})
ARITH = frozenset({"$add", "$sub"})
MUXES = frozenset({"$mux", "$pmux"})
COMPARE = ("$eq", "$ne", "$lt", "$le", "$gt", "$ge")

# Derived instance types (spec 12.2): not L0 word types.
REGISTER, COUNTER, MUX_TREE, FSM = "register", "counter", "mux_tree", "fsm"

# Kind to the L0 types it is scored against (spec 6.1, last column). Kinds not listed are not
# construct-scored (bus and role have their own scores; units only enter the hierarchy metric).
SCORED_TYPES: dict[str, frozenset[str]] = {
    "ff_en": frozenset({"$dffe", "$adffe", "$sdffe", "$sdffce"}),
    "ff_srst": frozenset({"$sdff", "$sdffe", "$sdffce"}),
    "register": frozenset({REGISTER}),
    "adder": frozenset({"$add"}),
    "subtractor": frozenset({"$sub"}),
    "adder_cin": frozenset({"$add"}),
    "comparator": frozenset(COMPARE),
    "eq_const": frozenset({"$eq", "$ne"}),
    "mux_bit": MUXES,
    "mux": MUXES,
    "mux_tree": frozenset({MUX_TREE}),
    "counter": frozenset({COUNTER}),
    "fsm": frozenset({FSM}),
    "fsm_onehot": frozenset({FSM}),
    "fsm_binary": frozenset({FSM}),
    "hard_add": frozenset({"$add"}),
    "hard_mul": frozenset({"$mul"}),
    "hard_mem": frozenset({"$mem"}),
}


@dataclass(frozen=True)
class GtInstance:
    gid: str
    type: str
    footprint: frozenset[str]


@dataclass(frozen=True)
class GtBus:
    """A label bus: ``members`` are node ids, ``bits`` the (node id, bit index) pairs."""

    gid: str
    name: str
    members: frozenset[str]
    bits: tuple[tuple[str, int], ...]


def _width(params: dict[str, Any]) -> int:
    w = params.get("WIDTH", 1)
    return w if isinstance(w, int) and not isinstance(w, bool) else 1


def _load_json(path: Path) -> dict[str, object]:
    obj = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(obj, dict):
        raise ValueError(f"{path}: not an object")
    return obj


def _mux_reach(
    start: int, succ: dict[int, set[int]], mux: set[int]
) -> set[int]:
    """Mux words reachable from ``start`` over ``succ`` through mux words only."""
    seen: set[int] = set()
    work = deque(w for w in succ.get(start, ()) if w in mux)
    while work:
        w = work.popleft()
        if w in seen:
            continue
        seen.add(w)
        work.extend(x for x in succ.get(w, ()) if x in mux)
    return seen


def derive_instances(words: Mapping[str, object]) -> list[GtInstance]:
    """Word instances plus the derived ``register``, ``counter``, ``mux_tree`` and ``fsm``."""
    items = words.get("words", [])
    edges = words.get("edges", [])
    if not isinstance(items, list) or not isinstance(edges, list):
        raise ValueError("words.json: words and edges must be lists")
    by_id = {int(w["id"]): w for w in items}
    foot = {i: frozenset(w["footprint"]) for i, w in by_id.items()}
    out = [
        GtInstance(f"w{i}", str(w["type"]), foot[i])
        for i, w in sorted(by_id.items()) if foot[i]
    ]
    storage = {i for i, w in by_id.items() if w["type"] in STORAGE}
    mux = {i for i, w in by_id.items() if w["type"] in MUXES}
    for i in sorted(storage):
        if _width(by_id[i].get("params", {})) >= 2 and foot[i]:
            out.append(GtInstance(f"r{i}", REGISTER, foot[i]))
    fwd: dict[int, set[int]] = {}
    for e in edges:
        fwd.setdefault(int(e["src"]), set()).add(int(e["dst"]))
    out += _counters(by_id, foot, edges, storage, mux, fwd)
    out += _mux_trees(foot, edges, mux)
    out += _fsms(by_id, foot, edges, storage, mux)
    return out


def _counters(
    by_id: dict[int, dict[str, Any]], foot: dict[int, frozenset[str]], edges: list[object],
    storage: set[int], mux: set[int], fwd: dict[int, set[int]],
) -> list[GtInstance]:
    d_of: dict[int, set[int]] = {}  # storage word -> sources of its D port
    for e in edges:
        assert isinstance(e, dict)
        if int(e["dst"]) in storage and e["dst_port"] == "D":
            d_of.setdefault(int(e["dst"]), set()).add(int(e["src"]))
    out: list[GtInstance] = []
    seen: set[tuple[int, int]] = set()
    for e in edges:
        assert isinstance(e, dict)
        r, a = int(e["src"]), int(e["dst"])
        if r not in storage or e["src_port"] != "Q" or by_id[a]["type"] not in ARITH:
            continue
        if e["dst_port"] not in ("A", "B") or (r, a) in seen:
            continue
        other = "B" if e["dst_port"] == "A" else "A"
        consts = by_id[a].get("const_ports", [])
        if other not in consts or _width(by_id[r].get("params", {})) < 2:
            continue
        reach = _mux_reach(a, fwd, mux)
        srcs = d_of.get(r, set())
        path = {m for m in reach if m in srcs or _mux_reach(m, fwd, mux) & srcs}
        if a not in srcs and not (reach & srcs):
            continue
        seen.add((r, a))
        cells = foot[r] | foot[a] | frozenset().union(*(foot[m] for m in path))
        if cells:
            out.append(GtInstance(f"c{r}_{a}", COUNTER, cells))
    return out


def _mux_trees(
    foot: dict[int, frozenset[str]], edges: list[object], mux: set[int]
) -> list[GtInstance]:
    adj: dict[int, set[int]] = {m: set() for m in mux}
    for e in edges:
        assert isinstance(e, dict)
        s, d = int(e["src"]), int(e["dst"])
        if s in mux and d in mux and e["src_port"] == "Y" and e["dst_port"] in ("A", "B"):
            adj[s].add(d)
            adj[d].add(s)
    out: list[GtInstance] = []
    seen: set[int] = set()
    for m in sorted(mux):
        if m in seen:
            continue
        comp: set[int] = set()
        work = [m]
        while work:
            x = work.pop()
            if x not in comp:
                comp.add(x)
                work.extend(adj[x] - comp)
        seen |= comp
        cells = frozenset().union(*(foot[x] for x in comp))
        if len(comp) >= 2 and cells:
            out.append(GtInstance(f"m{min(comp)}", MUX_TREE, cells))
    return out


def _fsms(
    by_id: dict[int, dict[str, Any]], foot: dict[int, frozenset[str]], edges: list[object],
    storage: set[int], mux: set[int],
) -> list[GtInstance]:
    preds: dict[int, set[int]] = {}
    for e in edges:
        assert isinstance(e, dict)
        if e["dst_port"] in ("D", "A", "B"):
            preds.setdefault(int(e["dst"]), set()).add(int(e["src"]))
    out: list[GtInstance] = []
    for r in sorted(storage):
        if not by_id[r].get("fsm"):
            continue
        seen: set[int] = set()
        work = deque(p for p in preds.get(r, ()) if p in mux)
        while work:
            m = work.popleft()
            if m in seen:
                continue
            seen.add(m)
            work.extend(p for p in preds.get(m, ()) if p in mux)
        cells = foot[r] | frozenset().union(*(foot[m] for m in seen))
        if cells:
            out.append(GtInstance(f"f{r}", FSM, cells))
    return out


def label_buses(rows: list[dict[str, str]]) -> list[GtBus]:
    """Nodes with equal non-empty ``(module_path, bus_name)`` and ``bit_index >= 0``, groups of
    at least 2 (spec 12.3)."""
    groups: dict[tuple[str, str], list[tuple[int, str]]] = {}
    for row in rows:
        bit = int(row["bit_index"])
        if row["bus_name"] and bit >= 0:
            groups.setdefault((row["module_path"], row["bus_name"]), []).append(
                (bit, row["node_id"]))
    out: list[GtBus] = []
    for k, key in enumerate(sorted(groups)):
        members = sorted(groups[key])
        if len(members) < 2:
            continue
        out.append(GtBus(
            f"b{k}", key[1], frozenset(n for _, n in members),
            tuple((n, b) for b, n in members),
        ))
    return out


def read_labels(floor_dir: Path) -> list[dict[str, str]]:
    """The rows of ``labels.csv``."""
    with (floor_dir / "labels.csv").open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def load_gt(
    floor_dir: Path,
) -> tuple[list[GtInstance], list[GtBus], dict[str, str], dict[str, str]]:
    """Instances (with the derived ones), label buses, role per node, ``module_path`` per node."""
    rows = read_labels(floor_dir)
    instances = derive_instances(_load_json(floor_dir / "words.json"))
    roles = {r["node_id"]: r["role"] for r in rows}
    paths = {r["node_id"]: r["module_path"] for r in rows}
    return instances, label_buses(rows), roles, paths


@dataclass(frozen=True)
class NetMap:
    """Net connectivity of ``graph.json``: node kinds, driver and readers per net name."""

    kinds: dict[str, str]
    driver: dict[str, str]
    readers: dict[str, tuple[str, ...]]


def load_netmap(floor_dir: Path) -> NetMap:
    """Read ``graph.json`` (nodes and edges only)."""
    graph = _load_json(floor_dir / "graph.json")
    nodes = graph.get("nodes", [])
    edges = graph.get("edges", [])
    if not isinstance(nodes, list) or not isinstance(edges, list):
        raise ValueError("graph.json: nodes and edges must be lists")
    kinds = {str(n["id"]): str(n["kind"]) for n in nodes}
    driver: dict[str, str] = {}
    readers: dict[str, list[str]] = {}
    for e in edges:
        driver[str(e["net"])] = str(e["src"])
        readers.setdefault(str(e["net"]), []).append(str(e["dst"]))
    return NetMap(kinds, driver, {k: tuple(sorted(v)) for k, v in readers.items()})
