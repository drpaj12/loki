"""L2 acceptance test: the five exit items of spec 12 (plan Task 15).

The synthetic dataset of :func:`tests.analysis_fixtures.make_dataset` proves the plugin
surface end to end without Odin III: export and structural determinism (item 1), clustering
(item 2), graphlets against the brute-force oracle (item 3), the GNN and its 1-WL baseline
(item 4) and the four Wyrd steps (item 5). ``$LOKI_L0_DATASET`` points the GNN item at a real
L0 micros dataset, defaulting to the workspace ``work/loki-rename-exp/dataset-base`` when that
exists; the designs the GNN refuses (no train-kind ``construct_type``) are skipped and counted.
Only there is ``beats_wl`` asserted (spec 14 item 8), and only on the structural rerun: a colour
lookup can beat a message-passing GNN on the tiny fixture (spec 9), and the default config's
result is the item-8 finding the acceptance reports with that rerun instead of failing on it.

Classes skip on a missing extra (spec 12: the acceptance test is local and skips without
extras) or on a missing ORCA/Wyrd; a skipped item is never a silent pass in CI, which installs
the extras. Outputs live in a ``tempfile`` directory so the dataset tree is never written.
"""

from __future__ import annotations

import contextlib
import dataclasses
import importlib
import io
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from typing import Any
from unittest import mock

from loki.analysis.export import load_pyg
from loki.analysis.gnn import TRAIN_KINDS
from loki.analysis.graphio import load_graph
from loki.analysis.graphlets import counting_graph
from loki.analysis.graphlets.ext import find_orca
from loki.analysis.partition import load_partition
from loki.analysis.region import region_hash
from loki.analysis.run import main
from tests.analysis_fixtures import make_dataset, make_graph, make_sync_design, write_graph
from tests.graphlet_oracle import brute_orbits
from tests.helpers import have, skip_without

DESIGNS = 8
DESIGN = "micro_a0"
FLOOR = "f2"
ANALYSIS = ("numpy", "scipy", "sklearn", "networkx")
GNN = (*ANALYSIS, "torch", "torch_geometric")
ORCA = find_orca()
ORCA_SKIP = "run: loki tools fetch-orca"
DATASET_ENV = "LOKI_L0_DATASET"
#: The workspace L0 micros dataset (68 designs, per-design split, 6 GNN-refused) used when
#: ``$LOKI_L0_DATASET`` is unset: a sibling of this worktree, never part of the repo.
WORKSPACE_DATASET = (
    Path(__file__).resolve().parent.parent.parent / "loki-rename-exp" / "dataset-base"
)


def run(argv: list[str]) -> tuple[int, str, str]:
    """Run ``loki analyze`` in process; return (exit code, stdout, stderr)."""
    out = io.StringIO()
    err = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = main(argv)
    return code, out.getvalue(), err.getvalue()


def read_json(path: Path) -> Any:
    """The parsed JSON object at ``path``."""
    return json.loads(path.read_text(encoding="utf-8"))


def dataset_under(root: Path) -> Path:
    """The fixture dataset of this item: ``DESIGNS`` designs at floor ``FLOOR``."""
    return make_dataset(root / "dataset", designs=DESIGNS)


def dataset_floor_ok(root: Path) -> bool:
    """True when ``root`` is an L0 dataset the analyses and the GNN dataset path can read.

    Every ``ok`` design at ``FLOOR`` must carry a per-design ``split`` and its ``graph.json``:
    a manifest without the split (an assembled but not yet split dataset, e.g. dataset-renamed)
    makes :func:`loki.analysis.graphio.iter_dataset` raise ``KeyError`` instead of skipping.
    """
    path = root / "manifest.json"
    if not path.is_file():
        return False
    manifest: Any = read_json(path)
    ok = [
        entry for entry in manifest.get("designs", [])
        if entry.get("floors", {}).get(FLOOR, {}).get("status") == "ok"
    ]
    return bool(ok) and all(
        isinstance(entry.get("split"), str)
        and (root / str(entry.get("design", "")) / FLOOR / "graph.json").is_file()
        for entry in ok
    )


