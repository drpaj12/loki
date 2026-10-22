"""Loki's BLIF writer against Odin III's own write_blif (plan Task 4 step 6, spec 6.2)."""

import tempfile
import unittest
from pathlib import Path

from loki.blifout import LUT_ROW_ORDER, identity_naming, write_blif
from loki.equiv import check_equiv
from loki.extract import extract_netlist
from loki.odin import open_front
from tests.helpers import can_run_flow, micro, odin3_root, vtr_arch

NAMES = ("bm_DL_4_bit_comparator", "bm_DL_four_bit_adder_continuous_assign", "bm_DL_74381_ALU")


@unittest.skipUnless(can_run_flow() and odin3_root() is not None, "needs Odin III and VTR")
class BlifVsOdinTest(unittest.TestCase):
    def test_lut_order_matches_write_blif(self) -> None:
        root = odin3_root()
        assert root is not None
        self.assertEqual(LUT_ROW_ORDER, "string_msb_first")
        for name in NAMES:
            with self.subTest(name), tempfile.TemporaryDirectory() as tmp:
                design, _ = open_front("f2", [micro(name)], None, vtr_arch(), None)
                design.run_script("lower; abc --lut 6")
                nl = extract_netlist(design, name)
                ours = write_blif(nl, identity_naming(nl))
                path = Path(tmp) / "odin.blif"
                design.run_script(f'write_blif --vtr "{path}"')
                res = check_equiv(path.read_text(encoding="utf-8"), ours, root, False)
                self.assertEqual(res.status, "equivalent", res.detail)


if __name__ == "__main__":
    unittest.main()
