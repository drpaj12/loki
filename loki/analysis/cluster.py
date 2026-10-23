"""Clustering methods: k-means, affinity propagation, spectral and Louvain (L2 spec section 7).

k-means and affinity propagation work in one float64 space (:func:`cluster_space`): six numeric
features of spec 4 (without the floor block, the hard-type one-hot and ``is_seq``/``is_const``),
``log1p``-scaled and standardised with ``StandardScaler``, then the kind one-hot columns, then
optional extra columns such as the graphlet signatures. Constant columns standardise to zeros and
are kept, never dropped.

k-means sees the whole netlist: ``KMeans`` up to :data:`KMEANS_FULL_MAX` nodes,
``MiniBatchKMeans`` above. Affinity propagation would build a dense N x N similarity matrix, so
it runs on a seeded sample of at most ``max_points`` nodes and assigns every other node to the
nearest exemplar in chunks of at most 10000 rows. Spectral clustering embeds the largest
connected component and gives every other component one cluster of its own (spec 7.3); Louvain
runs on the whole undirected projection (spec 7.4). :func:`run_cluster` runs a requested subset
of :data:`METHODS` in table order and writes each partition. Partitions are built by
:func:`loki.analysis.partition.make_partition`, which numbers clusters canonically.

numpy, scipy and scikit-learn belong to the ``analysis`` extra and are imported inside the
functions after :func:`loki.analysis.require`, so importing this module needs the standard
library only.
"""

from __future__ import annotations

import importlib
import math
import warnings
from typing import TYPE_CHECKING, Any

from loki.analysis import require
from loki.analysis.graphio import canonical_numbers, undirected_adjacency
from loki.analysis.partition import Partition, make_partition, write_partition
from loki.schemas import KINDS

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path

    import numpy.typing as npt

    from loki.analysis.graphio import Graph

#: Up to this many nodes k-means is exact; above it ``MiniBatchKMeans`` is used (spec 7.1).
KMEANS_FULL_MAX = 20000
#: The clustering methods :func:`run_cluster` knows, in the order it runs them (plan Task 8).
METHODS: tuple[str, ...] = ("kmeans", "affinity", "spectral", "louvain")
#: The six numeric clustering features, ``log1p``-scaled (spec 7.1: spec 4 without floor/hard).
_LOG_FEATURES: tuple[str, ...] = (
    "fan_in", "fan_out", "level", "lut_width", "hard_ports", "lut_ones",
)
#: ``auto`` k is ``clip(round(sqrt(N / 2)), 2, 200)`` (spec 7).
_AUTO_MIN = 2
_AUTO_MAX = 200
_AP_CONVERGENCE_ITER = 15
_AP_DAMPING = 0.5
_AP_MAX_ITER = 200
_AP_RETRY_DAMPING = 0.95
_AP_RETRY_MAX_ITER = 400
_KMEANS_METHOD = "kmeans"
_AFFINITY_METHOD = "affinity"
_SPECTRAL_METHOD = "spectral"
_LOUVAIN_METHOD = "louvain"
_NOT_CONVERGED = "affinity propagation did not converge"
#: Largest-component size up to which the spectral embedding uses ``"arpack"`` (spec 7.3).
_SPECTRAL_ARPACK_MAX = 5000


class ClusterError(RuntimeError):
    """A clustering method could not produce a valid partition (spec 7.2 non-convergence)."""


def resolve_k(k: int | str, n: int) -> int:
    """The cluster count for ``n`` nodes (spec 7).

    ``"auto"`` is ``clip(round(sqrt(N / 2)), 2, 200)``; an integer must be at least 1. ``k`` is
    validated before the small-graph case, so an unknown string or an integer below 1 raises even
    when ``n < 2``. Both forms are then capped at ``n``, and fewer than two nodes give one cluster.
    """
    if isinstance(k, str):
        if k != "auto":
            raise ValueError(f"unknown k {k!r}: use an integer or 'auto'")
        if n < 2:
            return 1
        automatic = round(math.sqrt(n / 2.0))
        return min(max(automatic, _AUTO_MIN), _AUTO_MAX, n)
    if k < 1:
        raise ValueError(f"k must be >= 1, got {k}")
    if n < 2:
        return 1
    return min(k, n)


