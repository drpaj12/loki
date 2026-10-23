"""Graphlet counting core: counting graph, backend interface, orbit files, features (L2 spec 8).

The global-signal classifier and its per-node role flags live in
:mod:`loki.analysis.graphlets.signals` (spec 8.1 and 8.2). This module builds the counting graph
of spec 8.3, defines the counter protocol and the backend registry of spec 8.5, and reads and
writes the files of spec 8.6. :func:`gsn_features` joins the numeric feature block and the
categorical NPN and WL ids of spec 8.6 for the GNN. Counts are ``int64`` end to end (spec 3): a hub
of degree ``d`` has
``C(d, 3)`` star centres. numpy is imported inside functions after :func:`loki.analysis.require`,
so importing this module needs the standard library only.

A backend may carry the optional attributes ``commit``, ``sha256`` and ``licence``; the ``tool``
object of spec 8.6 reads them when present and records ``""`` otherwise.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol

from loki.analysis import require
from loki.analysis.graphio import Graph
from loki.analysis.graphlets.signals import CLASS_NAMES, SignalConfig, SignalInfo, classify_signals
from loki.analysis.partition import version_info
from loki.schemas import dump_json

if TYPE_CHECKING:
    import numpy.typing as npt

    from loki.analysis.structural import StructuralArrays

#: Orbit columns per graphlet size (spec 8.4 and 8.5): 15 for 4-node, 73 for 5-node graphlets.
N_ORBITS: dict[int, int] = {4: 15, 5: 73}
#: The spike's decision (spec 8.5): ORCA as a separate process is the default backend.
DEFAULT_BACKEND = "ext"
_SIZES = tuple(sorted(N_ORBITS))
_REMOVALS = ("global", "none")
_CLASSES = ("clock", "reset", "enable", "const")
_HUB = "hub"
_SIGNAL = CLASS_NAMES.index("signal")
_SCHEMA = 1
_KIND = "graphlets"
_DEFAULT_CONFIG = SignalConfig()


class BackendUnavailable(RuntimeError):
    """A graphlet backend is missing, not built, or refuses the requested work."""


class GraphletCounter(Protocol):
    """One orbit counter behind :func:`run_graphlets` (spec 8.5).

    ``count`` receives a simple undirected graph (``src < dst``, each edge once, int32 node
    indices) and returns int64 orbit counts of shape ``(n, N_ORBITS[size])``.
    """

    name: str
    max_size: int

    def available(self) -> tuple[bool, str]:
        """``(True, "")`` when the counter can run, else ``(False, reason)``."""
        ...

    def count(
        self, n: int, src: npt.NDArray[Any], dst: npt.NDArray[Any], size: int = 4
    ) -> npt.NDArray[Any]:
        """Orbit counts int64 ``(n, N_ORBITS[size])`` of the simple undirected graph."""
        ...


#: Registered backends by name; Task G-ext registers ``"ext"`` (ORCA).
BACKENDS: dict[str, GraphletCounter] = {}


def _backend_key(name: str) -> str:
    """The registry key a backend spelling resolves to: ``"default"`` is :data:`DEFAULT_BACKEND`.

    File names and the JSON ``backend`` use this key, so a registered counter whose own ``name``
    differs from its registry key still reads back the file it wrote.
    """
    return DEFAULT_BACKEND if name == "default" else name


def get_backend(name: str) -> GraphletCounter:
    """The registered counter ``name`` (spec 8.5); ``"default"`` is :data:`DEFAULT_BACKEND`.

    An unknown name raises ``ValueError``; a registered backend that reports itself unavailable
    raises :class:`BackendUnavailable` carrying its reason.
    """
    resolved = _backend_key(name)
    counter = BACKENDS.get(resolved)
    if counter is None:
        known = ", ".join(sorted(BACKENDS)) if BACKENDS else "none registered"
        raise ValueError(f"unknown graphlet backend {resolved!r}: use default or one of {known}")
    ok, reason = counter.available()
    if not ok:
        raise BackendUnavailable(f"graphlet backend {resolved!r} is not available: {reason}")
    return counter


@dataclass(frozen=True)
class CountingGraph:
    """The graph the counter sees (spec 8.3): node order kept, removed edges accounted.

    ``src``/``dst`` are int32 indices into the original ``node_ids`` (``src < dst``, each edge
    once, no self-loops); removed nodes stay as all-zero rows. ``removed_edges`` has the class
    names and ``hub``, every value counting undirected projected edges (one unit, so Task 13's
    total sums them); ``dropped_hubs`` lists ``(node_id, degree)`` in node order.
    """

    n: int
    src: npt.NDArray[Any]
    dst: npt.NDArray[Any]
    removed_edges: dict[str, int]
    dropped_hubs: list[tuple[str, int]]
    info: SignalInfo | None


def _projection(
    n: int, src: npt.NDArray[Any], dst: npt.NDArray[Any], mask: npt.NDArray[Any]
) -> tuple[npt.NDArray[Any], npt.NDArray[Any]]:
    """Simple undirected projection of the masked edges: int32, sorted, ``src < dst``."""
    import numpy as np

    empty = np.zeros(0, dtype=np.int32)
    if n <= 0 or not mask.any():
        return empty, empty.copy()
    low = np.minimum(src, dst).astype(np.int64)
    high = np.maximum(src, dst).astype(np.int64)
    simple = mask & (low != high)
    if not simple.any():
        return empty, empty.copy()
    keys = np.unique(low[simple] * int(n) + high[simple])
    return (keys // int(n)).astype(np.int32), (keys % int(n)).astype(np.int32)


def counting_graph(
    g: Graph,
    removal: str = "global",
    cfg: SignalConfig = _DEFAULT_CONFIG,
    hub_threshold: int = 1000,
) -> CountingGraph:
    """The counting graph of ``g`` under ``removal`` (spec 8.3).

    ``global`` drops every directed edge whose net class is not ``signal`` and then every edge
    of a node whose remaining degree exceeds ``hub_threshold``, listing ``(node_id, degree)``.
    ``none`` keeps every edge. Both are simple undirected projections with every node kept, and
    the signal info is computed for either because the role features are never removed.
    ``removed_edges`` counts undirected projected edges only: each class counts the unique
    ``src < dst`` pairs it drops and ``hub`` the pairs the fallback drops. A negative
    ``hub_threshold`` raises ``ValueError`` instead of silently disabling the fallback.
    """
    require("analysis")
    import numpy as np

    if removal not in _REMOVALS:
        raise ValueError(f"unknown removal {removal!r}: use 'global' or 'none'")
    if hub_threshold < 0:
        raise ValueError(f"hub_threshold must be >= 0, got {hub_threshold}")
    info = classify_signals(g, cfg)
    removed = dict.fromkeys((*_CLASSES, _HUB), 0)
    mask = np.ones(g.n_edges, dtype=bool)
    if removal == "global":
        for name in _CLASSES:
            class_mask = info.edge_class == CLASS_NAMES.index(name)
            removed[name] = int(_projection(g.n_nodes, g.src, g.dst, class_mask)[0].size)
        mask = info.edge_class == _SIGNAL
    src, dst = _projection(g.n_nodes, g.src, g.dst, mask)
    dropped: list[tuple[str, int]] = []
    if removal == "global" and src.size:
        degree = np.bincount(np.concatenate([src, dst]), minlength=g.n_nodes)
        hubs = np.flatnonzero(degree > hub_threshold)
        if hubs.size:
            dropped = [(g.node_ids[int(row)], int(degree[row])) for row in hubs]
            keep = ~(np.isin(src, hubs) | np.isin(dst, hubs))
            removed[_HUB] = int(np.count_nonzero(~keep))
            src, dst = src[keep], dst[keep]
    return CountingGraph(
        n=g.n_nodes, src=src, dst=dst, removed_edges=removed, dropped_hubs=dropped, info=info
    )


def write_edge_file(
    path: Path, n: int, src: npt.NDArray[Any], dst: npt.NDArray[Any]
) -> None:
    """Write the counter protocol's input file (spec 8.5): a ``N M`` line, then ``u v`` lines."""
    require("analysis")
    import numpy as np

    m = int(np.size(src))
    if int(np.size(dst)) != m:
        raise ValueError(f"src has {m} edges and dst {int(np.size(dst))}")
    pairs = np.column_stack(
        [np.asarray(src, dtype=np.int64), np.asarray(dst, dtype=np.int64)]
    ).reshape(m, 2)
    np.savetxt(path, pairs, fmt="%d", header=f"{int(n)} {m}", comments="")


