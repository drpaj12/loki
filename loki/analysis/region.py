"""Regions: node sets from cones, partitions and node lists (L2 spec section 4).

A region names a set of node ids of one ``graph.json``. Every constructor keeps the ids in graph
order, so an induced subgraph and its export are deterministic. Walk directions are transitive
fan-in (``in``), fan-out (``out``) and their union (``both``); a flip-flop does not stop a walk.
numpy and scipy belong to the ``analysis`` extra and are imported inside the functions after
:func:`loki.analysis.require`.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from loki.analysis import require

if TYPE_CHECKING:
    from collections.abc import Sequence
    from typing import Protocol

    import numpy.typing as npt

    from loki.analysis.graphio import Graph

    class PartitionLike(Protocol):
        """What :func:`from_partition` needs of ``loki.analysis.partition.Partition`` (Task 6)."""

        @property
        def key(self) -> str: ...

        def members(self, cluster: int) -> tuple[str, ...]: ...

#: Walk directions of :func:`cone`: transitive fan-in, transitive fan-out, or both.
DIRECTIONS = ("in", "out", "both")

_SPEC_HELP = "cone:<id>[,<id>...]:<in|out|both>:<depth|all>, cluster:<partition.json>:<int> or " \
    "nodes:<file with one id per line>"


class RegionError(ValueError):
    """A region spec or node id is invalid, or the resulting region is empty."""


@dataclass(frozen=True)
class Region:
    """A set of node ids of one graph (L2 spec 4), in graph order, and the spec that made it.

    ``spec`` is a canonical spelling, not the CLI spelling of :func:`parse_region`:
    ``cone:<ids in graph order>:<direction>:<depth|all>``, ``nodes:<id>[,<id>...]`` or the
    partition's ``cluster:<key>:<cluster>``. It is not re-parsable by design (``parse_region``
    reads ``nodes:...`` as a file name) and its :func:`region_hash` can differ from the hash of
    the CLI input that produced it.
    """

    spec: str
    node_ids: tuple[str, ...]


def cone(g: Graph, roots: Sequence[str], direction: str, depth: int | None) -> Region:
    """The cone on ``roots``: transitively their fan-in, fan-out or both (spec 4).

    ``depth`` counts edges, the roots are depth 0, and ``None`` walks without a limit. A
    flip-flop does not stop the walk. Unknown roots and an empty result raise
    :class:`RegionError`.
    """
    require("analysis")
    import numpy as np

    if direction not in DIRECTIONS:
        raise RegionError(
            f"unknown direction {direction!r}: use one of {', '.join(DIRECTIONS)}"
        )
    if depth is not None and depth < 0:
        raise RegionError(f"depth must be >= 0 or None, got {depth}")
    index = g.index()
    unknown = sorted({root for root in roots if root not in index})
    if unknown:
        raise RegionError("unknown node id(s): " + ", ".join(unknown))
    wanted = set(roots)
    ordered = tuple(node for node in g.node_ids if node in wanted)
    label = "all" if depth is None else str(depth)
    spec = f"cone:{','.join(ordered)}:{direction}:{label}"
    if not ordered:
        raise RegionError(f"empty region: {spec}")
    starts = np.asarray([index[root] for root in ordered], dtype=np.int64)
    adjacency = _walk_adjacency(g, direction)
    reached = _walk(adjacency, starts, depth)
    node_ids = tuple(g.node_ids[int(row)] for row in reached)
    return Region(spec=spec, node_ids=node_ids)


def from_partition(p: PartitionLike, cluster: int) -> Region:
    """The members of one cluster of a partition (spec 4).

    An empty cluster raises :class:`RegionError`. The ids keep the partition's ``node_ids``
    order, which is the graph order of the netlist the partition was made from.
    """
    members = tuple(p.members(cluster))
    spec = f"cluster:{p.key}:{cluster}"
    if not members:
        raise RegionError(f"empty region: {spec}")
    return Region(spec=spec, node_ids=members)


def from_nodes(g: Graph, ids: Sequence[str]) -> Region:
    """The region of an explicit node id set, e.g. an L1 hypothesis (spec 4).

    Duplicates are dropped, the ids are returned in graph order, and unknown ids or an empty set
    raise :class:`RegionError`.
    """
    index = g.index()
    unknown = sorted({node_id for node_id in ids if node_id not in index})
    if unknown:
        raise RegionError("unknown node id(s): " + ", ".join(unknown))
    wanted = set(ids)
    selected = tuple(node_id for node_id in g.node_ids if node_id in wanted)
    spec = "nodes:" + ",".join(selected)
    if not selected:
        raise RegionError(f"empty region: {spec}")
    return Region(spec=spec, node_ids=selected)


def parse_region(g: Graph, spec: str) -> Region:
    """Parse the CLI spelling of ``--region`` (spec 4) into a :class:`Region`."""
    kind, separator, body = spec.partition(":")
    if not separator:
        raise RegionError(f"region spec needs a kind prefix: use {_SPEC_HELP}")
    if kind == "cone":
        return _parse_cone(g, body)
    if kind == "cluster":
        return _parse_cluster(body)
    if kind == "nodes":
        path = Path(body)
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as exc:
            raise RegionError(f"cannot read nodes file {body!r}: {exc}") from exc
        return from_nodes(g, [line.strip() for line in text.splitlines() if line.strip()])
    raise RegionError(f"unknown region kind {kind!r}: use {_SPEC_HELP}")


def region_hash(spec: str) -> str:
    """The first 8 hex characters of the SHA-256 of a region spec (cache key)."""
    return hashlib.sha256(spec.encode("utf-8")).hexdigest()[:8]


def _parse_cone(g: Graph, body: str) -> Region:
    parts = body.split(":")
    if len(parts) != 3:
        raise RegionError(
            f"cone spec is cone:<id>[,<id>...]:<in|out|both>:<depth|all>; got {body!r}"
        )
    roots_text, direction, depth_text = parts
    roots = [root for root in roots_text.split(",") if root]
    if not roots:
        raise RegionError("cone spec needs at least one root id")
    if direction not in DIRECTIONS:
        raise RegionError(f"unknown direction {direction!r}: use one of {', '.join(DIRECTIONS)}")
    if depth_text == "all":
        return cone(g, roots, direction, None)
    try:
        depth = int(depth_text)
    except ValueError as exc:
        raise RegionError(f"depth is 'all' or an integer >= 0, got {depth_text!r}") from exc
    return cone(g, roots, direction, depth)


def _parse_cluster(body: str) -> Region:
    path_text, separator, cluster_text = body.rpartition(":")
    if not separator or not path_text:
        raise RegionError("cluster spec is cluster:<partition.json>:<int>")
    try:
        cluster = int(cluster_text)
    except ValueError as exc:
        raise RegionError(f"cluster index must be an integer, got {cluster_text!r}") from exc
    import importlib

    partition_module = importlib.import_module("loki.analysis.partition")
    return from_partition(partition_module.load_partition(Path(path_text)), cluster)


def _walk_adjacency(g: Graph, direction: str) -> Any:
    """The CSR matrix the walk follows: successors, predecessors, or both."""
    require("analysis")
    import importlib

    import numpy as np

    sp = importlib.import_module("scipy.sparse")
    shape = (g.n_nodes, g.n_nodes)
    if g.n_edges == 0:
        empty = sp.csr_matrix(shape, dtype=np.int32)
        return empty
    data = np.ones(g.n_edges, dtype=np.int32)
    out = sp.csr_matrix((data, (g.src, g.dst)), shape=shape, dtype=np.int32)
    if direction == "out":
        return out
    fan_in = out.transpose().tocsr()
    if direction == "in":
        return fan_in
    return out.maximum(fan_in)


def _walk(adjacency: Any, starts: npt.NDArray[Any], depth: int | None) -> npt.NDArray[Any]:
    """Breadth-first rows from ``starts`` up to ``depth`` edges (``None`` = unbounded)."""
    import numpy as np

    seen = np.zeros(adjacency.shape[0], dtype=bool)
    frontier = np.unique(starts)
    seen[frontier] = True
    levels = 0
    while frontier.size and (depth is None or levels < depth):
        chunks = [
            adjacency.indices[adjacency.indptr[node]:adjacency.indptr[node + 1]]
            for node in frontier
        ]
        neighbours = np.unique(np.concatenate(chunks))
        frontier = neighbours[~seen[neighbours]]
        seen[frontier] = True
        levels += 1
    return np.flatnonzero(seen)