def cluster_space(g: Graph, extra: npt.NDArray[Any] | None = None) -> npt.NDArray[Any]:
    """The float64 feature space of a graph: standardised ``log1p`` numeric, kind, extra.

    The numeric block is :data:`_LOG_FEATURES` in spec order, ``log1p``-scaled and standardised
    with ``sklearn.preprocessing.StandardScaler``; a constant column therefore becomes zeros and
    stays in the matrix. The kind one-hot block uses :data:`loki.schemas.KINDS`; a kind outside
    that vocabulary leaves its row all zeros. ``extra`` holds one row per node of further float
    columns (graphlet signatures, spec 8.6) and is appended unchanged.
    """
    require("analysis")
    import numpy as np

    table = _extra_table(g.n_nodes, extra)
    width = len(_LOG_FEATURES) + len(KINDS) + (0 if table is None else int(table.shape[1]))
    if g.n_nodes == 0:
        return np.zeros((0, width), dtype=np.float64)
    scaler = importlib.import_module("sklearn.preprocessing").StandardScaler()
    numeric = np.column_stack([
        np.log1p(g.num[name].astype(np.float64)) for name in _LOG_FEATURES
    ])
    scaled = np.asarray(scaler.fit_transform(numeric), dtype=np.float64)
    kinds = np.zeros((g.n_nodes, len(KINDS)), dtype=np.float64)
    positions = {kind: column for column, kind in enumerate(KINDS)}
    for row, node_kind in enumerate(g.kind):
        column = positions.get(node_kind)
        if column is not None:
            kinds[row, column] = 1.0
    parts = [scaled, kinds]
    if table is not None:
        parts.append(table)
    return np.ascontiguousarray(np.concatenate(parts, axis=1), dtype=np.float64)


def cluster_kmeans(
    g: Graph, *, k: int | str = "auto", seed: int = 0, extra: npt.NDArray[Any] | None = None
) -> Partition:
    """k-means on the whole graph in :func:`cluster_space` (spec 7.1).

    ``KMeans`` runs when the graph has at most :data:`KMEANS_FULL_MAX` nodes and
    ``MiniBatchKMeans`` above it, both with ``n_init=3`` and ``random_state=seed``. The params
    record the resolved ``k``, the feature column names (``"features"``), the algorithm that ran
    (``"kmeans"``, ``"minibatch"``, or ``"none"`` when fewer than two clusters were asked for or
    possible) and whether sklearn raised a ``ConvergenceWarning`` (``"convergence_warning"``,
    always false for ``"none"``, which never calls sklearn).
    """
    require("analysis")
    import numpy as np

    clusters = resolve_k(k, g.n_nodes)
    space = cluster_space(g, extra)
    algorithm = _kmeans_algorithm(g.n_nodes, clusters)
    convergence_warning = False
    if algorithm == "none":
        assignment = np.zeros(g.n_nodes, dtype=np.int64)
    else:
        module = importlib.import_module("sklearn.cluster")
        if algorithm == "minibatch":
            model = module.MiniBatchKMeans(n_clusters=clusters, n_init=3, random_state=seed)
        else:
            model = module.KMeans(n_clusters=clusters, n_init=3, random_state=seed)
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            assignment = np.asarray(model.fit_predict(space), dtype=np.int64)
        exceptions = importlib.import_module("sklearn.exceptions")
        convergence_warning = any(
            issubclass(entry.category, exceptions.ConvergenceWarning) for entry in caught
        )
    extra_width = int(space.shape[1]) - len(_LOG_FEATURES) - len(KINDS)
    params: dict[str, object] = {
        "k": clusters,
        "features": _feature_names(extra_width),
        "algorithm": algorithm,
        "convergence_warning": convergence_warning,
    }
    return make_partition(g, _KMEANS_METHOD, params, seed, assignment)


