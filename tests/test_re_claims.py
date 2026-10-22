import unittest

from loki.re.claims import CONE_TEMPLATES, DONT_CARE, REFS, Claim, template_args


class ClaimsTest(unittest.TestCase):
    def test_refs_add_sub_compare(self) -> None:
        p = {"A_WIDTH": 4, "B_WIDTH": 4, "Y_WIDTH": 4}
        self.assertEqual(REFS["add"](p, {"A": 9, "B": 9}), {"Y": 2})
        self.assertEqual(REFS["sub"](p, {"A": 3, "B": 5}), {"Y": 14})
        self.assertEqual(REFS["add_cin"](p, {"A": 7, "B": 8, "CI": 1}), {"Y": 0})
        self.assertEqual(REFS["add"]({"Y_WIDTH": 5}, {"A": 9, "B": 9}), {"Y": 18})
        for op, a, b, want in (("eq", 3, 3, 1), ("ne", 3, 3, 0), ("lt", 2, 3, 1),
                               ("le", 3, 3, 1), ("gt", 2, 3, 0), ("ge", 2, 3, 0)):
            self.assertEqual(REFS[op]({}, {"A": a, "B": b}), {"Y": want}, op)
        self.assertEqual(REFS["eq_const"]({"C": 5}, {"A": 5}), {"Y": 1})
        self.assertEqual(REFS["ne_const"]({"C": 5}, {"A": 5}), {"Y": 0})
        self.assertEqual(REFS["mux2"]({}, {"A": 1, "B": 2, "S": 1}), {"Y": 2})
        self.assertEqual(REFS["mux2"]({}, {"A": 1, "B": 2, "S": 0}), {"Y": 1})

    def test_ref_counter_modulo(self) -> None:
        p: dict[str, int | str] = {"width": 4, "dir": "up", "modulus": 10, "rst_value": 0}
        self.assertEqual(REFS["counter"](p, {"Q": 9}), {"D": 0})
        self.assertEqual(REFS["counter"](p, {"Q": 3}), {"D": 4})
        self.assertEqual(REFS["counter"](p, {"Q": 3, "EN": 0}), {"D": 3})
        self.assertEqual(REFS["counter"](p, {"Q": 3, "RST": 1, "EN": 0}), {"D": 0})
        down: dict[str, int | str] = {**p, "dir": "down"}
        self.assertEqual(REFS["counter"](down, {"Q": 0}), {"D": 9})
        wrap: dict[str, int | str] = {**p, "modulus": 0}
        self.assertEqual(REFS["counter"](wrap, {"Q": 15}), {"D": 0})

    def test_ref_shift_lfsr(self) -> None:
        shl: dict[str, int | str] = {"width": 4, "dir": "l"}
        self.assertEqual(REFS["shift"](shl, {"Q": 0b1001, "X": 1}), {"D": 0b0011})
        shr: dict[str, int | str] = {"width": 4, "dir": "r"}
        self.assertEqual(REFS["shift"](shr, {"Q": 0b1001, "X": 1}), {"D": 0b1100})
        self.assertEqual(REFS["lfsr"]({"width": 4, "taps": 0b1001}, {"Q": 0b1001}),
                         {"D": 0b0010})

    def test_ref_muxn_dont_care(self) -> None:
        p = {"N": 3, "S_WIDTH": 2}
        self.assertEqual(REFS["muxn"](p, {"D": 0b101, "S": 2}), {"Y": 1})
        self.assertEqual(REFS["muxn"](p, {"D": 0b101, "S": 1}), {"Y": 0})
        self.assertFalse(DONT_CARE["muxn"](p, {"D": 0, "S": 2}))
        self.assertTrue(DONT_CARE["muxn"](p, {"D": 0, "S": 3}))

    def test_template_args_sorted(self) -> None:
        claim = Claim("add", (("Y_WIDTH", 3), ("A_WIDTH", 2), ("B_WIDTH", 2)),
                      (("A", (1, 2)), ("B", (3, 4))), (("Y", (5, 6, 7)),))
        self.assertEqual(template_args(claim),
                         "-cell $add -param A_WIDTH=2 -param B_WIDTH=2 -param Y_WIDTH=3")
        self.assertEqual(claim.param("A_WIDTH"), 2)
        with self.assertRaises(KeyError):
            claim.param("nope")
        self.assertEqual(CONE_TEMPLATES["counter_en"], "$add")
        self.assertEqual(CONE_TEMPLATES["mux2"], "$mux")


if __name__ == "__main__":
    unittest.main()
