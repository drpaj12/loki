"""L2 Task 14: the four Wyrd step plugins (L2 spec section 10)."""

from __future__ import annotations

import dataclasses
import importlib.metadata
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

try:
    from wyrd import settings as wyrd_settings
    from wyrd.model import Design, Recipe, RunSpec, StepSpec
    from wyrd.steps import get_step
except ImportError as exc:  # pragma: no cover - wyrd is a dev dependency
    raise unittest.SkipTest(f"wyrd is not importable: {exc}") from exc

from loki.analysis.steps import ClusterStep, ExportStep, GnnStep, GraphletStep
from tests.analysis_fixtures import make_dataset

_STEPS = (ExportStep, ClusterStep, GraphletStep, GnnStep)


def settings() -> wyrd_settings.Settings:
    with mock.patch.dict("os.environ", {"WYRD_CONFIG": "/nonexistent/m.toml"}):
        return dataclasses.replace(wyrd_settings.load(None, {}), vtr_root=None)


def run_for(name: str = "micro_a0") -> RunSpec:
    return RunSpec(Design(name, (Path("/src/d.v"),), None), "arch", Recipe("l2", ()))


class StepTest(unittest.TestCase):
    def test_cluster_command_argv(self) -> None:
        step = ClusterStep(StepSpec("loki-cluster", {"dataset": "/ds"}))
        argv, env = step.command(run_for(), Path("/s"), settings())
        self.assertEqual(argv[:4], [sys.executable, "-m", "loki.analysis.run", "cluster"])
        self.assertEqual(argv[argv.index("--dataset") + 1], "/ds")
        self.assertEqual(argv[argv.index("--design") + 1], "micro_a0")
        self.assertEqual(argv[argv.index("--floor") + 1], "f2")
        self.assertEqual(argv[argv.index("--out") + 1], "/s/analysis")
        self.assertEqual(argv[argv.index("--seed") + 1], "0")
        self.assertEqual(env, {})
        chosen = ClusterStep(
            StepSpec("loki-cluster", {"dataset": "/ds", "method": "kmeans", "k": 4, "seed": 7})
        )
        argv, _ = chosen.command(run_for(), Path("/s"), settings())
        self.assertEqual(argv[argv.index("--method") + 1], "kmeans")
        self.assertEqual(argv[argv.index("--k") + 1], "4")
        self.assertEqual(argv[argv.index("--seed") + 1], "7")

    def test_export_format_list_joined(self) -> None:
        step = ExportStep(StepSpec("loki-export", {"dataset": "/ds",
                                                   "format": ["edgelist", "pyg"]}))
        argv, _ = step.command(run_for(), Path("/s"), settings())
        self.assertEqual(argv[argv.index("--format") + 1], "edgelist,pyg")
        self.assertEqual(argv.count("--format"), 1)

    def test_gnn_has_no_design_flag(self) -> None:
        step = GnnStep(StepSpec("loki-gnn", {"dataset": "/ds"}))
        argv, _ = step.command(run_for(), Path("/s"), settings())
        self.assertEqual(argv[:4], [sys.executable, "-m", "loki.analysis.run", "gnn"])
        self.assertNotIn("--design", argv)
        self.assertEqual(argv[argv.index("--dataset") + 1], "/ds")
        self.assertEqual(argv[argv.index("--floor") + 1], "f2")
        self.assertEqual(argv[argv.index("--out") + 1], "/s/analysis")

    def test_missing_dataset_rejected(self) -> None:
        for cls in _STEPS:
            with self.assertRaisesRegex(ValueError, f"step '{cls.name}': dataset is required"):
                cls(StepSpec(cls.name, {}))

    def test_unknown_arg_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError,
                                    r"step 'loki-cluster': unknown argument 'x'"):
            ClusterStep(StepSpec("loki-cluster", {"dataset": "/d", "x": 1}))

    def test_collect_reads_metrics_json(self) -> None:
        step = ClusterStep(StepSpec("loki-cluster", {"dataset": "/ds"}))
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "metrics.json").write_text(
                json.dumps({"n_clusters_kmeans": 4, "modularity_louvain": 0.51}),
                encoding="utf-8",
            )
            metrics = step.collect(Path(tmp))
        self.assertEqual({m.name: m.value for m in metrics},
                         {"n_clusters_kmeans": 4.0, "modularity_louvain": 0.51})

    def test_collect_missing_file_empty(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(ExportStep(StepSpec("loki-export", {"dataset": "/ds"}))
                             .collect(Path(tmp)), [])

    def test_entry_points_load(self) -> None:
        names = {ep.name for ep in importlib.metadata.entry_points(group="wyrd.steps")}
        wanted = {"loki-export", "loki-cluster", "loki-graphlets", "loki-gnn"}
        if not wanted <= names:
            self.skipTest("loki is not installed with the L2 entry points (pip install -e .)")
        self.assertIsInstance(get_step(StepSpec("loki-cluster", {"dataset": "/d"})), ClusterStep)

    def test_command_runs_end_to_end(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            dataset = make_dataset(root / "dataset", designs=2)
            step = ExportStep(StepSpec("loki-export", {"dataset": str(dataset)}))
            step_dir = root / "step"
            argv, env = step.command(run_for(), step_dir, settings())
            proc = subprocess.run(argv, capture_output=True, text=True, check=False,
                                  env={**os.environ, **env})
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertTrue((step_dir / "analysis" / "metrics.json").is_file())
            metrics = {m.name: m.value for m in step.collect(step_dir)}
            self.assertEqual(metrics, {"files": 2.0})


if __name__ == "__main__":
    unittest.main()
