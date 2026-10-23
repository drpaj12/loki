"""The Odin III ``unmap`` facts L1 spec 7.2 relies on; skip without the pass (plan Task 17).

A BLIF input gives every hard cell its own IMPORTED record, so a group of RAM cells with equal
control nets is ambiguous and every member carries ``unmap_cand`` (unmap R-6/R-7).
"""

import importlib
import tempfile
import unittest
from pathlib import Path
from typing import Any

from loki.re.fngraph import FnGraph, from_design
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


if __name__ == "__main__":
    unittest.main()