def l0_dataset() -> Path | None:
    """``$LOKI_L0_DATASET`` when set, else the workspace ``dataset-base`` when present."""
    raw = os.environ.get(DATASET_ENV, "")
    if raw:
        return Path(raw)
    return WORKSPACE_DATASET if WORKSPACE_DATASET.is_dir() else None


def labelled_subset(source: Path, root: Path) -> tuple[Path, list[str]]:
    """Write a copy of ``source`` at ``root`` holding only the designs the GNN can train on.

    The GNN refuses a design with no :data:`TRAIN_KINDS` node carrying a non-empty
    ``construct_type`` (spec 9, ``UNLABELLED_MESSAGE``); the port/const-only micros designs are
    left out and returned so the test reports the count. Only ``manifest.json`` and each kept
    design's ``graph.json`` are written: that is all ``loki analyze gnn`` reads.
    """
    manifest: Any = read_json(source / "manifest.json")
    dataset = root / "dataset"
    dataset.mkdir(parents=True)
    kept: list[dict[str, Any]] = []
    refused: list[str] = []
    for entry in manifest.get("designs", []):
        if entry.get("floors", {}).get(FLOOR, {}).get("status") != "ok":
            continue
        name = str(entry["design"])
        graph_path = source / name / FLOOR / "graph.json"
        graph = load_graph(graph_path)
        construct = None if graph.labels is None else graph.labels.get("construct_type")
        labelled = construct is not None and any(
            kind in TRAIN_KINDS and str(construct[row]) for row, kind in enumerate(graph.kind)
        )
        if not labelled:
            refused.append(name)
            continue
        kept.append(entry)
        (dataset / name / FLOOR).mkdir(parents=True)
        (dataset / name / FLOOR / "graph.json").write_bytes(graph_path.read_bytes())
    (dataset / "manifest.json").write_text(
        json.dumps({**manifest, "designs": kept}, sort_keys=True, indent=1) + "\n",
        encoding="utf-8",
    )
    return dataset, refused