def read_orbit_file(path: Path, n: int, n_orbits: int) -> npt.NDArray[Any]:
    """Read the counter protocol's output file (spec 8.5) as int64 ``(n, n_orbits)``.

    The whole text is split once and reshaped, so no Python loop runs per line. A wrong number
    of rows or a wrong width raises ``ValueError``.
    """
    require("analysis")
    import numpy as np

    if n < 0 or n_orbits < 1:
        raise ValueError(f"n must be >= 0 and n_orbits >= 1, got {n} and {n_orbits}")
    tokens = path.read_text(encoding="utf-8").split()
    if len(tokens) != n * n_orbits:
        if len(tokens) % n_orbits == 0:
            rows = len(tokens) // n_orbits
            raise ValueError(f"{path} has {rows} orbit rows of {n_orbits} values, expected {n}")
        raise ValueError(f"{path} has {len(tokens)} values: not {n} rows of {n_orbits}")
    return np.array(tokens, dtype=np.int64).reshape(n, n_orbits)


def graphlet_features(
    orbits: npt.NDArray[Any], roles: npt.NDArray[Any]
) -> npt.NDArray[Any]:
    """The numeric feature block of spec 8.6: standardised ``log1p`` orbits, then ``roles``.

    Constant orbit columns are dropped after ``log1p`` (they carry no information); the four
    role columns are appended as they are (``clock_domain`` stays a number, models may one-hot
    it). A graph with no varying orbit column (no edges, a single node) gives just the roles.
    """
    require("analysis")
    import numpy as np

    counts = np.asarray(orbits, dtype=np.float64)
    flags = np.asarray(roles, dtype=np.float64)
    if counts.ndim != 2:
        raise ValueError(f"orbits must be a 2-D array, got shape {counts.shape}")
    if flags.shape != (counts.shape[0], 4):
        raise ValueError(f"roles must be {(counts.shape[0], 4)}, got shape {flags.shape}")
    values = np.log1p(counts)
    if values.shape[0] == 0:
        return np.zeros((0, 4), dtype=np.float64)
    mean = values.mean(axis=0)
    spread = values.std(axis=0)
    keep = spread > 0
    scaled = (values[:, keep] - mean[keep]) / spread[keep]
    return np.concatenate([scaled, flags], axis=1)


