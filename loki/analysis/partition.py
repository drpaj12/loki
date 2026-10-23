"""Partition records: storage, quality and evidence loading (L2 spec section 6).

A :class:`Partition` is one cluster number per ``graph.json`` node plus the identity that names it:
method, params, seed and the graph hash. :func:`write_partition` and :func:`load_partition` keep
the record as deterministic JSON (schema 1, sorted keys, floats rounded to 6 decimals);
:func:`compute_quality` is the report Peter reads and tests assert on, never an input to a method.
numpy, scipy, scikit-learn and networkx belong to the ``analysis`` extra and are imported inside
the functions after :func:`loki.analysis.require`, so importing this module needs the standard
library only.
"""

from __future__ import annotations

import hashlib
import json
import statistics
from dataclasses import dataclass
from functools import cached_property
from importlib import metadata
from pathlib import Path
from typing import TYPE_CHECKING, Any

from loki.analysis import require
from loki.analysis.graphio import canonical_numbers, undirected_adjacency
from loki.schemas import dump_json

if TYPE_CHECKING:
    import numpy.typing as npt

    from loki.analysis.graphio import Graph

_SCHEMA = 1
_KIND = "partition"
#: Kinds the ground-truth scores compare over: the answer key's cell kinds (spec 6).
_QUALITY_KINDS = frozenset({"lut", "ff", "hard", "gate"})
_VERSION_LIBRARIES = ("numpy", "networkx", "scikit-learn")
_REQUIRED_KEYS = (
    "schema", "kind", "design", "floor", "method", "params", "seed", "graph_sha256", "n_nodes",
    "n_clusters", "node_ids", "assignment", "quality", "versions", "sampled",
)
_OPTIONAL_KEYS = ("components",)


@dataclass(frozen=True)
class Partition:
    """One clustering of a graph: a cluster number per node plus the evidence identity (spec 6)."""

    design: str
    floor: str
    method: str
    params: dict[str, object]
    seed: int
    graph_sha256: str
    node_ids: tuple[str, ...]
    assignment: tuple[int, ...]
    quality: dict[str, object]
    versions: dict[str, str]
    sampled: dict[str, int] | None = None
    components: int | None = None

    @property
    def n_clusters(self) -> int:
        """Number of clusters: ``max(assignment) + 1``, because numbers are canonical 0..K-1."""
        return len(self.sizes())

    def members(self, cluster: int) -> tuple[str, ...]:
        """The node ids of ``cluster``, in ``node_ids`` (graph) order; empty when absent."""
        return tuple(
            node_id
            for node_id, number in zip(self.node_ids, self.assignment, strict=True)
            if number == cluster
        )

    @cached_property
    def _rows(self) -> dict[str, int]:
        """``node_ids`` row map, built once: L1 calls :meth:`cluster_of` for every node."""
        rows: dict[str, int] = {}
        for row, node_id in enumerate(self.node_ids):
            rows.setdefault(node_id, row)
        return rows

    def cluster_of(self, node_id: str) -> int:
        """The cluster number of ``node_id``; ``ValueError`` when the node is not in the record."""
        try:
            row = self._rows[node_id]
        except KeyError:
            raise ValueError(f"node {node_id!r} is not in partition {self.key}") from None
        return self.assignment[row]

    def sizes(self) -> list[int]:
        """Cluster sizes in cluster order (length :attr:`n_clusters`)."""
        return _cluster_sizes(self.assignment)

    @property
    def key(self) -> str:
        """``<method>:<hash8>``, the evidence identity of spec 6 (hashed over the stored params)."""
        hash8 = partition_hash(
            self.method, _rounded_dict(self.params), self.seed, self.graph_sha256
        )
        return f"{self.method}:{hash8}"


def partition_hash(method: str, params: dict[str, object], seed: int, graph_sha256: str) -> str:
    """First 8 hex of the sha256 of the canonical JSON of method/params/seed/graph hash (spec 6).

    Canonical JSON here is compact with sorted keys:
    ``json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)``.
    It is deliberately not :func:`loki.schemas.dump_json` (indent 1 plus a trailing newline):
    the hash covers exactly these bytes, so a second implementation can reproduce a key. Pass
    JSON-ready params in their stored form (:func:`write_partition` and :attr:`Partition.key`
    hash ``_rounded_dict`` output; numpy scalars do not serialise).
    """
    payload = {"method": method, "params": params, "seed": seed, "graph_sha256": graph_sha256}
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:8]


def version_info() -> dict[str, str]:
    """Installed versions of the analysis libraries, recorded in every partition (spec 3)."""
    require("analysis")
    return {name: metadata.version(name) for name in _VERSION_LIBRARIES}