def cluster_affinity(
    g: Graph,
    *,
    seed: int = 0,
    max_points: int = 3000,
    extra: npt.NDArray[Any] | None = None,
) -> Partition:
    """Affinity propagation on a seeded node sample, every other node assigned by distance.

    The sample is ``min(N, max_points)`` indices drawn with ``numpy.random.default_rng(seed)``
    and sorted; AP runs on those rows with ``damping=0.5, max_iter=200, convergence_iter=15``
    and ``preference=None`` (spec 7.2). The remaining nodes join the nearest exemplar
    (``cluster_centers_``) through :func:`assign_nearest`, while sampled nodes keep their own AP
    cluster. The record holds ``sampled={"points": size}``. Non-convergence (sklearn labels every
    sample ``-1``) retries once with ``damping=0.95, max_iter=400`` and sets ``retried`` in the
    params; failing that it raises :class:`ClusterError`.
    """
    require("analysis")
    import numpy as np

    if max_points < 1:
        raise ValueError(f"max_points must be >= 1, got {max_points}")
    space = cluster_space(g, extra)
    sample = _sample_rows(g.n_nodes, max_points, seed)
    params: dict[str, object] = {
        "damping": _AP_DAMPING,
        "max_iter": _AP_MAX_ITER,
        "convergence_iter": _AP_CONVERGENCE_ITER,
        "retried": False,
    }
    if sample.size < 2:
        assignment = np.zeros(g.n_nodes, dtype=np.int64)
    else:
        attempt = _affinity_attempt(space[sample], seed, _AP_DAMPING, _AP_MAX_ITER)
        if attempt is None:
            params["damping"] = _AP_RETRY_DAMPING
            params["max_iter"] = _AP_RETRY_MAX_ITER
            params["retried"] = True
            attempt = _affinity_attempt(space[sample], seed, _AP_RETRY_DAMPING, _AP_RETRY_MAX_ITER)
        if attempt is None:
            raise ClusterError(_NOT_CONVERGED)
        labels, centers = attempt
        assignment = assign_nearest(space, centers)
        assignment[sample] = labels
    return make_partition(
        g, _AFFINITY_METHOD, params, seed, assignment, sampled={"points": int(sample.size)}
    )


def cluster_spectral(
    g: Graph, *, k: int | str = "auto", seed: int = 0
) -> Partition:
    """Spectral clustering on the largest connected component (spec 7.3).

    The undirected projection is split into its connected components; the largest one (ties: the
    one whose lowest node comes first) is embedded with ``sklearn.manifold.spectral_embedding``
    using ``n_components=min(k, |L|-1)``, ``"arpack"`` up to :data:`_SPECTRAL_ARPACK_MAX` nodes
    and ``"lobpcg"`` above, then k-means (``n_init=3``) splits the unit-L2 rows into
    ``min(k, |L|)`` clusters. Zero embedding rows stay zero. Every other component becomes one
    cluster of its own; hundreds of tiny components (constants, unused logic) are normal. A
    largest component below three nodes, or fewer than two clusters asked for, makes every
    component one cluster without an embedding. The params record the resolved ``k`` and the
    ``n_components`` the embedding used (0 when it was skipped); the record also carries the
    connected component count (``components``).
    """
    require("analysis")
    import numpy as np

    csgraph = importlib.import_module("scipy.sparse.csgraph")
    clusters = resolve_k(k, g.n_nodes)
    adjacency = undirected_adjacency(g)
    count, raw = csgraph.connected_components(adjacency, directed=False)
    labels = np.asarray(raw, dtype=np.int64)
    assignment, n_components = _spectral_assignment(adjacency, labels, int(count), clusters, seed)
    params: dict[str, object] = {"k": clusters, "n_components": n_components}
    return make_partition(
        g, _SPECTRAL_METHOD, params, seed, assignment, components=int(count)
    )


def cluster_louvain(
    g: Graph, *, resolution: float = 1.0, seed: int = 0
) -> Partition:
    """Louvain communities on the undirected projection (spec 7.4).

    ``networkx.community.louvain_communities`` runs on the ``networkx.Graph`` built from the
    simple undirected projection with ``weight=None`` (every edge weight 1), the given
    ``resolution`` and ``seed``. The result sets are numbered canonically; the params record
    ``resolution``. There is no ``k``.
    """
    require("analysis")
    import numpy as np

    nx = importlib.import_module("networkx")
    graph = nx.from_scipy_sparse_array(undirected_adjacency(g))
    assignment = np.zeros(g.n_nodes, dtype=np.int64)
    if g.n_nodes:
        communities = nx.community.louvain_communities(
            graph, weight=None, resolution=resolution, seed=seed
        )
        for number, community in enumerate(sorted(communities, key=min)):
            assignment[sorted(community)] = number
    params: dict[str, object] = {"resolution": resolution}
    return make_partition(g, _LOUVAIN_METHOD, params, seed, canonical_numbers(assignment))


