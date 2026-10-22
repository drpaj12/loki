import unittest

from loki.model import Port, WordCell
from loki.rules import UnlistedWordType, assign_roles, combine_roles


def word(
    wid: int,
    typ: str,
    ins: dict[str, int],
    outs: dict[str, int],
    fsm: bool = False,
) -> WordCell:
    return WordCell(
        id=wid, type=typ, name="", params={}, spans=(), fsm=fsm,
        inputs=tuple(Port(p, 1, (n,)) for p, n in ins.items()),
        outputs=tuple(Port(p, 1, (n,)) for p, n in outs.items()),
    )


class RolesTest(unittest.TestCase):
    def test_mux_select_is_control(self) -> None:
        words = [
            word(1, "$eq", {"A": 1, "B": 2}, {"Y": 10}),
            word(2, "$mux", {"A": 3, "B": 4, "S": 10}, {"Y": 11}),
            word(3, "$add", {"A": 11, "B": 5}, {"Y": 12}),
        ]
        r = assign_roles(words, frozenset({12}))
        self.assertEqual(r[1], "control")
        self.assertEqual(r[2], "datapath")

    def test_adder_input_is_datapath(self) -> None:
        words = [
            word(1, "$and", {"A": 1, "B": 2}, {"Y": 3}),
            word(2, "$add", {"A": 3, "B": 4}, {"Y": 5}),
        ]
        self.assertEqual(assign_roles(words, frozenset())[1], "datapath")

    def test_mixed(self) -> None:
        words = [
            word(1, "$eq", {"A": 1, "B": 2}, {"Y": 10}),
            word(2, "$mux", {"A": 3, "B": 4, "S": 10}, {"Y": 11}),
            word(3, "$add", {"A": 10, "B": 5}, {"Y": 12}),
        ]
        self.assertEqual(assign_roles(words, frozenset())[1], "mixed")

    def test_fsm_seed_and_next_state(self) -> None:
        words = [
            word(1, "$dff", {"D": 20, "CLK": 9}, {"Q": 21}, fsm=True),
            word(2, "$mux", {"A": 21, "B": 22, "S": 23}, {"Y": 20}),
        ]
        r = assign_roles(words, frozenset())
        self.assertEqual(r[1], "control")
        self.assertEqual(r[2], "control")

    def test_po_is_data(self) -> None:
        words = [word(1, "$and", {"A": 1, "B": 2}, {"Y": 3})]
        self.assertEqual(assign_roles(words, frozenset({3}))[1], "datapath")

    def test_loop_terminates(self) -> None:
        words = [
            word(1, "$dff", {"D": 2, "CLK": 9}, {"Q": 1}),
            word(2, "$not", {"A": 1}, {"Y": 2}),
        ]
        r = assign_roles(words, frozenset({1}))
        self.assertEqual(r, {1: "datapath", 2: "datapath"})

    def test_dead_logic_unknown(self) -> None:
        words = [word(1, "$and", {"A": 1, "B": 2}, {"Y": 3})]
        self.assertEqual(assign_roles(words, frozenset())[1], "unknown")

    def test_unlisted_type_raises(self) -> None:
        with self.assertRaisesRegex(UnlistedWordType, r"unlisted word type \$weird"):
            assign_roles([word(1, "$weird", {}, {})], frozenset())

    def test_combine_roles(self) -> None:
        self.assertEqual(combine_roles(["control", "control"]), "control")
        self.assertEqual(combine_roles(["control", "datapath"]), "mixed")
        self.assertEqual(combine_roles(["mixed", "datapath"]), "mixed")
        self.assertEqual(combine_roles(["unknown", "datapath"]), "datapath")
        self.assertEqual(combine_roles(["unknown", "unknown"]), "unknown")
        self.assertEqual(combine_roles([]), "unknown")


if __name__ == "__main__":
    unittest.main()