@skip_without(*GNN)
class AcceptanceExportStructuralTest(unittest.TestCase):
    """Item 1: export (whole and cone region) and the structural determinism."""

    tmp: tempfile.TemporaryDirectory[str]
    dataset: Path

    @classmethod
    def setUpClass(cls) -> None:
        cls.tmp = tempfile.TemporaryDirectory(prefix="loki-l2-acc-export-")
        cls.dataset = dataset_under(Path(cls.tmp.name))

    @classmethod
    def tearDownClass(cls) -> None:
        cls.tmp.cleanup()

    def export(self, out: Path, *extra: str) -> Path:
        code, _text, err = run([
            "export", "--dataset", str(self.dataset), "--design", DESIGN, "--floor", FLOOR,
            "--format", "edgelist,graphml,pyg", "--out", str(out), *extra,
        ])
        self.assertEqual(code, 0, err)
        return out / DESIGN / FLOOR / "export"

    def test_1a_export_whole_pyg_and_structural_keys(self) -> None:
        files = self.export(Path(self.tmp.name) / "out")
        for name in ("whole.edges.tsv", "whole.nodes.tsv", "whole.graphml", "whole.pt"):
            self.assertTrue((files / name).is_file(), name)
        data = load_pyg(files / "whole.pt")
        n = int(data.num_nodes)
        self.assertEqual(int(data.x.shape[1]), len(data.feature_names))
        for key in ("gsn_wl", "gsn_npn", "gsn_roles"):
            self.assertEqual(int(getattr(data, key).shape[0]), n, key)
        self.assertEqual(int(data.gsn_wl.shape[1]), 5)  # initial colours + 4 rounds
        self.assertEqual(len(data.npn_keys), n)
        self.assertEqual(str(data.wl_variant), "npn/both")

    def test_1b_export_cone_region(self) -> None:
        files = self.export(Path(self.tmp.name) / "out", "--region", "cone:n16:in:2")
        stem = f"region-{region_hash('cone:n16:in:2')}"
        for suffix in (".edges.tsv", ".nodes.tsv", ".graphml", ".pt"):
            self.assertTrue((files / f"{stem}{suffix}").is_file(), suffix)
        whole = load_pyg(files / "whole.pt")
        region = load_pyg(files / f"{stem}.pt")
        self.assertLess(int(region.num_nodes), int(whole.num_nodes))
        self.assertEqual(int(region.x.shape[1]), len(region.feature_names))
        for key in ("gsn_wl", "gsn_npn", "gsn_roles"):
            self.assertEqual(int(getattr(region, key).shape[0]), int(region.num_nodes), key)

    def test_1c_structural_two_runs_identical_except_seconds(self) -> None:
        # Plan Task 10a pins the determinism as "byte-identical except seconds": the JSON
        # records the wall clock by design, the arrays and every other field are stable.
        import numpy as np

        paths = []
        for name in ("a", "b"):
            out = Path(self.tmp.name) / f"structural-{name}"
            code, _text, err = run([
                "structural", "--dataset", str(self.dataset), "--design", DESIGN,
                "--floor", FLOOR, "--rounds", "4", "--out", str(out),
            ])
            self.assertEqual(code, 0, err)
            paths.append(out / DESIGN / FLOOR / "structural" / "structural-npn-both.json")
        first: Any = read_json(paths[0])
        second: Any = read_json(paths[1])
        first.pop("seconds")
        second.pop("seconds")
        self.assertEqual(first, second)
        with np.load(paths[0].with_suffix(".npz")) as a, np.load(paths[1].with_suffix(".npz")) as b:
            self.assertEqual(sorted(a.files), sorted(b.files))
            for key in a.files:
                np.testing.assert_array_equal(a[key], b[key], key)


@skip_without(*ANALYSIS)
class AcceptanceClusterTest(unittest.TestCase):
    """Item 2: four partitions that load, cover every node and repeat byte for byte."""

    tmp: tempfile.TemporaryDirectory[str]
    dataset: Path

    @classmethod
    def setUpClass(cls) -> None:
        cls.tmp = tempfile.TemporaryDirectory(prefix="loki-l2-acc-cluster-")
        cls.dataset = dataset_under(Path(cls.tmp.name))

    @classmethod
    def tearDownClass(cls) -> None:
        cls.tmp.cleanup()

    def cluster(self, name: str) -> Path:
        out = Path(self.tmp.name) / name
        code, _text, err = run([
            "cluster", "--dataset", str(self.dataset), "--design", DESIGN, "--floor", FLOOR,
            "--method", "all", "--out", str(out),
        ])
        self.assertEqual(code, 0, err)
        return out / DESIGN / FLOOR / "partition"

    def test_2_cluster_all_partitions_and_determinism(self) -> None:
        first = self.cluster("a")
        second = self.cluster("b")
        graph = load_graph(self.dataset / DESIGN / FLOOR / "graph.json")
        for method in ("kmeans", "affinity", "spectral", "louvain"):
            paths = sorted(first.glob(f"{method}-*.json"))
            self.assertEqual(len(paths), 1, method)
            partition = load_partition(paths[0])
            self.assertEqual(partition.node_ids, graph.node_ids, method)
            self.assertEqual(len(partition.assignment), graph.n_nodes, method)
            self.assertEqual(set(partition.assignment), set(range(partition.n_clusters)), method)
            self.assertEqual(paths[0].read_bytes(),
                             (second / paths[0].name).read_bytes(), method)