def run_cluster(
    g: Graph,
    methods: Sequence[str],
    out_dir: Path,
    *,
    k: int | str = "auto",
    seed: int = 0,
    resolution: float = 1.0,
    max_points: int = 3000,
    extra: npt.NDArray[Any] | None = None,
) -> list[Path]:
    """Run the requested clustering methods in :data:`METHODS` order and write each partition.

    ``methods`` names a subset of :data:`METHODS` in any order; an unknown name raises
    ``ValueError`` before anything runs or is written. Each partition is written to ``out_dir``
    by :func:`loki.analysis.partition.write_partition` (``<method>-<hash8>.json``) and the paths
    are returned in run order. ``k``, ``seed``, ``resolution`` and ``extra`` reach every method
    that takes them; ``max_points`` only affinity propagation (spec 7).
    """
    unknown = [method for method in methods if method not in METHODS]
    if unknown:
        choices = ", ".join(METHODS)
        raise ValueError(f"unknown clustering method {unknown[0]!r}: use one of {choices}")
    wanted = set(methods)
    paths: list[Path] = []
    for method in METHODS:
        if method not in wanted:
            continue
        if method == _KMEANS_METHOD:
            partition = cluster_kmeans(g, k=k, seed=seed, extra=extra)
        elif method == _AFFINITY_METHOD:
            partition = cluster_affinity(g, seed=seed, max_points=max_points, extra=extra)
        elif method == _SPECTRAL_METHOD:
            partition = cluster_spectral(g, k=k, seed=seed)
        else:
            partition = cluster_louvain(g, resolution=resolution, seed=seed)
        paths.append(write_partition(partition, out_dir))
    return paths


def assign_nearest(
    x: npt.NDArray[Any], centers: npt.NDArray[Any], chunk: int = 10000
) -> npt.NDArray[Any]:
    """Index of the nearest row of ``centers`` for every row of ``x`` (Euclidean distance).

    Rows are processed in blocks of ``chunk`` so memory stays at ``chunk x len(centers)`` and
    never at ``len(x) x len(centers)``; the result does not depend on the chunk size.
    """
    require("analysis")
    import numpy as np

    if chunk < 1:
        raise ValueError(f"chunk must be >= 1, got {chunk}")
    points = np.asarray(x, dtype=np.float64)
    table = np.asarray(centers, dtype=np.float64)
    if points.ndim != 2:
        raise ValueError(f"x must be a 2-D array, got shape {points.shape}")
    if table.ndim != 2 or table.shape[0] < 1:
        raise ValueError(f"centers must be a non-empty 2-D array, got shape {table.shape}")
    if points.shape[1] != table.shape[1]:
        raise ValueError(
            f"x has {points.shape[1]} columns, centers have {table.shape[1]}"
        )
    nearest = np.empty(points.shape[0], dtype=np.int64)
    squared_centers = np.sum(table * table, axis=1)[None, :]
    for start in range(0, points.shape[0], chunk):
        block = points[start:start + chunk]
        squared = (
            np.sum(block * block, axis=1)[:, None] - 2.0 * (block @ table.T) + squared_centers
        )
        nearest[start:start + chunk] = np.argmin(squared, axis=1)
    return nearest


def _kmeans_algorithm(n: int, clusters: int) -> str:
    """``"none"``, ``"kmeans"`` or ``"minibatch"`` for a graph of ``n`` nodes (spec 7.1)."""
    if clusters < 2 or n < 2:
        return "none"
    return "minibatch" if n > KMEANS_FULL_MAX else "kmeans"