def gsn_features(
    orbits: npt.NDArray[Any] | None,
    roles: npt.NDArray[Any],
    s: StructuralArrays,
) -> tuple[npt.NDArray[Any], npt.NDArray[Any]]:
    """The two GSN blocks of spec 8.6 for one graph.

    The numeric block is :func:`graphlet_features` of ``orbits`` and ``roles`` (standardised
    ``log1p`` orbit counts, then the four role columns) or, without an orbit file, the role
    columns alone as float64. The categorical block is int64 ``(N, 2 + rounds)``: the NPN class
    id in column 0 and the WL colour ids of rounds 0 to ``rounds`` after it. Categorical ids are
    hashes and never enter the numeric block (spec 4.1).
    """
    require("analysis")
    import numpy as np

    flags = np.asarray(roles)
    if flags.ndim != 2 or flags.shape[1] != 4:
        raise ValueError(f"roles must be (n, 4), got shape {flags.shape}")
    n = int(flags.shape[0])
    wl_values = np.asarray(s.wl)
    npn_values = np.asarray(s.npn)
    expected = (n, len(s.colours))
    if wl_values.shape != expected:
        raise ValueError(f"wl must be {expected}, got shape {wl_values.shape}")
    if npn_values.shape != (n,):
        raise ValueError(f"npn must be {(n,)}, got shape {npn_values.shape}")
    if orbits is None:
        numeric = np.asarray(flags, dtype=np.float64)
    else:
        numeric = graphlet_features(orbits, flags)
    categorical = np.empty((n, 1 + wl_values.shape[1]), dtype=np.int64)
    categorical[:, 0] = npn_values
    categorical[:, 1:] = wl_values
    return numeric, categorical


def _tool_info(counter: GraphletCounter) -> dict[str, str]:
    """The ``tool`` object of spec 8.6 from the backend's optional tool attributes."""
    return {
        "name": counter.name,
        "commit": str(getattr(counter, "commit", "")),
        "sha256": str(getattr(counter, "sha256", "")),
        "licence": str(getattr(counter, "licence", "")),
    }


