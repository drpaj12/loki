"""L2 Task 13: the runner and the ``loki analyze`` CLI (L2 spec sections 10 and 11)."""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import importlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from typing import TYPE_CHECKING, Any
from unittest import mock

from loki.analysis import MissingExtra
from loki.analysis.graphlets import BACKENDS, DEFAULT_BACKEND, N_ORBITS
from loki.analysis.graphlets.ext import ORCA_CITATION, ORCA_LICENCE, OrcaCounter
from loki.analysis.run import main
from tests.analysis_fixtures import make_dataset, make_graph, write_graph
from tests.graphlet_oracle import brute_orbits
from tests.helpers import skip_without

if TYPE_CHECKING:
    from collections.abc import Mapping

    import numpy.typing as npt


class _FakeCounter:
    """The 4-node oracle registered under the default backend's key (plan Task 10)."""

    name = DEFAULT_BACKEND
    max_size = 5
    commit = "0" * 40
    sha256 = "1" * 64
    licence = "test only"

    def __init__(self) -> None:
        self.calls = 0

    def available(self) -> tuple[bool, str]:
        """Always installed: the oracle is Python."""
        return True, ""

    def count(
        self, n: int, src: npt.NDArray[Any], dst: npt.NDArray[Any], size: int = 4
    ) -> npt.NDArray[Any]:
        """The oracle's counts; size 5 is zero-filled because the oracle is 4-node only."""
        import numpy as np

        self.calls += 1
        if size == 5:
            return np.zeros((n, N_ORBITS[5]), dtype=np.int64)
        return brute_orbits(n, src, dst)


def run(argv: list[str]) -> tuple[int, str, str]:
    """Run ``loki analyze`` in process; return (exit code, stdout, stderr)."""
    out = io.StringIO()
    err = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = main(argv)
    return code, out.getvalue(), err.getvalue()