@unittest.skipUnless(ORCA is not None, ORCA_SKIP)
@skip_without(*ANALYSIS)
class AcceptanceGraphletsTest(unittest.TestCase):
    """Item 3: ORCA orbits equal the brute-force oracle; roles match the spec-8.1 micros."""

    tmp: tempfile.TemporaryDirectory[str]
    out: Path

    @classmethod
    def setUpClass(cls) -> None:
        cls.tmp = tempfile.TemporaryDirectory(prefix="loki-l2-acc-graphlets-")
        cls.out = Path(cls.tmp.name)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.tmp.cleanup()

    def graphlets(self, path: Path, out_name: str) -> Path:
        out = self.out / out_name
        code, _text, err = run([
            "graphlets", "--graph", str(path), "--backend", "ext", "--size", "4",
            "--removal", "global", "--out", str(out),
        ])
        self.assertEqual(code, 0, err)
        return out

    def test_3a_orbits_match_the_oracle(self) -> None:
        import numpy as np

        path = write_graph(self.out / "graph", make_graph(12))
        out = self.graphlets(path, "plain")
        graph = load_graph(path)
        orbits, _roles = _load_ext_orbits(graph, out)
        counting = counting_graph(graph, "global")
        expected = brute_orbits(counting.n, counting.src, counting.dst)
        np.testing.assert_array_equal(orbits, expected)

    def test_3b_clock_domains_and_reset_flags(self) -> None:
        # 20 flip-flops over two clocks and one reset: the fan-out of spec 8.1's default
        # SignalConfig (16), so the reset is found without a lowered min_fanout.
        path = write_graph(self.out / "sync",
                           make_sync_design(n_ff=20, reset=True, clocks=2))
        out = self.graphlets(path, "sync")
        graph = load_graph(path)
        _orbits, roles = _load_ext_orbits(graph, out)
        record: Any = read_json(out / "sync" / FLOOR / "graphlets" / "graphlets-ext-global.json")
        self.assertEqual(record["clock_domains"], 2)
        self.assertEqual(record["classified"]["clock"], 2)
        self.assertGreaterEqual(record["classified"]["reset"], 1)
        clocked = [row for row, kind in enumerate(graph.kind) if kind == "ff"]
        self.assertEqual(len(clocked), 20)
        # Domain numbers follow the lowest driver index: clk0 (n0) is 1, clk1 (n1) is 2.
        self.assertEqual(sorted(int(roles[row, 0]) for row in clocked),
                         [1] * 10 + [2] * 10)
        for row, kind in enumerate(graph.kind):
            if kind == "pi":  # neither a clock sink nor the rst PI carries a role flag
                self.assertEqual(int(roles[row, 0]), 0, graph.node_ids[row])
                self.assertEqual(int(roles[row, 1]), 0, graph.node_ids[row])
        d_drivers = {
            int(graph.src[edge]) for edge in range(graph.n_edges)
            if graph.kind[int(graph.dst[edge])] == "ff" and graph.pin[edge] == "D"
        }
        self.assertEqual(len(d_drivers), 20)
        for row in sorted(d_drivers):
            self.assertEqual(int(roles[row, 1]), 1, graph.node_ids[row])
        for row in clocked:
            self.assertEqual(int(roles[row, 1]), 1, graph.node_ids[row])
        self.assertEqual(int(roles[graph.index()["n2"], 1]), 0)  # the rst PI itself


def _load_ext_orbits(graph: Any, out: Path) -> tuple[Any, Any]:
    """The ``ext``/``global`` orbits and roles of a ``loki analyze graphlets`` run."""
    from loki.analysis.graphlets import load_orbits

    return load_orbits(graph, "ext", "global", out / graph.design / graph.floor / "graphlets")


