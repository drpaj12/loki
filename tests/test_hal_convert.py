"""BLIF reader, BLIF to HAL Verilog converter, HAL gate libraries and the function round trip."""

import json
import os
import re
import shutil
import tempfile
import unittest
from pathlib import Path

from loki.hal import hgl
from loki.hal.blif import BlifError, Gate, parse_blif
from loki.hal.blif2hal import ConvertError, convert
from loki.hal.sim import compare_traces

ROOT = Path(__file__).resolve().parents[1]
MICRO = Path(os.environ.get("LOKI_MICRO", str(ROOT.parent / "loki-rename-exp" / "dataset-rebuild")))
HAVE_IVERILOG = shutil.which("iverilog") is not None and shutil.which("vvp") is not None

F2 = """\
.model top
.inputs n0 n1 n2 n3 n4
.outputs n9 n10 n11
.names n0 n1 n2 n5
100 1
111 1
.cname n20
.names n6
1
.cname n21
.names n5 n6 n7
1- 1
-0 1
.cname n22
.latch n7 n8 re n4 1
.cname n23
.latch n3 n9 re n4 3
.cname n24
.names n8 n9 n10
01 1
10 1
.cname n25
.names n8 n11
0 1
.cname n26
.end
"""

F3 = """\
.model top
.inputs n0 n1 n2 n3
.outputs n8 n9 n10 n11
.names n12
.cname n30
.names n0 n1 n4
00 1
01 1
10 1
.cname n31
.names n4 n2 n5
00 1
.cname n32
.names n5 n6
0 1
.cname n33
.names n6 n12 n7
00 1
01 1
10 1
.cname n34
.names n7 n8
1 1
.cname n35
.latch n6 n9 re n3 3
.cname n36
.subckt DFFSR C=n3 D=n5 S=n1 R=n2 Q=n10
.cname n37
.names n4 n10 n11
00 1
01 1
10 1
.cname n38
.end
"""


def workdir() -> Path:
    return Path(tempfile.mkdtemp(prefix="lhl-"))


class BlifTest(unittest.TestCase):
    def test_parse_cells_and_cnames(self) -> None:
        b = parse_blif(F2)
        self.assertEqual(b.inputs, ("n0", "n1", "n2", "n3", "n4"))
        self.assertEqual(len(b.cells), 7)
        self.assertEqual([c.cname for c in b.cells][:3], ["n20", "n21", "n22"])

    def test_tables(self) -> None:
        b = parse_blif(F2)
        g = [c for c in b.cells if isinstance(c, Gate)]
        self.assertEqual(g[0].table(), 0b10000010)
        self.assertEqual(g[1].table(), 1)
        self.assertEqual(g[2].table(), 0b1011)

    def test_off_set_and_continuation(self) -> None:
        b = parse_blif(".model m\n.inputs a \\\n b\n.outputs y\n.names a b y\n11 0\n.end\n")
        self.assertEqual(b.inputs, ("a", "b"))
        gate = b.cells[0]
        assert isinstance(gate, Gate)
        self.assertEqual(gate.table(), 0b0111)

    def test_errors(self) -> None:
        with self.assertRaises(BlifError):
            parse_blif("11 1\n")
        with self.assertRaises(BlifError):
            parse_blif(".inputs a\n")


class ConvertTest(unittest.TestCase):
    def test_f2_text(self) -> None:
        v = convert(parse_blif(F2), "f2")
        self.assertIn("LUT3 #(.INIT(8'h82)) n20 (.I0(n0), .I1(n1), .I2(n2), .O(n5));", v)
        self.assertIn("VCC n21 (.O(n6));", v)
        self.assertIn("LUT2 #(.INIT(4'hB)) n22 (.I0(n5), .I1(n6), .O(n7));", v)
        self.assertIn("FF #(.INIT(1'b1)) n23 (.C(n4), .D(n7), .Q(n8));", v)
        self.assertIn("  FF n24 (.C(n4), .D(n3), .Q(n9));", v)
        self.assertIn("wire n5;", v)
        self.assertNotIn("wire n9;", v)
        self.assertTrue(v.startswith("module top (n0, n1, n2, n3, n4, n9, n10, n11);"))

    def test_f3_text(self) -> None:
        v = convert(parse_blif(F3), "f3")
        self.assertIn("GND n30 (.O(n12));", v)
        self.assertIn("NAND2 n31 (.A(n0), .B(n1), .Y(n4));", v)
        self.assertIn("NOR2 n32 (.A(n4), .B(n2), .Y(n5));", v)
        self.assertIn("INV n33 (.A(n5), .Y(n6));", v)
        self.assertIn("NAND2 n34 (.A(n6), .B(n12), .Y(n7));", v)
        self.assertIn("BUF n35 (.A(n7), .Y(n8));", v)
        self.assertIn("DFF n36 (.C(n3), .D(n6), .Q(n9));", v)
        self.assertIn("DFFSR n37 (.C(n3), .D(n5), .S(n1), .R(n2), .Q(n10));", v)

    def test_f3_rejects_and2(self) -> None:
        with self.assertRaises(ConvertError):
            convert(parse_blif(F3.replace("00 1\n.cname n32", "11 1\n.cname n32")), "f3")

    def test_rejections(self) -> None:
        hard = ".model t\n.inputs a\n.outputs y\n.subckt multiply a[0]=a out[0]=y\n.end\n"
        with self.assertRaises(ConvertError):
            convert(parse_blif(hard), "f2")
        fe = ".model t\n.inputs a c\n.outputs q\n.latch a q fe c 3\n.end\n"
        with self.assertRaises(ConvertError):
            convert(parse_blif(fe), "f2")
        odd = ".model t\n.inputs a[0]\n.outputs y\n.names a[0] y\n1 1\n.end\n"
        with self.assertRaises(ConvertError):
            convert(parse_blif(odd), "f2")
        with self.assertRaises(ConvertError):
            convert(parse_blif(F2), "f1")

    def test_seven_inputs_rejected_on_f2(self) -> None:
        text = ".model t\n.inputs a b c d e f g\n.outputs y\n.names a b c d e f g y\n" \
               "1111111 1\n.end\n"
        with self.assertRaises(ConvertError):
            convert(parse_blif(text), "f2")

    def test_instance_pins_exist_in_library(self) -> None:
        for floor, text in (("f2", F2), ("f3", F3)):
            lib = {c["name"]: {p["name"] for g in c["pin_groups"] for p in g["pins"]}
                   for c in hgl.LIBRARIES["lut6" if floor == "f2" else "cmos6"]()["cells"]}
            for line in convert(parse_blif(text), floor).splitlines():
                m = re.match(r"\s+(\w+)(?: #\(.*?\))? (\w+) \((.*)\);", line)
                if not m:
                    continue
                self.assertIn(m.group(1), lib, line)
                pins = set(re.findall(r"\.(\w+)\(", m.group(3)))
                self.assertLessEqual(pins, lib[m.group(1)], line)