def compute_quality(g: Graph, assignment: npt.NDArray[Any]) -> dict[str, object]:
    """Quality report of one assignment (spec 6): modularity, sizes, NMI/ARI against the labels.

    ``modularity`` is computed on the undirected simple projection with
    ``networkx.community.modularity``; a projection with no edges gets ``0.0`` without the call
    (networkx raises there). Numbers must be contiguous ``0..K-1``, as :func:`make_partition`
    canonicalises them: negative numbers and gaps raise ``ValueError``. ``nmi_module_path``,
    ``ari_module_path`` and ``nmi_construct_type`` compare the partition with the ground truth
    over nodes of kind lut, ff, hard and gate; each is ``None`` when the graph carries no labels,
    when its column is absent, when those kinds hold fewer than two labelled nodes, or when the
    partition has fewer than two nodes.
    """
    require("analysis")
    import numpy as np

    values = np.asarray(assignment)
    if values.ndim != 1 or values.size != g.n_nodes:
        raise ValueError(
            f"quality needs one number per node: got shape {values.shape} "
            f"for {g.n_nodes} nodes"
        )
    labels = tuple(int(number) for number in values.tolist())
    if any(number < 0 for number in labels):
        raise ValueError("assignment numbers must be >= 0")
    if labels and max(labels) + 1 != len(set(labels)):
        raise ValueError("assignment numbers must be 0..K-1 without gaps")
    sizes = _cluster_sizes(labels)
    quality: dict[str, object] = {
        "modularity": _modularity(g, labels, sizes),
        "size_min": min(sizes, default=0),
        "size_median": float(statistics.median(sizes)) if sizes else 0.0,
        "size_max": max(sizes, default=0),
    }
    quality.update(_truth_scores(g, labels))
    return quality


def make_partition(
    g: Graph,
    method: str,
    params: dict[str, object],
    seed: int,
    assignment: npt.NDArray[Any],
    sampled: dict[str, int] | None = None,
    components: int | None = None,
) -> Partition:
    """Build a :class:`Partition` from a raw assignment (spec 6).

    The numbers are canonicalised 0..K-1 in order of their first node, quality and versions are
    filled in, and floats of ``params``/``quality`` are rounded to 6 decimals, so the in-memory
    record equals the one :func:`load_partition` reads back from disk. ``sampled`` records a
    method that worked on a node sample (affinity propagation); ``components`` the connected
    component count spectral clustering measured.
    """
    require("analysis")
    import numpy as np

    values = np.asarray(assignment)
    if values.ndim != 1 or values.size != g.n_nodes:
        raise ValueError(
            f"assignment needs one number per node: got shape {values.shape} "
            f"for {g.n_nodes} nodes"
        )
    canonical = canonical_numbers(values)
    labels = tuple(int(number) for number in canonical.tolist())
    return Partition(
        design=g.design,
        floor=g.floor,
        method=method,
        params=_rounded_dict(_canonical_params(params)),
        seed=seed,
        graph_sha256=g.sha256,
        node_ids=g.node_ids,
        assignment=labels,
        quality=_rounded_dict(compute_quality(g, canonical)),
        versions=version_info(),
        sampled=None if sampled is None else {str(name): int(count)
                                              for name, count in sampled.items()},
        components=components,
    )


def write_partition(p: Partition, out_dir: Path) -> Path:
    """Write ``<out_dir>/<method>-<hash8>.json`` (schema 1, deterministic); return the path."""
    out_dir.mkdir(parents=True, exist_ok=True)
    params = _rounded_dict(p.params)
    hash8 = partition_hash(p.method, params, p.seed, p.graph_sha256)
    path = out_dir / f"{p.method}-{hash8}.json"
    obj: dict[str, object] = {
        "schema": _SCHEMA,
        "kind": _KIND,
        "design": p.design,
        "floor": p.floor,
        "method": p.method,
        "params": params,
        "seed": p.seed,
        "graph_sha256": p.graph_sha256,
        "n_nodes": len(p.node_ids),
        "n_clusters": p.n_clusters,
        "node_ids": list(p.node_ids),
        "assignment": list(p.assignment),
        "quality": _rounded_dict(p.quality),
        "sampled": None if p.sampled is None else dict(p.sampled),
        "components": p.components,
        "versions": dict(p.versions),
    }
    path.write_text(dump_json(obj), encoding="utf-8")
    return path


