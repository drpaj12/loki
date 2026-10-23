"""Edge-list and GraphML exports of a whole graph or a region (L2 spec section 5).

An export writes into ``out`` (the caller supplies the ``export`` directory) with the stem
``whole`` or ``region-<hash8>`` of the region spec. The edge list is text written directly: one
``src<TAB>dst`` line per directed edge in ``graph.json`` order, plus a ``.nodes.tsv`` table whose
columns are ``id``, ``kind``, the spec-4 feature matrix and, when the graph is labelled, the label
columns. GraphML goes through ``networkx.DiGraph`` and ``networkx.write_graphml`` with the same
features and labels as node attributes, the edge ``pin`` and ``net``, and the graph ``design`` and
``floor``; node and edge insertion order follows the graph for deterministic output. The ``pyg``
format saves the spec-5 plain dict of :func:`pyg_dict` with ``torch.save`` at ``<stem>.pt`` and
loads it back into a ``torch_geometric.data.Data`` through :func:`load_pyg`; the dict carries the
spec-4.1 structural block (GSN role, NPN and WL arrays) and an orbit block only when the graphlets
directory beside ``out`` holds an orbit file for the exported graph (export never runs a backend).

networkx and torch belong to the ``analysis`` and ``gnn`` extras and are imported inside the
functions through ``importlib`` (they ship no type marker), after :func:`loki.analysis.require`.
"""

from __future__ import annotations

import importlib
from typing import TYPE_CHECKING, Any

from loki.analysis import require
from loki.analysis.graphio import featurize
from loki.analysis.region import region_hash
from loki.analysis.structural import compute_structural

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path

    import numpy.typing as npt

    from loki.analysis.graphio import Graph
    from loki.analysis.region import Region

#: Export formats of the plugin surface.
FORMATS: tuple[str, ...] = ("edgelist", "graphml", "pyg")
#: The label columns of the PyG vocabulary, in spec-5 order.
TARGETS: tuple[str, ...] = ("construct_type", "role")
_WHOLE = "whole"
#: The graphlets output directory of spec 11, a sibling of the export directory.
_GRAPHLETS_DIR = "graphlets"


def export_graph(
    g: Graph,
    region: Region | None,
    formats: Sequence[str],
    out: Path,
    *,
    split: str | None = None,
    include_structural: bool = True,
) -> list[Path]:
    """Export ``g`` or its induced region in every requested format into ``out``.

    ``formats`` is a subset of :data:`FORMATS`; an unknown name raises ``ValueError`` before
    anything is written. ``split`` is the manifest split of a dataset input and reaches the PyG
    payload (spec 5, mandatory for a dataset export); a bare ``graph.json`` passes ``None`` and
    writes no ``split`` key. ``include_structural`` reaches the PyG payload: ``False``
    (``--no-structural``) leaves out the spec-4.1 block. The returned paths are sorted and the
    export is deterministic byte for byte.
    """
    require("analysis")
    chosen = tuple(formats)
    unknown = sorted({name for name in chosen if name not in FORMATS})
    if unknown:
        raise ValueError(
            "unknown export format(s): " + ", ".join(unknown)
            + "; use one of " + ", ".join(FORMATS)
        )
    if "pyg" in chosen:
        require("gnn")
    target = g if region is None else g.induced(region.node_ids)
    stem = out / (_WHOLE if region is None else f"region-{region_hash(region.spec)}")
    paths: list[Path] = []
    if "edgelist" in chosen:
        paths.extend(write_edgelist(target, stem))
    if "graphml" in chosen:
        paths.append(write_graphml(target, _with_suffix(stem, ".graphml")))
    if "pyg" in chosen:
        paths.append(
            write_pyg(
                target, _with_suffix(stem, ".pt"), split, orbits_dir=out.parent / _GRAPHLETS_DIR,
                include_structural=include_structural,
            )
        )
    return sorted(paths)


def write_edgelist(g: Graph, stem: Path) -> list[Path]:
    """Write ``<stem>.edges.tsv`` (header-free) and ``<stem>.nodes.tsv``; return both paths."""
    require("analysis")
    stem.parent.mkdir(parents=True, exist_ok=True)
    edges_path = _with_suffix(stem, ".edges.tsv")
    nodes_path = _with_suffix(stem, ".nodes.tsv")
    edges = [
        f"{g.node_ids[int(src)]}\t{g.node_ids[int(dst)]}\n"
        for src, dst in zip(g.src, g.dst, strict=True)
    ]
    edges_path.write_text("".join(edges), encoding="utf-8")
    nodes_path.write_text(_nodes_text(g), encoding="utf-8")
    return sorted((edges_path, nodes_path))


