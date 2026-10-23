"""Clustering methods: k-means and affinity propagation (L2 spec sections 7.1 and 7.2).

Both work in one float64 space (:func:`cluster_space`): the six numeric features of spec 4
without the floor and hard-type blocks, ``log1p``-scaled and standardised with
``StandardScaler``, then the kind one-hot columns, then optional extra columns such as the
graphlet signatures. Constant columns standardise to zeros and are kept, never dropped.

k-means sees the whole netlist: ``KMeans`` up to :data:`KMEANS_FULL_MAX` nodes,
``MiniBatchKMeans`` above. Affinity propagation would build a dense N x N similarity matrix, so
it runs on a seeded sample of at most ``max_points`` nodes and assigns every other node to the
nearest exemplar in chunks of at most 10000 rows. Partitions are built by
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
from loki.analysis.partition import Partition, make_partition
from loki.schemas import KINDS

if TYPE_CHECKING:
    import numpy.typing as npt

    from loki.analysis.graphio import Graph

#: Up to this many nodes k-means is exact; above it ``MiniBatchKMeans`` is used (spec 7.1).
KMEANS_FULL_MAX = 20000
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
_NOT_CONVERGED = "affinity propagation did not converge"


class ClusterError(RuntimeError):
    """A clustering method could not produce a valid partition (spec 7.2 non-convergence)."""


def resolve_k(k: int | str, n: int) -> int:
    """The cluster count for ``n`` nodes (spec 7).

    ``"auto"`` is ``clip(round(sqrt(N / 2)), 2, 200)``; an integer must be at least 1. Both
    are then capped at ``n``, and fewer than two nodes always give one cluster.
    """
    if n < 2:
        return 1
    if isinstance(k, str):
        if k != "auto":
            raise ValueError(f"unknown k {k!r}: use an integer or 'auto'")
        automatic = round(math.sqrt(n / 2.0))
        return min(max(automatic, _AUTO_MIN), _AUTO_MAX, n)
    if k < 1:
        raise ValueError(f"k must be >= 1, got {k}")
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
    record the resolved ``k``, the feature width and which algorithm ran (``"kmeans"``,
    ``"minibatch"``, or ``"none"`` when fewer than two clusters were asked for or possible).
    """
    require("analysis")
    import numpy as np

    clusters = resolve_k(k, g.n_nodes)
    space = cluster_space(g, extra)
    algorithm = _kmeans_algorithm(g.n_nodes, clusters)
    if algorithm == "none":
        assignment = np.zeros(g.n_nodes, dtype=np.int64)
    else:
        module = importlib.import_module("sklearn.cluster")
        if algorithm == "minibatch":
            model = module.MiniBatchKMeans(n_clusters=clusters, n_init=3, random_state=seed)
        else:
            model = module.KMeans(n_clusters=clusters, n_init=3, random_state=seed)
        assignment = np.asarray(model.fit_predict(space), dtype=np.int64)
    params: dict[str, object] = {
        "k": clusters, "features": int(space.shape[1]), "algorithm": algorithm,
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
