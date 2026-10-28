"""Tests for docs/paper/make_register.py, make_glossary.py and split_tables.py (stdlib only).
Run from the repo root:
    python3 tests/test_paper_tools.py
Each script writes next to itself, so the tests copy it into a temporary directory with a small
fixture, run it twice, and check the output and that the second run is byte-identical."""

import importlib
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAPER = ROOT / "docs" / "paper"
sys.path.insert(0, str(PAPER))
mr = importlib.import_module("make_register")

HEAD = (
    "| H-ID | round / section | a | b | c | d | e | f | g | verdict | h |\n"
    "|---|---|---|---|---|---|---|---|---|---|---|\n"
)
HYP = (
    "# Register\n\n## Round 1\n\n" + HEAD
    + "| A1 | R1, f.md:1 | x | Alpha & beta 50% | f | e | m | 0.5 > 0.2 | t | USEFUL | yes |\n"
    + "| A2 | same | x | Gamma | frame | exp | m | res_two | t | POSSIBLY GOOD (narrow) | yes |\n"
    + "| R2-L1 | R2:22 | x | Delta | frame | exp | m | res | t | DISMISSED | no |\n"
    + "| QQ | f.md:9 | x | Eps | frame | exp | m | res | t | MEASUREMENT (not counted) | no |\n"
    + "\n## Untested hypotheses\n\n| H-ID | idea | experiment it needs |\n|---|---|---|\n"
    + "| L3 | An idea. | An experiment. |\n"
)


def run(script: str, workdir: Path, *args: str) -> None:
    subprocess.run([sys.executable, str(workdir / script), *args], cwd=workdir, check=True,
                   capture_output=True)


class Register(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        shutil.copy(PAPER / "make_register.py", self.dir)
        (self.dir / "hypotheses.md").write_text(HYP, encoding="utf-8")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_round_tag(self) -> None:
        self.assertEqual(mr.round_tag("R2:22, loki.tex", "-"), "R2")
        self.assertEqual(mr.round_tag("HAL:95", "-"), "HAL")
        self.assertEqual(mr.round_tag("same", "R4"), "R4")
        self.assertEqual(mr.round_tag("loki.tex:1933", "R4"), "Q")

    def test_escape(self) -> None:
        self.assertEqual(mr.esc("a & b_c 5%"), r"a \& b\_c 5\%")
        self.assertEqual(mr.esc("x `a_b` y"), r"x \code{a\_b} y")
        self.assertEqual(mr.esc("0.5 > 0.2"), "0.5 $>$ 0.2")

    def test_verdict_word_unknown(self) -> None:
        with self.assertRaises(SystemExit):
            mr.verdict_word("MAYBE")

    def test_output_and_determinism(self) -> None:
        run("make_register.py", self.dir)
        first = (self.dir / "register.tex").read_text(encoding="utf-8")
        self.assertIn("hypotheses 1 to 5 of 5", first)
        self.assertIn(r"A1 & R1 & Alpha \& beta 50\% & 0.5 $>$ 0.2 & \textsc{useful}", first)
        self.assertIn(r"\textsc{possibly good}", first)
        self.assertIn(r"\textsc{measurement}", first)
        self.assertIn("L3 & - & An idea. & not run; needs: An experiment. &", first)
        self.assertIn("\\textsc{untested}", first)
        self.assertIn("A2 & R1 &", first)
        self.assertIn("R2-L1 & R2 &", first)
        run("make_register.py", self.dir)
        self.assertEqual(first, (self.dir / "register.tex").read_text(encoding="utf-8"))


TABLE = (
    "% header\n\\newcommand{{\\m{n}}}{{7}}\n\\begin{{table}}[t]\n\\caption{{c}}\n"
    "\\label{{tab:{n}-a}}\n"
    "x\n\\end{{table}}\n\\begin{{table*}}[t]\n\\label{{tab:{n}-b}}\n\\end{{table*}}\n"
)
NAMES = ["round2", "round3", "round4", "round5", "round6", "hal"]


class Split(unittest.TestCase):
    def test_split(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            shutil.copy(PAPER / "split_tables.py", d)
            for n in NAMES:
                (d / f"{n}-tables.tex").write_text(TABLE.format(n=n), encoding="utf-8")
            run("split_tables.py", d)
            snap = {p.name: p.read_bytes() for p in (d / "gen").iterdir()}
            self.assertEqual(len(snap), 3 * len(NAMES))
            self.assertIn("tab-round2-a.tex", snap)
            self.assertIn(b"\\begin{table*}", snap["tab-hal-b.tex"])
            self.assertIn(b"\\newcommand{\\mround2}{7}", snap["round2-macros.tex"])
            self.assertNotIn(b"\\begin{table}", snap["round2-macros.tex"])
            run("split_tables.py", d)
            self.assertEqual(snap, {p.name: p.read_bytes() for p in (d / "gen").iterdir()})

    def test_unlabelled_table_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            shutil.copy(PAPER / "split_tables.py", d)
            for n in NAMES:
                (d / f"{n}-tables.tex").write_text("\\begin{table}\nx\n\\end{table}\n",
                                                   encoding="utf-8")
            res = subprocess.run([sys.executable, str(d / "split_tables.py")], cwd=d,
                                 capture_output=True, text=True)
            self.assertNotEqual(res.returncode, 0)
            self.assertIn("table without label", res.stderr)


TEX = (
    "\\section{Intro}\nA designer writes HDL here. % def:hdl\n"
    "A netlist is a list of gates. % def:netlist\n"
)


class Glossary(unittest.TestCase):
    def test_glossary_and_terms(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            for f in ("make_glossary.py", "check_terms.py"):
                shutil.copy(PAPER / f, d)
            (d / "loki.tex").write_text(TEX, encoding="utf-8")
            run("make_glossary.py", d, "--tex", str(d / "loki.tex"))
            gloss = (d / "glossary.tex").read_text(encoding="utf-8")
            terms = (d / "terms.md").read_text(encoding="utf-8")
            self.assertTrue(gloss.startswith("% Generated by make_glossary.py"))
            self.assertIn("% ref:hdl", gloss)
            self.assertIn("% def:ff", gloss)
            self.assertNotIn("% def:hdl", gloss)
            self.assertIn("| HDL |", terms)
            self.assertIn("loki.tex:2", terms)
            run("make_glossary.py", d, "--tex", str(d / "loki.tex"))
            self.assertEqual(gloss, (d / "glossary.tex").read_text(encoding="utf-8"))
            self.assertEqual(terms, (d / "terms.md").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