def write_graphml(g: Graph, path: Path) -> Path:
    """Write ``g`` as GraphML at ``path`` and return it."""
    require("analysis")
    nx: Any = importlib.import_module("networkx")
    matrix = featurize(g)
    labels = () if g.labels is None else tuple(g.labels)
    graph = nx.DiGraph()
    graph.graph["design"] = g.design
    graph.graph["floor"] = g.floor
    for row, node_id in enumerate(g.node_ids):
        attrs = {
            name: _attribute(matrix.x[row, column])
            for column, name in enumerate(matrix.names)
        }
        if g.labels is not None:
            for name in labels:
                attrs[name] = _attribute(g.labels[name][row])
        graph.add_node(node_id, **attrs)
    for edge, (src, dst) in enumerate(zip(g.src, g.dst, strict=True)):
        graph.add_edge(
            g.node_ids[int(src)], g.node_ids[int(dst)], pin=g.pin[edge], net=g.net[edge]
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    nx.write_graphml(graph, path)
    return path


def build_vocab_for_graph(g: Graph) -> dict[str, list[str]]:
    """The two label vocabularies of one graph (spec 5): sorted unique non-empty values.

    Unlabelled graphs (``g.labels is None``, i.e. every label object is empty) give an empty
    list for both entries. Class indices are not comparable across exports of different designs.
    """
    if g.labels is None:
        return {name: [] for name in TARGETS}
    return {
        name: sorted({str(value) for value in g.labels[name].tolist() if str(value)})
        for name in TARGETS
    }


def pyg_dict(
    g: Graph,
    split: str | None = None,
    include_structural: bool = True,
    *,
    orbits_dir: Path | None = None,
) -> dict[str, object]:
    """The spec-5 PyG payload of ``g``: a plain dict of tensors and builtins.

    ``x`` is float32 ``(n, len(feature_names))``, ``edge_index`` int64 ``(2, n_edges)`` with the
    driver in row 0, and the label tensors are int64 with ``-1`` where a node's target value is
    empty. The label tensors are absent when the graph is unlabelled; ``vocab`` is always present
    (both lists empty when unlabelled), and ``split`` is present only when given (an export taken
    from a dataset).

    ``include_structural`` adds the spec-4.1 block of spec 5: ``gsn_roles``, ``gsn_npn``,
    ``gsn_wl``, ``npn_keys`` and ``wl_variant``. ``gsn_orbits`` and ``gsn_orbits_source`` are
    added only when ``orbits_dir`` holds an orbit file for exactly this graph (export never runs a
    graphlet backend); :func:`export_graph` passes the ``graphlets`` directory beside the export
    directory of spec 11.
    """
    require("gnn")
    import numpy as np

    torch: Any = importlib.import_module("torch")
    matrix = featurize(g)
    vocab = build_vocab_for_graph(g)
    payload: dict[str, object] = {
        "x": torch.from_numpy(matrix.x),
        "edge_index": torch.from_numpy(np.asarray([g.src, g.dst], dtype=np.int64)),
        "node_ids": list(g.node_ids),
        "feature_names": list(matrix.names),
        "hard_types": list(matrix.hard_types),
    }
    # Unlabelled = every target empty (Task 2); role-only keeps y_role only via a spec change.
    if g.labels is not None:
        payload["y_construct_type"] = torch.from_numpy(
            _encode_targets(g.labels["construct_type"].tolist(), vocab["construct_type"])
        )
        payload["y_role"] = torch.from_numpy(
            _encode_targets(g.labels["role"].tolist(), vocab["role"])
        )
    payload["vocab"] = vocab
    payload["design"] = g.design
    payload["floor"] = g.floor
    if split is not None:
        payload["split"] = split
    if include_structural:
        structural = compute_structural(g)
        payload["gsn_roles"] = torch.from_numpy(structural.roles)
        payload["gsn_npn"] = torch.from_numpy(structural.npn)
        payload["gsn_wl"] = torch.from_numpy(structural.wl)
        payload["npn_keys"] = list(structural.npn_keys)
        payload["wl_variant"] = structural.variant
        orbits = _orbit_arrays(g, orbits_dir)
        if orbits is not None:
            payload["gsn_orbits"], payload["gsn_orbits_source"] = orbits
    return payload


def write_pyg(
    g: Graph,
    path: Path,
    split: str | None = None,
    *,
    orbits_dir: Path | None = None,
    include_structural: bool = True,
) -> Path:
    """Save :func:`pyg_dict` of ``g`` at ``path`` with ``torch.save`` and return ``path``.

    ``include_structural`` is forwarded to :func:`pyg_dict`; ``False`` writes no structural key
    (the export ``--no-structural`` flag).
    """
    require("gnn")
    torch: Any = importlib.import_module("torch")
    path.parent.mkdir(parents=True, exist_ok=True)
    torch.save(
        pyg_dict(g, split, include_structural, orbits_dir=orbits_dir), path
    )
    return path


def load_pyg(path: Path) -> Any:
    """Load a ``.pt`` written by :func:`write_pyg` into a ``torch_geometric.data.Data``.

    The file holds a plain dict so ``torch.load(path, weights_only=True)`` reads it; the ``Data``
    carries ``node_ids`` and ``feature_names`` beside the tensor and metadata attributes. The
    return is typed ``Any`` because torch_geometric ships no type stubs.
    """
    require("gnn")
    torch: Any = importlib.import_module("torch")
    data_module: Any = importlib.import_module("torch_geometric.data")
    raw: Any = torch.load(path, weights_only=True)
    node_ids = raw.pop("node_ids")
    feature_names = raw.pop("feature_names")
    data: Any = data_module.Data(**raw)
    data.node_ids = node_ids
    data.feature_names = feature_names
    return data


def _orbit_arrays(
    g: Graph, orbits_dir: Path | None
) -> tuple[Any, dict[str, str]] | None:
    """``gsn_orbits`` and ``gsn_orbits_source`` from an orbit file for ``g``, or ``None``.

    The candidates are tried in preference order and the first file that loads wins. A file that
    belongs to another graph (a region export, a stale run) raises ``ValueError`` inside
    :func:`load_orbits` and is skipped, because no orbit file exists for the subgraph.
    """
    if orbits_dir is None:
        return None
    import numpy as np

    from loki.analysis.graphlets import load_orbits

    for backend, removal in _orbit_files(orbits_dir):
        try:
            orbits, _roles = load_orbits(g, backend, removal, orbits_dir)
        except ValueError:
            continue
        torch: Any = importlib.import_module("torch")
        arrays = torch.from_numpy(np.asarray(orbits, dtype=np.int64))
        return arrays, {"backend": backend, "removal": removal}
    return None


def _orbit_files(orbits_dir: Path) -> list[tuple[str, str]]:
    """``(backend, removal)`` candidates of ``orbits_dir``; the default backend's file first."""
    from loki.analysis.graphlets import DEFAULT_BACKEND

    if not orbits_dir.is_dir():
        return []
    pairs: list[tuple[str, str]] = []
    for path in sorted(orbits_dir.glob("orbits-*.npz")):
        stem = path.name[len("orbits-"):-len(".npz")]
        backend, separator, removal = stem.rpartition("-")
        if separator and backend and removal in ("global", "none"):
            pairs.append((backend, removal))
    preferred = (DEFAULT_BACKEND, "global")
    return sorted(pairs, key=lambda pair: pair != preferred)


def _encode_targets(values: Sequence[object], vocab: Sequence[str]) -> npt.NDArray[Any]:
    """Target values as int64 vocabulary indices, ``-1`` for an empty value."""
    import numpy as np

    positions = {name: column for column, name in enumerate(vocab)}
    return np.asarray([positions.get(str(value), -1) for value in values], dtype=np.int64)


def _nodes_text(g: Graph) -> str:
    """The ``.nodes.tsv`` table: ``id``, ``kind``, features, then the label columns."""
    matrix = featurize(g)
    labels = () if g.labels is None else tuple(g.labels)
    header = ("id", "kind", *matrix.names, *labels)
    lines = ["\t".join(header)]
    for row, node_id in enumerate(g.node_ids):
        cells = [node_id, g.kind[row], *(_number(value) for value in matrix.x[row])]
        if g.labels is not None:
            cells.extend(str(g.labels[name][row]) for name in labels)
        lines.append("\t".join(cells))
    return "\n".join(lines) + "\n"


def _number(value: Any) -> str:
    """A feature value as text: integral values without a decimal point."""
    number = float(value)
    if number.is_integer():
        return str(int(number))
    return format(number, ".9g")


def _attribute(value: object) -> str | int | float:
    """A GraphML attribute: numpy scalars unwrapped, anything else as text."""
    import numpy as np

    item = value.item() if isinstance(value, np.generic) else value
    if isinstance(item, (str, int, float)):
        return item
    return str(item)


def _with_suffix(stem: Path, suffix: str) -> Path:
    """``<stem><suffix>`` without ``Path.with_suffix``'s dot handling."""
    return stem.with_name(stem.name + suffix)
