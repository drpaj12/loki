import unittest
from pathlib import Path

from loki.re.fngraph import Cell, FnGraph, cover_to_table
from loki.re.normalise import floor_from_path


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


if __name__ == "__main__":
    unittest.main()