@skip_without(*GNN)
class AcceptanceGnnTest(unittest.TestCase):
    """Item 4: the GNN beats the majority baseline; ``beats_wl`` on the real micros only."""

    tmp: tempfile.TemporaryDirectory[str]
    dataset: Path

    @classmethod
    def setUpClass(cls) -> None:
        cls.tmp = tempfile.TemporaryDirectory(prefix="loki-l2-acc-gnn-")
        cls.dataset = dataset_under(Path(cls.tmp.name))

    @classmethod
    def tearDownClass(cls) -> None:
        cls.tmp.cleanup()

    def gnn(self, dataset: Path, out: Path, *extra: str) -> Any:
        code, _text, err = run([
            "gnn", "--dataset", str(dataset), "--floor", FLOOR, "--out", str(out), *extra,
        ])
        self.assertEqual(code, 0, err)
        return read_json(out / "gnn" / "metrics.json")

    def assert_complete(self, metrics: Any, out: Path) -> None:
        for key in ("train", "test", "baselines", "beats_wl", "note"):
            self.assertIn(key, metrics)
        for key in ("majority", "logreg", "wl"):
            self.assertIn(key, metrics["baselines"])
            self.assertIn("accuracy", metrics["baselines"][key])
            self.assertIn("macro_f1", metrics["baselines"][key])
        self.assertIsInstance(metrics["beats_wl"], bool)
        for name in ("config.json", "vocab.json", "model.pt", "metrics.json"):
            self.assertTrue((out / "gnn" / name).is_file(), name)
        predictions = list((out / "gnn").glob("predictions-*.csv"))
        self.assertEqual(len(predictions), metrics["test"]["n_designs"])

    def test_4a_fixture_gnn_beats_majority(self) -> None:
        out = Path(self.tmp.name) / "out"
        metrics = self.gnn(self.dataset, out)
        self.assert_complete(metrics, out)
        self.assertGreater(metrics["test"]["accuracy"],
                           metrics["baselines"]["majority"]["accuracy"])
        self.assertGreater(metrics["test"]["n_nodes"], 0)
        # beats_wl is computed even on the fixture (spec 14 item 8: reported always, asserted
        # only on the real dataset, where a colour lookup is not planted to be perfect).

    def test_4b_real_micros_beats_wl(self) -> None:
        source = l0_dataset()
        if source is None:
            self.skipTest(f"set {DATASET_ENV} to a real L0 dataset")
        if not dataset_floor_ok(source):
            self.skipTest(
                f"{source}: no {FLOOR} design with status ok, a per-design split and a graph.json"
            )
        dataset, refused = labelled_subset(source, Path(self.tmp.name) / "l0")
        if refused:
            print(f"{source}: {len(refused)} GNN-refused design(s) skipped "
                  f"(no train-kind construct_type): {', '.join(refused)}")
        out = Path(self.tmp.name) / "real"
        default = self.gnn(dataset, out)
        self.assert_complete(default, out)
        if default["beats_wl"]:
            print(f"{source}: the default config beats the 1-WL baseline (test macro_f1 "
                  f"{default['test']['macro_f1']} vs wl {default['baselines']['wl']['macro_f1']})")
        else:
            # Spec 14 item 8: the default config's loss is a finding reported to the controller
            # with the structural rerun, never a hard failure and never a baseline change.
            print(f"finding (spec 14 item 8, reported with the rerun --features "
                  f"node,graphlet,wl,npn): {source}: the default config does not beat the 1-WL "
                  f"baseline: test macro_f1 {default['test']['macro_f1']} vs wl "
                  f"{default['baselines']['wl']['macro_f1']} (accuracy "
                  f"{default['test']['accuracy']} / wl "
                  f"{default['baselines']['wl']['accuracy']})")
        rerun = self._structural_rerun(dataset, Path(self.tmp.name) / "real-structural")
        if "error" in rerun:
            self.skipTest(f"the spec 14 item 8 rerun needs ORCA: {rerun['error']}")
        if "exit" in rerun:
            self.fail(f"the rerun --features node,graphlet,wl,npn failed: exit "
                      f"{rerun['exit']}: {rerun['stderr']}")
        self.assertTrue(
            rerun["beats_wl"],
            f"{source}: the rerun --features node,graphlet,wl,npn does not beat the 1-WL "
            f"baseline either: test macro_f1 {rerun['test']['macro_f1']} vs wl "
            f"{rerun['wl']['macro_f1']} (default config: beats_wl {default['beats_wl']}, "
            f"test macro_f1 {default['test']['macro_f1']} vs wl "
            f"{default['baselines']['wl']['macro_f1']})",
        )
        print(f"{source}: the rerun --features node,graphlet,wl,npn beats the 1-WL baseline: "
              f"test macro_f1 {rerun['test']['macro_f1']} vs wl {rerun['wl']['macro_f1']} "
              f"(default config: beats_wl {default['beats_wl']}, test macro_f1 "
              f"{default['test']['macro_f1']} vs wl {default['baselines']['wl']['macro_f1']})")

    def _structural_rerun(self, source: Path, out: Path) -> Any:
        """The spec-14-item-8 rerun on ``node,graphlet,wl,npn``; its metrics or the error."""
        if find_orca() is None:
            return {"error": f"graphlet features need ORCA ({ORCA_SKIP})"}
        code, _text, err = run([
            "gnn", "--dataset", str(source), "--floor", FLOOR, "--out", str(out),
            "--features", "node,graphlet,wl,npn",
        ])
        if code != 0:
            return {"exit": code, "stderr": err.strip()[-800:]}
        metrics: Any = read_json(out / "gnn" / "metrics.json")
        return {"beats_wl": metrics["beats_wl"], "test": metrics["test"],
                "wl": metrics["baselines"]["wl"]}


