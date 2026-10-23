"""GNN data preparation, training and baselines (L2 spec section 9).

The trainer of Task 12 never reads a ``graph.json`` itself: this module turns the dataset split
of L0 into :class:`Prepared` tensors (standardised features, edge list, target indices,
categorical NPN and WL ids) and provides the three baselines the GNN must be read against: the
majority class, features-only logistic regression and the 1-WL colour lookup of spec 9.
:func:`train_eval` fits the two-layer message-passing model of spec 9 and writes the output
tree; :class:`Net` is built on first attribute access so importing this module stays free of
torch.

Labels are an answer key: only nodes of kind :data:`TRAIN_KINDS` with a non-empty target enter
the vocabulary, the loss and the metrics; PI, PO and constants are trivially labelled and would
inflate accuracy. The vocabulary comes from the train designs only, so a class first seen in a
test design maps to ``__other__``. The scaler is fitted on the train nodes of spec 9, the
``y >= 0`` rows of the train designs that the caller selects: a feature matrix has no kind
column, so :func:`fit_scaler` cannot apply :data:`TRAIN_KINDS` itself. Test rows never reach it.

An unlabelled graph is detected by the spec-9 rule "no node of :data:`TRAIN_KINDS` carries a
non-empty ``construct_type``", not by ``Graph.labels is None`` (Task 2 documents ``None`` as
"every label object is empty"; a from-blif graph labels its ports only and is refused here while
cluster and export accept it).

numpy and scikit-learn belong to the ``analysis`` extra, torch and torch_geometric to ``gnn``,
and all of them are imported inside functions after :func:`loki.analysis.require`, so importing
this module needs the standard library only. scikit-learn and torch_geometric have no type
marker, so they are imported through :func:`importlib.import_module`.
"""

from __future__ import annotations

import csv
import importlib
import random
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, Any, cast

from loki.analysis import require
from loki.analysis.graphio import NUMERIC_FEATURES, Graph, featurize, iter_dataset, load_graph
from loki.analysis.graphlets import gsn_features
from loki.analysis.structural import compute_structural
from loki.schemas import dump_json

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping, Sequence
    from pathlib import Path

    import numpy.typing as npt

    from loki.analysis.graphio import DatasetEntry

#: Targets of spec 9: the construct class and the role class of L0's answer key.
TARGETS: tuple[str, ...] = ("construct_type", "role")
#: Node kinds that carry a meaningful target (spec 9); PI, PO and const are trivially labelled.
TRAIN_KINDS: tuple[str, ...] = ("lut", "ff", "hard", "gate")
#: The class that collects every value outside the train vocabulary (spec 9), always last.
OTHER = "__other__"
#: The message of an unlabelled graph (spec 9; detection rule in :func:`_check_labelled`).
UNLABELLED_MESSAGE = "graph has no labels: the GNN needs L0 labels"
#: Count columns scaled with ``log1p`` before standardisation, the Task 7 set (spec 9).
LOG1P_COLUMNS: tuple[str, ...] = ("fan_in", "fan_out", "level", "lut_width", "hard_ports",
                                  "lut_ones")
#: Structural inputs of spec 9: ``node`` is the base block, the rest are optional additions.
FEATURES: tuple[str, ...] = ("node", "graphlet", "wl", "npn")
#: Size of the categorical embedding of every ``wl`` and ``npn`` id (spec 9).
EMBEDDING_DIM = 8
#: The WL round whose colour the ``wl`` feature embeds (spec 9: "the round-2 WL id").
WL_EMBEDDING_ROUND = 2
#: The "honest limit" sentence of spec 9, written into every ``metrics.json``.
NOTE = ("a LUT merges the logic of several constructs; its label is the primary construct "
        "(L0 spec 5.3), so accuracy has a ceiling below 1.")
_TRAIN_KINDS = frozenset(TRAIN_KINDS)
_LOG1P_INDICES = tuple(NUMERIC_FEATURES.index(name) for name in LOG1P_COLUMNS)


@dataclass(frozen=True)
class Prepared:
    """One design as the trainer sees it (spec 9).

    ``x`` is float64 ``(N, features)``: the Task 2 feature matrix with ``log1p`` on the count
    columns and standardised by the train scaler. ``edge_index`` is int64 ``(2, E)`` with the
    directed driver-to-sink edges of the file; the trainer adds the reverse edges with
    ``to_undirected`` (spec 9). ``y`` is int64 ``(N,)`` with the target index in the vocabulary,
    ``-1`` for an empty target or a kind outside :data:`TRAIN_KINDS`. ``cat`` is int64
    ``(N, 2 + rounds)`` with the categorical block of :func:`gsn_features` mapped through the
    train id vocabularies (the NPN id, then the WL id of every round; unseen ids become the last
    index). ``prepare`` always fills ``cat``; ``None`` is reserved for callers that build tensors
    without the categorical block.
    """

    design: str
    split: str
    x: npt.NDArray[Any]
    edge_index: npt.NDArray[Any]
    y: npt.NDArray[Any]
    node_ids: tuple[str, ...]
    cat: npt.NDArray[Any] | None


def _check_target(target: str) -> None:
    """Reject a target outside :data:`TARGETS`."""
    if target not in TARGETS:
        raise ValueError(f"unknown target {target!r}: use one of {', '.join(TARGETS)}")


