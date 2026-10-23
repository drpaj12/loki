"""Structural features of a graph: role flags, WL colours and NPN classes (L2 spec 4.1).

The algorithms live in L1's standard-library :mod:`loki.features`; this module adapts an L2
:class:`~loki.analysis.graphio.Graph` to L1's feature graph through
:func:`~loki.analysis.graphio.to_feature_graph`, computes the arrays of spec 4.1, stores them as
the npz and JSON of spec 4.1 and reads them back. Colour and NPN class ids are :func:`hash64` of
the stable strings behind them, so they compare across designs without a shared vocabulary; they
are categorical and never enter a numeric feature matrix (spec 4.1).

numpy belongs to the ``analysis`` extra and is imported inside functions after
:func:`loki.analysis.require`, so importing this module needs the standard library only.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from loki.analysis import require
from loki.analysis.graphio import Graph, to_feature_graph
from loki.analysis.partition import version_info
from loki.features import WL_ROUNDS
from loki.features.npn import npn_class, transforms
from loki.features.roles import classify_nets
from loki.features.wl import Quotient, WLConfig, quotient, refine, stable_partition
from loki.schemas import dump_json

if TYPE_CHECKING:
    from pathlib import Path

    import numpy.typing as npt

_SCHEMA = 1
_KIND = "structural"


@dataclass(frozen=True)
class StructuralArrays:
    """The structural arrays of one graph (L2 spec 4.1).

    ``wl`` is int64 ``(N, rounds + 1)`` of :func:`hash64` colour ids, ``npn`` int64 ``(N,)`` of
    :func:`hash64` class keys (0 for a node without a LUT table), ``roles`` int64 ``(N, 4)`` with
    columns ``clock_domain, has_reset, const_inputs, enable``; ``npn_keys`` and ``colours`` hold
    the strings behind those ids. ``stable_round`` is the first round whose class count repeats
    (or ``None``); ``stable_class`` and ``quotient`` are present only with ``with_quotient``.
    """

    variant: str
    wl: npt.NDArray[Any]
    npn: npt.NDArray[Any]
    roles: npt.NDArray[Any]
    npn_keys: tuple[str, ...]
    colours: tuple[tuple[str, ...], ...]
    stable_round: int | None
    stable_class: npt.NDArray[Any] | None
    quotient: Quotient | None


def hash64(s: str) -> int:
    """The first 8 bytes of ``sha256(s)`` as a signed big-endian int64; 0 for ``""`` (spec 4.1)."""
    if not s:
        return 0
    return int.from_bytes(hashlib.sha256(s.encode("utf-8")).digest()[:8], "big", signed=True)


def compute_structural(
    g: Graph, variant: str = "npn/both", rounds: int = WL_ROUNDS, with_quotient: bool = False
) -> StructuralArrays:
    """The spec-4.1 structural arrays of ``g``.

    ``variant`` is ``<start>/<direction>`` (``npn/both`` or ``table/both``); the WL colours come
    from :func:`loki.features.wl.refine` with that configuration, the NPN keys from
    :func:`loki.features.npn.npn_class` for every node with a LUT table, and the role flags from
    :func:`loki.features.roles.classify_nets` on the same feature graph Task 9's
    :func:`~loki.analysis.graphlets.signals.classify_signals` uses. ``with_quotient`` adds the
    coarsest equitable partition and its quotient graph (needs direction ``in`` or ``both``).
    """
    require("analysis")
    import numpy as np

    cfg = _config(variant, rounds)
    fg = to_feature_graph(g)
    net_roles = classify_nets(fg)
    result = refine(fg, net_roles, cfg)
    n = g.n_nodes
    wl = np.empty((n, len(result.colours)), dtype=np.int64)
    for round_index, colours in enumerate(result.colours):
        wl[:, round_index] = np.fromiter(
            (hash64(colour) for colour in colours), dtype=np.int64, count=n
        )
    keys = tuple(
        npn_class(fg.table[row], fg.width[row]).key if fg.table[row] >= 0 else ""
        for row in range(n)
    )
    npn = np.fromiter((hash64(key) for key in keys), dtype=np.int64, count=n)
    roles = np.asarray(
        [
            (node.clock_domain, node.has_reset, node.const_inputs, node.enable)
            for node in net_roles.nodes
        ],
        dtype=np.int64,
    ).reshape(n, 4)
    stable_class: npt.NDArray[Any] | None = None
    quotient_graph: Quotient | None = None
    if with_quotient:
        partition = stable_partition(fg, net_roles, cfg)
        stable_class = np.asarray(partition.class_of, dtype=np.int64)
        quotient_graph = quotient(fg, net_roles, partition, cfg)
    return StructuralArrays(
        variant=cfg.name,
        wl=wl,
        npn=npn,
        roles=roles,
        npn_keys=keys,
        colours=result.colours,
        stable_round=result.stable_round,
        stable_class=stable_class,
        quotient=quotient_graph,
    )


def run_structural(
    g: Graph,
    out_dir: Path,
    variant: str = "npn/both",
    rounds: int = WL_ROUNDS,
    with_quotient: bool = False,
) -> Path:
    """Write the spec-4.1 npz and JSON of ``g`` into ``out_dir`` and return the JSON path.

    Files are ``structural-<variant>.npz`` and ``structural-<variant>.json``; the variant's ``/``
    becomes ``-`` (the default is ``structural-npn-both.*``). An existing pair with the same
    ``graph_sha256``, variant, round count and quotient option is reused unchanged.
    """
    require("analysis")
    import numpy as np

    out_dir.mkdir(parents=True, exist_ok=True)
    stem = f"structural-{_slug(variant)}"
    json_path = out_dir / f"{stem}.json"
    npz_path = out_dir / f"{stem}.npz"
    if _reusable(json_path, npz_path, g, variant, rounds, with_quotient):
        return json_path
    start = time.perf_counter()
    arrays = compute_structural(g, variant, rounds, with_quotient)
    payload: dict[str, Any] = {
        "wl": arrays.wl,
        "npn": arrays.npn,
        "roles": arrays.roles,
        "node_ids": np.asarray(g.node_ids),
    }
    if arrays.stable_class is not None:
        payload["stable_class"] = arrays.stable_class
    np.savez(npz_path, **payload)
    record: dict[str, object] = {
        "schema": _SCHEMA,
        "kind": _KIND,
        "design": g.design,
        "floor": g.floor,
        "variant": arrays.variant,
        "rounds": int(arrays.wl.shape[1]) - 1,
        "stable_round": arrays.stable_round,
        "classes_per_round": [len(set(colours)) for colours in arrays.colours],
        "npn": _npn_summary(g),
        "npn_keys": list(arrays.npn_keys),
        "colours": [list(colours) for colours in arrays.colours],
        "quotient": _quotient_json(arrays.quotient),
        "graph_sha256": g.sha256,
        "seconds": round(time.perf_counter() - start, 6),
        "versions": version_info(),
    }
    json_path.write_text(dump_json(record), encoding="utf-8")
    return json_path


def load_structural(g: Graph, variant: str, out_dir: Path) -> StructuralArrays:
    """Read back the files :func:`run_structural` wrote for ``g``.

    A file for another graph (different ``graph_sha256`` or node ids) raises ``ValueError``. The
    quotient's ``size`` is rebuilt from ``stable_class`` because the JSON keeps only
    ``n_classes`` and ``edges`` (spec 4.1); its per-class start labels are not stored and read
    back empty.
    """
    require("analysis")
    import numpy as np

    stem = f"structural-{_slug(variant)}"
    json_path = out_dir / f"{stem}.json"
    npz_path = out_dir / f"{stem}.npz"
    record: Any = json.loads(json_path.read_text(encoding="utf-8"))
    with np.load(npz_path) as data:
        wl = np.asarray(data["wl"])
        npn = np.asarray(data["npn"])
        roles = np.asarray(data["roles"])
        node_ids = tuple(str(node_id) for node_id in np.asarray(data["node_ids"]).tolist())
        stable_class = (
            np.asarray(data["stable_class"]) if "stable_class" in data.files else None
        )
    if node_ids != tuple(g.node_ids):
        raise ValueError(f"{npz_path}: node ids do not match the {g.n_nodes} nodes of the graph")
    if str(record.get("graph_sha256")) != g.sha256:
        raise ValueError(f"{json_path}: written for graph {record.get('graph_sha256')}")
    colours = tuple(tuple(str(colour) for colour in round_) for round_ in record["colours"])
    if wl.shape != (g.n_nodes, len(colours)):
        raise ValueError(f"{npz_path}: wl of shape {wl.shape} does not match {g.n_nodes} nodes")
    if npn.shape != (g.n_nodes,):
        raise ValueError(f"{npz_path}: npn of shape {npn.shape} does not match {g.n_nodes} nodes")
    if roles.shape != (g.n_nodes, 4):
        raise ValueError(f"{npz_path}: roles of shape {roles.shape} do not match {g.n_nodes}")
    if stable_class is not None and stable_class.shape != (g.n_nodes,):
        raise ValueError(
            f"{npz_path}: stable_class of shape {stable_class.shape} does not match {g.n_nodes}"
        )
    stable_round = record.get("stable_round")
    return StructuralArrays(
        variant=str(record["variant"]),
        wl=wl,
        npn=npn,
        roles=roles,
        npn_keys=tuple(str(key) for key in record["npn_keys"]),
        colours=colours,
        stable_round=None if stable_round is None else int(stable_round),
        stable_class=stable_class,
        quotient=_quotient_from(record.get("quotient"), stable_class),
    )


def _config(variant: str, rounds: int) -> WLConfig:
    """The WL configuration named ``<start>/<direction>`` (``ValueError`` when malformed)."""
    parts = variant.split("/")
    if len(parts) != 2:
        raise ValueError(f"wl variant {variant!r} must be '<start>/<direction>'")
    return WLConfig(parts[0], parts[1], rounds)


def _slug(variant: str) -> str:
    """The variant as a file-name fragment: ``npn/both`` becomes ``npn-both``."""
    return variant.replace("/", "-")


def _reusable(
    json_path: Path,
    npz_path: Path,
    g: Graph,
    variant: str,
    rounds: int,
    with_quotient: bool,
) -> bool:
    """True when both files exist and describe this graph and these options."""
    if not (json_path.is_file() and npz_path.is_file()):
        return False
    try:
        record: Any = json.loads(json_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    return bool(
        record.get("graph_sha256") == g.sha256
        and record.get("variant") == variant
        and record.get("rounds") == int(rounds)
        and (record.get("quotient") is not None) == with_quotient
    )


def _npn_summary(g: Graph) -> dict[str, object]:
    """The ``npn`` JSON block: the per-graph NPN cost, deterministic across runs.

    ``distinct_tables`` counts distinct ``(table, width)`` pairs, ``classes`` distinct class
    keys, ``exact`` says every class was exact, and ``worst_enum`` is the most transforms any
    one table needed.
    """
    pairs = {
        (int(g.table[row]), int(g.num["lut_width"][row]))
        for row in range(g.n_nodes)
        if g.table[row] >= 0
    }
    return {
        "distinct_tables": len(pairs),
        "classes": len({npn_class(table, width).key for table, width in pairs}),
        "exact": all(npn_class(table, width).exact for table, width in pairs),
        "worst_enum": max((transforms(table, width) for table, width in pairs), default=0),
    }


def _quotient_json(quotient_graph: Quotient | None) -> dict[str, object] | None:
    """The ``quotient`` JSON object of spec 4.1: ``n_classes`` and ``edges``."""
    if quotient_graph is None:
        return None
    return {
        "n_classes": len(quotient_graph.size),
        "edges": [list(edge) for edge in quotient_graph.edges],
    }


def _quotient_from(
    raw: object, stable_class: npt.NDArray[Any] | None
) -> Quotient | None:
    """Rebuild the quotient of a stored record (sizes from ``stable_class``, labels empty)."""
    import numpy as np

    if not isinstance(raw, dict):
        return None
    n_classes = int(raw["n_classes"])
    if stable_class is None:
        size = tuple(0 for _ in range(n_classes))
    else:
        size = tuple(int(count) for count in np.bincount(stable_class, minlength=n_classes))
    edges = tuple(
        (int(edge[0]), int(edge[1]), str(edge[2]), int(edge[3])) for edge in raw["edges"]
    )
    return Quotient(size, tuple("" for _ in range(n_classes)), edges)
