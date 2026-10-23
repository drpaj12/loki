"""Graph loading, features, undirected projections and dataset iteration (L2 spec section 4).

``graph.json`` becomes numpy arrays once: node order is the file order, ``num`` holds the numeric
feature columns, ``src``/``dst`` are endpoint indices and the label columns stay optional. Memory
note (L2 spec 3): loading and featurizing a 100k-node, 500k-edge netlist peaks at about 2 GB, inside
the 30 s / 2 GB budget; nothing here builds a dense N x N array.

numpy and scipy belong to the ``analysis`` extra and are imported inside functions after
:func:`loki.analysis.require`, so importing this module needs the standard library only.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from loki.analysis import require
from loki.features.graph import FeatureGraph, make_feature_graph
from loki.schemas import FLOORS, KINDS, LABEL_COLUMNS, validate_graph

if TYPE_CHECKING:
    from collections.abc import Iterator, Sequence

    import numpy.typing as npt

NUMERIC_FEATURES: tuple[str, ...] = (
    "fan_in", "fan_out", "level", "lut_width", "is_seq", "is_const", "hard_ports", "lut_ones",
)
#: label columns of the answer key (L0 spec 6.5) that must never become a feature column; the
#: node id and the structural kind are identifiers, and ``cell_type`` feeds the hard-type block.
LABEL_COLUMNS_FORBIDDEN: frozenset[str] = frozenset(
    column for column in LABEL_COLUMNS if column not in ("node_id", "kind", "cell_type")
)
_LABEL_KEYS: tuple[str, ...] = LABEL_COLUMNS[3:]
_TEXT_LABELS = frozenset(
    {"construct_type", "construct_types", "module_path", "bus_name", "role", "hdl_file"}
)
_UNKNOWN = "<unk>"
_HARD_UNKNOWN = f"hard:{_UNKNOWN}"


@dataclass(frozen=True)
class Graph:
    """One ``graph.json`` in numpy form (L2 spec 4).

    ``src`` and ``dst`` are indices into ``node_ids`` (driver to sink, one per ``edges`` item,
    parallel edges kept). ``num`` holds :data:`NUMERIC_FEATURES` as int64 arrays and ``table``
    the integer ``lut_table`` of every node (-1 when the node has no table). ``labels`` maps
    each label column of the file to an array (text columns as strings, the rest int64), or is
    ``None`` when every label object of the file is empty (see :func:`_label_columns`); ``None``
    does not mean the label objects are absent, because a valid ``graph.json`` always writes them.
    """

    design: str
    floor: str
    node_ids: tuple[str, ...]
    kind: tuple[str, ...]
    num: dict[str, npt.NDArray[Any]]
    table: tuple[int, ...]
    src: npt.NDArray[Any]
    dst: npt.NDArray[Any]
    pin: tuple[str, ...]
    net: tuple[str, ...]
    labels: dict[str, npt.NDArray[Any]] | None
    sha256: str

    @property
    def n_nodes(self) -> int:
        """Number of nodes."""
        return len(self.node_ids)

    @property
    def n_edges(self) -> int:
        """Number of directed edges of the file."""
        return len(self.pin)

    def index(self) -> dict[str, int]:
        """Node id -> row index."""
        return {node_id: row for row, node_id in enumerate(self.node_ids)}

    def induced(self, node_ids: Sequence[str]) -> Graph:
        """The subgraph on ``node_ids``: node order kept, feature values kept as measured.

        Edges survive only when both endpoints are inside. Unknown ids raise ``ValueError``.
        """
        require("analysis")
        import numpy as np

        known = self.index()
        wanted = set(node_ids)
        unknown = sorted(wanted - known.keys())
        if unknown:
            raise ValueError("unknown node ids: " + ", ".join(unknown))
        keep = np.asarray([node_id in wanted for node_id in self.node_ids], dtype=bool)
        rows = np.flatnonzero(keep)
        remap = np.full(self.n_nodes, -1, dtype=np.int32)
        remap[rows] = np.arange(rows.size, dtype=np.int32)
        edge_mask = keep[self.src] & keep[self.dst]
        edges = np.flatnonzero(edge_mask)
        return Graph(
            design=self.design,
            floor=self.floor,
            node_ids=tuple(self.node_ids[int(row)] for row in rows),
            kind=tuple(self.kind[int(row)] for row in rows),
            num={name: values[rows] for name, values in self.num.items()},
            table=tuple(self.table[int(row)] for row in rows),
            src=remap[self.src[edge_mask]],
            dst=remap[self.dst[edge_mask]],
            pin=tuple(self.pin[int(edge)] for edge in edges),
            net=tuple(self.net[int(edge)] for edge in edges),
            labels=None if self.labels is None else {
                name: values[rows] for name, values in self.labels.items()
            },
            sha256=self.sha256,
        )


def load_graph(path: Path) -> Graph:
    """Read and validate a ``graph.json`` (L0 spec 6.4); ``ValueError`` lists validator errors."""
    require("analysis")
    import numpy as np

    raw = path.read_bytes()
    obj = json.loads(raw)
    errors = validate_graph(obj)
    if errors:
        raise ValueError(f"{path}: invalid graph.json: " + "; ".join(errors))
    nodes = obj["nodes"]
    edges = obj["edges"]
    node_ids = tuple(str(node["id"]) for node in nodes)
    index = {node_id: row for row, node_id in enumerate(node_ids)}
    num: dict[str, npt.NDArray[Any]] = {
        name: np.zeros(len(node_ids), dtype=np.int64) for name in NUMERIC_FEATURES
    }
    for row, node in enumerate(nodes):
        features = node["features"]
        for name in NUMERIC_FEATURES[:-1]:
            num[name][row] = int(features[name])
        table = str(features["lut_table"])
        num["lut_ones"][row] = int(table, 16).bit_count() if table else 0
    return Graph(
        design=str(obj["design"]),
        floor=str(obj["floor"]),
        node_ids=node_ids,
        kind=tuple(str(node["kind"]) for node in nodes),
        num=num,
        table=tuple(_int_table(node["features"]["lut_table"]) for node in nodes),
        src=np.asarray([index[str(edge["src"])] for edge in edges], dtype=np.int32),
        dst=np.asarray([index[str(edge["dst"])] for edge in edges], dtype=np.int32),
        pin=tuple(str(edge["pin"]) for edge in edges),
        net=tuple(str(edge["net"]) for edge in edges),
        labels=_label_columns(nodes),
        sha256=hashlib.sha256(raw).hexdigest(),
    )


def _int_table(lut_table: object) -> int:
    """``lut_table`` hex (L0 spec 6.4, MSB first) as an integer; ``""`` gives -1."""
    text = str(lut_table)
    return int(text, 16) if text else -1


def _label_columns(nodes: Sequence[dict[str, Any]]) -> dict[str, npt.NDArray[Any]] | None:
    """The label columns of the file, or ``None`` when no node carries a construct type.

    The rule distinguishes the two empty-looking states precisely: L0 writes every label object
    even for an unlabelled design, so ``None`` here means "all label objects are empty", never
    "the labels are absent" (``validate_graph`` requires the objects). A from-blif file is
    therefore labelled, because its ports carry ``$port_in``/``$port_out``, while every
    ``lut``/``ff``/``hard`` construct type stays empty; callers that ask whether the answer key
    covers a node kind must look at that kind's ``construct_type`` values, not at
    ``labels is None`` (Task 11 does so explicitly).
    """
    import numpy as np

    if not nodes or not any(str(node["labels"]["construct_type"]) for node in nodes):
        return None
    columns: dict[str, npt.NDArray[Any]] = {}
    for key in _LABEL_KEYS:
        if key in _TEXT_LABELS:
            columns[key] = np.asarray([str(node["labels"][key]) for node in nodes])
        else:
            columns[key] = np.asarray(
                [int(node["labels"][key]) for node in nodes], dtype=np.int64
            )
    return columns


@dataclass(frozen=True)
class FeatureMatrix:
    """A float32 feature matrix with its column names and the hard-cell type vocabulary."""

    names: tuple[str, ...]
    x: npt.NDArray[Any]
    hard_types: tuple[str, ...]


def featurize(g: Graph, hard_types: Sequence[str] | None = None) -> FeatureMatrix:
    """The spec-4 feature matrix: 8 numeric, 7 kind, 4 floor, then ``len(hard_types) + 1``.

    ``hard_types=None`` derives the sorted hard cell types from the ``cell_type`` label of nodes
    with kind ``hard``; a ``graph.json`` accepted by ``validate_graph`` has no such column, so the
    derived vocabulary is empty there (see :func:`_hard_vocabulary`). Every hard node one-hots one
    column regardless: its cell type, or the final ``hard:<unk>`` column when the type is missing
    from the vocabulary (no ``cell_type`` column at all, an empty value, or a type absent from an
    explicit ``hard_types``).
    """
    require("analysis")
    import numpy as np

    types = _hard_vocabulary(g, hard_types)
    names = (
        *NUMERIC_FEATURES,
        *(f"kind:{kind}" for kind in KINDS),
        *(f"floor:{floor}" for floor in FLOORS),
        *(f"hard:{cell_type}" for cell_type in types),
        _HARD_UNKNOWN,
    )
    x = np.zeros((g.n_nodes, len(names)), dtype=np.float32)
    for column, name in enumerate(NUMERIC_FEATURES):
        x[:, column] = g.num[name]
    kind_start = len(NUMERIC_FEATURES)
    positions = {kind: kind_start + column for column, kind in enumerate(KINDS)}
    for row, node_kind in enumerate(g.kind):
        kind_column = positions.get(node_kind)
        if kind_column is not None:
            x[row, kind_column] = 1.0
    if g.floor in FLOORS:
        x[:, kind_start + len(KINDS) + FLOORS.index(g.floor)] = 1.0
    hard_start = kind_start + len(KINDS) + len(FLOORS)
    columns = {cell_type: hard_start + column for column, cell_type in enumerate(types)}
    unknown = hard_start + len(types)
    cells = None if g.labels is None else g.labels.get("cell_type")
    for row, node_kind in enumerate(g.kind):
        if node_kind == "hard":
            cell_type = "" if cells is None else str(cells[row])
            x[row, columns.get(cell_type, unknown)] = 1.0
    return FeatureMatrix(names=names, x=x, hard_types=types)


def _hard_vocabulary(g: Graph, hard_types: Sequence[str] | None) -> tuple[str, ...]:
    """Sorted unique hard cell types, without the ``<unk>`` column."""
    if hard_types is not None:
        return tuple(sorted({str(t) for t in hard_types if str(t) and str(t) != _UNKNOWN}))
    cells = None if g.labels is None else g.labels.get("cell_type")
    if cells is None:
        return ()
    found = {str(cells[row]) for row, kind in enumerate(g.kind) if kind == "hard"}
    found -= {"", _UNKNOWN}
    return tuple(sorted(found))


def to_feature_graph(g: Graph) -> FeatureGraph:
    """The :mod:`loki.features` feature graph of ``g`` (spec 4.1).

    Node order and ids are ``graph.json``'s; ``type`` is the kind (the file holds no cell types);
    ``lut_table`` hex becomes an integer table (``""`` gives -1); pins and nets are as in the
    file. Equal to :func:`loki.features.graph.from_graph_json` on the same file, which a test
    pins; both raise ``ValueError`` for a net not named ``n<k>``.
    """
    nodes = [
        (g.node_ids[row], g.kind[row], g.kind[row], int(g.num["lut_width"][row]), g.table[row])
        for row in range(g.n_nodes)
    ]
    edges = [
        (int(g.src[e]), int(g.dst[e]), g.pin[e], int(g.net[e][1:]))
        for e in range(g.n_edges)
    ]
    return make_feature_graph(nodes, edges)


def undirected_edges(g: Graph) -> tuple[npt.NDArray[Any], npt.NDArray[Any]]:
    """The simple undirected projection: int32 ``src < dst``, unique, sorted (spec 4)."""
    require("analysis")
    import numpy as np

    empty = np.zeros(0, dtype=np.int32)
    if g.n_edges == 0:
        return empty, empty.copy()
    low = np.minimum(g.src, g.dst).astype(np.int64)
    high = np.maximum(g.src, g.dst).astype(np.int64)
    simple = low != high
    keys = np.unique(low[simple] * int(g.n_nodes) + high[simple])
    return (keys // int(g.n_nodes)).astype(np.int32), (keys % int(g.n_nodes)).astype(np.int32)


def undirected_adjacency(g: Graph) -> Any:
    """The ``scipy.sparse.csr_matrix`` of the simple undirected graph (spec 3).

    Symmetric, float32 0/1, no self-loops, parallel edges merged. The return is typed ``Any``
    because scipy ships no type stubs; it is a ``csr_matrix`` of shape ``(n_nodes, n_nodes)``.
    """
    require("analysis")
    import importlib

    import numpy as np

    sp = importlib.import_module("scipy.sparse")
    src, dst = undirected_edges(g)
    rows = np.concatenate([src, dst])
    columns = np.concatenate([dst, src])
    data = np.ones(rows.size, dtype=np.float32)
    matrix = sp.coo_matrix(
        (data, (rows, columns)), shape=(g.n_nodes, g.n_nodes), dtype=np.float32
    )
    return matrix.tocsr()


@dataclass(frozen=True)
class DatasetEntry:
    """One design of a dataset that ran a floor with status ``ok``."""

    design: str
    floor: str
    split: str
    graph_path: Path


def iter_dataset(root: Path, floor: str) -> Iterator[DatasetEntry]:
    """Yield a dataset's designs whose ``floors[floor].status`` is ``ok``, sorted by design."""
    manifest: Any = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    entries: list[DatasetEntry] = []
    for design in manifest.get("designs", []):
        status = design.get("floors", {}).get(floor)
        if not isinstance(status, dict) or status.get("status") != "ok":
            continue
        name = str(design["design"])
        entries.append(
            DatasetEntry(
                design=name,
                floor=floor,
                split=str(design["split"]),
                graph_path=root / name / floor / "graph.json",
            )
        )
    entries.sort(key=lambda entry: entry.design)
    return iter(entries)


def canonical_numbers(raw: npt.NDArray[Any]) -> npt.NDArray[Any]:
    """Renumber cluster labels 0..K-1 in order of their first node (spec 3)."""
    require("analysis")
    import numpy as np

    values = np.asarray(raw)
    if values.ndim != 1:
        raise ValueError("canonical_numbers needs a 1-D array")
    out = np.empty(values.shape, dtype=np.int64)
    numbers: dict[int, int] = {}
    for row, value in enumerate(values.tolist()):
        label = int(value)
        if label not in numbers:
            numbers[label] = len(numbers)
        out[row] = numbers[label]
    return out
