import re
import unittest

from loki.anon import build_key, number
from loki.blifout import anon_naming, deanonymise, identity_naming, write_blif
from loki.model import FinalCell, Net, Netlist, Port, PortBit
from tests.helpers import and_netlist, lut_cell


def cell(cid: int, kind: str, typ: str, ins: list[Port], outs: list[Port]) -> FinalCell:
    return FinalCell(cid, kind, typ, "", {}, (), tuple(ins), tuple(outs))


def netlist(cells: list[FinalCell], nets: int, pbs: list[PortBit]) -> Netlist:
    return Netlist("t", {i: Net(i, ()) for i in range(1, nets + 1)}, tuple(cells), tuple(pbs))


def parse(blif: str) -> list[tuple[str, tuple[str, ...], str]]:
    """Structure of a BLIF: (gate, input signals, output signal), internal nets renamed."""
    seen: dict[str, str] = {}
    ports: set[str] = set()
    lines = blif.splitlines()
    for ln in lines:
        if ln.startswith((".inputs", ".outputs")):
            ports.update(ln.split()[1:])

    def nm(s: str) -> str:
        if s in ports:
            return s
        return seen.setdefault(s, f"#{len(seen)}")

    out: list[tuple[str, tuple[str, ...], str]] = []
    rows: list[str] = []
    for ln in lines:
        tok = ln.split()
        if not tok or tok[0] in (".model", ".inputs", ".outputs", ".end", ".cname"):
            continue
        if tok[0] in (".names", ".latch"):
            args = [nm(t) for t in tok[1:]]
            out.append((tok[0], tuple(args[:-1]), args[-1]))
            rows = []
        else:
            rows.append(ln)
    return sorted(out)


class BlifTest(unittest.TestCase):
    def test_blif_lut_cover(self) -> None:
        nl = and_netlist()
        text = write_blif(nl, anon_naming(number(nl), nl))
        self.assertIn(".names n0 n1 n2\n11 1\n.cname n3\n", text)
        self.assertIn(".inputs n0 n1\n.outputs n2\n", text)

    def test_blif_const_and_latch(self) -> None:
        one = cell(20, "const", "$_CONST1_", [], [Port("Y", 1, (1,))])
        zero = cell(21, "const", "$_CONST0_", [], [Port("Y", 1, (2,))])
        pos = cell(22, "ff", "$_DFF_P_", [Port("C", 1, (3,)), Port("D", 1, (1,))],
                   [Port("Q", 1, (4,))])
        neg = cell(23, "ff", "$_DFF_N_", [Port("C", 1, (3,)), Port("D", 1, (2,))],
                   [Port("Q", 1, (5,))])
        nl = netlist([one, zero, pos, neg], 5, [PortBit("c", "in", 3), PortBit("q", "out", 4)])
        text = write_blif(nl, identity_naming(nl))
        self.assertIn(".names w1\n1\n.names w2\n", text)
        self.assertNotIn(".cname", text)
        self.assertIn(".latch w1 q re c 3\n", text)
        self.assertIn(".latch w2 w5 fe c 3\n", text)

    def test_hard_subckt(self) -> None:
        add = cell(30, "hard", "adder", [Port("a", 2, (1, 2)), Port("b", 2, (3, 0))],
                   [Port("cout", 1, (4,))])
        nl = netlist([add], 4, [PortBit("x", "in", 1)])
        text = write_blif(nl, identity_naming(nl))
        self.assertIn(".subckt adder a[0]=x a[1]=w2 b[0]=w3 cout=w4\n", text)
        anon = write_blif(nl, anon_naming(number(nl), nl))
        self.assertIn(".subckt adder a[0]=n0 a[1]=n1 b[0]=n2 cout=n3\n.cname n4\n", anon)
        model = ".model adder\n.inputs a[0] a[1] b[0] b[1]\n.outputs cout\n.blackbox\n.end"
        self.assertIn(model, anon)

    def test_output_aliases_buffered(self) -> None:
        nl = Netlist(
            "t", {1: Net(1, ()), 2: Net(2, ())}, (lut_cell(10, [1], 2, "01"),),
            (PortBit("I", "in", 1), PortBit("PI_OUT", "out", 1),
             PortBit("O1", "out", 2), PortBit("O2", "out", 2)),
        )
        text = write_blif(nl, identity_naming(nl))
        self.assertIn(".outputs PI_OUT O1 O2\n", text)
        self.assertIn(".names I PI_OUT\n1 1\n", text)
        self.assertIn(".names O1 O2\n1 1\n", text)
        self.assertEqual(text.count(".names O1 O2"), 1)
        anon = write_blif(nl, anon_naming(number(nl), nl))
        m = re.search(r"\.outputs (.*)", anon)
        self.assertIsNotNone(m)
        self.assertEqual(len(set((m.group(1) if m else "").split())), 3)

    def test_no_original_names_in_anon_blif(self) -> None:
        nl = and_netlist()
        text = write_blif(nl, anon_naming(number(nl), nl))
        self.assertNotIn("A[0]", text)
        self.assertNotIn(" X", text)
        for tok in re.findall(r"\S+", text):
            self.assertTrue(tok.startswith(".") or re.fullmatch(r"n\d+|[01]+|top", tok), tok)

    def test_deanonymise_roundtrip(self) -> None:
        nl = Netlist(
            "t", {i: Net(i, ()) for i in (1, 2, 3, 4)},
            (lut_cell(10, [1, 2], 3, "0110"), lut_cell(11, [3, 1], 4, "1000")),
            (PortBit("A[0]", "in", 1), PortBit("A[1]", "in", 2), PortBit("X", "out", 4),
             PortBit("Y", "out", 4), PortBit("Z", "out", 1)),
        )
        num = number(nl)
        key = build_key(nl, num, "d", "f2", {})
        back = deanonymise(write_blif(nl, anon_naming(num, nl)), key)
        self.assertEqual(parse(back), parse(write_blif(nl, identity_naming(nl))))
        self.assertIn(".inputs A[0] A[1]", back)
        self.assertIn(".outputs X Y Z", back)


if __name__ == "__main__":
    unittest.main()
