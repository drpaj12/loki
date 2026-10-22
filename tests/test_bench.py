import hashlib
import json
import os
import tempfile
import tomllib
import unittest
from pathlib import Path
from unittest import mock

from loki import bench
from loki.bench import (
    VERILOG_EVAL,
    design_id,
    discover_micros,
    fetch_verilog_eval,
    write_project,
)
from loki.schemas import validate_design
from tests.helpers import odin3_root


def fake_odin3(root: Path) -> Path:
    micro = root / "tests" / "micro" / "verilog" / "micro"
    micro.mkdir(parents=True)
    (micro / "b_two.v").write_text("module b_two; endmodule\n", encoding="utf-8")
    (micro / "a_one.v").write_text("module a_one; endmodule\n", encoding="utf-8")
    return root


def clean_git(args: list[str], cwd: Path | None = None) -> str:
    return "" if args[:1] == ["status"] else VERILOG_EVAL["commit"]


class BenchTest(unittest.TestCase):
    def test_design_id(self) -> None:
        self.assertEqual(design_id(Path("/x/bm_a.v"), "micro"), "micro_bm_a")
        ve = design_id(Path("/x/Prob001_zero_ref.sv"), "verilog-eval")
        self.assertEqual(ve, "ve_Prob001_zero")
        self.assertEqual(design_id(Path("/x/stereo.v"), "vtr"), "vtr_stereo")

    def test_discover_micros_count(self) -> None:
        root = odin3_root()
        if root is None:
            self.skipTest("ODIN3_ROOT not set")
        self.assertEqual(len(discover_micros(root)), 68)

    def test_write_project_toml(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            odin = fake_odin3(Path(tmp) / "odin3")
            out = Path(tmp) / "proj"
            toml = write_project("micro", odin, Path(tmp) / "cache", out)
            text = toml.read_text(encoding="utf-8")
            data = tomllib.loads(text)
            self.assertEqual([d["name"] for d in data["design"]], ["micro_a_one", "micro_b_two"])
            self.assertEqual(data["design"][0]["files"], ["designs/micro_a_one/micro_a_one.v"])
            self.assertEqual(data["recipe"]["l0"]["steps"][0]["use"], "loki-dataset")
            self.assertEqual(data["sweep"]["design"], ["micro_a_one", "micro_b_two"])
            self.assertEqual(sorted(data["sweep"]["arch"]), sorted(bench.ARCHS))
            self.assertNotIn(str(Path.home()), text)
            self.assertNotIn("top", data["design"][0])

    def test_design_json_valid(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            odin = fake_odin3(Path(tmp) / "odin3")
            out = Path(tmp) / "proj"
            write_project("micro", odin, Path(tmp) / "cache", out)
            path = out / "designs" / "micro_a_one" / "design.json"
            obj = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(validate_design(obj), [])
            copied = out / "designs" / "micro_a_one" / "micro_a_one.v"
            digest = hashlib.sha256(copied.read_bytes()).hexdigest()
            self.assertEqual(obj["files"][0]["sha256"], digest)

    def test_verilog_eval_count_guard(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cache = Path(tmp)
            (cache / ".git").mkdir()
            fake = [cache / f"p{i}_ref.sv" for i in range(155)]
            with (
                mock.patch.object(bench, "_git", side_effect=clean_git),
                mock.patch.object(bench, "_ve_files", return_value=fake),
                self.assertRaisesRegex(RuntimeError, "156"),
            ):
                fetch_verilog_eval(cache)

    def test_verilog_eval_dirty_cache(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / ".git").mkdir()
            replies = [VERILOG_EVAL["commit"], " M x_ref.sv"]
            with (
                mock.patch.object(bench, "_git", side_effect=replies),
                self.assertRaisesRegex(RuntimeError, "local changes"),
            ):
                fetch_verilog_eval(Path(tmp))

    def test_verilog_eval_rejects_symlinks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cache = Path(tmp)
            (cache / ".git").mkdir()
            target = cache / "real.sv"
            target.write_text("x", encoding="utf-8")
            link = cache / "p0_ref.sv"
            link.symlink_to(target)
            with (
                mock.patch.object(bench, "_git", side_effect=clean_git),
                mock.patch.object(bench, "_ve_files", return_value=[link]),
                self.assertRaisesRegex(RuntimeError, "symbolic links"),
            ):
                fetch_verilog_eval(cache)

    def test_verilog_eval_wrong_commit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / ".git").mkdir()
            with (
                mock.patch.object(bench, "_git", return_value="0" * 40),
                self.assertRaisesRegex(RuntimeError, "another commit"),
            ):
                fetch_verilog_eval(Path(tmp))

    def test_verilog_eval_project_has_top(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cache = Path(tmp) / "cache"
            src = cache / "dataset_spec-to-rtl"
            src.mkdir(parents=True)
            fake = [src / "Prob001_zero_ref.sv", src / "Prob002_one_ref.sv"]
            for f in fake:
                f.write_text("module RefModule; endmodule\n", encoding="utf-8")
            with mock.patch.object(bench, "fetch_verilog_eval", return_value=fake):
                toml = write_project("verilog-eval", Path(tmp), cache, Path(tmp) / "proj")
            data = tomllib.loads(toml.read_text(encoding="utf-8"))
            self.assertEqual({d["top"] for d in data["design"]}, {"RefModule"})
            first = data["design"][0]["files"]
            self.assertEqual(first, ["designs/ve_Prob001_zero/ve_Prob001_zero.sv"])

    @unittest.skipUnless(os.environ.get("LOKI_NETWORK") == "1", "set LOKI_NETWORK=1 to fetch")
    def test_fetch_needs_network(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(len(fetch_verilog_eval(Path(tmp) / "verilog-eval")), 156)


if __name__ == "__main__":
    unittest.main()
