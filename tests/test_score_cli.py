import contextlib
import io
import json
import os
import tempfile
import unittest
from pathlib import Path

from loki.cli import main
from loki.re.main import main as re_main
from tests.helpers import DATA, can_run_f2, write_fake_floor
from tests.score_fixtures import write_floor_and_run


def quiet(argv: list[str]) -> int:
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        return main(argv)


class ScoreCliTest(unittest.TestCase):
    def test_score_then_score_all_and_compare(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            floor, run, _ = write_floor_and_run(root)
            dataset = root
            self.assertEqual(quiet(["score", str(run), "--dataset", str(dataset),
                                    "--design", "d", "--floor", "f2"]), 0)
            self.assertTrue((run / "score.json").is_file())
            out = root / "out"
            self.assertEqual(quiet(["score-all", str(run), "--out", str(out),
                                    "--compare", str(run)]), 0)
            for name in ("scores.json", "scores.md", "ablation.json", "ablation.md"):
                self.assertTrue((out / name).is_file(), name)
            obj = json.loads((out / "scores.json").read_text(encoding="utf-8"))
            self.assertEqual(obj["floors"]["f2"]["constructs"]["adder"]["precision"], 1.0)

    def test_score_all_scores_missing_with_dataset(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            floor, run, _ = write_floor_and_run(root)
            named = root / "runs" / "d__f2"
            named.parent.mkdir()
            run.rename(named)
            code = quiet(["score-all", str(root / "runs"), "--dataset", str(root),
                          "--out", str(root / "out")])
            self.assertEqual(code, 0)
            self.assertTrue((named / "score.json").is_file())

    def test_usage_errors(self) -> None:
        self.assertEqual(quiet(["score"]), 2)
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(quiet(["score-all", tmp, "--out", tmp]), 2)
            self.assertEqual(quiet(["score", tmp, "--dataset", tmp, "--design", "x",
                                    "--floor", "f2"]), 2)

    def test_re_score_options_go_together(self) -> None:
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(re_main(["x.blif", "--score-dataset", "d"]), 2)
            self.assertEqual(re_main(["x.blif", "--score-design", "d"]), 2)


@unittest.skipUnless(can_run_f2(), "needs Odin III, ABC and an F2 architecture")
class ReScoreTest(unittest.TestCase):
    def test_re_writes_score_and_metrics(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_fake_floor(root / "ds", "d", "f2")
            out = root / "step" / "re"
            with contextlib.redirect_stderr(io.StringIO()):
                code = re_main([str(DATA / "re" / "add2.blif"), "--floor", "f2", "--out", str(out),
                                "--odin3-root", os.environ.get("ODIN3_ROOT", ""),
                                "--score-dataset", str(root / "ds"), "--score-design", "d"])
            self.assertEqual(code, 0)
            score = json.loads((out / "score.json").read_text(encoding="utf-8"))
            metrics = json.loads((root / "step" / "metrics.json").read_text(encoding="utf-8"))
        self.assertEqual((score["design"], score["floor"]), ("d", "f2"))
        self.assertIn("rounds", metrics)
        self.assertEqual(metrics["final_equiv_ok"], 1)