def _check_labelled(g: Graph) -> None:
    """Raise :data:`UNLABELLED_MESSAGE` unless a train-kind node carries a construct type.

    This is the explicit spec-9 rule, not ``g.labels is None``: a from-blif graph labels its
    ports (so ``labels`` is not ``None``) but no ``lut``/``ff``/``hard``/``gate`` node has a
    non-empty ``construct_type``, and the GNN has nothing to learn from it.
    """
    labels = g.labels
    construct = None if labels is None else labels.get("construct_type")
    if construct is None:
        raise ValueError(UNLABELLED_MESSAGE)
    for row, kind in enumerate(g.kind):
        if kind in _TRAIN_KINDS and str(construct[row]):
            return
    raise ValueError(UNLABELLED_MESSAGE)


def _train_mask(g: Graph) -> npt.NDArray[Any]:
    """Boolean mask of the nodes whose kind is in :data:`TRAIN_KINDS`."""
    import numpy as np

    return np.fromiter((kind in _TRAIN_KINDS for kind in g.kind), dtype=bool, count=g.n_nodes)


def _target_values(g: Graph, target: str) -> npt.NDArray[Any] | None:
    """The target label column of ``g`` (strings), or ``None`` when the file has no such column."""
    labels = g.labels
    if labels is None:
        return None
    values = labels.get(target)
    return None if values is None else values


def build_vocab(graphs: Iterable[Graph], target: str, min_count: int = 5) -> list[str]:
    """The target vocabulary of the train designs (spec 9).

    Values of train-kind nodes with at least ``min_count`` train nodes, sorted by name, then
    ``__other__`` last, so the class index C is ``len(names) - 1``. Values first seen in a test
    design never appear. A graph without L0 labels raises :data:`UNLABELLED_MESSAGE`.
    """
    require("analysis")
    _check_target(target)
    if min_count < 1:
        raise ValueError(f"min_count must be >= 1, got {min_count}")
    counts: dict[str, int] = {}
    for g in graphs:
        _check_labelled(g)
        values = _target_values(g, target)
        mask = _train_mask(g)
        for row in range(g.n_nodes):
            if not mask[row] or values is None:
                continue
            value = str(values[row])
            if value:
                counts[value] = counts.get(value, 0) + 1
    names = sorted(name for name, count in counts.items() if count >= min_count)
    return [*names, OTHER]


def encode(g: Graph, target: str, vocab: Sequence[str]) -> npt.NDArray[Any]:
    """Target indices of ``g`` (int64 ``(N,)``; spec 9).

    ``-1`` for an empty target or a node whose kind is outside :data:`TRAIN_KINDS`; a value
    absent from ``vocab`` maps to its last entry, :data:`OTHER`. ``vocab`` must end with
    :data:`OTHER` (as :func:`build_vocab` returns it).
    """
    require("analysis")
    import numpy as np

    _check_target(target)
    if not vocab or vocab[-1] != OTHER:
        raise ValueError(f"vocabulary must end with {OTHER!r}")
    _check_labelled(g)
    values = _target_values(g, target)
    mask = _train_mask(g)
    index = {name: column for column, name in enumerate(vocab)}
    other = len(vocab) - 1
    out = np.full(g.n_nodes, -1, dtype=np.int64)
    for row in range(g.n_nodes):
        if not mask[row] or values is None:
            continue
        value = str(values[row])
        if value:
            out[row] = index.get(value, other)
    return out


def fit_scaler(x_train_list: Sequence[npt.NDArray[Any]]) -> dict[str, npt.NDArray[Any]]:
    """The train scaler of spec 9: ``{"mean": ..., "std": ...}`` over the given train rows.

    Each array holds feature rows of one train design, selected to the nodes with ``y >= 0``
    (train kinds with a known target), so no test row can reach it. ``log1p`` is applied to the
    count columns first (the Task 7 set); a column with zero spread gets ``std == 1``, like
    ``StandardScaler``. An empty sequence raises ``ValueError`` because the width is unknown.
    """
    require("analysis")
    import numpy as np

    if not x_train_list:
        raise ValueError("fit_scaler needs at least one train design")
    arrays = [np.asarray(x, dtype=np.float64) for x in x_train_list]
    for x in arrays:
        if x.ndim != 2:
            raise ValueError(f"feature rows must be 2-D, got shape {x.shape}")
        if x.shape[1] < len(NUMERIC_FEATURES):
            raise ValueError(f"feature matrix has {x.shape[1]} columns, expected at least "
                             f"{len(NUMERIC_FEATURES)}")
    width = arrays[0].shape[1]
    if any(x.shape[1] != width for x in arrays):
        raise ValueError("every train design must have the same feature columns")
    stacked = np.concatenate(arrays, axis=0)
    if stacked.shape[0] == 0:
        return {"mean": np.zeros(width, dtype=np.float64), "std": np.ones(width, dtype=np.float64)}
    for column in _LOG1P_INDICES:
        stacked[:, column] = np.log1p(stacked[:, column])
    mean = stacked.mean(axis=0)
    spread = stacked.std(axis=0)
    return {"mean": mean, "std": np.where(spread == 0, 1.0, spread)}


