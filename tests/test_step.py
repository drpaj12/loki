import dataclasses
import importlib.metadata
import json
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

from loki.step import DatasetStep, expand_floor

K6 = "k6_frac_N10_frac_chain_mem32K_40nm"


def settings_with_vtr() -> wyrd_settings.Settings:
    with mock.patch.dict("os.environ", {"WYRD_CONFIG": "/nonexistent/m.toml"}):
        base = wyrd_settings.load(None, {})
    return dataclasses.replace(base, vtr_root=Path("/vtr"))


def run_for(arch: str, top: str | None = "top") -> RunSpec:
    design = Design("d", (Path("/x/a.v"), Path("/x/b.v")), top)
    return RunSpec(design, arch, Recipe("l0", ()))


class StepTest(unittest.TestCase):
    def test_command_argv(self) -> None:
        step = DatasetStep(StepSpec("loki-dataset", {"odin3_root": "/odin"}))
        argv, env = step.command(run_for("EArch"), Path("/s"), settings_with_vtr())
        self.assertEqual(argv[:3], [sys.executable, "-m", "loki.build"])
        self.assertEqual(argv[argv.index("--floors") + 1], "f1-earch,f2")
        self.assertEqual(argv[argv.index("--out") + 1], "/s/dataset")
        files = argv[argv.index("--files") + 1 : argv.index("--top")]
        self.assertEqual(files, ["/x/a.v", "/x/b.v"])
        self.assertEqual(argv[argv.index("--arch-xml") + 1], "/vtr/vtr_flow/arch/timing/EArch.xml")
        self.assertEqual(env["ODIN3_ROOT"], "/odin")

    def test_odin3_root_from_environment(self) -> None:
        step = DatasetStep(StepSpec("loki-dataset"))
        with mock.patch.dict("os.environ", {"ODIN3_ROOT": "/env"}):
            self.assertEqual(step.command(run_for(K6, None), Path("/s"), settings_with_vtr())[1],
                             {"ODIN3_ROOT": "/env"})
        with mock.patch.dict("os.environ", clear=True), self.assertRaises(ValueError):
            step.command(run_for(K6), Path("/s"), settings_with_vtr())

    def test_floor_expansion_names(self) -> None:
        self.assertEqual(expand_floor("f1", K6), "f1-k6")
        self.assertEqual(expand_floor("f1", "EArch"), "f1-earch")
        self.assertEqual(expand_floor("f2", "EArch"), "f2")

    def test_collect_reads_metrics_json(self) -> None:
        step = DatasetStep(StepSpec("loki-dataset"))
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "metrics.json").write_text(json.dumps({"nodes": 12, "luts": 5}))
            metrics = step.collect(Path(tmp))
        self.assertEqual({m.name: m.value for m in metrics}, {"nodes": 12.0, "luts": 5.0})

    def test_collect_missing_file_empty(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(DatasetStep(StepSpec("loki-dataset")).collect(Path(tmp)), [])

    def test_bad_floor_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "step 'loki-dataset'"):
            DatasetStep(StepSpec("loki-dataset", {"floors": ["f1", "f9"]}))

    def test_entry_point_loads(self) -> None:
        names = {ep.name for ep in importlib.metadata.entry_points(group="wyrd.steps")}
        if "loki-dataset" not in names:
            self.skipTest("loki is not installed (pip install -e .)")
        self.assertIsInstance(get_step(StepSpec("loki-dataset")), DatasetStep)


if __name__ == "__main__":
    unittest.main()
