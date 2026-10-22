import contextlib
import io
import json
import os
import tempfile
import unittest
from pathlib import Path

from loki.cli import main as loki_main
from loki.re.main import main
from loki.re.report import validate_report
from tests.helpers import DATA, can_run_f2, odin_available

ADD2 = DATA / "re" / "add2.blif"
FILES = ("design.v", "overlay.json", "report.json", "report.md")


def run(*argv: str) -> tuple[int, str]:
    err = io.StringIO()
    with contextlib.redirect_stderr(err):
        code = main(list(argv))
    return code, err.getvalue()


def tool_args() -> list[str]:
    return ["--odin3-root", os.environ.get("ODIN3_ROOT", "")]


class UsageTest(unittest.TestCase):
    def test_cli_usage_exit_2(self) -> None:
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(main([]), 2)
            self.assertEqual(main(["x.blif", "--features", "some"]), 2)
            self.assertEqual(main(["x.blif", "--floor", "f9"]), 2)

    def test_cli_features_option(self) -> None:
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(main(["x.blif", "--features", "bogus"]), 2)
            code, err = run("/nonexistent/x.blif", "--features", "none")
        self.assertEqual(code, 3)
        self.assertIn("cannot read", err)

    def test_loki_re_delegates(self) -> None:
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(loki_main(["re"]), 2)


@unittest.skipUnless(odin_available(), "needs Odin III")
class UnreadableTest(unittest.TestCase):
    def test_cli_unreadable_exit_3(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            bad = Path(tmp) / "bad.blif"
            bad.write_text(".model x\n.names\n.bogus\n.end\n", encoding="utf-8")
            code, err = run(str(bad), "--floor", "f2", "--out", str(Path(tmp) / "o"))
        self.assertEqual(code, 3)
        self.assertTrue(err.startswith("odin3:"))


@unittest.skipUnless(can_run_f2(), "needs Odin III, ABC and an F2 architecture")
class EndToEndTest(unittest.TestCase):
    def two_runs(self, *extra: str) -> tuple[Path, Path, tempfile.TemporaryDirectory[str]]:
        tmp = tempfile.TemporaryDirectory()
        a, b = Path(tmp.name) / "a", Path(tmp.name) / "b"
        for out in (a, b):
            code, _ = run(str(ADD2), "--floor", "f2", "--out", str(out), *tool_args(), *extra)
            self.assertEqual(code, 0)
        return a, b, tmp

    def test_cli_end_to_end_byte_identical(self) -> None:
        a, b, tmp = self.two_runs()
        with tmp:
            for name in FILES:
                self.assertEqual((a / name).read_bytes(), (b / name).read_bytes(), name)
            self.assertTrue((a / "timing.json").is_file())
            rep = json.loads((a / "report.json").read_text(encoding="utf-8"))
        self.assertEqual(validate_report(rep), [])
        self.assertEqual(rep["final_equiv"]["status"], "equivalent")

    def test_design_v_has_confidence(self) -> None:
        a, _, tmp = self.two_runs()
        with tmp:
            text = (a / "design.v").read_text(encoding="utf-8")
        self.assertIn("(* ", text)
        self.assertIn('loki_conf = "', text)
        line = next(ln for ln in text.splitlines() if "loki_conf" in ln)
        self.assertIn("loki_hid", line)

    def test_report_features_keys(self) -> None:
        for mode, enabled in (("all", True), ("none", False)):
            with tempfile.TemporaryDirectory() as tmp:
                out = Path(tmp) / "o"
                code, _ = run(str(ADD2), "--floor", "f2", "--out", str(out), *tool_args(),
                              "--features", mode)
                rep = json.loads((out / "report.json").read_text(encoding="utf-8"))
            self.assertEqual(code, 0)
            feats = rep["features"]
            self.assertEqual(feats["enabled"], enabled)
            for key in ("wl", "npn", "transfers", "transfer_failures"):
                self.assertIn(key, feats)
        self.assertEqual(rep["features"]["transfers"], 0)

    def test_loki_re_subcommand(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "o"
            code = loki_main(["re", str(ADD2), "--floor", "f2", "--out", str(out), *tool_args()])
            self.assertEqual(code, 0)
            self.assertTrue((out / "report.md").is_file())


if __name__ == "__main__":
    unittest.main()