def _transform(x: npt.NDArray[Any], scaler: dict[str, npt.NDArray[Any]]) -> npt.NDArray[Any]:
    """``log1p`` on the count columns, then ``(x - mean) / std`` with the train scaler."""
    import numpy as np

    mean = np.asarray(scaler["mean"], dtype=np.float64)
    std = np.asarray(scaler["std"], dtype=np.float64)
    values = np.array(x, dtype=np.float64, copy=True)
    if values.ndim != 2:
        raise ValueError(f"feature matrix must be 2-D, got shape {values.shape}")
    if mean.shape != std.shape or mean.size != values.shape[1]:
        raise ValueError(
            f"scaler has {mean.size} columns of mean and {std.size} of std, "
            f"the feature matrix {values.shape[1]}"
        )
    if values.shape[1] < len(NUMERIC_FEATURES):
        raise ValueError(f"feature matrix has {values.shape[1]} columns, expected at least "
                         f"{len(NUMERIC_FEATURES)}")
    for column in _LOG1P_INDICES:
        values[:, column] = np.log1p(values[:, column])
    return (values - mean) / std


def build_id_vocab(ids: Iterable[npt.NDArray[Any]], min_count: int = 5) -> dict[int, int]:
    """Categorical id -> index over the train nodes, ids with at least ``min_count`` nodes.

    Ids are sorted ascending and numbered ``0..C-1``; the index for an unseen id is
    ``len(vocab)``, i.e. ``__other__`` is last (spec 9).
    """
    require("analysis")
    import numpy as np

    if min_count < 1:
        raise ValueError(f"min_count must be >= 1, got {min_count}")
    counts: dict[int, int] = {}
    for array in ids:
        for raw in np.asarray(array, dtype=np.int64).reshape(-1).tolist():
            value = int(raw)
            counts[value] = counts.get(value, 0) + 1
    kept = sorted(value for value, count in counts.items() if count >= min_count)
    return {value: index for index, value in enumerate(kept)}


def _map_ids(values: npt.NDArray[Any], vocab: dict[int, int]) -> npt.NDArray[Any]:
    """Map one categorical column through :func:`build_id_vocab`; unseen ids get ``len(vocab)``."""
    import numpy as np

    flat = np.asarray(values, dtype=np.int64).reshape(-1)
    if not vocab:
        return np.zeros(flat.shape, dtype=np.int64)
    keys = np.asarray(sorted(vocab), dtype=np.int64)
    indices = np.asarray([vocab[int(key)] for key in keys], dtype=np.int64)
    position = np.searchsorted(keys, flat)
    clipped = np.minimum(position, keys.size - 1)
    hit = (position < keys.size) & (keys[clipped] == flat)
    out = np.full(flat.shape, len(vocab), dtype=np.int64)
    out[hit] = indices[clipped[hit]]
    return out


def prepare(
    entries: Iterable[DatasetEntry],
    target: str,
    vocab: Sequence[str],
    hard_types: Sequence[str] | None,
    scaler: dict[str, npt.NDArray[Any]],
    *,
    cat_min_count: int = 5,
) -> list[Prepared]:
    """The per-design tensors of spec 9 for ``entries`` (an :func:`iter_dataset` run).

    ``vocab`` and ``scaler`` come from the train designs; ``hard_types`` is the hard-cell type
    vocabulary the scaler was fitted with. The categorical NPN and WL ids are mapped through id
    vocabularies built from the train designs only, keeping ids with at least ``cat_min_count``
    train nodes (the trainer passes its own ``min_count``); a graph without L0 labels raises
    :data:`UNLABELLED_MESSAGE`.
    """
    require("analysis")
    import numpy as np

    prepared: list[Prepared] = []
    cats: list[npt.NDArray[Any]] = []
    for entry in entries:
        g = load_graph(entry.graph_path)
        matrix = featurize(g, hard_types)
        y = encode(g, target, vocab)
        x = _transform(matrix.x, scaler)
        edge_index = np.vstack([g.src, g.dst]).astype(np.int64).reshape(2, g.n_edges)
        structural = compute_structural(g)
        _, cat = gsn_features(None, structural.roles, structural)
        prepared.append(
            Prepared(
                design=entry.design,
                split=entry.split,
                x=x,
                edge_index=edge_index,
                y=y,
                node_ids=tuple(g.node_ids),
                cat=None,
            )
        )
        cats.append(np.asarray(cat))
    if not prepared:
        return []
    widths = {cat.shape[1] for cat in cats}
    if len(widths) != 1:
        raise ValueError(f"categorical blocks differ in width: {sorted(widths)}")
    vocabularies = [
        build_id_vocab(
            [cat[:, column] for cat, p in zip(cats, prepared, strict=True)
             if p.split == "train"],
            cat_min_count,
        )
        for column in range(cats[0].shape[1])
    ]
    mapped = [
        np.column_stack([_map_ids(cat[:, column], vocabularies[column])
                         for column in range(cat.shape[1])]).astype(np.int64)
        for cat in cats
    ]
    return [
        replace(p, cat=mapped[index]) for index, p in enumerate(prepared)
    ]


def metrics(y_true: npt.NDArray[Any], y_pred: npt.NDArray[Any]) -> dict[str, float]:
    """``accuracy``, ``macro_f1`` and ``n_nodes`` over the nodes with ``y_true >= 0`` (spec 9).

    ``n_nodes`` counts only the nodes of the scored kinds; with none, accuracy and macro F1 are
    ``0.0`` and ``n_nodes`` is ``0``, so an empty split stays valid JSON instead of ``NaN``.
    """
    require("analysis")
    import numpy as np

    true = np.asarray(y_true, dtype=np.int64)
    pred = np.asarray(y_pred, dtype=np.int64)
    if true.shape != pred.shape:
        raise ValueError(f"y_true has shape {true.shape} and y_pred {pred.shape}")
    mask = true >= 0
    scored_true, scored_pred = true[mask], pred[mask]
    if scored_true.size == 0:
        return {"accuracy": 0.0, "macro_f1": 0.0, "n_nodes": 0}
    f1_score = importlib.import_module("sklearn.metrics").f1_score
    return {
        "accuracy": float((scored_true == scored_pred).mean()),
        "macro_f1": float(f1_score(scored_true, scored_pred, average="macro")),
        "n_nodes": int(scored_true.size),
    }


