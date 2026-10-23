"""L2 Task 11: GNN data (vocabulary, tensors, baselines; L2 spec 9)."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from typing import Any

from loki.analysis.gnn import (
    LOG1P_COLUMNS,
    OTHER,
    TRAIN_KINDS,
    Prepared,
    baseline_logreg,
    baseline_majority,
    baseline_wl,
    build_id_vocab,
    build_vocab,
    encode,
    fit_scaler,
    metrics,
    prepare,
)
from loki.analysis.graphio import (
    NUMERIC_FEATURES,
    DatasetEntry,
    featurize,
    iter_dataset,
    load_graph,
)
from loki.schemas import dump_json, split_of
from tests.analysis_fixtures import make_dataset, make_graph, write_graph
from tests.helpers import skip_without

_UNLABELLED = "graph has no labels: the GNN needs L0 labels"


def _graph(root: Path, obj: dict[str, Any]) -> Any:
    """Write the fixture object under ``root`` and load it back."""
    return load_graph(write_graph(root, obj))


def _train_scaler(entries: list[DatasetEntry]) -> dict[str, Any]:
    """Fit the scaler on the ``y >= 0`` rows of the train designs, as the trainer does."""
    rows = []
    for entry in entries:
        if entry.split != "train":
            continue
        g = load_graph(entry.graph_path)
        y = encode(g, "construct_type", build_vocab([g], "construct_type", min_count=1))
        rows.append(featurize(g).x[y >= 0])
    return dict(fit_scaler(rows))


@skip_without("numpy", "sklearn")
class GnnDataTest(unittest.TestCase):
    """The eleven tests of plan Task 11 step 1."""

    def test_vocab_train_only_and_other(self) -> None:
        """min_count excludes rare train classes, and a test-only class encodes as ``__other__``."""
        import numpy as np

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            train_obj: Any = make_graph(design="dtr")
            rare = 0
            for node in train_obj["nodes"]:
                label = node["labels"]
                if node["kind"] == "lut" and label["construct_type"] == "$eq" and rare < 3:
                    label["construct_type"] = "$rare"
                    rare += 1
            self.assertEqual(rare, 3)
            g_train = _graph(root / "train", train_obj)
            test_obj: Any = make_graph(design="dte")
            for node in test_obj["nodes"]:
                if node["kind"] == "lut" and node["labels"]["construct_type"] == "$eq":
                    node["labels"]["construct_type"] = "$only_test"
            g_test = _graph(root / "test", test_obj)
        vocab = build_vocab([g_train], "construct_type")
        self.assertEqual(vocab, ["$add", OTHER])
        self.assertNotIn("$eq", vocab)
        self.assertNotIn("$rare", vocab)
        self.assertNotIn("$only_test", vocab)
        exposed = np.asarray(encode(g_train, "construct_type", vocab)).tolist()
        self.assertEqual(
            exposed, [-1, -1, 1, 1, 1, 1, 1, 1, 0, 0, 0, 0, 0, 0, 1, 1, -1]
        )
        unseen = np.asarray(encode(g_test, "construct_type", vocab)).tolist()
        other = len(vocab) - 1
        self.assertEqual(unseen[2:8], [other] * 6)
        self.assertEqual(unseen[8:14], [0] * 6)

    def test_encode_masks_pi_po_const(self) -> None:
        """PI, PO and const nodes are -1; an empty target on a train kind is -1 too."""
        import numpy as np

        with tempfile.TemporaryDirectory() as tmp:
            obj: Any = make_graph()
            obj["nodes"][2]["kind"] = "const"
            obj["nodes"][3]["labels"]["construct_type"] = ""
            g = _graph(Path(tmp), obj)
        vocab = build_vocab([g], "construct_type", min_count=1)
        y = np.asarray(encode(g, "construct_type", vocab))
        self.assertEqual(int(y[0]), -1)  # pi
        self.assertEqual(int(y[1]), -1)  # pi
        self.assertEqual(int(y[2]), -1)  # const, construct_type kept non-empty
        self.assertEqual(int(y[3]), -1)  # lut with an empty construct_type
        self.assertEqual(int(y[16]), -1)  # po
        self.assertIn(str(g.kind[4]), TRAIN_KINDS)
        self.assertGreaterEqual(int(y[4]), 0)
        self.assertEqual(int(y[14]), vocab.index("$dff"))

    def test_unlabelled_graph_raises(self) -> None:
        """Detection is "no train-kind node has a construct_type", not ``labels is None``."""
        import numpy as np

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            empty = load_graph(write_graph(root / "a", make_graph(labels=False)))
            ports: Any = make_graph(design="dports")
            for node in ports["nodes"]:
                if node["kind"] in TRAIN_KINDS:
                    node["labels"]["construct_type"] = ""
            port_labels = _graph(root / "b", ports)
            self.assertIsNone(empty.labels)
            self.assertIsNotNone(port_labels.labels)
            for graph in (empty, port_labels):
                with self.assertRaises(ValueError) as ctx:
                    build_vocab([graph], "construct_type")
                self.assertEqual(str(ctx.exception), _UNLABELLED)
                with self.assertRaises(ValueError) as ctx:
                    encode(graph, "construct_type", [OTHER])
                self.assertEqual(str(ctx.exception), _UNLABELLED)
            scaler = dict(fit_scaler([np.asarray(featurize(empty).x)]))
            for name, path in (("empty", root / "a"), ("ports", root / "b")):
                entry = DatasetEntry(
                    design=name, floor="f2", split="train", graph_path=path / "graph.json"
                )
                with self.assertRaises(ValueError) as ctx:
                    prepare([entry], "construct_type", [OTHER], None, scaler)
                self.assertEqual(str(ctx.exception), _UNLABELLED)

    def test_scaler_fit_on_train_only(self) -> None:
        """Only the train rows reach the scaler; the count columns are log1p first."""
        import numpy as np

        train_a = np.array([[0.0, 0, 0, 0, 0, 0, 0, 0], [3.0, 1, 3, 1, 0, 0, 2, 1]])
        train_b = np.array([[8.0, 0, 0, 0, 1, 0, 0, 0]])
        test_rows = np.array([[1e6] * 8, [5e5] * 8])
        first = fit_scaler([train_a, train_b])
        # The caller passes the train rows only (agent default 1); changing the test rows
        # between the two fits cannot move the mean or the std (the plan's assertion).
        test_rows *= 2.0
        second = fit_scaler([train_a, train_b])
        self.assertEqual(set(first), {"mean", "std"})
        for key in ("mean", "std"):
            np.testing.assert_array_equal(first[key], second[key])
        # The fitted values are the stats of the train rows alone, log1p first.
        train = np.vstack([train_a, train_b])
        for name in LOG1P_COLUMNS:
            column = NUMERIC_FEATURES.index(name)
            train[:, column] = np.log1p(train[:, column])
        spread = train.std(axis=0)
        np.testing.assert_allclose(first["mean"], train.mean(axis=0))
        np.testing.assert_allclose(first["std"], np.where(spread == 0, 1.0, spread))
        self.assertEqual(first["mean"].shape, (len(NUMERIC_FEATURES),))
        log1p_fan_in = np.log1p([0.0, 3.0, 8.0])
        self.assertAlmostEqual(float(first["mean"][0]), float(log1p_fan_in.mean()), places=12)
        self.assertAlmostEqual(float(first["std"][0]), float(log1p_fan_in.std()), places=12)
        is_seq = NUMERIC_FEATURES.index("is_seq")
        self.assertAlmostEqual(float(first["mean"][is_seq]), 1.0 / 3.0)
        self.assertAlmostEqual(float(first["std"][is_seq]), float(np.std([0.0, 0.0, 1.0])))
        constant = NUMERIC_FEATURES.index("is_const")
        self.assertEqual(float(first["mean"][constant]), 0.0)
        self.assertEqual(float(first["std"][constant]), 1.0)

    def test_majority_baseline_value(self) -> None:
        """The majority train class predicts every valid test node; ties pick the lowest id."""
        import numpy as np

        result = baseline_majority(np.array([0, 0, 0, 1]), np.array([0, 1, 1]))
        self.assertEqual(result["n_nodes"], 3)
        self.assertAlmostEqual(result["accuracy"], 1.0 / 3.0)
        self.assertAlmostEqual(result["macro_f1"], 0.25)
        tie = baseline_majority(np.array([1, 1, 0, 0]), np.array([0]))
        self.assertAlmostEqual(tie["accuracy"], 1.0)
        masked = baseline_majority(np.array([0, 0, -1]), np.array([1, -1, 1]))
        self.assertEqual(masked["n_nodes"], 2)
        self.assertAlmostEqual(masked["accuracy"], 0.0)
        self.assertAlmostEqual(masked["macro_f1"], 0.0)

    def test_logreg_baseline_learns_planted_signal(self) -> None:
        """Features-only logistic regression beats the majority on the planted dataset."""
        import numpy as np

        with tempfile.TemporaryDirectory() as tmp:
            root = make_dataset(Path(tmp) / "ds", designs=8)
            entries = list(iter_dataset(root, "f2"))
            train = [entry for entry in entries if entry.split == "train"]
            test = [entry for entry in entries if entry.split == "test"]
            self.assertTrue(train)
            self.assertTrue(test)
            vocab = build_vocab(
                [load_graph(entry.graph_path) for entry in train], "construct_type"
            )
            self.assertIn("$eq", vocab)
            self.assertIn("$add", vocab)
            scaler = _train_scaler(entries)
            prepared = prepare(entries, "construct_type", vocab, None, scaler)
        x_train = np.concatenate([p.x[p.y >= 0] for p in prepared if p.split == "train"])
        y_train = np.concatenate([p.y[p.y >= 0] for p in prepared if p.split == "train"])
        x_test = np.concatenate([p.x[p.y >= 0] for p in prepared if p.split == "test"])
        y_test = np.concatenate([p.y[p.y >= 0] for p in prepared if p.split == "test"])
        majority = baseline_majority(y_train, y_test)
        logreg = baseline_logreg(x_train, y_train, x_test, y_test, seed=0)
        self.assertEqual(int(majority["n_nodes"]), int(y_test.size))
        self.assertGreater(float(logreg["accuracy"]), float(majority["accuracy"]))
        self.assertGreaterEqual(float(logreg["accuracy"]), 0.9)

    def test_metrics_empty(self) -> None:
        """No valid node gives zeros and ``n_nodes`` 0; an empty side gives zeros too."""
        import numpy as np

        empty = np.zeros(0, dtype=np.int64)
        self.assertEqual(metrics(empty, empty), {"accuracy": 0.0, "macro_f1": 0.0, "n_nodes": 0})
        masked = metrics(np.array([-1, -1]), np.array([0, 1]))
        self.assertEqual(masked, {"accuracy": 0.0, "macro_f1": 0.0, "n_nodes": 0})
        wl = np.array([[5, 6], [7, 8], [9, 10]], dtype=np.int64)
        y = np.array([0, 1, 1], dtype=np.int64)
        no_label = np.full(3, -1, dtype=np.int64)
        self.assertEqual(
            baseline_wl(wl, no_label, wl, y), {"accuracy": 0.0, "macro_f1": 0.0, "n_nodes": 3}
        )
        self.assertEqual(
            baseline_wl(wl, y, wl, no_label), {"accuracy": 0.0, "macro_f1": 0.0, "n_nodes": 0}
        )

    def test_split_respected(self) -> None:
        """Designs split exactly as ``split_of``; a non-ok floor entry is absent."""
        with tempfile.TemporaryDirectory() as tmp:
            root = make_dataset(Path(tmp) / "ds", designs=6)
            manifest: Any = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
            manifest["designs"].append(
                {
                    "design": "micro_skip",
                    "benchmark": "micro",
                    "split": "train",
                    "floors": {"f2": {"status": "skipped"}},
                }
            )
            (root / "manifest.json").write_text(dump_json(manifest), encoding="utf-8")
            entries = list(iter_dataset(root, "f2"))
            train = [entry for entry in entries if entry.split == "train"]
            vocab = build_vocab(
                [load_graph(entry.graph_path) for entry in train], "construct_type"
            )
            scaler = _train_scaler(entries)
            prepared = prepare(entries, "construct_type", vocab, None, scaler)
        self.assertEqual([p.design for p in prepared], [entry.design for entry in entries])
        self.assertNotIn("micro_skip", [p.design for p in prepared])
        self.assertEqual({p.split for p in prepared}, {"train", "test"})
        for p, entry in zip(prepared, entries, strict=True):
            self.assertIsInstance(p, Prepared)
            self.assertEqual(p.split, split_of(entry.design))
            self.assertEqual(p.split, entry.split)
            self.assertEqual(p.x.shape[0], len(p.node_ids))
            self.assertEqual(p.y.shape, (len(p.node_ids),))
            self.assertEqual(p.edge_index.shape[0], 2)
            self.assertIsNotNone(p.cat)
        self.assertEqual(
            [p.design for p in prepared if p.split == "train"],
            [entry.design for entry in entries if split_of(entry.design) == "train"],
        )

    def test_wl_baseline_backoff(self) -> None:
        """Last round first, a thin or unseen colour backs off, round 0 counts, then majority."""
        import numpy as np

        next_colour = 1000
        rows: list[list[int]] = []
        labels: list[int] = []
        for _ in range(10):  # global majority class, unique colours everywhere
            rows.append([next_colour + i for i in range(5)])
            next_colour += 10
            labels.append(0)
        round4 = 7
        for _ in range(6):  # seen at round 4 six times, majority class 1
            rows.append([next_colour, next_colour + 1, next_colour + 2, next_colour + 3, round4])
            next_colour += 10
            labels.append(1)
        round2 = 9
        for _ in range(5):  # seen at round 2 five times, majority class 2
            rows.append([next_colour, next_colour + 1, round2, next_colour + 2, next_colour + 3])
            next_colour += 10
            labels.append(2)
        thin4, backoff1 = 11, 12
        for label in (3, 3, 4):  # round-4 colour 11 is thin (3 < min_count), majority class 3
            rows.append([next_colour, backoff1, next_colour + 1, next_colour + 2, thin4])
            next_colour += 10
            labels.append(label)
        for _ in range(3):  # round-1 colour 12 has six train nodes, majority class 4
            rows.append([next_colour, backoff1, next_colour + 1, next_colour + 2,
                         next_colour + 3])
            next_colour += 10
            labels.append(4)
        round0 = 13
        for _ in range(5):  # only the round-0 colour 13 is seen, majority class 4
            rows.append([round0, next_colour, next_colour + 1, next_colour + 2, next_colour + 3])
            next_colour += 10
            labels.append(4)
        wl_train = np.asarray(rows, dtype=np.int64)
        y_train = np.asarray(labels, dtype=np.int64)
        test_rows = [
            [next_colour, next_colour + 1, next_colour + 2, next_colour + 3, round4],
            [next_colour + 4, next_colour + 5, round2, next_colour + 6, next_colour + 7],
            [next_colour + 8, next_colour + 9, next_colour + 10, next_colour + 11,
             next_colour + 12],
            [next_colour + 13, backoff1, next_colour + 14, next_colour + 15, thin4],
            [round0, next_colour + 16, next_colour + 17, next_colour + 18, next_colour + 19],
        ]
        wl_test = np.asarray(test_rows, dtype=np.int64)
        y_test = np.asarray([1, 2, 0, 4, 4], dtype=np.int64)
        result = baseline_wl(wl_train, y_train, wl_test, y_test)
        self.assertEqual(result["n_nodes"], 5)
        self.assertAlmostEqual(result["accuracy"], 1.0)
        self.assertAlmostEqual(result["macro_f1"], 1.0)

    def test_wl_baseline_planted_colour(self) -> None:
        """Labels fixed by the round-1 colour give accuracy 1.0."""
        import numpy as np

        next_colour = 1000
        rows: list[list[int]] = []
        labels: list[int] = []
        for colour, label in ((20, 0), (21, 1)):
            for _ in range(5):
                rows.append(
                    [next_colour, colour, next_colour + 1, next_colour + 2, next_colour + 3]
                )
                next_colour += 10
                labels.append(label)
        wl_train = np.asarray(rows, dtype=np.int64)
        y_train = np.asarray(labels, dtype=np.int64)
        test_rows = [
            [next_colour, 20, next_colour + 1, next_colour + 2, next_colour + 3],
            [next_colour + 10, 20, next_colour + 11, next_colour + 12, next_colour + 13],
            [next_colour + 20, 21, next_colour + 21, next_colour + 22, next_colour + 23],
        ]
        result = baseline_wl(
            wl_train, y_train, np.asarray(test_rows, dtype=np.int64), np.asarray([0, 0, 1])
        )
        self.assertEqual(result["n_nodes"], 3)
        self.assertAlmostEqual(result["accuracy"], 1.0)

    def test_id_vocab_min_count(self) -> None:
        """Ids with at least ``min_count`` train nodes, sorted; ``__other__`` is ``len(vocab)``."""
        import numpy as np

        ids = [np.array([5] * 6 + [7] * 4), np.array([9] * 5 + [-3] * 5)]
        vocab = build_id_vocab(ids, min_count=5)
        self.assertEqual(vocab, {-3: 0, 5: 1, 9: 2})
        self.assertNotIn(7, vocab)
        self.assertNotIn(len(vocab), vocab.values())
        wider = build_id_vocab(ids, min_count=4)
        self.assertEqual(wider, {-3: 0, 5: 1, 7: 2, 9: 3})
