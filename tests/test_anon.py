import unittest
from typing import Any

from loki.anon import build_key, number
from loki.model import FinalCell, Net, Netlist, PortBit
from loki.schemas import validate_key
from tests.helpers import and_netlist, lut_cell


class AnonTest(unittest.TestCase):
    def test_numbering_order_and_unique(self) -> None:
        nl = and_netlist()
        num = number(nl)
        self.assertEqual(num.net, {1: "n0", 2: "n1", 3: "n2"})
        self.assertEqual(num.cell, {10: "n3"})
        self.assertEqual((num.pi["A[0]"], num.pi["A[1]"], num.po["X"]), ("n4", "n5", "n6"))
        names = [*num.net.values(), *num.cell.values(), *num.pi.values(), *num.po.values()]
        self.assertEqual(len(names), len(set(names)))

    def test_ports_not_in_cell_numbering(self) -> None:
        nl = and_netlist()
        port = FinalCell(5, "pi", "$port_in", "", {}, (), (), ())
        nl2 = Netlist(nl.top, nl.nets, (port, *nl.cells), nl.port_bits)
        self.assertEqual(number(nl2).cell, {10: "n3"})

    def test_key_covers_everything(self) -> None:
        nl = Netlist(
            "t", {1: Net(1, ("A[0]",)), 2: Net(2, ()), 3: Net(3, ("X[0]", "y"))},
            (lut_cell(10, [1, 2], 3, "0001"),),
            (PortBit("A[0]", "in", 1), PortBit("A[1]", "in", 2), PortBit("X", "out", 3)),
        )
        num = number(nl)
        key: dict[str, Any] = build_key(nl, num, "d", "f2", {10: (6,)})
        self.assertEqual(validate_key(key), [])
        self.assertEqual(set(key["nets"]), set(num.net.values()))
        self.assertEqual(key["cells"]["n3"]["word_ids"], [6])
        self.assertEqual(len(key["ports"]), 3)
        self.assertEqual(key["nets"]["n2"]["names"], ["X[0]", "y"])


if __name__ == "__main__":
    unittest.main()
