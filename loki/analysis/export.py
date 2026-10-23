"""Edge-list and GraphML exports of a whole graph or a region (L2 spec section 5).

An export writes into ``out`` (the caller supplies the ``export`` directory) with the stem
``whole`` or ``region-<hash8>`` of the region spec. The edge list is text written directly: one
``src<TAB>dst`` line per directed edge in ``graph.json`` order, plus a ``.nodes.tsv`` table whose
columns are ``id``, ``kind``, the spec-4 feature matrix and, when the graph is labelled, the label
columns. GraphML goes through ``networkx.DiGraph`` and ``networkx.write_graphml`` with the same
features and labels as node attributes, the edge ``pin`` and ``net``, and the graph ``design`` and
``floor``; node and edge insertion order follows the graph for deterministic output. The ``pyg``
format is implemented by L2 Task 5 and raises ``NotImplementedError`` here.

networkx belongs to the ``analysis`` extra and is imported inside the function through
``importlib`` (it ships no type marker), after :func:`loki.analysis.require`.
"""

from __future__ import annotations

import importlib
from typing import TYPE_CHECKING, Any

from loki.analysis import require
from loki.analysis.graphio import featurize
from loki.analysis.region import region_hash

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path

    from loki.analysis.graphio import Graph
    from loki.analysis.region import Region

#: Export formats of the plugin surface; ``pyg`` arrives in L2 Task 5.
FORMATS: tuple[str, ...] = ("edgelist", "graphml", "pyg")
_WHOLE = "whole"


def export_graph(
    g: Graph, region: Region | None, formats: Sequence[str], out: Path
) -> list[Path]:
    """Export ``g`` or its induced region in every requested format into ``out``.

    ``formats`` is a subset of :data:`FORMATS`; an unknown name raises ``ValueError`` before
    anything is written, and ``pyg`` raises ``NotImplementedError`` (L2 Task 5). The returned
    paths are sorted and the export is deterministic byte for byte.
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
        raise NotImplementedError("the pyg export is implemented in L2 Task 5")
    target = g if region is None else g.induced(region.node_ids)
    stem = out / (_WHOLE if region is None else f"region-{region_hash(region.spec)}")
    paths: list[Path] = []
    if "edgelist" in chosen:
        paths.extend(write_edgelist(target, stem))
    if "graphml" in chosen:
        paths.append(write_graphml(target, _with_suffix(stem, ".graphml")))
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