def _zero_metrics(n_nodes: int) -> dict[str, float]:
    """The spec-9 scores of an empty split."""
    return {"accuracy": 0.0, "macro_f1": 0.0, "n_nodes": n_nodes}


def baseline_majority(y_train: npt.NDArray[Any], y_test: npt.NDArray[Any]) -> dict[str, float]:
    """Predict the most common train class for every test node (spec 9).

    Ties pick the lowest class index. Only nodes with ``y >= 0`` on either side are used; an
    empty side gives the zeros of :func:`metrics`.
    """
    require("analysis")
    import numpy as np

    train = np.asarray(y_train, dtype=np.int64)
    test = np.asarray(y_test, dtype=np.int64)
    scored_train, scored_test = train[train >= 0], test[test >= 0]
    if scored_train.size == 0 or scored_test.size == 0:
        return _zero_metrics(int(scored_test.size))
    majority = int(np.argmax(np.bincount(scored_train)))
    return metrics(scored_test, np.full(scored_test.shape, majority, dtype=np.int64))


def baseline_logreg(
    xtr: npt.NDArray[Any],
    ytr: npt.NDArray[Any],
    xte: npt.NDArray[Any],
    yte: npt.NDArray[Any],
    seed: int,
) -> dict[str, float]:
    """Features-only logistic regression (spec 9): no graph, ``max_iter=1000``, ``seed`` fixed.

    Only nodes with ``y >= 0`` are fitted or scored; an empty side gives the zeros of
    :func:`metrics`.
    """
    require("analysis")
    import numpy as np

    x_train = np.asarray(xtr, dtype=np.float64)
    x_test = np.asarray(xte, dtype=np.float64)
    train = np.asarray(ytr, dtype=np.int64)
    test = np.asarray(yte, dtype=np.int64)
    if x_train.shape[0] != train.size or x_test.shape[0] != test.size:
        raise ValueError("feature rows and labels differ in length")
    keep_train, keep_test = train >= 0, test >= 0
    scored_train, scored_test = train[keep_train], test[keep_test]
    if scored_train.size == 0 or scored_test.size == 0:
        return _zero_metrics(int(scored_test.size))
    model = importlib.import_module("sklearn.linear_model").LogisticRegression(
        max_iter=1000, random_state=seed
    )
    model.fit(x_train[keep_train], scored_train)
    predicted = np.asarray(model.predict(x_test[keep_test]), dtype=np.int64)
    return metrics(scored_test, predicted)


def _majority_by_id(
    ids: npt.NDArray[Any], labels: npt.NDArray[Any]
) -> tuple[npt.NDArray[Any], npt.NDArray[Any], npt.NDArray[Any]]:
    """For each sorted unique id: its majority class (lowest wins a tie) and node count.

    The counts are taken with ``np.unique`` over the ``(id, class)`` pairs, so the work and the
    memory stay proportional to the pairs present instead of the dense ``N x C`` table a
    ``bincount`` of flattened ``inverse * n_classes + label`` indices would build (carried from
    the Task 11 review: WL ids can be numerous and the class count free).
    """
    import numpy as np

    unique, inverse = np.unique(ids, return_inverse=True)
    empty = np.zeros(unique.size, dtype=np.int64)
    if labels.size == 0 or unique.size == 0:
        return unique, empty, empty.copy()
    pairs = np.column_stack([inverse.astype(np.int64), labels.astype(np.int64)])
    pair_keys, pair_counts = np.unique(pairs, axis=0, return_counts=True)
    pair_classes = pair_keys[:, 1].astype(np.int64)
    per_id = np.bincount(pair_keys[:, 0].astype(np.int64), minlength=unique.size)
    starts = np.concatenate([np.zeros(1, dtype=np.int64), np.cumsum(per_id)[:-1]])
    totals = np.add.reduceat(pair_counts, starts).astype(np.int64)
    best = np.repeat(np.maximum.reduceat(pair_counts, starts), per_id)
    row_group = np.repeat(np.arange(unique.size, dtype=np.int64), per_id)
    candidate_rows = np.flatnonzero(pair_counts == best)
    groups_hit, first = np.unique(row_group[candidate_rows], return_index=True)
    majority = np.zeros(unique.size, dtype=np.int64)
    majority[groups_hit] = pair_classes[candidate_rows[first]]
    return unique, majority, totals