def load_partition(path: Path) -> Partition:
    """Read a partition record and validate it (spec 6); ``ValueError`` on any inconsistency.

    Checked: the exact schema-1 key set, ``kind``, ``schema``, the types of every field, that
    ``node_ids`` and ``assignment`` both hold ``n_nodes`` entries, that ``node_ids`` are unique
    (no id repeats, so ``cluster_of`` is unambiguous), that the numbers are 0..K-1 without gaps,
    and that ``n_clusters`` matches them. ``components`` is optional (``None`` when absent) so a
    hand-written record of the spec-6 example still loads.
    """
    data = _record(json.loads(path.read_text(encoding="utf-8")), path)
    node_ids = _texts(data, "node_ids", path)
    n_nodes = _integer(data, "n_nodes", path)
    assignment = _integers(data, "assignment", path)
    if len(node_ids) != n_nodes:
        raise ValueError(f"{path}: node_ids holds {len(node_ids)} ids, n_nodes is {n_nodes}")
    if len(set(node_ids)) != len(node_ids):
        raise ValueError(f"{path}: node_ids holds duplicate ids")
    if len(assignment) != n_nodes:
        raise ValueError(
            f"{path}: assignment holds {len(assignment)} numbers, n_nodes is {n_nodes}"
        )
    _check_numbers(assignment, path)
    clusters = 0 if not assignment else max(assignment) + 1
    declared = _integer(data, "n_clusters", path)
    if clusters != declared:
        raise ValueError(
            f"{path}: n_clusters {declared} does not match the assignment ({clusters})"
        )
    return Partition(
        design=_text(data, "design", path),
        floor=_text(data, "floor", path),
        method=_text(data, "method", path),
        params=_mapping(data, "params", path),
        seed=_integer(data, "seed", path),
        graph_sha256=_text(data, "graph_sha256", path),
        node_ids=node_ids,
        assignment=assignment,
        quality=_mapping(data, "quality", path),
        versions=_versions(data, path),
        sampled=_samples(data, path),
        components=_optional_int(data, "components", path),
    )


def _cluster_sizes(labels: tuple[int, ...]) -> list[int]:
    """Cluster sizes in cluster order; empty for an empty assignment."""
    if not labels:
        return []
    sizes = [0] * (max(labels) + 1)
    for number in labels:
        sizes[number] += 1
    return sizes


def _modularity(g: Graph, labels: tuple[int, ...], sizes: list[int]) -> float:
    """Modularity of the assignment on the undirected simple projection (spec 6)."""
    import importlib

    adjacency = undirected_adjacency(g)
    if int(adjacency.nnz) == 0:
        return 0.0
    nx = importlib.import_module("networkx")
    communities: list[list[int]] = [[] for _ in sizes]
    for row, number in enumerate(labels):
        communities[number].append(row)
    return float(
        nx.community.modularity(
            nx.from_scipy_sparse_array(adjacency), [group for group in communities if group]
        )
    )


def _truth_scores(g: Graph, labels: tuple[int, ...]) -> dict[str, object]:
    """NMI/ARI against ``module_path`` and ``construct_type``; ``None`` where truth is absent."""
    scores: dict[str, object] = {
        "nmi_module_path": None,
        "ari_module_path": None,
        "nmi_construct_type": None,
    }
    modules = _truth_pairs(g, labels, "module_path")
    constructs = _truth_pairs(g, labels, "construct_type")
    if modules is None and constructs is None:
        return scores
    import importlib

    metrics = importlib.import_module("sklearn.metrics")
    if modules is not None:
        scores["nmi_module_path"] = float(metrics.normalized_mutual_info_score(*modules))
        scores["ari_module_path"] = float(metrics.adjusted_rand_score(*modules))
    if constructs is not None:
        scores["nmi_construct_type"] = float(metrics.normalized_mutual_info_score(*constructs))
    return scores


def _truth_pairs(
    g: Graph, labels: tuple[int, ...], column: str
) -> tuple[list[str], list[int]] | None:
    """(truth, assignment) over labelled lut/ff/hard/gate nodes, or ``None`` below two nodes."""
    if g.labels is None:
        return None
    values = g.labels.get(column)
    if values is None:
        return None
    truth: list[str] = []
    predicted: list[int] = []
    for row, kind in enumerate(g.kind):
        if kind not in _QUALITY_KINDS:
            continue
        text = str(values[row])
        if not text:
            continue
        truth.append(text)
        predicted.append(labels[row])
    if len(truth) < 2:
        return None
    return truth, predicted


