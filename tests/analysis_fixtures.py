"""Hand-built ``graph.json`` fixtures shared by the L2 analysis tests (L2 plan Task 1).

The graphs are structured by hand: no randomness except ``big_synthetic``'s seeded generator.
``make_graph`` plants two LUT blocks that differ in ``lut_width`` and ``module_path`` and whose
``construct_type`` follows the width, so a model can learn ``lut_width -> construct_type``.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from loki import __version__
from loki.schemas import SCHEMA, SPLIT_SEED, dump_json, split_of

if TYPE_CHECKING:
    import numpy as np


def _features(
    *,
    fan_in: int = 0,
    fan_out: int = 0,
    level: int = 0,
    lut_width: int = 0,
    lut_table: str = "",
    is_seq: int = 0,
    is_const: int = 0,
    hard_ports: int = 0,
) -> dict[str, object]:
    """A complete ``features`` object of L0 spec 6.4."""
    return {
        "fan_in": fan_in, "fan_out": fan_out, "level": level, "lut_width": lut_width,
        "lut_table": lut_table, "is_seq": is_seq, "is_const": is_const,
        "hard_ports": hard_ports,
    }


def _label(
    construct_type: str,
    module_path: str,
    role: str,
    *,
    n_construct_cells: int = 1,
    bus_name: str = "",
    bit_index: int = -1,
    n_spans: int = 1,
) -> dict[str, object]:
    """A complete ``labels`` object of L0 spec 6.4."""
    return {
        "construct_type": construct_type,
        "construct_types": construct_type,
        "n_construct_cells": n_construct_cells,
        "module_path": module_path,
        "bus_name": bus_name,
        "bit_index": bit_index,
        "role": role,
        "hdl_file": "d.v" if construct_type else "",
        "hdl_line": -1,
        "hdl_col": -1,
        "hdl_end_line": -1,
        "hdl_end_col": -1,
        "n_spans": n_spans,
    }


_EMPTY_LABELS = _label("", "", "unknown", n_construct_cells=-1, n_spans=0)


def make_graph(
    n_lut: int = 12, floor: str = "f2", design: str = "d", seed: int = 0, labels: bool = True
) -> dict[str, object]:
    """A valid L0 ``graph.json`` object: 2 PI, ``n_lut`` LUTs, 2 FF, 1 PO, connected.

    The first half of the LUTs is a chain of width-2 ``$eq`` LUTs in ``top/u0``; the second half
    is a chain of width-3 ``$add`` LUTs in ``top/u1`` fed by the first chain's last LUT. Two data
    PIs feed the chains, the FFs take their D from each chain's last LUT and the shared clock
    ``n0``, and the PO reads the first FF's output. ``seed`` is accepted for interface symmetry
    but unused: the fixture is purely arithmetic. ``labels=False`` writes the valid all-empty,
    ``unknown`` labels of the unlabelled case.
    """
    if n_lut < 0:
        raise ValueError("n_lut must be >= 0")
    half = n_lut // 2
    luts = [f"n{i}" for i in range(2, 2 + n_lut)]
    ff0, ff1 = f"n{2 + n_lut}", f"n{3 + n_lut}"
    po = f"n{4 + n_lut}"
    block0, block1 = luts[:half], luts[half:]
    block0_set, block1_set = set(block0), set(block1)
    order = ["n0", "n1", *luts, ff0, ff1, po]
    kind = dict.fromkeys(order, "lut") | {
        "n0": "pi", "n1": "pi", ff0: "ff", ff1: "ff", po: "po",
    }
    net = {driver: f"n{5 + n_lut + i}" for i, driver in enumerate(["n0", "n1", *luts, ff0, ff1])}
    pairs: list[tuple[str, str, str]] = []

    def edge(src: str, dst: str, pin: str) -> None:
        pairs.append((src, dst, pin))

    for i, lut in enumerate(block0):
        edge("n0" if i == 0 else block0[i - 1], lut, "I0")
        edge("n1", lut, "I1")
    for i, lut in enumerate(block1):
        edge("n0" if i == 0 else block1[i - 1], lut, "I0")
        edge("n1", lut, "I1")
        edge(block0[-1] if block0 else "n0", lut, "I2")
    edge(block0[-1] if block0 else "n0", ff0, "D")
    edge("n0", ff0, "CLK")
    edge(block1[-1] if block1 else "n0", ff1, "D")
    edge("n0", ff1, "CLK")
    edge(ff0, po, "I")

    fan_in: dict[str, int] = dict.fromkeys(order, 0)
    fan_out: dict[str, int] = dict.fromkeys(order, 0)
    drivers: dict[str, list[str]] = {nid: [] for nid in order}
    for src, dst, _pin in pairs:
        fan_out[src] += 1
        fan_in[dst] += 1
        drivers[dst].append(src)
    level: dict[str, int] = {}
    for nid in order:
        if kind[nid] in ("pi", "ff", "const"):
            level[nid] = 0
        else:
            level[nid] = max((level[src] for src in drivers[nid]), default=-1) + 1

    nodes: list[dict[str, object]] = []
    for nid in order:
        width = 2 if nid in block0_set else 3 if nid in block1_set else 0
        table = "8" if width == 2 else "80" if width == 3 else ""
        if not labels:
            lab = dict(_EMPTY_LABELS)
        elif kind[nid] == "pi":
            lab = _label("$port_in", "top", "io", bus_name=nid, bit_index=0)
        elif kind[nid] == "po":
            lab = _label("$port_out", "top", "io", bus_name="y", bit_index=0)
        elif kind[nid] == "ff":
            module = "top/u0" if nid == ff0 else "top/u1"
            lab = _label("$dff", module, "control")
        else:
            module = "top/u0" if nid in block0_set else "top/u1"
            lab = _label("$eq" if width == 2 else "$add", module, "datapath")
        nodes.append(
            {
                "id": nid,
                "kind": kind[nid],
                "features": _features(
                    fan_in=fan_in[nid], fan_out=fan_out[nid], level=level[nid],
                    lut_width=width, lut_table=table, is_seq=int(kind[nid] == "ff"),
                ),
                "labels": lab,
            }
        )
    pairs.sort(key=lambda p: (int(p[0][1:]), int(p[1][1:]), p[2]))
    edges = [{"src": src, "dst": dst, "net": net[src], "pin": pin} for src, dst, pin in pairs]
    return {"schema": SCHEMA, "design": design, "floor": floor, "nodes": nodes, "edges": edges}


def write_graph(directory: Path, obj: dict[str, object]) -> Path:
    """Write ``obj`` as ``<directory>/graph.json`` (deterministic output); return the path."""
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "graph.json"
    path.write_text(dump_json(obj), encoding="utf-8")
    return path


def make_dataset(root: Path, designs: int = 6, floor: str = "f2", seed: int = 0) -> Path:
    """Write a valid L0 dataset under ``root``: ``manifest.json`` plus one graph per design.

    Designs are ``micro_a0`` .. ``micro_a<designs-1>``, each with both planted LUT classes, so a
    model can learn ``lut_width -> construct_type``. ``split`` comes from
    :func:`loki.schemas.split_of`, so the small default set holds train and test designs.
    """
    entries: list[dict[str, object]] = []
    for index in range(designs):
        name = f"micro_a{index}"
        graph = make_graph(floor=floor, design=name, seed=seed + index)
        write_graph(root / name / floor, graph)
        nodes = graph["nodes"]
        count = len(nodes) if isinstance(nodes, list) else 0
        entries.append(
            {
                "design": name,
                "benchmark": "micro",
                "split": split_of(name),
                "floors": {floor: {"status": "ok", "nodes": count}},
            }
        )
    manifest: dict[str, object] = {
        "schema": SCHEMA,
        "created_by": f"loki {__version__}",
        "odin3_version": "1.0.0",
        "split_seed": SPLIT_SEED,
        "split_rule": ("sha256(seed + ':' + design) first 8 bytes, big-endian, "
                       "mod 100 < 80 is train"),
        "designs": entries,
    }
    root.mkdir(parents=True, exist_ok=True)
    (root / "manifest.json").write_text(dump_json(manifest), encoding="utf-8")
    return root


def star_graph(d: int) -> dict[str, object]:
    """A valid ``graph.json`` object: hub ``n0`` with ``d`` leaf LUTs (L2 plan Task 1)."""
    if d < 0:
        raise ValueError("d must be >= 0")
    hub_features = _features(fan_out=d, lut_width=d)
    leaf_features = _features(fan_in=1, level=1)
    nodes: list[dict[str, object]] = [
        {"id": "n0", "kind": "lut", "features": hub_features, "labels": dict(_EMPTY_LABELS)}
    ]
    for i in range(1, d + 1):
        nodes.append(
            {
                "id": f"n{i}",
                "kind": "lut",
                "features": dict(leaf_features),
                "labels": dict(_EMPTY_LABELS),
            }
        )
    edges = [
        {"src": "n0", "dst": f"n{i}", "net": f"n{d + 1}", "pin": f"I{i - 1}"}
        for i in range(1, d + 1)
    ]
    return {"schema": SCHEMA, "design": "star", "floor": "f2", "nodes": nodes, "edges": edges}


def big_synthetic(n: int, m: int, seed: int = 0) -> tuple[np.ndarray, np.ndarray]:
    """The L2 spec 3 benchmark graph: local edges within +-50 plus a 20000-fan-out hub.

    ``m`` is the wanted number of undirected edges including the hub's. The hub is node 0 with
    exactly ``min(20000, n - 1)`` leaves; every other edge joins nodes at an offset of 1 to 50.
    The result is simple (no self-loops, no parallel edges), canonical (``src < dst``) and sorted,
    and deterministic for a given ``(n, m, seed)``. It returns fewer than ``m`` edges only when
    the request is denser than the generator fills in 64 batches.
    """
    import numpy as np

    if n < 2:
        raise ValueError("big_synthetic needs n >= 2")
    rng = np.random.default_rng(seed)
    hub_edges = min(20000, n - 1, m)
    leaves = rng.choice(n - 1, size=hub_edges, replace=False).astype(np.int64) + 1
    keys = leaves  # key = src * n + dst; src 0 gives dst
    rounds = 0
    while keys.size < m and rounds < 64:
        need = m - keys.size
        batch = max(4096, 2 * need)
        anchor = rng.integers(1, n, size=batch, dtype=np.int64)
        delta = rng.integers(1, 51, size=batch, dtype=np.int64)
        sign = 2 * rng.integers(0, 2, size=batch, dtype=np.int64) - 1
        other = anchor + sign * delta
        other = np.where((other < 1) | (other >= n), anchor - sign * delta, other)
        keep = (other >= 1) & (other < n) & (other != anchor)
        low = np.minimum(anchor, other)[keep]
        high = np.maximum(anchor, other)[keep]
        combined = np.concatenate([keys, low * n + high])
        _, first = np.unique(combined, return_index=True)
        keys = combined[np.sort(first)]
        rounds += 1
    if keys.size > m:
        keys = keys[:m]
    src = keys // n
    dst = keys % n
    order = np.lexsort((dst, src))
    return src[order].astype(np.int64), dst[order].astype(np.int64)