def _spectral_assignment(
    adjacency: Any,
    labels: npt.NDArray[Any],
    count: int,
    clusters: int,
    seed: int,
) -> tuple[npt.NDArray[Any], int]:
    """Assignment of spec 7.3 and the ``n_components`` its embedding used (0 when skipped)."""
    import numpy as np

    n_nodes = int(labels.size)
    if count == 0:
        return np.zeros(0, dtype=np.int64), 0
    sizes = np.bincount(labels, minlength=count)
    first = np.full(count, n_nodes, dtype=np.int64)
    np.minimum.at(first, labels, np.arange(n_nodes, dtype=np.int64))
    largest = int(min(range(count), key=lambda component: (
        -int(sizes[component]), int(first[component])
    )))
    if sizes[largest] < 3 or clusters < 2:
        return labels.astype(np.int64, copy=True), 0
    rows = np.flatnonzero(labels == largest)
    size = int(rows.size)
    n_components = min(clusters, size - 1)
    solver = "arpack" if size <= _SPECTRAL_ARPACK_MAX else "lobpcg"
    manifold = importlib.import_module("sklearn.manifold")
    embedding = np.asarray(
        manifold.spectral_embedding(
            adjacency[rows][:, rows],
            n_components=n_components,
            eigen_solver=solver,
            random_state=seed,
            drop_first=False,
        ),
        dtype=np.float64,
    )
    norms = np.linalg.norm(embedding, axis=1)
    nonzero = norms > 0.0
    embedding[nonzero] = embedding[nonzero] / norms[nonzero][:, None]
    local = _embedding_kmeans(embedding, min(clusters, size), seed)
    assignment = np.zeros(n_nodes, dtype=np.int64)
    assignment[rows] = local
    others = sorted(
        (component for component in range(count) if component != largest),
        key=lambda component: int(first[component]),
    )
    for offset, component in enumerate(others):
        assignment[labels == component] = min(clusters, size) + offset
    return assignment, n_components


def _embedding_kmeans(
    embedding: npt.NDArray[Any], clusters: int, seed: int
) -> npt.NDArray[Any]:
    """k-means over spectral embedding rows (``n_init=3``; minibatch above the node cap)."""
    import numpy as np

    module = importlib.import_module("sklearn.cluster")
    if clusters <= KMEANS_FULL_MAX:
        model = module.KMeans(n_clusters=clusters, n_init=3, random_state=seed)
    else:
        model = module.MiniBatchKMeans(n_clusters=clusters, n_init=3, random_state=seed)
    return np.asarray(model.fit_predict(embedding), dtype=np.int64)


def _feature_names(extra_width: int) -> list[str]:
    """One name per :func:`cluster_space` column, in column order (the ``features`` param, 7.1)."""
    names = list(_LOG_FEATURES) + [f"kind:{kind}" for kind in KINDS]
    names.extend(f"extra:{column}" for column in range(extra_width))
    return names


def _extra_table(n: int, extra: npt.NDArray[Any] | None) -> npt.NDArray[Any] | None:
    """``extra`` as a float64 ``(n, width)`` matrix, or ``None`` when absent."""
    import numpy as np

    if extra is None:
        return None
    table = np.asarray(extra, dtype=np.float64)
    if table.ndim != 2 or table.shape[0] != n:
        raise ValueError(f"extra must have {n} rows, got shape {table.shape}")
    return table


def _sample_rows(n: int, max_points: int, seed: int) -> npt.NDArray[Any]:
    """Sorted sample indices: ``min(n, max_points)`` draws without replacement, seeded (7.2)."""
    import numpy as np

    size = min(n, max_points)
    if size >= n:
        return np.arange(n, dtype=np.int64)
    rng = np.random.default_rng(seed)
    return np.sort(rng.choice(n, size=size, replace=False)).astype(np.int64)


def _affinity_attempt(
    space: npt.NDArray[Any], seed: int, damping: float, max_iter: int
) -> tuple[npt.NDArray[Any], npt.NDArray[Any]] | None:
    """One AP run: (labels, centers), or ``None`` when sklearn labelled every sample ``-1``.

    sklearn signals non-convergence by warning and, when it finds no exemplar, by labelling
    every sample ``-1``; the labels are the signal (spec 7.2) and the warnings are recorded so
    they do not reach the caller. Labels that are usable despite a ``ConvergenceWarning`` (the
    library's degenerate-centres case) are returned as they are.
    """
    import numpy as np

    module = importlib.import_module("sklearn.cluster")
    with warnings.catch_warnings(record=True) as _caught:
        warnings.simplefilter("always")
        model = module.AffinityPropagation(
            damping=damping,
            max_iter=max_iter,
            convergence_iter=_AP_CONVERGENCE_ITER,
            preference=None,
            random_state=seed,
        )
        model.fit(space)
    labels = np.asarray(model.labels_, dtype=np.int64)
    if labels.size and bool(np.all(labels == -1)):
        return None
    return labels, np.asarray(model.cluster_centers_, dtype=np.float64)
