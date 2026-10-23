"""The feature graph: one node per cell plus PI/PO pseudo-nodes, edges driver to sink pin."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

_Adj = tuple[tuple[tuple[int, ...], ...], tuple[tuple[int, ...], ...]]


@dataclass(frozen=True)
class FeatureGraph:
    """Nodes in index order; edges sorted by ``(dst, pin, src)``; ``table`` is -1 when none."""

    node_ids: tuple[str, ...]
    kind: tuple[str, ...]
    type: tuple[str, ...]
    width: tuple[int, ...]
    table: tuple[int, ...]
    src: tuple[int, ...]
    dst: tuple[int, ...]
    pin: tuple[str, ...]
    net: tuple[int, ...]
    _adj: _Adj | None = field(default=None, init=False, repr=False, compare=False)

    @property
    def n_nodes(self) -> int:
        return len(self.node_ids)

    @property
    def n_edges(self) -> int:
        return len(self.src)

    def adjacency(self) -> _Adj:
        """In-edge and out-edge indices per node (cached on the instance)."""
        if self._adj is not None:
            return self._adj
        ins: list[list[int]] = [[] for _ in range(self.n_nodes)]
        outs: list[list[int]] = [[] for _ in range(self.n_nodes)]
        for e in range(self.n_edges):
            ins[self.dst[e]].append(e)
            outs[self.src[e]].append(e)
        adj: _Adj = (tuple(tuple(x) for x in ins), tuple(tuple(x) for x in outs))
        object.__setattr__(self, "_adj", adj)
        return adj


def make_feature_graph(
    nodes: Sequence[tuple[str, str, str, int, int]],
    edges: Sequence[tuple[int, int, str, int]],
) -> FeatureGraph:
    """Build a graph from ``(id, kind, type, width, table)`` nodes and ``(src, dst, pin, net)``
    edges; the edges are sorted by ``(dst, pin, src, net)``."""
    ordered = sorted(edges, key=lambda e: (e[1], e[2], e[0], e[3]))
    return FeatureGraph(
        tuple(n[0] for n in nodes), tuple(n[1] for n in nodes), tuple(n[2] for n in nodes),
        tuple(n[3] for n in nodes), tuple(n[4] for n in nodes),
        tuple(e[0] for e in ordered), tuple(e[1] for e in ordered),
        tuple(e[2] for e in ordered), tuple(e[3] for e in ordered),
    )


def validate_feature_graph(fg: FeatureGraph) -> list[str]:
    """Structural errors of ``fg`` (empty when well formed)."""
    errors: list[str] = []
    n = fg.n_nodes
    if not (len(fg.kind) == len(fg.type) == len(fg.width) == len(fg.table) == n):
        errors.append("node arrays differ in length")
    if not (len(fg.src) == len(fg.dst) == len(fg.pin) == len(fg.net)):
        errors.append("edge arrays differ in length")
        return errors
    if len(set(fg.node_ids)) != n:
        errors.append("duplicate node ids")
    prev: tuple[int, str, int] | None = None
    for e in range(fg.n_edges):
        s, d = fg.src[e], fg.dst[e]
        if not 0 <= s < n:
            errors.append(f"edge {e}: src {s} is not a node")
        if not 0 <= d < n:
            errors.append(f"edge {e}: dst {d} is not a node")
        key = (d, fg.pin[e], s)
        if prev is not None and key < prev:
            errors.append(f"edge {e}: not sorted by (dst, pin, src)")
        prev = key
    return errors


def _int(obj: object, where: str) -> int:
    if isinstance(obj, bool) or not isinstance(obj, int):
        raise ValueError(f"{where}: not an integer")
    return obj


def from_graph_json(obj: Mapping[str, object]) -> FeatureGraph:
    """The feature graph of an L0 ``graph.json`` object (L0 spec 6.4).

    Node ids and order are kept; ``lut_table`` hex becomes an integer (``""`` gives -1); pins are
    as given; net ``n<k>`` becomes ``k``. ``type`` is the kind; the file's ``cell_type`` label
    is not used here.
    """
    raw_nodes = obj["nodes"]
    raw_edges = obj["edges"]
    if not isinstance(raw_nodes, list) or not isinstance(raw_edges, list):
        raise ValueError("graph.json: nodes and edges must be lists")
    index: dict[str, int] = {}
    nodes: list[tuple[str, str, str, int, int]] = []
    for i, node in enumerate(raw_nodes):
        nid = str(node["id"])
        feats = node["features"]
        hexs = str(feats["lut_table"])
        index[nid] = i
        kind = str(node["kind"])
        nodes.append((nid, kind, kind, _int(feats["lut_width"], nid),
                      int(hexs, 16) if hexs else -1))
    edges = [
        (index[str(e["src"])], index[str(e["dst"])], str(e["pin"]), int(str(e["net"])[1:]))
        for e in raw_edges
    ]
    return make_feature_graph(nodes, edges)
