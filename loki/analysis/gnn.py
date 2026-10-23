"""GNN data preparation and baselines (L2 spec section 9).

The trainer of Task 12 never reads a ``graph.json`` itself: this module turns the dataset split
of L0 into :class:`Prepared` tensors (standardised features, edge list, target indices,
categorical NPN and WL ids) and provides the three baselines the GNN must be read against: the
majority class, features-only logistic regression and the 1-WL colour lookup of spec 9.

Labels are an answer key: only nodes of kind :data:`TRAIN_KINDS` with a non-empty target enter
the vocabulary, the loss and the metrics; PI, PO and constants are trivially labelled and would
inflate accuracy. The vocabulary and the scaler come from the train designs only, so a class
first seen in a test design maps to ``__other__`` and the test data cannot move the scaler.

An unlabelled graph is detected by the spec-9 rule "no node of :data:`TRAIN_KINDS` carries a
non-empty ``construct_type``", not by ``Graph.labels is None`` (Task 2 documents ``None`` as
"every label object is empty"; a from-blif graph labels its ports only and is refused here while
cluster and export accept it).

numpy and scikit-learn belong to the ``analysis`` extra and are imported inside functions after
:func:`loki.analysis.require`, so importing this module needs the standard library only.
scikit-learn has no type marker, so it is imported through :func:`importlib.import_module`.
"""

from __future__ import annotations

import importlib
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, Any

from loki.analysis import require
from loki.analysis.graphio import NUMERIC_FEATURES, Graph, featurize, load_graph
from loki.analysis.graphlets import gsn_features
from loki.analysis.structural import compute_structural

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence

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
) -> list[Prepared]:
    """The per-design tensors of spec 9 for ``entries`` (an :func:`iter_dataset` run).

    ``vocab`` and ``scaler`` come from the train designs; ``hard_types`` is the hard-cell type
    vocabulary the scaler was fitted with. The categorical NPN and WL ids are mapped through id
    vocabularies built from the train designs only; a graph without L0 labels raises
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
            [cat[:, column] for cat, p in zip(cats, prepared, strict=True) if p.split == "train"]
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
    """For each sorted unique id: its majority class (lowest wins a tie) and node count."""
    import numpy as np

    unique, inverse = np.unique(ids, return_inverse=True)
    n_classes = int(labels.max()) + 1 if labels.size else 0
    flat = inverse.astype(np.int64) * n_classes + labels.astype(np.int64)
    counts = np.bincount(flat, minlength=unique.size * n_classes).reshape(unique.size, n_classes)
    return unique, counts.argmax(axis=1).astype(np.int64), counts.sum(axis=1)


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
    Only nodes with ``y >= 0`` are used.
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
    if scored_test.size == 0:
        return _zero_metrics(0)
    predicted = np.full(scored_test.size, -1, dtype=np.int64)
    if scored_train.size:
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
        fallback = int(np.argmax(np.bincount(scored_train))) if scored_train.size else 0
        predicted[unfilled] = fallback
    return metrics(scored_test, predicted)
