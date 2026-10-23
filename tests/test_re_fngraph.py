import os
import tempfile
import unittest
from pathlib import Path
from typing import Any

from loki.build import build_floor
from loki.equiv import check_equiv
from loki.odin import odin_module
from loki.re.fngraph import Cell, FnGraph, cover_to_table, from_design
from loki.re.normalise import floor_from_path, load_level0
from tests.helpers import have_f3, micro, odin3_root

# The cmos6 gate functions: (width, table) as L0 writes them as `.names` covers.
GATE_TABLES = {(1, 0b01), (1, 0b10), (2, 0b0001), (2, 0b0111)}
DATASET = os.environ.get("LOKI_DATASET", "")
SAMPLE = 8


def cell(cid: int, name: str = "", kind: str = "lut") -> Cell:
    return Cell(cid, name, kind, "$sop", (), (), 0, 0, 0, 0, {})


class CoverTest(unittest.TestCase):
    def test_cover_on_set(self) -> None:
        self.assertEqual(cover_to_table("10 1\n01 1\n", 2), 0b0110)

    def test_cover_dash(self) -> None:
        self.assertEqual(cover_to_table("1- 1\n", 2), 0b1010)

    def test_cover_off_set(self) -> None:
        self.assertEqual(cover_to_table("11 0\n", 2), 0b0111)

    def test_const_covers(self) -> None:
        self.assertEqual(cover_to_table("1\n", 0), 1)
        self.assertEqual(cover_to_table("", 0), 0)
        self.assertEqual(cover_to_table("", 3), 0)

    def test_mixed_rows_rejected(self) -> None:
        with self.assertRaises(ValueError):
            cover_to_table("1 1\n0 0\n", 1)


class GraphTest(unittest.TestCase):
    def test_floor_from_path(self) -> None:
        self.assertEqual(floor_from_path(Path("d/x/f1-k6/netlist.blif")), "f1-k6")
        with self.assertRaises(ValueError):
            floor_from_path(Path("x.blif"))

    def test_label_fallback(self) -> None:
        g = FnGraph({5: cell(5), 6: cell(6, "n6")}, {}, {}, {}, (), (), {}, "")
        self.assertEqual((g.label(5), g.label(6)), ("c5", "n6"))

    def test_sources(self) -> None:
        ff = Cell(2, "", "ff", "$_DFF_P_", (1,), (9,), 0, 0, 3, 0, {})
        lut = Cell(1, "", "lut", "$sop", (4,), (1,), 2, 1, 0, 0, {})
        g = FnGraph({1: lut, 2: ff}, {1: 1, 9: 2}, {}, {}, (4, 3), (9,), {}, "")
        self.assertEqual(g.sources(), frozenset({4, 3, 9}))


def _f3_floor(name: str, out: Path) -> Path:
    """Build one micro at floor F3; returns its floor directory."""
    root = odin3_root()
    assert root is not None
    design = f"micro_{name}"
    res = build_floor(design, [micro(name)], None, "f3", None, out, root)
    assert res.status == "ok", res.reason
    return out / design / "f3"


def _logic_tables(graph: FnGraph) -> list[tuple[str, int, int]]:
    """The function tables of the logic cells; constants are not logic (a dangling one may
    not survive a round trip)."""
    return sorted((c.kind, c.width, c.table) for c in graph.cells.values()
                  if c.kind in ("lut", "ff", "latch"))


def _write_blif(design: Any, out: Path) -> str:
    """Spec 9.4's final write: flatten, lower, a BLIF with the gates as named subcircuits."""
    mod = odin_module()
    with mod.default().capture_log():
        design.run_script(f'flatten; lower; write_blif --gates-as-names "{out}"')
    return out.read_text(encoding="utf-8")


@unittest.skipUnless(have_f3(), "needs Odin III with gate mapping")
class F3NormaliseTest(unittest.TestCase):
    """Task 18: an L0 F3 floor reads as `$sop` gates from both its BLIF and its Verilog."""

    tmp: tempfile.TemporaryDirectory[str]
    floor: Path
    ff_floor: Path

    @classmethod
    def setUpClass(cls) -> None:
        cls.tmp = tempfile.TemporaryDirectory(prefix="loki-f3-")
        root = Path(cls.tmp.name)
        cls.floor = _f3_floor("bm_DL_4_bit_comparator", root)
        cls.ff_floor = _f3_floor("bm_DL_D_flipflop", root)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.tmp.cleanup()

    def test_f3_blif_reads_as_sop(self) -> None:
        graph = from_design(load_level0(self.floor / "netlist.blif", "f3", None, None))
        luts = [c for c in graph.cells.values() if c.kind == "lut"]
        self.assertGreaterEqual(len(luts), 20)
        self.assertEqual({c.kind for c in graph.cells.values()} - {"const"}, {"lut"})
        for cell in luts:
            self.assertIn((cell.width, cell.table), GATE_TABLES, (cell.line, cell.type))
        self.assertEqual((len(graph.pis), len(graph.pos)), (8, 3))

    def test_f3_verilog_normalised(self) -> None:
        # A combinational floor and one with a process (the `always` block of a DFF).
        for floor in (self.floor, self.ff_floor):
            blif = from_design(load_level0(floor / "netlist.blif", "f3", None, None))
            verilog = from_design(load_level0(floor / "netlist.v", "f3", odin3_root(), None))
            self.assertLessEqual({c.kind for c in verilog.cells.values()} - {"const"},
                                 {"lut", "ff"})
            self.assertEqual(_logic_tables(verilog), _logic_tables(blif), floor)
            self.assertEqual((len(verilog.pis), len(verilog.pos)),
                             (len(blif.pis), len(blif.pos)), floor)


@unittest.skipUnless(have_f3() and DATASET, "needs Odin III with gate mapping and LOKI_DATASET")
class F3SampleEquivTest(unittest.TestCase):
    """Task 18 review: only the comparator reproduces gate for gate; a re-synthesised floor
    (different `(kind, width, table)` multiset) must still be logically equivalent to its
    BLIF normalisation by the acceptance tests' equiv-check (spec 9.4)."""

    def test_sample_logically_equivalent(self) -> None:
        root = odin3_root()
        assert root is not None
        floors = sorted(p.parent for p in Path(DATASET).glob("*/f3/netlist.v"))
        self.assertGreaterEqual(len(floors), SAMPLE)
        sample = floors[:: max(1, len(floors) // SAMPLE)]
        re_synthesised = 0
        for floor in sample:
            blif = load_level0(floor / "netlist.blif", "f3", None, None)
            verilog = load_level0(floor / "netlist.v", "f3", root, None)
            try:
                if _logic_tables(from_design(blif)) == _logic_tables(from_design(verilog)):
                    continue
                re_synthesised += 1
                with tempfile.TemporaryDirectory(prefix="loki-f3-eq-") as tmp:
                    a = _write_blif(blif, Path(tmp) / "a.blif")
                    b = _write_blif(verilog, Path(tmp) / "b.blif")
            finally:
                blif.close()
                verilog.close()
            res = check_equiv(a, b, root, False)
            self.assertEqual(res.status, "equivalent", f"{floor.name}: {res.detail}")
        self.assertGreater(re_synthesised, 0, "sample: every floor reproduced gate for gate")


if __name__ == "__main__":
    unittest.main()