def _canonical_params(params: dict[str, object]) -> dict[str, object]:
    """Params as plain JSON values: numpy scalars to Python numbers, tuples to lists."""
    import numpy as np

    def plain(value: object) -> object:
        if isinstance(value, np.integer):
            return int(value)
        if isinstance(value, np.floating):
            return float(value)
        if isinstance(value, np.bool_):
            return bool(value)
        if isinstance(value, dict):
            return {str(name): plain(item) for name, item in value.items()}
        if isinstance(value, (list, tuple)):
            return [plain(item) for item in value]
        return value

    return {str(name): plain(value) for name, value in params.items()}


def _round_floats(value: object) -> object:
    """Floats rounded to 6 decimals, recursively (spec 3)."""
    if isinstance(value, float):
        return round(value, 6)
    if isinstance(value, dict):
        return {str(name): _round_floats(item) for name, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_round_floats(item) for item in value]
    return value


def _rounded_dict(values: dict[str, object]) -> dict[str, object]:
    """A copy of ``values`` whose floats are rounded recursively to 6 decimals (spec 3)."""
    return {str(name): _round_floats(item) for name, item in values.items()}


def _record(obj: object, path: Path) -> dict[str, object]:
    """The partition object with its key set, ``schema`` and ``kind`` checked (spec 6)."""
    if not isinstance(obj, dict):
        raise ValueError(f"{path}: not a partition object")
    data: dict[str, object] = {str(key): value for key, value in obj.items()}
    missing = [key for key in _REQUIRED_KEYS if key not in data]
    if missing:
        raise ValueError(f"{path}: missing partition key(s): {', '.join(missing)}")
    unknown = sorted(key for key in data if key not in _REQUIRED_KEYS + _OPTIONAL_KEYS)
    if unknown:
        raise ValueError(f"{path}: unknown partition key(s): {', '.join(unknown)}")
    schema = data["schema"]
    if not isinstance(schema, int) or isinstance(schema, bool) or schema != _SCHEMA:
        raise ValueError(f"{path}: unsupported partition schema {schema!r}")
    if data["kind"] != _KIND:
        raise ValueError(f"{path}: kind is {data['kind']!r}, not {_KIND!r}")
    return data


def _check_numbers(assignment: tuple[int, ...], path: Path) -> None:
    """Every number of ``0..K-1`` used at least once, so the cluster list has no gaps (spec 6)."""
    if not assignment:
        return
    if min(assignment) < 0:
        raise ValueError(f"{path}: assignment numbers must be >= 0")
    if max(assignment) + 1 != len(set(assignment)):
        raise ValueError(f"{path}: assignment numbers must be 0..K-1 without gaps")


def _text(data: dict[str, object], key: str, path: Path) -> str:
    value = data[key]
    if not isinstance(value, str):
        raise ValueError(f"{path}: key {key!r} must be a string")
    return value


def _integer(data: dict[str, object], key: str, path: Path) -> int:
    value = data[key]
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"{path}: key {key!r} must be an integer")
    return value


def _texts(data: dict[str, object], key: str, path: Path) -> tuple[str, ...]:
    value = data[key]
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValueError(f"{path}: key {key!r} must be a list of strings")
    return tuple(str(item) for item in value)


def _integers(data: dict[str, object], key: str, path: Path) -> tuple[int, ...]:
    value = data[key]
    if not isinstance(value, list) or not all(
        isinstance(item, int) and not isinstance(item, bool) for item in value
    ):
        raise ValueError(f"{path}: key {key!r} must be a list of integers")
    return tuple(int(item) for item in value)


def _mapping(data: dict[str, object], key: str, path: Path) -> dict[str, object]:
    value = data[key]
    if not isinstance(value, dict):
        raise ValueError(f"{path}: key {key!r} must be an object")
    return {str(name): item for name, item in value.items()}


def _versions(data: dict[str, object], path: Path) -> dict[str, str]:
    values = _mapping(data, "versions", path)
    if not all(isinstance(item, str) for item in values.values()):
        raise ValueError(f"{path}: versions values must be strings")
    return {name: str(item) for name, item in values.items()}


def _samples(data: dict[str, object], path: Path) -> dict[str, int] | None:
    value = data["sampled"]
    if value is None:
        return None
    if not isinstance(value, dict):
        raise ValueError(f"{path}: key 'sampled' must be null or an object")
    samples: dict[str, int] = {}
    for name, item in value.items():
        if not isinstance(item, int) or isinstance(item, bool):
            raise ValueError(f"{path}: sampled values must be integers")
        samples[str(name)] = item
    return samples


def _optional_int(data: dict[str, object], key: str, path: Path) -> int | None:
    value = data.get(key)
    if value is None:
        return None
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"{path}: key {key!r} must be null or an integer")
    return value
