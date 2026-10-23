"""L2 Task 12: GNN training, evaluation and outputs (L2 spec 9)."""

from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path
from typing import Any
from unittest import mock

from loki.analysis import MissingExtra
from loki.analysis.gnn import (
    GRAPHLET_ROLE_NAMES,
    OTHER,
    UNLABELLED_MESSAGE,
    GraphletInput,
    baseline_wl,
    build_id_vocab,
    build_vocab,
    encode,
    graphlet_block,
    graphlet_columns,
    train_eval,
)
from loki.analysis.graphio import NUMERIC_FEATURES, iter_dataset
from loki.schemas import FLOORS, KINDS, dump_json
from tests.analysis_fixtures import make_dataset, make_graph, write_graph
from tests.helpers import skip_without

#: Feature matrix width of the fixture dataset: 8 numeric, 7 kind, 4 floor, 0 hard types + 1.
_FIXTURE_IN_DIM = len(NUMERIC_FEATURES) + len(KINDS) + len(FLOORS) + 1


def _read(path: Path) -> Any:
    """Load one JSON file of the output tree."""
    return json.loads(path.read_text(encoding="utf-8"))


def _run(root: Path, out: Path, **options: Any) -> dict[str, Any]:
    """Run :func:`train_eval` and return the metrics dict."""
    return dict(train_eval(root, "f2", out, **options))