def tree_hash(root: Path) -> dict[str, str]:
    """Every file under ``root`` mapped to the sha256 of its bytes."""
    return {
        str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


@skip_without("numpy", "scipy", "sklearn", "networkx")
class AnalysisCliTest(unittest.TestCase):
    """The nineteen Task-13 tests of the plan, one per CLI contract."""

    def graph(self, root: Path, **kwargs: Any) -> Path:
        """A single-design fixture ``graph.json`` under ``root/graph``."""
        return write_graph(root / "graph", make_graph(**kwargs))

    def register_fake(self) -> _FakeCounter:
        """Register a :class:`_FakeCounter` as the default backend for this test."""
        counter = _FakeCounter()
        previous = BACKENDS.get(DEFAULT_BACKEND)
        BACKENDS[DEFAULT_BACKEND] = counter

        def restore() -> None:
            if previous is None:
                BACKENDS.pop(DEFAULT_BACKEND, None)
            else:
                BACKENDS[DEFAULT_BACKEND] = previous

        self.addCleanup(restore)
        return counter

    def assert_numbers(self, obj: Mapping[str, Any]) -> None:
        """Every value of ``metrics.json`` is a number (never a bool or ``None``)."""
        for key, value in obj.items():
            self.assertIsInstance(value, (int, float), key)
            self.assertNotIsInstance(value, bool, key)

    @skip_without("torch", "torch_geometric")
    def test_export_all_formats(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = self.graph(root)
            out = root / "out"
            code, _text, err = run(
                ["export", "--graph", str(path), "--format", "edgelist,graphml,pyg",
                 "--out", str(out)]
            )
            self.assertEqual(code, 0, err)
            files = out / "d" / "f2" / "export"
            for name in (
                "whole.edges.tsv", "whole.nodes.tsv", "whole.graphml", "whole.pt",
            ):
                self.assertTrue((files / name).is_file(), name)
            metrics: Any = json.loads((out / "metrics.json").read_text(encoding="utf-8"))
            self.assert_numbers(metrics)
            self.assertEqual(metrics["files"], 4)

    @skip_without("torch", "torch_geometric")
    def test_export_dataset_split_key(self) -> None:
        """A dataset export writes the manifest split (spec 5); a bare graph export omits it."""
        torch: Any = importlib.import_module("torch")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            dataset = make_dataset(root / "ds", designs=4)
            out = root / "out"
            code, _text, err = run(
                ["export", "--dataset", str(dataset), "--design", "micro_a0",
                 "--floor", "f2", "--format", "pyg", "--out", str(out)]
            )
            self.assertEqual(code, 0, err)
            payload: Any = torch.load(
                out / "micro_a0" / "f2" / "export" / "whole.pt", weights_only=True
            )
            manifest: Any = json.loads(
                (dataset / "manifest.json").read_text(encoding="utf-8")
            )
            split = next(
                entry["split"] for entry in manifest["designs"]
                if entry["design"] == "micro_a0"
            )
            self.assertEqual(payload["split"], split)
            plain = root / "plain"
            code, _text, err = run(
                ["export", "--graph", str(self.graph(root)), "--format", "pyg",
                 "--out", str(plain)]
            )
            self.assertEqual(code, 0, err)
            without: Any = torch.load(
                plain / "d" / "f2" / "export" / "whole.pt", weights_only=True
            )
            self.assertNotIn("split", without)

    def test_export_region_cone(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = self.graph(root)
            out = root / "out"
            code, _text, err = run(
                ["export", "--graph", str(path), "--format", "edgelist",
                 "--region", "cone:n10:in:2", "--out", str(out)]
            )
            self.assertEqual(code, 0, err)
            names = sorted(p.name for p in (out / "d" / "f2" / "export").iterdir())
            self.assertEqual(len(names), 2)
            stem = names[0].split(".")[0]
            self.assertRegex(stem, r"^region-[0-9a-f]{8}$")
            self.assertEqual(names[1].split(".")[0], stem)

    def test_cluster_all_four_files_and_metrics_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = self.graph(root)
            out = root / "out"
            code, _text, err = run(
                ["cluster", "--graph", str(path), "--method", "all", "--out", str(out)]
            )
            self.assertEqual(code, 0, err)
            names = sorted(p.name for p in (out / "d" / "f2" / "partition").iterdir())
            prefixes = {name.split("-", 1)[0] for name in names}
            self.assertEqual(prefixes, {"kmeans", "affinity", "spectral", "louvain"})
            metrics: Any = json.loads((out / "metrics.json").read_text(encoding="utf-8"))
            self.assert_numbers(metrics)
            self.assertIn("n_clusters_kmeans", metrics)
            self.assertIn("modularity_louvain", metrics)

    def test_cluster_with_graphlet_features(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = self.graph(root)
            out = root / "out"
            counter = self.register_fake()
            argv = ["cluster", "--graph", str(path), "--method", "kmeans",
                    "--features", "node,graphlet", "--out", str(out)]
            code, _text, err = run(argv)
            self.assertEqual(code, 0, err)
            orbit_file = out / "d" / "f2" / "graphlets" / "orbits-ext-global.npz"
            self.assertTrue(orbit_file.is_file())
            self.assertEqual(counter.calls, 1)
            code, _text, err = run(argv)
            self.assertEqual(code, 0, err)
            self.assertEqual(counter.calls, 1)

    def test_graphlets_ext_missing_exit_3(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = self.graph(root)
            out = root / "out"
            previous = BACKENDS.get(DEFAULT_BACKEND)
            BACKENDS[DEFAULT_BACKEND] = OrcaCounter()

            def restore() -> None:
                if previous is None:
                    BACKENDS.pop(DEFAULT_BACKEND, None)
                else:
                    BACKENDS[DEFAULT_BACKEND] = previous

            self.addCleanup(restore)
            with mock.patch(
                "loki.analysis.graphlets.ext.find_orca", return_value=None
            ):
                code, _text, err = run(["graphlets", "--graph", str(path), "--out", str(out)])
            self.assertEqual(code, 3, err)
            self.assertIn("run: loki tools fetch-orca", err)

    def test_graphlets_removal_none_size5_exit_3(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = self.graph(root)
            out = root / "out"
            self.register_fake()
            code, _text, err = run(
                ["graphlets", "--graph", str(path), "--size", "5", "--removal", "none",
                 "--out", str(out)]
            )
            self.assertEqual(code, 3, err)
            self.assertIn("--force", err)

    def test_backend_names_unknown_exit_2_own_exit_3(self) -> None:
        """An unknown name is usage (2); the unbuilt optional own backend is unavailable (3)."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = self.graph(root)
            out = root / "out"
            code, _text, err = run(
                ["graphlets", "--graph", str(path), "--backend", "own", "--out", str(out)]
            )
            self.assertEqual(code, 3, err)
            self.assertIn("'own' is not built", err)
            self.assertNotIn("unknown graphlet backend", err)
            code, _text, err = run(
                ["cluster", "--graph", str(path), "--features", "node,graphlet",
                 "--backend", "bogus", "--out", str(out)]
            )
            self.assertEqual(code, 2, err)
            self.assertIn("unknown graphlet backend 'bogus'", err)

    def test_backend_runtime_error_exit_1(self) -> None:
        """A backend RuntimeError is one line on stderr and exit 1, never a traceback."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = self.graph(root)
            counter = self.register_fake()
            failure = RuntimeError("ORCA failed (exit 1): boom")
            with mock.patch.object(counter, "count", side_effect=failure):
                code, _text, err = run(
                    ["graphlets", "--graph", str(path), "--out", str(root / "out")]
                )
            self.assertEqual(code, 1, err)
            self.assertEqual(err.strip(), "loki analyze: ORCA failed (exit 1): boom")

    def test_graphlets_metrics_keys(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = self.graph(root)
            out = root / "out"
            self.register_fake()
            code, _text, err = run(["graphlets", "--graph", str(path), "--out", str(out)])
            self.assertEqual(code, 0, err)
            metrics: Any = json.loads((out / "metrics.json").read_text(encoding="utf-8"))
            self.assert_numbers(metrics)
            for key in (
                "removed_edges_total", "dropped_hubs", "clock_domains", "nodes", "edges",
                "seconds",
            ):
                self.assertIn(key, metrics)
            graphlets = out / "d" / "f2" / "graphlets"
            self.assertTrue((graphlets / "orbits-ext-global.npz").is_file())
            self.assertTrue((graphlets / "graphlets-ext-global.json").is_file())

    def test_licence_flag_prints_gpl_notice(self) -> None:
        code, text, err = run(["graphlets", "--licence"])
        self.assertEqual(code, 0, err)
        self.assertIn(ORCA_LICENCE, text)
        self.assertIn(ORCA_CITATION, text)
        self.assertIn("GPL-3.0", text)

    @skip_without("torch", "torch_geometric")
    def test_gnn_metrics_json_keys(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            dataset = make_dataset(root / "ds", designs=6)
            out = root / "out"
            code, _text, err = run(
                ["gnn", "--dataset", str(dataset), "--floor", "f2", "--epochs", "1",
                 "--out", str(out)]
            )
            self.assertEqual(code, 0, err)
            metrics: Any = json.loads((out / "metrics.json").read_text(encoding="utf-8"))
            self.assert_numbers(metrics)
            for key in ("test_accuracy", "test_macro_f1", "baseline_majority_accuracy"):
                self.assertIn(key, metrics)
            self.assertTrue((out / "gnn" / "config.json").is_file())

    def test_public_run_gnn_delegates_to_runner(self) -> None:
        """``loki.analysis.gnn.run_gnn`` is the spec-10 public entry point of the gnn kind."""
        gnn: Any = importlib.import_module("loki.analysis.gnn")
        runner: Any = importlib.import_module("loki.analysis.run")
        args = argparse.Namespace()
        with mock.patch.object(runner, "run_gnn", return_value=7) as handler:
            self.assertEqual(gnn.run_gnn(args), 7)
        handler.assert_called_once_with(args)

    def test_missing_extra_exit_3(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = self.graph(root)
            out = root / "out"
            missing = MissingExtra("this needs the 'analysis' extra: pip install "
                                   "'loki[analysis]'")
            with mock.patch("loki.analysis.run.require", side_effect=missing):
                code, _text, err = run(["export", "--graph", str(path), "--out", str(out)])
            self.assertEqual(code, 3, err)
            self.assertIn("loki[analysis]", err)

    def test_bad_args_exit_2(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = self.graph(root)
            out = root / "out"
            self.assertEqual(run(["bogus"])[0], 2)
            self.assertEqual(
                run(["cluster", "--graph", str(path), "--method", "nope",
                     "--out", str(out)])[0],
                2,
            )
            self.assertEqual(
                run(["export", "--graph", str(path), "--dataset", str(root),
                     "--design", "d", "--floor", "f2", "--out", str(out)])[0],
                2,
            )

    def test_failure_exit_1(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = self.graph(root)
            out = root / "out"
            with mock.patch("loki.analysis.cluster._affinity_attempt", return_value=None):
                code, _text, err = run(
                    ["cluster", "--graph", str(path), "--method", "affinity",
                     "--out", str(out)]
                )
            self.assertEqual(code, 1, err)
            self.assertIn("affinity propagation did not converge", err)
            bad = root / "bad.json"
            bad.write_text("{}", encoding="utf-8")
            code, _text, err = run(["export", "--graph", str(bad), "--out", str(out)])
            self.assertEqual(code, 1, err)
            self.assertEqual(len(err.strip().splitlines()), 1)

    def test_deterministic_rerun_byte_identical(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = self.graph(root)
            first = root / "first"
            second = root / "second"
            for out in (first, second):
                code, _text, err = run(
                    ["cluster", "--graph", str(path), "--method", "all", "--out", str(out)]
                )
                self.assertEqual(code, 0, err)
            left = {p.name: p.read_bytes() for p in (first / "d" / "f2" / "partition").iterdir()}
            right = {
                p.name: p.read_bytes() for p in (second / "d" / "f2" / "partition").iterdir()
            }
            self.assertEqual(left, right)
            self.assertEqual(
                (first / "metrics.json").read_bytes(), (second / "metrics.json").read_bytes()
            )

    def test_unlabelled_graph_json_cluster_and_export_ok(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = self.graph(root, labels=False)
            out = root / "out"
            code, _text, err = run(
                ["cluster", "--graph", str(path), "--method", "kmeans", "--out", str(out)]
            )
            self.assertEqual(code, 0, err)
            code, _text, err = run(
                ["export", "--graph", str(path), "--format", "edgelist", "--out", str(out)]
            )
            self.assertEqual(code, 0, err)
            partition = next((out / "d" / "f2" / "partition").iterdir())
            obj: Any = json.loads(partition.read_text(encoding="utf-8"))
            self.assertIsNone(obj["quality"]["nmi_module_path"])
            self.assertIsNone(obj["quality"]["nmi_construct_type"])
            metrics: Any = json.loads((out / "metrics.json").read_text(encoding="utf-8"))
            self.assert_numbers(metrics)

    def test_never_writes_in_dataset_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            dataset = make_dataset(root / "ds", designs=2)
            before = tree_hash(dataset)
            out = root / "out"
            argv = ["--dataset", str(dataset), "--design", "micro_a0", "--floor", "f2"]
            code, _text, err = run(["export", *argv, "--format", "edgelist", "--out",
                                    str(out / "export")])
            self.assertEqual(code, 0, err)
            code, _text, err = run(["cluster", *argv, "--method", "kmeans", "--out",
                                    str(out / "cluster")])
            self.assertEqual(code, 0, err)
            self.assertEqual(tree_hash(dataset), before)

    def test_structural_kind_outputs(self) -> None:
        np: Any = importlib.import_module("numpy")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = self.graph(root)
            out = root / "out"
            code, _text, err = run(["structural", "--graph", str(path), "--out", str(out)])
            self.assertEqual(code, 0, err)
            files = out / "d" / "f2" / "structural"
            npz = files / "structural-npn-both.npz"
            record_path = files / "structural-npn-both.json"
            self.assertTrue(npz.is_file())
            self.assertTrue(record_path.is_file())
            with np.load(npz) as data:
                self.assertEqual(data["wl"].shape, (17, 5))
                self.assertEqual(data["npn"].shape, (17,))
                self.assertEqual(data["roles"].shape, (17, 4))
            record: Any = json.loads(record_path.read_text(encoding="utf-8"))
            self.assertEqual(record["kind"], "structural")
            metrics: Any = json.loads((out / "metrics.json").read_text(encoding="utf-8"))
            self.assert_numbers(metrics)
            for key in ("stable_round", "classes_last_round", "npn_classes", "seconds"):
                self.assertIn(key, metrics)
            self.assertGreaterEqual(metrics["stable_round"], -1)
            self.assertEqual(metrics["classes_last_round"], record["classes_per_round"][-1])

    def test_cluster_rejects_wl_features(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = self.graph(root)
            out = root / "out"
            code, _text, err = run(
                ["cluster", "--graph", str(path), "--features", "wl", "--out", str(out)]
            )
            self.assertEqual(code, 2, err)
            self.assertIn("wl and npn are categorical ids; only gnn uses them", err)

    @skip_without("torch", "torch_geometric")
    def test_export_no_structural_flag(self) -> None:
        torch: Any = importlib.import_module("torch")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = self.graph(root)
            plain = root / "plain"
            full = root / "full"
            code, _text, err = run(
                ["export", "--graph", str(path), "--format", "pyg", "--no-structural",
                 "--out", str(plain)]
            )
            self.assertEqual(code, 0, err)
            code, _text, err = run(
                ["export", "--graph", str(path), "--format", "pyg", "--out", str(full)]
            )
            self.assertEqual(code, 0, err)
            without: Any = torch.load(
                plain / "d" / "f2" / "export" / "whole.pt", weights_only=True
            )
            with_structural: Any = torch.load(
                full / "d" / "f2" / "export" / "whole.pt", weights_only=True
            )
            for key in ("gsn_roles", "gsn_npn", "gsn_wl", "npn_keys", "wl_variant"):
                self.assertNotIn(key, without)
                self.assertIn(key, with_structural)

    @skip_without("torch", "torch_geometric")
    def test_gnn_features_wl(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            dataset = make_dataset(root / "ds", designs=6)
            out = root / "out"
            code, _text, err = run(
                ["gnn", "--dataset", str(dataset), "--floor", "f2", "--epochs", "1",
                 "--features", "node,wl,npn", "--out", str(out)]
            )
            self.assertEqual(code, 0, err)
            config: Any = json.loads((out / "gnn" / "config.json").read_text(encoding="utf-8"))
            self.assertEqual(config["features"], ["node", "wl", "npn"])


if __name__ == "__main__":
    unittest.main()
