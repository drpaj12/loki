import unittest

from loki.extract import Unsupported, extract_netlist
from loki.odin import open_front
from tests.helpers import DATA, can_run_f2, f2_arch, micro


@unittest.skipUnless(can_run_f2(), "needs Odin III")
class ExtractTest(unittest.TestCase):
    def test_comparator_f2(self) -> None:
        design, _ = open_front("f2", [micro("bm_DL_4_bit_comparator")], None, f2_arch(), None)
        design.run_script("lower; abc --lut 6")
        nl = extract_netlist(design, "bm_DL_4_bit_comparator")
        outs = [pb.name for pb in nl.port_bits if pb.direction == "out"]
        ins = [pb.name for pb in nl.port_bits if pb.direction == "in"]
        self.assertEqual(outs, ["AeqB", "AgtB", "AltB"])
        self.assertEqual(ins, [f"{x}[{i}]" for x in "AB" for i in range(4)])
        kinds = sorted(c.kind for c in nl.cells)
        self.assertEqual(kinds, ["const", "lut", "lut", "lut", "lut", "lut"])
        self.assertTrue(all(pb.spans for pb in nl.port_bits))
        self.assertIn("AeqB[0]", {n for net in nl.nets.values() for n in net.names})
        for c in nl.cells:
            for p in (*c.inputs, *c.outputs):
                self.assertTrue(all(n in nl.nets for n in p.nets if n))

    def test_black_box_is_unsupported(self) -> None:
        design, _ = open_front("f2", [DATA / "blackbox.v"], None, f2_arch(), None)
        design.run_script("lower; abc --lut 6")
        with self.assertRaisesRegex(Unsupported, "bb"):
            extract_netlist(design, "blackbox")


if __name__ == "__main__":
    unittest.main()