def baseline_wl(
    wl_train: npt.NDArray[Any],
    y_train: npt.NDArray[Any],
    wl_test: npt.NDArray[Any],
    y_test: npt.NDArray[Any],
    min_count: int = 5,
) -> dict[str, float]:
    """The 1-WL colour baseline of spec 9.

    ``wl_*`` are int64 ``(n, rounds + 1)``: column ``r`` is the WL colour of round ``r`` (the
    NPN column of :func:`gsn_features` is not part of the baseline). For a test node the lookup
    starts at the last round and backs off to round 0 when its colour has fewer than
    ``min_count`` train nodes; a node no round qualifies predicts the majority train class.
    Only nodes with ``y >= 0`` are used; an empty train or test side gives the zeros of
    :func:`metrics` with the test side's ``n_nodes``.
    """
    require("analysis")
    import numpy as np

    if min_count < 1:
        raise ValueError(f"min_count must be >= 1, got {min_count}")
    train_ids = np.asarray(wl_train)
    test_ids = np.asarray(wl_test)
    train = np.asarray(y_train, dtype=np.int64)
    test = np.asarray(y_test, dtype=np.int64)
    if train_ids.ndim != 2 or test_ids.ndim != 2:
        raise ValueError("wl_train and wl_test must be 2-D")
    if train_ids.shape[1] != test_ids.shape[1]:
        raise ValueError(
            f"wl_train has {train_ids.shape[1]} columns and wl_test {test_ids.shape[1]}"
        )
    if train_ids.shape[0] != train.size or test_ids.shape[0] != test.size:
        raise ValueError("WL rows and labels differ in length")
    keep_train, keep_test = train >= 0, test >= 0
    train_ids, scored_train = train_ids[keep_train], train[keep_train]
    test_ids, scored_test = test_ids[keep_test], test[keep_test]
    if scored_train.size == 0 or scored_test.size == 0:
        return _zero_metrics(int(scored_test.size))
    predicted = np.full(scored_test.size, -1, dtype=np.int64)
    for column in range(test_ids.shape[1] - 1, -1, -1):
        missing = np.flatnonzero(predicted < 0)
        if missing.size == 0:
            break
        keys, majority, totals = _majority_by_id(train_ids[:, column], scored_train)
        if keys.size == 0:
            continue
        values = test_ids[missing, column]
        position = np.searchsorted(keys, values)
        clipped = np.minimum(position, keys.size - 1)
        found = (
            (position < keys.size) & (keys[clipped] == values) & (totals[clipped] >= min_count)
        )
        predicted[missing[found]] = majority[clipped[found]]
    unfilled = predicted < 0
    if unfilled.any():
        predicted[unfilled] = int(np.argmax(np.bincount(scored_train)))
    return metrics(scored_test, predicted)


_NET: Any = None


def _net_class() -> Any:
    """Build :class:`Net` on first use, so importing this module needs no torch (spec 9)."""
    global _NET
    if _NET is not None:
        return _NET
    require("gnn")
    import torch

    # torch_geometric has no type marker (like scikit-learn): import it dynamically so
    # ``mypy --strict`` does not chase an untyped package.
    geometric_nn = cast(Any, importlib.import_module("torch_geometric.nn"))
    SAGEConv = geometric_nn.SAGEConv
    GCNConv = geometric_nn.GCNConv

    class Net(torch.nn.Module):
        """The spec-9 classifier: two message-passing layers, ReLU, dropout and a linear head.

        ``cat_sizes`` gives one size-8 :class:`torch.nn.Embedding` per categorical column; the
        embeddings are concatenated to the input of the first layer. Without them the model
        reads the feature matrix alone.
        """

        def __init__(
            self,
            in_dim: int,
            n_classes: int,
            kind: str = "sage",
            hidden: int = 64,
            dropout: float = 0.2,
            cat_sizes: Sequence[int] = (),
        ) -> None:
            super().__init__()
            if kind not in ("sage", "gcn"):
                raise ValueError(f"unknown model {kind!r}: use 'sage' or 'gcn'")
            conv = SAGEConv if kind == "sage" else GCNConv
            self.embeddings = torch.nn.ModuleList(
                [torch.nn.Embedding(size, EMBEDDING_DIM) for size in cat_sizes]
            )
            first = in_dim + EMBEDDING_DIM * len(self.embeddings)
            self.conv1 = conv(first, hidden)
            self.conv2 = conv(hidden, hidden)
            self.dropout = torch.nn.Dropout(dropout)
            self.head = torch.nn.Linear(hidden, n_classes)

        def forward(self, x: Any, edge_index: Any, cat: Any | None = None) -> Any:
            if len(self.embeddings) > 0:
                if cat is None:
                    raise ValueError("the model has categorical embeddings but no ids")
                parts = [x]
                for column, embedding in enumerate(self.embeddings):
                    parts.append(embedding(cat[:, column]))
                x = torch.cat(parts, dim=1)
            x = self.dropout(torch.relu(self.conv1(x, edge_index)))
            x = self.dropout(torch.relu(self.conv2(x, edge_index)))
            return self.head(x)

    Net.__name__ = "Net"
    Net.__qualname__ = "Net"
    Net.__module__ = __name__
    _NET = Net
    return _NET


def __getattr__(name: str) -> Any:
    """Expose :class:`Net` lazily: the class needs torch at build time only."""
    if name == "Net":
        return _net_class()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


@dataclass(frozen=True)
class _TrainData:
    """The prepared designs and the train-only artifacts of one dataset (spec 9)."""

    prepared: list[Prepared]
    vocab: list[str]
    scaler: dict[str, npt.NDArray[Any]]
    names: tuple[str, ...]

    @property
    def in_dim(self) -> int:
        """Width of the Task 2 feature matrix, embeddings excluded."""
        return len(self.names)


def _check_features(features: Sequence[str]) -> None:
    """Reject an empty feature list or a name outside :data:`FEATURES`."""
    if not features:
        raise ValueError("features must name at least 'node'")
    unknown = [name for name in features if name not in FEATURES]
    if unknown:
        raise ValueError(f"unknown feature(s) {unknown}: use {', '.join(FEATURES)}")


def _round_scores(scores: Mapping[str, float]) -> dict[str, Any]:
    """Spec 9 rounding: floats to 4 decimals, counts stay integers."""
    rounded: dict[str, Any] = {}
    for key, value in scores.items():
        rounded[key] = int(value) if isinstance(value, int) else round(float(value), 4)
    return rounded


