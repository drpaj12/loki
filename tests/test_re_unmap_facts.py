"""The Odin III ``unmap`` facts L1 spec 7.2 relies on; skip without the pass (plan Task 17).

A BLIF input gives every hard cell its own IMPORTED record, so a group of RAM cells with equal
control nets is ambiguous and every member carries ``unmap_cand`` (unmap R-6/R-7).
"""

import importlib
import json
import os
import tempfile
import unittest
from pathlib import Path
from typing import Any

from loki.re.detectors.hard import HardDetector
from loki.re.fngraph import FnGraph, from_design
from loki.re.normalise import load_level0
from tests.helpers import odin3_root

MIX = (
    ".model mix\n"
    ".inputs a b d\n"
    ".outputs s co p\n"
    ".names k\n"
    ".subckt adder a=a b=b cin=k cout=co sumout=s\n"
    ".subckt multiply a[0]=d b[0]=d out[0]=p\n"
    ".end\n"
)
RAM = (
    ".model ram_pair\n"
    ".inputs c w a0 a1 d0 d1\n"
    ".outputs o0 o1\n"
    ".subckt single_port_ram clk=c we=w addr[0]=a0 addr[1]=a1 data[0]=d0 out[0]=o0\n"
    ".subckt single_port_ram clk=c we=w addr[0]=a0 addr[1]=a1 data[0]=d1 out[0]=o1\n"
    ".end\n"
)
# 1-based lines of the ``.subckt`` rows above.
MIX_LINES = (5, 6)
RAM_LINES = (4, 5)


def unmap_available() -> bool:
    """True when the odin3 module imports and its pass list has ``unmap``."""
    try:
        mod = importlib.import_module("odin3")
        o = mod.Odin3()
    except Exception:
        return False
    return "unmap" in o.passes()


def _source_lines(node: Any) -> list[int]:
    return [int(s.line) for s in node.sources()]


@unittest.skipUnless(
    unmap_available() and odin3_root() is not None, "needs an Odin III build with `unmap`"
)
class UnmapFactsTest(unittest.TestCase):
    o: Any
    root: Path

    @classmethod
    def setUpClass(cls) -> None:
        cls.o = importlib.import_module("odin3").default()
        root = odin3_root()
        assert root is not None
        cls.root = root

    def _load(self, text: str) -> tuple[Any, FnGraph]:
        mod = importlib.import_module("odin3")
        tmp = tempfile.TemporaryDirectory(prefix="loki-unmap-facts-")
        self.addCleanup(tmp.cleanup)
        path = Path(tmp.name) / "netlist.blif"
        path.write_text(text, encoding="utf-8")
        design = mod.Design(self.o)
        with self.o.capture_log():
            design.run_script(
                f'read_techlib "{self.root / "lib" / "vtr.o3lib"}"; read_blif "{path}"'
            )
        return design, from_design(design)

    def test_recovered_cells_have_the_rule_and_the_subckt_sources(self) -> None:
        design, _ = self._load(MIX)
        with self.o.capture_log():
            design.run_script("unmap")
        nodes = list(design.top().nodes())
        recovered = [n for n in nodes if n.attr("unmap") is not None]
        self.assertEqual(sorted(str(n.type_name) for n in recovered), ["$add", "$mul"])
        rules = {str(n.type_name): n.attr("unmap") for n in recovered}
        self.assertEqual(rules, {"$add": "chain", "$mul": "mul"})
        self.assertEqual(
            sorted(line for n in recovered for line in _source_lines(n)), list(MIX_LINES)
        )
        design.close()

    def test_ram_candidates_carry_unmap_cand(self) -> None:
        design, _ = self._load(RAM)
        with self.o.capture_log():
            design.run_script("unmap")
        mems = [n for n in design.top().nodes() if str(n.type_name) == "$mem"]
        self.assertEqual(len(mems), 2)
        for node in mems:
            self.assertEqual(node.attr("unmap"), "ram")
            self.assertEqual(node.attr("unmap_cand"), "ram:0")
        self.assertEqual(sorted(line for n in mems for line in _source_lines(n)), list(RAM_LINES))
        design.close()

    def test_second_unmap_changes_nothing(self) -> None:
        design, _ = self._load(MIX)
        with tempfile.TemporaryDirectory(prefix="loki-unmap-facts-") as tmpname:
            first, second = Path(tmpname) / "a.il", Path(tmpname) / "b.il"
            with self.o.capture_log():
                design.run_script("unmap")
                design.run_pass("write_rtlil", f'"{first}"')
                design.run_script("unmap")
                design.run_pass("write_rtlil", f'"{second}"')
            self.assertEqual(first.read_bytes(), second.read_bytes())
        design.close()


