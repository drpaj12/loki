import dataclasses
import importlib.metadata
import json
import sys
import tempfile
import tomllib
import unittest
from pathlib import Path
from unittest import mock

try:
    from wyrd import settings as wyrd_settings
    from wyrd.model import Design, Recipe, RunSpec, StepSpec
    from wyrd.steps import get_step
except ImportError as exc:  # pragma: no cover - wyrd is a dev dependency
    raise unittest.SkipTest(f"wyrd is not importable: {exc}") from exc

from loki.cli import main as loki_main
from loki.re_project import write_re_project
from loki.re_step import ReStep, split_name


def settings() -> wyrd_settings.Settings:
    with mock.patch.dict("os.environ", {"WYRD_CONFIG": "/nonexistent/m.toml"}):
        return dataclasses.replace(wyrd_settings.load(None, {}), vtr_root=Path("/vtr"))


def run_for(name: str) -> RunSpec:
    return RunSpec(Design(name, (Path("/d/x/netlist.blif"),), None), "arch", Recipe("re", ()))


class StepTest(unittest.TestCase):
    def test_command_argv(self) -> None:
        step = ReStep(StepSpec("loki-re", {"calib": "/c", "dataset": "/ds", "odin3_root": "/o"}))
        argv, env = step.command(run_for("ve_Prob035_count1to10__f2"), Path("/s"), settings())
        self.assertEqual(argv[:3], [sys.executable, "-m", "loki.re.main"])
        self.assertEqual(argv[3], "/d/x/netlist.blif")
        self.assertEqual(argv[argv.index("--floor") + 1], "f2")
        self.assertEqual(argv[argv.index("--calib") + 1], "/c/f2.json")
        self.assertEqual(argv[argv.index("--out") + 1], "/s/re")
        self.assertEqual(argv[argv.index("--score-dataset") + 1], "/ds")
        self.assertEqual(argv[argv.index("--score-design") + 1], "ve_Prob035_count1to10")
        self.assertEqual(argv[argv.index("--odin3-root") + 1], "/o")
        self.assertEqual(env, {"ODIN3_ROOT": "/o"})

    def test_calib_optional_and_root_from_environment(self) -> None:
        step = ReStep(StepSpec("loki-re", {"dataset": "/ds"}))
        with mock.patch.dict("os.environ", clear=True):
            argv, env = step.command(run_for("a__f1-k6"), Path("/s"), settings())
        self.assertEqual(argv[argv.index("--calib") + 1], "none")
        self.assertNotIn("--odin3-root", argv)
        self.assertEqual(env, {})

    def test_features_option_and_project(self) -> None:
        """The ablation of spec 15 runs the same project with ``features = "none"``."""
        step = ReStep(StepSpec("loki-re", {"dataset": "/ds", "features": "none"}))
        argv, _ = step.command(run_for("a__f2"), Path("/s"), settings())
        self.assertEqual(argv[argv.index("--features") + 1], "none")
        plain = ReStep(StepSpec("loki-re", {"dataset": "/ds"}))
        self.assertNotIn("--features", plain.command(run_for("a__f2"), Path("/s"), settings())[0])
        with self.assertRaises(ValueError):
            ReStep(StepSpec("loki-re", {"dataset": "/ds", "features": "some"}))

    def test_floor_from_design_name(self) -> None:
        self.assertEqual(split_name("x__f1-k6"), ("x", "f1-k6"))
        self.assertEqual(split_name("a__b__f2"), ("a__b", "f2"))
        for bad in ("x", "x__f9", "__f2"):
            with self.assertRaises(ValueError):
                split_name(bad)

    def test_dataset_arg_required(self) -> None:
        with self.assertRaisesRegex(ValueError, "step 'loki-re'"):
            ReStep(StepSpec("loki-re"))

    def test_collect_metrics(self) -> None:
        step = ReStep(StepSpec("loki-re", {"dataset": "/ds"}))
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "metrics.json").write_text(
                json.dumps({"rounds": 3, "precision": 0.5, "note": "x"}), encoding="utf-8")
            got = {m.name: m.value for m in step.collect(Path(tmp))}
        self.assertEqual(got, {"rounds": 3.0, "precision": 0.5})

    def test_collect_missing_empty(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(ReStep(StepSpec("loki-re", {"dataset": "/ds"})).collect(Path(tmp)), [])

    def test_entry_point_loads(self) -> None:
        names = {ep.name for ep in importlib.metadata.entry_points(group="wyrd.steps")}
        if "loki-re" not in names:
            self.skipTest("loki is not installed (pip install -e .)")
        self.assertIsInstance(get_step(StepSpec("loki-re", {"dataset": "/ds"})), ReStep)


def manifest(root: Path) -> None:
    def entry(name: str, split: str, floors: dict[str, str]) -> dict[str, object]:
        return {"design": name, "benchmark": "micro", "split": split,
                "floors": {f: {"status": s} for f, s in floors.items()}}

    designs = [
        entry("b", "test", {"f2": "ok", "f3": "ok"}), entry("a", "test", {"f2": "ok"}),
        entry("c", "train", {"f2": "ok"}), entry("d", "test", {"f2": "skipped"}),
    ]
    (root / "manifest.json").write_text(json.dumps({"designs": designs}), encoding="utf-8")


class ProjectTest(unittest.TestCase):
    def test_project_toml(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest(root)
            toml = write_re_project(root, ["f2"], "test", root / "calib", root / "out")
            data = tomllib.loads(toml.read_text(encoding="utf-8"))
            toml = write_re_project(root, ["f2"], "test", root / "calib", root / "out2", "none")
            none = tomllib.loads(toml.read_text(encoding="utf-8"))
        names = [d["name"] for d in data["design"]]
        self.assertEqual(names, ["a__f2", "b__f2"])
        self.assertTrue(data["design"][0]["files"][0].endswith("/a/f2/netlist.blif"))
        step = data["recipe"]["re"]["steps"][0]
        self.assertEqual(step["use"], "loki-re")
        self.assertTrue(step["calib"].endswith("/calib"))
        self.assertEqual(data["sweep"]["design"], names)
        self.assertEqual(data["sweep"]["recipe"], ["re"])
        self.assertEqual(data["sweep"]["arch"], ["k6_frac_N10_frac_chain_mem32K_40nm"])
        self.assertNotIn("features", step)
        self.assertEqual(none["recipe"]["re"]["steps"][0]["features"], "none")

    def test_project_errors_and_cli(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest(root)
            with self.assertRaises(ValueError):
                write_re_project(root, ["f9"], "test", root, root / "o")
            with self.assertRaises(ValueError):
                write_re_project(root, ["f1-k6"], "test", root, root / "o")
            code = loki_main(["re-project", "--dataset", str(root), "--floors", "f2,f3",
                              "--calib", str(root), "--out", str(root / "o")])
            self.assertEqual(code, 0)
            data = tomllib.loads((root / "o" / "wyrd.toml").read_text(encoding="utf-8"))
        self.assertEqual([d["name"] for d in data["design"]], ["a__f2", "b__f2", "b__f3"])


if __name__ == "__main__":
    unittest.main()