@skip_without(*ANALYSIS)
class AcceptanceStepsTest(unittest.TestCase):
    """Item 5: the four kinds run as Wyrd steps through ``get_step`` and ``command``."""

    def test_5_four_steps_run_end_to_end(self) -> None:
        model, settings_mod, steps_mod = _wyrd()
        with tempfile.TemporaryDirectory(prefix="loki-l2-acc-steps-") as tmpname:
            root = Path(tmpname)
            dataset = dataset_under(root)
            settings = _settings(settings_mod)
            configs: tuple[tuple[str, dict[str, object]], ...] = (
                ("loki-export", {"format": ["edgelist", "graphml"]}),
                ("loki-cluster", {"method": "kmeans"}),
                ("loki-graphlets", {"size": 4, "removal": "global"}),
                ("loki-gnn", {}),
            )
            for name, args in configs:
                with self.subTest(step=name):
                    if name == "loki-graphlets" and find_orca() is None:
                        self.skipTest(ORCA_SKIP)
                    if name == "loki-gnn":
                        missing = [module for module in GNN if not have(module)]
                        if missing:
                            self.skipTest(
                                f"missing optional module(s): {', '.join(missing)}"
                            )
                    step = steps_mod.get_step(
                        model.StepSpec(name, {"dataset": str(dataset), **args})
                    )
                    run_spec = model.RunSpec(
                        model.Design(DESIGN, (Path("/src/d.v"),), None), "arch",
                        model.Recipe("l2", ()),
                    )
                    step_dir = root / name
                    argv, env = step.command(run_spec, step_dir, settings)
                    done = subprocess.run(
                        argv, capture_output=True, text=True, check=False,
                        env={**os.environ, **env},
                    )
                    self.assertEqual(done.returncode, 0, done.stderr[-800:])
                    self.assertTrue((step_dir / "analysis" / "metrics.json").is_file())
                    self.assertTrue(step.collect(step_dir), name)


def _wyrd() -> tuple[Any, Any, Any]:
    """Wyrd's model, settings and steps modules, or a skip when Wyrd is not installed."""
    try:
        return (
            importlib.import_module("wyrd.model"),
            importlib.import_module("wyrd.settings"),
            importlib.import_module("wyrd.steps"),
        )
    except ImportError as exc:
        raise unittest.SkipTest(f"wyrd is not importable: {exc}") from exc


def _settings(settings_mod: Any) -> Any:
    """Wyrd machine settings for the step command (the spec-10 test harness pattern)."""
    with mock.patch.dict("os.environ", {"WYRD_CONFIG": "/nonexistent/m.toml"}):
        return dataclasses.replace(settings_mod.load(None, {}), vtr_root=None)


if __name__ == "__main__":
    unittest.main()