DATASET_ENV = "LOKI_L0_DATASET"
FLOOR = "f1-k6"


def l0_dataset() -> Path | None:
    """``$LOKI_L0_DATASET`` (an assembled L0 dataset) when set."""
    raw = os.environ.get(DATASET_ENV, "")
    return Path(raw) if raw else None


@unittest.skipUnless(
    unmap_available() and odin3_root() is not None, "needs an Odin III build with `unmap`"
)
class DatasetFloorTest(unittest.TestCase):
    """Plan Task 17 Step 1 on the L0 ``f1-k6`` BLIF of real dataset designs, not a synthetic one."""

    root: Path
    dataset: Path

    def setUp(self) -> None:
        dataset = l0_dataset()
        if dataset is None:
            self.skipTest(f"set {DATASET_ENV} to an assembled L0 dataset")
        root = odin3_root()
        assert root is not None
        self.root, self.dataset = root, dataset

    def _floors(self) -> list[tuple[str, Path]]:
        """(design, netlist) of every dataset design whose ``f1-k6`` floor was built."""
        manifest = json.loads((self.dataset / "manifest.json").read_text(encoding="utf-8"))
        out: list[tuple[str, Path]] = []
        for entry in manifest.get("designs", []):
            if entry.get("floors", {}).get(FLOOR, {}).get("status") != "ok":
                continue
            path = self.dataset / str(entry.get("design", "")) / FLOOR / "netlist.blif"
            if path.is_file():
                out.append((str(entry.get("design", "")), path))
        out.sort()
        return out

    def _unmapped(self, path: Path) -> tuple[Any, FnGraph]:
        """The re level 0 of a dataset BLIF, its graph and the design after ``unmap``."""
        design = load_level0(path, FLOOR, self.root, None)
        self.addCleanup(design.close)
        graph = from_design(design)
        with importlib.import_module("odin3").default().capture_log():
            design.run_pass("unmap")
        return design, graph

    def test_dataset_micro_with_adder_and_multiply(self) -> None:
        """A dataset micro recovers ``$add``/``$sub`` from ``chain`` and ``$mul`` from ``mul``,
        with the ``.subckt`` lines as their sources (plan Task 17 Step 1)."""
        floors = self._floors()
        if not floors:
            self.skipTest("the dataset has no f1-k6 netlist.blif")
        for _, path in floors:
            text = path.read_text(encoding="utf-8")
            if ".subckt adder" not in text or ".subckt multiply" not in text:
                continue
            design, graph = self._unmapped(path)
            nodes = [n for n in design.top().nodes() if n.attr("unmap") is not None]
            muls = [n for n in nodes if str(n.type_name) == "$mul"]
            adds = [n for n in nodes if str(n.type_name) in ("$add", "$sub")]
            if not (muls and adds):
                continue
            records = HardDetector.read_unmap(design, graph)
            self.assertTrue([r for r in records if r.node_type == "$mul" and r.rule == "mul"])
            self.assertTrue([r for r in records if r.node_type in ("$add", "$sub") and r.rule])
            lines = text.splitlines()
            add_lines = {
                i for i, line in enumerate(lines, 1)
                if line.startswith((".subckt adder", ".subckt subtract"))
            }
            mul_lines = {
                i for i, line in enumerate(lines, 1) if line.startswith(".subckt multiply")
            }
            for node in muls:
                self.assertEqual(node.attr("unmap"), "mul")
                self.assertTrue(_source_lines(node))
                self.assertLessEqual(set(_source_lines(node)), mul_lines)
            for node in adds:
                self.assertTrue(node.attr("unmap"))
                self.assertLessEqual(set(_source_lines(node)), add_lines)
            return
        self.skipTest("no dataset f1-k6 micro recovered both an adder and a multiply")

    def test_dataset_ram_micro(self) -> None:
        """A dataset RAM micro's ``$mem`` cells carry ``unmap`` ``ram`` and ``unmap_cand``
        ``ram:<N>`` (plan Task 17 Step 1); skips when the dataset has no RAM floor."""
        path = next(
            (
                p for _, p in self._floors()
                if any(
                    line.startswith(".subckt") and "ram" in line.lower()
                    for line in p.read_text(encoding="utf-8").splitlines()
                )
            ),
            None,
        )
        if path is None:
            self.skipTest("the dataset has no f1-k6 RAM micro")
        design, _ = self._unmapped(path)
        mems = [n for n in design.top().nodes() if str(n.type_name) == "$mem"]
        self.assertTrue(mems)
        for node in mems:
            self.assertEqual(node.attr("unmap"), "ram")
            self.assertTrue(str(node.attr("unmap_cand")).startswith("ram:"))


if __name__ == "__main__":
    unittest.main()