def _stack(arrays: Sequence[npt.NDArray[Any]], width: int = 0) -> npt.NDArray[Any]:
    """Concatenate the per-design arrays; an empty sequence gives an empty array of ``width``."""
    import numpy as np

    if arrays:
        return np.concatenate(arrays, axis=0)
    if width:
        return np.zeros((0, width), dtype=np.int64)
    return np.zeros(0, dtype=np.int64)


def _cat_of(p: Prepared) -> npt.NDArray[Any]:
    """The categorical block of a prepared design (``prepare`` always fills it)."""
    if p.cat is None:
        raise ValueError(f"{p.design}: the prepared design has no categorical block")
    return p.cat


def _fit_dataset(
    train_entries: Sequence[DatasetEntry], entries: Sequence[DatasetEntry], target: str,
    min_count: int,
) -> _TrainData:
    """Fit the vocabulary and scaler on the train designs, then prepare every design."""
    import numpy as np

    graphs = [load_graph(entry.graph_path) for entry in train_entries]
    vocab = build_vocab(graphs, target, min_count)
    hard_types = tuple(sorted({kind for g in graphs for kind in featurize(g).hard_types}))
    rows: list[npt.NDArray[Any]] = []
    names: tuple[str, ...] = ()
    for g in graphs:
        matrix = featurize(g, hard_types)
        names = matrix.names
        y = encode(g, target, vocab)
        rows.append(np.asarray(matrix.x)[y >= 0])
    scaler = fit_scaler(rows)
    prepared = prepare(entries, target, vocab, hard_types, scaler, cat_min_count=min_count)
    return _TrainData(prepared=prepared, vocab=vocab, scaler=scaler, names=names)


def _extra_blocks(
    prepared: Sequence[Prepared], features: Sequence[str],
    extra: Mapping[str, npt.NDArray[Any]] | None,
) -> tuple[dict[str, npt.NDArray[Any]], int]:
    """Validate the per-design numeric blocks a caller passes for ``features=('graphlet',)``."""
    import numpy as np

    if "graphlet" not in features:
        if extra is not None:
            raise ValueError("extra needs features=('graphlet',)")
        return {}, 0
    if extra is None:
        raise ValueError(
            "features=('graphlet',) needs extra={design: graphlet_features(orbits, roles)}"
        )
    blocks: dict[str, npt.NDArray[Any]] = {}
    widths: set[int] = set()
    for p in prepared:
        block = extra.get(p.design)
        if block is None:
            raise ValueError(f"no extra block for design {p.design!r}")
        values = np.asarray(block, dtype=np.float64)
        if values.ndim != 2 or values.shape[0] != p.x.shape[0]:
            raise ValueError(
                f"extra block of {p.design!r} has shape {values.shape}, "
                f"expected ({p.x.shape[0]}, k)"
            )
        widths.add(int(values.shape[1]))
        blocks[p.design] = values
    if len(widths) != 1:
        raise ValueError(f"extra blocks differ in width: {sorted(widths)}")
    return blocks, widths.pop()


def _embedding_sizes(prepared: Sequence[Prepared], columns: Sequence[int]) -> list[int]:
    """Rows of each id embedding: the largest mapped index over the designs, plus the other row."""
    import numpy as np

    cats = [_cat_of(p) for p in prepared]
    sizes: list[int] = []
    for column in columns:
        values = [np.asarray(cat)[:, column] for cat in cats if cat.shape[0]]
        sizes.append(int(np.concatenate(values).max()) + 1 if values else 1)
    return sizes


def _numeric_inputs(
    prepared: Sequence[Prepared], blocks: Mapping[str, npt.NDArray[Any]]
) -> dict[str, npt.NDArray[Any]]:
    """The numeric matrix of each design: the standardised features plus the extra block."""
    import numpy as np

    inputs: dict[str, npt.NDArray[Any]] = {}
    for p in prepared:
        block = blocks.get(p.design)
        x = np.asarray(p.x, dtype=np.float64)
        inputs[p.design] = x if block is None else np.concatenate([x, block], axis=1)
    return inputs


def _design_tensors(
    p: Prepared, block: npt.NDArray[Any] | None, columns: Sequence[int]
) -> tuple[Any, Any, Any, Any]:
    """The torch tensors of one design: features, undirected edges, labels, categorical ids."""
    import numpy as np
    import torch

    to_undirected = cast(Any, importlib.import_module("torch_geometric.utils")).to_undirected

    x = torch.as_tensor(np.asarray(p.x, dtype=np.float64), dtype=torch.float32)
    if block is not None:
        values = torch.as_tensor(np.asarray(block, dtype=np.float64), dtype=torch.float32)
        x = torch.cat([x, values], dim=1)
    edges = torch.as_tensor(np.asarray(p.edge_index, dtype=np.int64), dtype=torch.long)
    edges = to_undirected(edges, num_nodes=int(p.x.shape[0]))
    y = torch.as_tensor(np.asarray(p.y, dtype=np.int64), dtype=torch.long)
    cat = None
    if columns:
        cat = torch.as_tensor(
            np.asarray(_cat_of(p))[:, list(columns)], dtype=torch.long
        )
    return x, edges, y, cat