class HglTest(unittest.TestCase):
    def test_committed_files_match_generator(self) -> None:
        for name in hgl.LIBRARIES:
            path = ROOT / "experiments" / "hal" / "hgl" / f"{name}.hgl"
            self.assertEqual(path.read_text(encoding="utf-8"), hgl.render(name), name)

    def test_shape(self) -> None:
        for name, make in hgl.LIBRARIES.items():
            lib = make()
            self.assertEqual(lib["version"], 4)
            json.dumps(lib)
            cells = {c["name"]: c for c in lib["cells"]}
            ffs = [c for c in cells.values() if "ff" in c["types"]]
            self.assertTrue(ffs, name)
            for c in ffs:
                self.assertEqual(c["ff_config"]["clocked_on"], "C")
                types = {p["type"] for g in c["pin_groups"] for p in g["pins"]}
                self.assertIn("clock", types)
        self.assertEqual(sorted(c["name"] for c in hgl.lut6()["cells"] if "c_lut" in c["types"]),
                         [f"LUT{k}" for k in range(1, 7)])
        sr = {c["name"]: c for c in hgl.cmos6()["cells"]}["DFFSR"]["ff_config"]
        self.assertEqual((sr["clear_on"], sr["preset_on"]), ("R", "S"))


@unittest.skipUnless(HAVE_IVERILOG, "iverilog not installed")
class RoundTripTest(unittest.TestCase):
    def check(self, text: str, floor: str) -> None:
        b = parse_blif(text)
        self.assertEqual(compare_traces(b, floor, convert(b, floor), workdir()), "")

    def test_f2_fixture(self) -> None:
        self.check(F2, "f2")

    def test_f3_fixture(self) -> None:
        self.check(F3, "f3")

    def test_detects_a_wrong_init(self) -> None:
        b = parse_blif(F2)
        bad = convert(b, "f2").replace("8'h82", "8'h83")
        self.assertNotEqual(compare_traces(b, "f2", bad, workdir()), "")


@unittest.skipUnless(HAVE_IVERILOG and MICRO.is_dir(), "iverilog or the micro dataset missing")
class MicroRoundTripTest(unittest.TestCase):
    def run_floor(self, floor: str) -> None:
        n = 0
        skipped = []
        for d in sorted(MICRO.iterdir()):
            blif = d / floor / "netlist.blif"
            if not blif.is_file():
                continue
            b = parse_blif(blif.read_text(encoding="utf-8"))
            try:
                v = convert(b, floor)
            except ConvertError:
                skipped.append(d.name)
                continue
            self.assertEqual(compare_traces(b, floor, v, workdir(), cycles=32), "", d.name)
            graph = json.loads((d / floor / "graph.json").read_text(encoding="utf-8"))
            ids = {x["id"] for x in graph["nodes"]}
            names = set(re.findall(r"^\s+\w+(?: #\(.*?\))? (\w+) \(", v, re.M))
            self.assertLessEqual({x for x in names if not x.startswith("_c")}, ids, d.name)
            ffs = {x["id"] for x in graph["nodes"] if x["kind"] == "ff"}
            self.assertLessEqual(ffs, names, d.name)
            n += 1
        self.assertGreater(n, 50)
        self.assertLessEqual(len(skipped), 3, skipped)

    def test_f2(self) -> None:
        self.run_floor("f2")

    def test_f3(self) -> None:
        self.run_floor("f3")


if __name__ == "__main__":
    unittest.main()
