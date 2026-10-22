import csv
import io
import json
import tempfile
import unittest
from pathlib import Path

from loki.blifout import identity_naming, write_blif
from loki.build import build_floor, cmos6_path
from loki.model import FinalCell, Net, Netlist, Port, PortBit
from loki.odin import floor_script
from loki.techlib import TechlibError, load_techlib, parse_techlib
from tests.helpers import have_f3, micro, odin3_root

GATES = {"BUF", "INV", "NAND2", "NOR2"}


def build_f3(name: str, out: Path) -> tuple[str, str]:
    root = odin3_root()
    assert root is not None
    res = build_floor(name, [micro(name)], None, "f3", None, out, root)
    return res.status, res.reason


class ScriptTest(unittest.TestCase):
    def test_f3_scripts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            lib = Path(tmp) / "x.o3lib"
            lib.write_text("library mylib\ncell BUF gate area 1\n in A 1 ; out Y 1\n"
                           " fn Y = A\nend\n", encoding="utf-8")
            front, mapping = floor_script("f3", [Path("/x/a.v")], None, lib)
        self.assertTrue(front.startswith(f'read_techlib "{lib}"; read_verilog --nolatches '))
        self.assertTrue(front.endswith("; proc; fsm; opt; flatten; opt -full; wreduce"))
        self.assertEqual(mapping, "lower; abc --gates mylib; dfflibmap mylib")


class TechlibTest(unittest.TestCase):
    def test_cmos6_covers(self) -> None:
        root = odin3_root()
        if root is None or not cmos6_path(root).is_file():
            self.skipTest("needs lib/cmos6.o3lib")
        lib = load_techlib(cmos6_path(root))
        self.assertEqual(lib.name, "cmos6")
        self.assertEqual(lib.gate_names(), frozenset(GATES))
        self.assertEqual(lib.state_names(), frozenset({"DFF"}))
        self.assertEqual(lib.cover("NAND2"), (("A", "B"), ["00", "01", "10"]))
        self.assertEqual(lib.cover("NOR2"), (("A", "B"), ["00"]))
        self.assertEqual(lib.cover("INV"), (("A",), ["0"]))
        self.assertEqual(lib.cover("BUF"), (("A",), ["1"]))

    def test_function_subset(self) -> None:
        text = (
            "library t\ncell M gate area 1\n  in A 1 ; in B 1 ; in S 1 ; out Y 1\n"
            "  fn Y = S ? B : ~A ^ 1'b1\nend\n"
        )
        lib = parse_techlib(text)
        ins, rows = lib.cover("M")
        self.assertEqual(ins, ("A", "B", "S"))
        want = [f"{a}{b}{s}" for a in "01" for b in "01" for s in "01"
                if ((int(b) if s == "1" else ((1 - int(a)) ^ 1)) == 1)]
        self.assertEqual(rows, want)

    def test_bad_function(self) -> None:
        text = "library t\ncell M gate area 1\n  in A 1 ; out Y 1\n  fn Y = A $ 1\nend\n"
        with self.assertRaises(TechlibError):
            parse_techlib(text).cover("M")

    def test_gate_names_blif(self) -> None:
        """Gates are written as .names of their function; a DFF as .latch."""
        root = odin3_root()
        if root is None or not cmos6_path(root).is_file():
            self.skipTest("needs lib/cmos6.o3lib")
        lib = load_techlib(cmos6_path(root))
        nets = {i: Net(i, ()) for i in range(1, 6)}
        nand = FinalCell(
            10, "gate", "NAND2", "", {}, (),
            (Port("A", 1, (1,)), Port("B", 1, (2,))), (Port("Y", 1, (3,)),),
        )
        dff = FinalCell(
            11, "ff", "DFF", "", {}, (),
            (Port("C", 1, (4,)), Port("D", 1, (3,))), (Port("Q", 1, (5,)),),
        )
        pbs = (PortBit("a", "in", 1), PortBit("b", "in", 2), PortBit("c", "in", 4),
               PortBit("q", "out", 5))
        text = write_blif(Netlist("t", nets, (nand, dff), pbs), identity_naming(
            Netlist("t", nets, (nand, dff), pbs)), lib)
        self.assertIn(".names a b w3\n00 1\n01 1\n10 1", text)
        self.assertIn(".latch w3 q re c 3", text)


@unittest.skipUnless(have_f3(), "needs Odin III with gate mapping")
class F3Test(unittest.TestCase):
    def test_f3_comparator(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            self.assertEqual(build_f3("bm_DL_4_bit_comparator", out), ("ok", ""))
            fdir = out / "bm_DL_4_bit_comparator" / "f3"
            graph = json.loads((fdir / "graph.json").read_text(encoding="utf-8"))
            meta = json.loads((fdir / "meta.json").read_text(encoding="utf-8"))
            kinds = {n["kind"] for n in graph["nodes"]}
            self.assertEqual(kinds, {"pi", "po", "const", "gate"})
            self.assertEqual(meta["equiv"]["writer"]["status"], "equivalent")
            self.assertEqual(meta["equiv"]["anon"]["status"], "equivalent")
            self.assertEqual(meta["equiv"]["writer"]["mode"], "full")
            key = json.loads((fdir / "key.json").read_text(encoding="utf-8"))
            types = {c["type"] for c in key["cells"].values()}
            self.assertEqual(types - {"$_CONST1_"}, types & GATES)
            self.assertTrue(types & GATES)
            rows = list(csv.DictReader(io.StringIO((fdir / "labels.csv").read_text("utf-8"))))
            gate_rows = [r for r in rows if r["kind"] == "gate"]
            self.assertTrue(gate_rows)
            for r in gate_rows:  # provenance is per cone (gatemap G-2), so a count above 1 is fine
                self.assertGreaterEqual(int(r["n_construct_cells"]), 1, r)
                self.assertTrue(r["hdl_file"], r)
            self.assertIn(max(int(r["n_construct_cells"]) for r in gate_rows), range(2, 99))
            self.assertEqual(meta["unmatched"], 0)

    def test_f3_flip_flops(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            self.assertEqual(build_f3("bm_DL_D_flipflop", out), ("ok", ""))
            text = (out / "bm_DL_D_flipflop" / "f3" / "netlist.blif").read_text("utf-8")
            self.assertIn(".latch", text)
            self.assertNotIn(".subckt", text)
            meta = json.loads(
                (out / "bm_DL_D_flipflop" / "f3" / "meta.json").read_text(encoding="utf-8")
            )
            self.assertEqual(meta["equiv"]["writer"]["status"], "equivalent")
            self.assertEqual(meta["counts"]["ff"], 1)


if __name__ == "__main__":
    unittest.main()
