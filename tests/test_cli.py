import contextlib
import io
import tempfile
import unittest
from pathlib import Path

from loki.cli import main
from tests.test_check import make_dataset


def run(argv: list[str]) -> tuple[int, str]:
    out = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
        code = main(argv)
    return code, out.getvalue()


class CliTest(unittest.TestCase):
    def test_usage_exit_2(self) -> None:
        self.assertEqual(run([])[0], 2)
        self.assertEqual(run(["bogus"])[0], 2)
        self.assertEqual(run(["bench", "init", "--suite", "nope"])[0], 2)
        self.assertEqual(run(["check", "/nonexistent/dataset/dir"])[0], 1)
        argv = ["assemble", "--project", "/nonexistent/p", "--out", "/nonexistent/o"]
        self.assertEqual(run(argv)[0], 2)

    def test_analyze_without_kind_exit_2(self) -> None:
        self.assertEqual(run(["analyze"])[0], 2)

    def test_check_exit_codes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = make_dataset(Path(tmp))
            code, text = run(["check", str(root)])
            self.assertEqual((code, text.strip()), (0, "loki check: 0 error(s)"))
            (root / "micro_a" / "f2" / "key.json").write_text("{}", encoding="utf-8")
            code, text = run(["check", str(root)])
            self.assertEqual(code, 1)
            self.assertIn("key.json", text)

    def test_check_lists_warnings(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = make_dataset(Path(tmp))
            meta = root / "micro_a" / "f2" / "meta.json"
            meta.write_text(
                meta.read_text(encoding="utf-8").replace('"equivalent"', '"unproven"', 1),
                encoding="utf-8",
            )
            code, text = run(["check", str(root)])
            self.assertEqual(code, 0, text)
            self.assertIn("warning: micro_a/f2: equiv writer: unproven", text)
            self.assertIn("0 error(s), 1 warning(s)", text)

    def test_bench_init_micro(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            odin = Path(tmp) / "odin3" / "tests" / "micro" / "verilog" / "micro"
            odin.mkdir(parents=True)
            (odin / "m.v").write_text("module m; endmodule\n", encoding="utf-8")
            out = Path(tmp) / "proj"
            code, text = run(["bench", "init", "--suite", "micro", "--odin3-root",
                              str(Path(tmp) / "odin3"), "--out", str(out)])
            self.assertEqual(code, 0, text)
            self.assertTrue((out / "wyrd.toml").is_file())


if __name__ == "__main__":
    unittest.main()
