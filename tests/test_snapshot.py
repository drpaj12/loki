import unittest

from loki.odin import open_front
from loki.snapshot import take_snapshot
from tests.helpers import DATA, can_run_f2, f2_arch, micro


@unittest.skipUnless(can_run_f2(), "needs Odin III")
class SnapshotTest(unittest.TestCase):
    def test_comparator_words(self) -> None:
        d, inst = open_front("f2", [micro("bm_DL_4_bit_comparator")], None, f2_arch(), None)
        snap = take_snapshot(d, inst)
        self.assertEqual(sorted(w.type for w in snap.words), ["$eq", "$gt", "$lt"])
        lines = {w.type: w.spans[0].line for w in snap.words}
        self.assertEqual(lines, {"$eq": 12, "$gt": 17, "$lt": 22})
        self.assertEqual(snap.top, "bm_DL_4_bit_comparator")
        eq = next(w for w in snap.words if w.type == "$eq")
        self.assertEqual([p.name for p in eq.inputs], ["A", "B"])
        self.assertEqual([p.width for p in eq.inputs], [4, 4])
        self.assertEqual(eq.outputs[0].name, "Y")
        self.assertTrue(all(eq.outputs[0].nets))

    def test_ctrl_ports_types(self) -> None:
        d, inst = open_front("f2", [DATA / "ctrl_ports.v"], None, f2_arch(), None)
        snap = take_snapshot(d, inst)
        types = {w.type for w in snap.words}
        self.assertTrue({"$mux", "$dffe", "$adff", "$sdff"} <= types)

    def test_instances(self) -> None:
        _, inst = open_front("f2", [DATA / "two_inst.v"], None, f2_arch(), None)
        self.assertEqual(sorted(i.name for i in inst), ["u1", "u2"])
        self.assertEqual({(i.module, i.parent_module) for i in inst}, {("sub", "two_inst")})


if __name__ == "__main__":
    unittest.main()