def run_graphlets(
    g: Graph,
    backend: str,
    out_dir: Path,
    *,
    size: int = 4,
    removal: str = "global",
    cfg: SignalConfig = _DEFAULT_CONFIG,
    hub_threshold: int = 1000,
    force: bool = False,
) -> Path:
    """Count orbits of ``g`` and write the npz and JSON of spec 8.6 into ``out_dir``.

    Files are ``orbits-<backend>-<removal>.npz`` and ``graphlets-<backend>-<removal>.json``,
    where ``<backend>`` is the registry key (``"default"`` resolves to :data:`DEFAULT_BACKEND`);
    the JSON path is returned. The npz stores the graphlet ``size``, so :func:`load_orbits` can
    check the orbit width against :data:`N_ORBITS`. ``n_nodes`` and ``n_edges`` describe the
    counting graph that was counted (``n_nodes`` always equals the graph's, because removed
    nodes keep a zero row). ``size == 5`` with ``removal == "none"`` is refused unless ``force``
    (measured: the full 5-node mcml did not finish in 30 min, spec 8.3).
    """
    require("analysis")
    import numpy as np

    if size not in N_ORBITS:
        raise ValueError(f"unknown graphlet size {size}: use one of {_SIZES}")
    if removal not in _REMOVALS:
        raise ValueError(f"unknown removal {removal!r}: use 'global' or 'none'")
    if size == 5 and removal == "none" and not force:
        raise BackendUnavailable(
            "5-node orbits on the full graph did not finish in 30 min; "
            "use --removal global or --force"
        )
    resolved = _backend_key(backend)
    counter = get_backend(resolved)
    if size > counter.max_size:
        raise BackendUnavailable(
            f"graphlet backend {counter.name!r} counts at most {counter.max_size}-node graphlets"
        )
    start = time.perf_counter()
    counting = counting_graph(g, removal, cfg, hub_threshold)
    orbits = np.asarray(counter.count(counting.n, counting.src, counting.dst, size))
    expected = (counting.n, N_ORBITS[size])
    if orbits.shape != expected or orbits.dtype != np.int64:
        raise ValueError(
            f"backend {counter.name!r} returned {orbits.dtype} of shape {orbits.shape}, "
            f"expected int64 of shape {expected}"
        )
    info = counting.info
    if info is None:
        raise RuntimeError("the counting graph carries no signal info")
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = f"{resolved}-{removal}"
    np.savez(
        out_dir / f"orbits-{stem}.npz",
        orbits=orbits,
        roles=info.roles,
        node_ids=np.asarray(g.node_ids),
        size=np.int64(size),
    )
    record: dict[str, object] = {
        "schema": _SCHEMA,
        "kind": _KIND,
        "design": g.design,
        "floor": g.floor,
        "backend": resolved,
        "tool": _tool_info(counter),
        "size": int(size),
        "n_orbits": N_ORBITS[size],
        "removal": removal,
        "hub_threshold": int(hub_threshold),
        "signal_config": {
            "min_fanout": int(cfg.min_fanout),
            "dominance": round(float(cfg.dominance), 6),
        },
        "classified": {name: int(info.classified.get(name, 0)) for name in _CLASSES},
        "removed_edges": {
            name: int(counting.removed_edges.get(name, 0)) for name in (*_CLASSES, _HUB)
        },
        "dropped_hubs": [
            {"id": node_id, "degree": degree} for node_id, degree in counting.dropped_hubs
        ],
        "clock_domains": int(info.clock_domains),
        "n_nodes": int(counting.n),
        "n_edges": int(counting.src.size),
        "graph_sha256": g.sha256,
        "seconds": round(time.perf_counter() - start, 6),
        "versions": version_info(),
    }
    path = out_dir / f"graphlets-{stem}.json"
    path.write_text(dump_json(record), encoding="utf-8")
    return path


def load_orbits(
    g: Graph, backend: str, removal: str, out_dir: Path
) -> tuple[npt.NDArray[Any], npt.NDArray[Any]]:
    """Orbits and roles of a previous :func:`run_graphlets` run (spec 8.6), by file name.

    A missing file raises ``FileNotFoundError`` (the caller computes it first); arrays whose
    node count differs from ``g``, a stored ``node_ids`` that differs from ``g``, or an orbit
    width that does not match the stored graphlet ``size`` (or any size of :data:`N_ORBITS`
    for files written before the size was stored) raise ``ValueError``.
    """
    require("analysis")
    import numpy as np

    name = _backend_key(backend)
    path = out_dir / f"orbits-{name}-{removal}.npz"
    with np.load(path) as data:
        orbits = np.asarray(data["orbits"])
        roles = np.asarray(data["roles"])
        node_ids = tuple(str(node_id) for node_id in np.asarray(data["node_ids"]).tolist())
        size = int(np.asarray(data["size"])) if "size" in data.files else None
    if node_ids != tuple(g.node_ids):
        raise ValueError(f"{path}: node ids do not match the {g.n_nodes} nodes of the graph")
    if orbits.ndim != 2 or orbits.shape[0] != g.n_nodes:
        raise ValueError(f"{path}: orbits of shape {orbits.shape} do not match {g.n_nodes} nodes")
    width = int(orbits.shape[1])
    if size is not None:
        if size not in N_ORBITS:
            raise ValueError(f"{path}: stored graphlet size {size} is not one of {_SIZES}")
        if width != N_ORBITS[size]:
            raise ValueError(f"{path}: {width} orbit columns do not match size {size}")
    elif width not in N_ORBITS.values():
        raise ValueError(f"{path}: {width} orbit columns do not match sizes {_SIZES}")
    if roles.shape != (g.n_nodes, 4):
        raise ValueError(f"{path}: roles of shape {roles.shape} do not match {g.n_nodes} nodes")
    return orbits, roles