@skip_without("torch", "torch_geometric", "sklearn")
class GnnTrainTest(unittest.TestCase):
    """The twelve tests of plan Task 12 step 1."""

    def test_trains_above_majority(self) -> None:
        """Both models beat the majority baseline on test and reach 0.9 accuracy on train."""
        with tempfile.TemporaryDirectory() as tmp:
            root = make_dataset(Path(tmp) / "ds", designs=8)
            for kind in ("sage", "gcn"):
                result = _run(root, Path(tmp) / kind, model=kind)
                self.assertGreater(
                    result["test"]["accuracy"], result["baselines"]["majority"]["accuracy"]
                )
                self.assertGreaterEqual(result["train"]["accuracy"], 0.9)

    def test_deterministic_metrics(self) -> None:
        """Two runs with the same seed write byte-identical metrics and config."""
        with tempfile.TemporaryDirectory() as tmp:
            root = make_dataset(Path(tmp) / "ds", designs=8)
            first = _run(root, Path(tmp) / "a", epochs=30)
            second = _run(root, Path(tmp) / "b", epochs=30)
            self.assertEqual(first, second)
            for name in ("metrics.json", "config.json"):
                self.assertEqual(
                    (Path(tmp) / "a" / name).read_bytes(), (Path(tmp) / "b" / name).read_bytes()
                )

    def test_outputs_complete(self) -> None:
        """The five output kinds exist; predictions have the header; metrics has its keys."""
        with tempfile.TemporaryDirectory() as tmp:
            root = make_dataset(Path(tmp) / "ds", designs=8)
            out = Path(tmp) / "out"
            _run(root, out, epochs=10)
            for name in ("config.json", "vocab.json", "model.pt", "metrics.json"):
                self.assertTrue((out / name).is_file(), name)
            test_entries = [entry for entry in iter_dataset(root, "f2") if entry.split != "train"]
            self.assertTrue(test_entries)
            for entry in test_entries:
                path = out / f"predictions-{entry.design}.csv"
                self.assertTrue(path.is_file(), entry.design)
                self.assertEqual(path.read_text(encoding="utf-8").splitlines()[0],
                                 "node_id,true,pred")
            metrics = _read(out / "metrics.json")
            for key in ("train", "test", "baselines", "note"):
                self.assertIn(key, metrics)
            self.assertIn("majority", metrics["baselines"])
            self.assertIn("logreg", metrics["baselines"])
            for split in ("train", "test"):
                for key in ("accuracy", "macro_f1", "n_nodes", "n_designs"):
                    self.assertIn(key, metrics[split])
            import torch

            payload = torch.load(out / "model.pt", weights_only=True)
            for key in ("state_dict", "scaler", "vocab", "config"):
                self.assertIn(key, payload)
            self.assertEqual(payload["vocab"], _read(out / "vocab.json"))

    def test_target_role(self) -> None:
        """``target="role"`` trains on the role answer key and records it in the config."""
        with tempfile.TemporaryDirectory() as tmp:
            root = make_dataset(Path(tmp) / "ds", designs=8)
            out = Path(tmp) / "out"
            result = _run(root, out, target="role", epochs=10)
            config = _read(out / "config.json")
            self.assertEqual(config["target"], "role")
            vocab = _read(out / "vocab.json")
            self.assertEqual(vocab[-1], OTHER)
            self.assertIn("datapath", vocab)
            self.assertGreater(result["train"]["n_nodes"], 0)

    def test_other_class_for_unseen(self) -> None:
        """A class planted only in a test design is encoded as ``__other__`` in the predictions."""
        with tempfile.TemporaryDirectory() as tmp:
            root = make_dataset(Path(tmp) / "ds", designs=8)
            test_entries = [entry for entry in iter_dataset(root, "f2") if entry.split != "train"]
            self.assertTrue(test_entries)
            target = test_entries[0]
            graph: Any = json.loads(target.graph_path.read_text(encoding="utf-8"))
            planted = 0
            for node in graph["nodes"]:
                labels = node["labels"]
                if node["kind"] == "lut" and labels["construct_type"] == "$eq":
                    labels["construct_type"] = "$only_test"
                    planted += 1
            self.assertGreater(planted, 0)
            target.graph_path.write_text(dump_json(graph), encoding="utf-8")
            out = Path(tmp) / "out"
            _run(root, out, epochs=10)
            self.assertNotIn("$only_test", _read(out / "vocab.json"))
            with (out / f"predictions-{target.design}.csv").open(encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))
            unseen = [row for row in rows if row["true"] == OTHER]
            self.assertEqual(len(unseen), planted)
            for row in rows:
                self.assertNotEqual(row["true"], "$only_test")
                self.assertNotEqual(row["pred"], "$only_test")

    def test_no_label_columns_in_input_dim(self) -> None:
        """``in_dim`` is the Task 2 feature matrix width, never a label column."""
        with tempfile.TemporaryDirectory() as tmp:
            root = make_dataset(Path(tmp) / "ds", designs=8)
            out = Path(tmp) / "out"
            _run(root, out, epochs=5)
            config = _read(out / "config.json")
            self.assertEqual(config["in_dim"], _FIXTURE_IN_DIM)
            self.assertEqual(config["features"], ["node"])

    def test_unlabelled_dataset_raises(self) -> None:
        """A dataset without L0 labels is refused with the spec 9 message."""
        with tempfile.TemporaryDirectory() as tmp:
            root = make_dataset(Path(tmp) / "ds", designs=4)
            for entry in iter_dataset(root, "f2"):
                write_graph(
                    entry.graph_path.parent,
                    make_graph(floor="f2", design=entry.design, labels=False),
                )
            with self.assertRaises(ValueError) as ctx:
                _run(root, Path(tmp) / "out", epochs=1)
            self.assertEqual(str(ctx.exception), UNLABELLED_MESSAGE)

    def test_no_test_designs_ok(self) -> None:
        """An all-train dataset gives an empty test split instead of a crash."""
        with tempfile.TemporaryDirectory() as tmp:
            root = make_dataset(Path(tmp) / "ds", designs=8)
            manifest = _read(root / "manifest.json")
            for design in manifest["designs"]:
                design["split"] = "train"
            (root / "manifest.json").write_text(dump_json(manifest), encoding="utf-8")
            out = Path(tmp) / "out"
            result = _run(root, out, epochs=10)
            self.assertEqual(result["test"]["n_nodes"], 0)
            self.assertEqual(result["test"]["n_designs"], 0)
            self.assertGreater(result["train"]["n_nodes"], 0)
            self.assertIs(result["beats_wl"], False)
            self.assertEqual(list(out.glob("predictions-*.csv")), [])

    def test_missing_extra_message(self) -> None:
        """``train_eval`` asks for the gnn extra first and lets ``MissingExtra`` through."""
        with tempfile.TemporaryDirectory() as tmp:
            root = make_dataset(Path(tmp) / "ds", designs=4)
            message = "this needs the 'gnn' extra: pip install 'loki[gnn]'"
            with (
                mock.patch("loki.analysis.gnn.require", side_effect=MissingExtra(message)),
                self.assertRaises(MissingExtra) as ctx,
            ):
                _run(root, Path(tmp) / "out")
            self.assertIn("loki[gnn]", str(ctx.exception))

    def test_metrics_wl_baseline_and_beats_wl(self) -> None:
        """``baselines.wl`` carries both scores and ``beats_wl`` compares the same numbers."""
        with tempfile.TemporaryDirectory() as tmp:
            root = make_dataset(Path(tmp) / "ds", designs=8)
            out = Path(tmp) / "out"
            result = _run(root, out, epochs=30)
            wl = result["baselines"]["wl"]
            self.assertIn("accuracy", wl)
            self.assertIn("macro_f1", wl)
            self.assertIsInstance(result["beats_wl"], bool)
            self.assertEqual(
                result["beats_wl"],
                result["test"]["macro_f1"] > wl["macro_f1"],
            )
            self.assertEqual(_read(out / "metrics.json"), result)

    def test_features_wl_npn_embeddings(self) -> None:
        """``wl`` and ``npn`` add size-8 embeddings over train vocabularies."""
        with tempfile.TemporaryDirectory() as tmp:
            root = make_dataset(Path(tmp) / "ds", designs=8)
            out = Path(tmp) / "out"
            result = _run(root, out, epochs=10, features=("node", "wl", "npn"))
            config = _read(out / "config.json")
            self.assertEqual(config["features"], ["node", "wl", "npn"])
            sizes = config["embedding_sizes"]
            self.assertIsInstance(sizes, list)
            self.assertEqual(len(sizes), 2)
            for size in sizes:
                self.assertGreaterEqual(int(size), 1)
            self.assertEqual(config["in_dim"], _FIXTURE_IN_DIM)
            self.assertEqual(
                config["input_dim"], _FIXTURE_IN_DIM + 8 * len(sizes)
            )
            self.assertGreater(result["train"]["n_nodes"], 0)

    def test_default_features_node_only(self) -> None:
        """The default features are the node block alone, with no embeddings."""
        with tempfile.TemporaryDirectory() as tmp:
            root = make_dataset(Path(tmp) / "ds", designs=8)
            out = Path(tmp) / "out"
            _run(root, out, epochs=5)
            config = _read(out / "config.json")
            self.assertEqual(config["features"], ["node"])
            self.assertEqual(config["embedding_sizes"], [])
            self.assertEqual(config["input_dim"], _FIXTURE_IN_DIM)

    def test_wl_baseline_uses_raw_ids(self) -> None:
        """A thin colour keeps its backoff: raw ids score 1.0 where merged mapped ids score 0."""
        import numpy as np

        raw_train = np.array([[100]] * 10 + [[200]] * 3 + [[300]] * 3, dtype=np.int64)
        y_train = np.array([0] * 10 + [1] * 6, dtype=np.int64)
        raw_test = np.array([[200]] * 3 + [[300]] * 3, dtype=np.int64)
        y_test = np.zeros(6, dtype=np.int64)
        raw = baseline_wl(raw_train, y_train, raw_test, y_test, min_count=5)
        self.assertEqual(raw["accuracy"], 1.0)
        vocabulary = build_id_vocab([raw_train[:, 0]], min_count=5)
        self.assertEqual(vocabulary, {100: 0})
        mapped_train = np.array(
            [vocabulary.get(int(value), len(vocabulary)) for value in raw_train[:, 0]],
            dtype=np.int64,
        ).reshape(-1, 1)
        mapped_test = np.array(
            [vocabulary.get(int(value), len(vocabulary)) for value in raw_test[:, 0]],
            dtype=np.int64,
        ).reshape(-1, 1)
        merged = baseline_wl(mapped_train, y_train, mapped_test, y_test, min_count=5)
        self.assertEqual(merged["accuracy"], 0.0)
        self.assertNotEqual(raw, merged)

    def test_baseline_reads_raw_colours(self) -> None:
        """``train_eval`` feeds ``baseline_wl`` the dataset's raw colours, not the mapped ids."""
        import numpy as np

        from loki.analysis.graphio import load_graph
        from loki.analysis.structural import compute_structural

        with tempfile.TemporaryDirectory() as tmp:
            root = make_dataset(Path(tmp) / "ds", designs=8)
            entries = list(iter_dataset(root, "f2"))
            graphs = {entry.design: load_graph(entry.graph_path) for entry in entries}
            train = [entry for entry in entries if entry.split == "train"]
            test = [entry for entry in entries if entry.split != "train"]
            self.assertTrue(train)
            self.assertTrue(test)
            vocab = build_vocab([graphs[entry.design] for entry in train], "construct_type", 5)
            wl_train = np.concatenate(
                [compute_structural(graphs[entry.design]).wl for entry in train]
            )
            wl_test = np.concatenate(
                [compute_structural(graphs[entry.design]).wl for entry in test]
            )
            y_train = np.concatenate(
                [encode(graphs[entry.design], "construct_type", vocab) for entry in train]
            )
            y_test = np.concatenate(
                [encode(graphs[entry.design], "construct_type", vocab) for entry in test]
            )
            expected = baseline_wl(wl_train, y_train, wl_test, y_test, min_count=5)
            with mock.patch("loki.analysis.gnn.baseline_wl", wraps=baseline_wl) as spy:
                result = _run(root, Path(tmp) / "out", epochs=10)
            captured_train, captured_test = spy.call_args.args[0], spy.call_args.args[2]
            np.testing.assert_array_equal(captured_train, wl_train)
            np.testing.assert_array_equal(captured_test, wl_test)
            wl = result["baselines"]["wl"]
            self.assertGreater(result["test"]["n_nodes"], 0)
            self.assertEqual(wl["accuracy"], round(expected["accuracy"], 4))
            self.assertEqual(wl["macro_f1"], round(expected["macro_f1"], 4))
            self.assertEqual(wl["n_nodes"], expected["n_nodes"])

    def test_graphlet_block_fixed_train_columns(self) -> None:
        """One train-selected orbit set keeps the block width when graphs drop different columns."""
        import numpy as np

        from loki.analysis.graphlets import graphlet_features

        roles = np.zeros((3, 4), dtype=np.int64)
        orbits_a = np.array([[0, 7, 0], [1, 7, 0], [2, 7, 0]], dtype=np.int64)
        orbits_b = np.array([[0, 0, 3], [1, 0, 4], [2, 0, 5]], dtype=np.int64)
        self.assertEqual(graphlet_features(orbits_a, roles).shape[1], 5)
        self.assertEqual(graphlet_features(orbits_b, roles).shape[1], 6)
        train = GraphletInput(orbits=orbits_a, roles=roles)
        columns = graphlet_columns([train])
        self.assertEqual(columns, (0,))
        block_a = graphlet_block(train, columns)
        block_b = graphlet_block(GraphletInput(orbits=orbits_b, roles=roles), columns)
        self.assertEqual(block_a.shape, (3, 5))
        self.assertEqual(block_b.shape, (3, 5))
        expected = np.log1p(orbits_b[:, 0].astype(np.float64))
        expected = (expected - expected.mean()) / expected.std()
        np.testing.assert_allclose(block_b[:, 0], expected)
        np.testing.assert_array_equal(block_b[:, 1:], roles)

    def test_graphlet_extra_aligned_across_designs(self) -> None:
        """Designs whose ``graphlet_features`` widths differ train on one fixed block width."""
        import numpy as np

        from loki.analysis.graphio import load_graph
        from loki.analysis.graphlets import graphlet_features

        with tempfile.TemporaryDirectory() as tmp:
            root = make_dataset(Path(tmp) / "ds", designs=8)
            entries = list(iter_dataset(root, "f2"))
            extra: dict[str, Any] = {}
            widths: set[int] = set()
            for position, entry in enumerate(entries):
                n = load_graph(entry.graph_path).n_nodes
                orbits = np.zeros((n, 2), dtype=np.int64)
                orbits[:, 0] = np.arange(n)
                orbits[:, 1] = (np.arange(n) + position) * (position % 2)
                roles = np.zeros((n, 4), dtype=np.int64)
                extra[entry.design] = GraphletInput(orbits=orbits, roles=roles)
                widths.add(graphlet_features(orbits, roles).shape[1])
            self.assertGreater(len(widths), 1)
            columns = graphlet_columns([extra[entry.design] for entry in entries
                                        if entry.split == "train"])
            out = Path(tmp) / "out"
            result = _run(root, out, epochs=3, features=("node", "graphlet"), extra=extra)
            config = _read(out / "config.json")
            self.assertEqual(
                config["graphlet_columns"],
                [f"orbit:{column}" for column in columns]
                + [f"role:{name}" for name in GRAPHLET_ROLE_NAMES],
            )
            self.assertEqual(config["input_dim"], _FIXTURE_IN_DIM + len(columns) + 4)
            self.assertGreater(result["train"]["n_nodes"], 0)

    def test_rng_state_restored_completely(self) -> None:
        """The CUDA generator states and the ``warn_only`` bit are restored, not only CPU RNGs."""
        import torch

        with tempfile.TemporaryDirectory() as tmp:
            root = make_dataset(Path(tmp) / "ds", designs=4)
            cuda_state = [object()]
            torch.use_deterministic_algorithms(False, warn_only=True)
            try:
                with (
                    mock.patch.object(torch.cuda, "is_available", return_value=True),
                    mock.patch.object(torch.cuda, "manual_seed_all"),
                    mock.patch.object(
                        torch.cuda, "get_rng_state_all", return_value=cuda_state
                    ) as get_state,
                    mock.patch.object(torch.cuda, "set_rng_state_all") as set_state,
                ):
                    _run(root, Path(tmp) / "out", epochs=1)
                get_state.assert_called_once_with()
                set_state.assert_called_once_with(cuda_state)
                self.assertFalse(torch.are_deterministic_algorithms_enabled())
                self.assertTrue(torch.is_deterministic_algorithms_warn_only_enabled())
            finally:
                torch.use_deterministic_algorithms(False)