def _class_weights(y: npt.NDArray[Any], n_classes: int) -> Any:
    """``1/sqrt(count)`` per class, normalised to mean 1 (spec 9); an empty class gets 1."""
    import numpy as np
    import torch

    scored = np.asarray(y, dtype=np.int64)
    counts = np.bincount(scored[scored >= 0], minlength=n_classes).astype(np.float64)
    weights = np.where(counts > 0, 1.0 / np.sqrt(np.maximum(counts, 1.0)), 1.0)
    weights = weights / weights.mean()
    return torch.as_tensor(weights, dtype=torch.float32)


def _fit(
    model: Any, train_data: Sequence[tuple[Any, Any, Any, Any]], weights: Any, *,
    epochs: int, lr: float, weight_decay: float,
) -> None:
    """Full-batch per design, gradients summed over the train designs of each epoch (spec 9)."""
    import torch
    import torch.nn.functional as functional

    optimizer = torch.optim.Adam(model.parameters(), lr=lr, weight_decay=weight_decay)
    for _ in range(epochs):
        model.train()
        optimizer.zero_grad()
        for x, edges, y, cat in train_data:
            mask = y >= 0
            if not bool(mask.any()):
                continue
            logits = model(x, edges, cat)
            loss: Any = functional.cross_entropy(
                logits[mask], y[mask], weight=weights, reduction="sum"
            )
            loss.backward()
        optimizer.step()


def _predict(model: Any, data: tuple[Any, Any, Any, Any]) -> npt.NDArray[Any]:
    """Class indices of one design; ``y >= 0`` rows are the ones scored."""
    import numpy as np
    import torch

    x, edges, _, cat = data
    model.eval()
    with torch.no_grad():
        logits = model(x, edges, cat)
    return np.asarray(logits.argmax(dim=1).detach().cpu().numpy(), dtype=np.int64)


def _split_metrics(
    predictions: Sequence[npt.NDArray[Any]], labels: Sequence[npt.NDArray[Any]]
) -> dict[str, Any]:
    """The spec-9 scores of one split plus its design count."""
    scores = _round_scores(metrics(_stack(labels), _stack(predictions)))
    return {**scores, "n_designs": len(labels)}


def _write_predictions(
    out: Path, p: Prepared, prediction: npt.NDArray[Any], vocab: Sequence[str]
) -> None:
    """Write ``predictions-<design>.csv`` of the scored nodes (spec 9)."""
    import numpy as np

    path = out / f"predictions-{p.design}.csv"
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(["node_id", "true", "pred"])
        for row, truth in enumerate(np.asarray(p.y, dtype=np.int64).tolist()):
            if truth < 0:
                continue
            writer.writerow([p.node_ids[row], vocab[int(truth)], vocab[int(prediction[row])]])


def _checkpoint(
    net: Any, scaler: Mapping[str, npt.NDArray[Any]], vocab: Sequence[str],
    config: Mapping[str, Any],
) -> dict[str, Any]:
    """The ``model.pt`` payload: tensors and builtins only, so ``weights_only=True`` loads it."""
    import numpy as np

    return {
        "state_dict": {
            name: tensor.detach().clone() for name, tensor in net.state_dict().items()
        },
        "scaler": {
            "mean": np.asarray(scaler["mean"], dtype=np.float64).tolist(),
            "std": np.asarray(scaler["std"], dtype=np.float64).tolist(),
        },
        "vocab": list(vocab),
        "config": dict(config),
    }


def _run_training(
    dataset: Path,
    floor: str,
    out: Path,
    *,
    model: str,
    target: str,
    epochs: int,
    hidden: int,
    lr: float,
    weight_decay: float,
    min_count: int,
    seed: int,
    features: Sequence[str],
    extra: Mapping[str, npt.NDArray[Any]] | None,
) -> dict[str, object]:
    """The body of :func:`train_eval`, run after the seeds and determinism flags are set."""
    import numpy as np
    import torch

    entries = list(iter_dataset(dataset, floor))
    if not entries:
        raise ValueError(f"dataset {dataset} has no design whose floor {floor!r} is ok")
    train_entries = [entry for entry in entries if entry.split == "train"]
    if not train_entries:
        raise ValueError(
            f"dataset {dataset} has no train design: the vocabulary and scaler come from "
            "the train split"
        )
    data = _fit_dataset(train_entries, entries, target, min_count)
    blocks, extra_width = _extra_blocks(data.prepared, features, extra)
    columns: list[int] = []
    embedding_features: list[str] = []
    for name in features:
        if name == "wl":
            columns.append(1 + WL_EMBEDDING_ROUND)
            embedding_features.append(name)
        elif name == "npn":
            columns.append(0)
            embedding_features.append(name)
    embedding_sizes = _embedding_sizes(data.prepared, columns)
    input_dim = data.in_dim + extra_width + EMBEDDING_DIM * len(columns)
    numeric_width = data.in_dim + extra_width
    config: dict[str, Any] = {
        "floor": floor,
        "model": model,
        "target": target,
        "epochs": epochs,
        "hidden": hidden,
        "lr": lr,
        "weight_decay": weight_decay,
        "min_count": min_count,
        "seed": seed,
        "features": list(features),
        "in_dim": data.in_dim,
        "input_dim": input_dim,
        "embedding_sizes": embedding_sizes,
        "embedding_features": embedding_features,
        "n_classes": len(data.vocab),
    }
    tensors = [(p, _design_tensors(p, blocks.get(p.design), columns)) for p in data.prepared]
    train_pairs = [(p, t) for p, t in tensors if p.split == "train"]
    test_pairs = [(p, t) for p, t in tensors if p.split != "train"]
    net = _net_class()(
        numeric_width, len(data.vocab), kind=model, hidden=hidden, dropout=0.2,
        cat_sizes=embedding_sizes,
    )
    y_train = _stack([p.y for p, _ in train_pairs])
    _fit(
        net, [t for _, t in train_pairs], _class_weights(y_train, len(data.vocab)),
        epochs=epochs, lr=lr, weight_decay=weight_decay,
    )
    train_metrics = _split_metrics(
        [_predict(net, t) for _, t in train_pairs], [p.y for p, _ in train_pairs]
    )
    test_predictions = [_predict(net, t) for _, t in test_pairs]
    test_metrics = _split_metrics(test_predictions, [p.y for p, _ in test_pairs])
    inputs = _numeric_inputs(data.prepared, blocks)
    x_train = _stack([inputs[p.design] for p, _ in train_pairs])
    x_test = _stack([inputs[p.design] for p, _ in test_pairs], width=numeric_width)
    y_test = _stack([p.y for p, _ in test_pairs])
    wl_width = _cat_of(data.prepared[0]).shape[1] - 1 if data.prepared else 0
    wl_train = _stack([np.asarray(_cat_of(p))[:, 1:] for p, _ in train_pairs], width=wl_width)
    wl_test = _stack([np.asarray(_cat_of(p))[:, 1:] for p, _ in test_pairs], width=wl_width)
    n_test = len(test_pairs)
    majority = _round_scores(baseline_majority(y_train, y_test))
    logreg = _round_scores(baseline_logreg(x_train, y_train, x_test, y_test, seed))
    wl = _round_scores(baseline_wl(wl_train, y_train, wl_test, y_test, min_count))
    for scores in (majority, logreg, wl):
        scores["n_designs"] = n_test
    result: dict[str, object] = {
        "model": model,
        "target": target,
        "features": list(features),
        "seed": seed,
        "train": train_metrics,
        "test": test_metrics,
        "baselines": {"majority": majority, "logreg": logreg, "wl": wl},
        "beats_wl": bool(test_metrics["macro_f1"] > wl["macro_f1"]),
        "note": NOTE,
    }
    out.mkdir(parents=True, exist_ok=True)
    (out / "config.json").write_text(dump_json(config), encoding="utf-8")
    (out / "vocab.json").write_text(dump_json(list(data.vocab)), encoding="utf-8")
    (out / "metrics.json").write_text(dump_json(result), encoding="utf-8")
    torch.save(_checkpoint(net, data.scaler, data.vocab, config), out / "model.pt")
    for (p, _), prediction in zip(test_pairs, test_predictions, strict=True):
        _write_predictions(out, p, prediction, data.vocab)
    return result


def train_eval(
    dataset: Path,
    floor: str,
    out: Path,
    *,
    model: str = "sage",
    target: str = "construct_type",
    epochs: int = 100,
    hidden: int = 64,
    lr: float = 0.01,
    weight_decay: float = 5e-4,
    min_count: int = 5,
    seed: int = 0,
    features: Sequence[str] = ("node",),
    extra: Mapping[str, npt.NDArray[Any]] | None = None,
) -> dict[str, object]:
    """Train and evaluate the spec-9 GNN baseline on one dataset floor.

    The split is L0's manifest split: train designs fit the vocabulary, the scaler, the class
    weights and the model; every other design is test. Seeds and
    ``torch.use_deterministic_algorithms(True)`` are set at entry and restored in ``finally``,
    so two runs with the same argument write byte-identical ``metrics.json`` and ``config.json``.

    ``features`` names the structural inputs of spec 9: ``node`` is always the base block,
    ``graphlet`` appends a caller-supplied numeric block per design through ``extra`` (the
    Task 13 runner computes it with :func:`loki.analysis.graphlets.graphlet_features`), and
    ``wl``/``npn`` add size-8 embeddings of the round-2 WL colour and of the NPN id.

    Outputs go directly into ``out``: ``config.json``, ``vocab.json``, ``model.pt`` (tensors and
    builtins only), ``metrics.json`` and ``predictions-<design>.csv`` per test design. The
    returned dict is the parsed ``metrics.json``.
    """
    require("gnn")
    _check_target(target)
    _check_features(features)
    if model not in ("sage", "gcn"):
        raise ValueError(f"unknown model {model!r}: use 'sage' or 'gcn'")
    if epochs < 0:
        raise ValueError(f"epochs must be >= 0, got {epochs}")
    selected = tuple(features)
    import numpy as np
    import torch

    seed_everything = cast(Any, importlib.import_module("torch_geometric")).seed_everything

    saved_python = random.getstate()
    saved_numpy = np.random.get_state()
    saved_torch = torch.random.get_rng_state()
    saved_deterministic = torch.are_deterministic_algorithms_enabled()
    saved_cudnn = (torch.backends.cudnn.deterministic, torch.backends.cudnn.benchmark)
    try:
        seed_everything(seed)
        torch.use_deterministic_algorithms(True)
        return _run_training(
            dataset, floor, out, model=model, target=target, epochs=epochs, hidden=hidden,
            lr=lr, weight_decay=weight_decay, min_count=min_count, seed=seed,
            features=selected, extra=extra,
        )
    finally:
        torch.use_deterministic_algorithms(saved_deterministic)
        torch.backends.cudnn.deterministic, torch.backends.cudnn.benchmark = saved_cudnn
        torch.random.set_rng_state(saved_torch)
        np.random.set_state(saved_numpy)
        random.setstate(saved_python)
