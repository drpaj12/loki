import dataclasses
import json
import re
import tempfile
import unittest
from pathlib import Path

from loki.build import build_floor
from loki.features.graph import from_graph_json, validate_feature_graph
from loki.features.npn import NAMED, class_name
from loki.re.claims import Claim
from loki.re.detectors import Candidate
from loki.re.fngraph import Cell, FnGraph, from_design
from loki.re.normalise import load_level0
from loki.re.overlay import Overlay
from loki.re.structural import (
    build_features,
    cone_match,
    feature_graph,
    transfer_key,
)
from tests.helpers import can_run_f2, f2_arch, micro, odin3_root, odin_available
from tests.test_re_sim import AND2, XOR2, XOR3, add2, graph_of, lut

MAJ3 = 0b11101000


def adder(bits: int, cid0: int, net0: int, table: int = XOR3) -> tuple[list[Cell], Claim]:
    """A ripple adder: inputs a (net0..), b, outputs y, carries c (each ``bits`` apart)."""
    a = [net0 + i for i in range(bits)]
    b = [net0 + bits + i for i in range(bits)]
    y = [net0 + 2 * bits + i for i in range(bits)]
    c = [net0 + 3 * bits + i for i in range(bits)]
    cells = [lut(cid0, (a[0], b[0]), y[0], XOR2), lut(cid0 + 1, (a[0], b[0]), c[0], AND2)]
    for i in range(1, bits):
        cells.append(lut(cid0 + 2 * i, (a[i], b[i], c[i - 1]), y[i],
                         table if i == bits - 1 else XOR3))
        if i < bits - 1:
            cells.append(lut(cid0 + 2 * i + 1, (a[i], b[i], c[i - 1]), c[i], MAJ3))
    params = (("A_WIDTH", bits), ("B_WIDTH", bits), ("Y_WIDTH", bits))
    claim = Claim("add", params, (("A", tuple(a)), ("B", tuple(b))), (("Y", tuple(y)),))
    return cells, claim


def two_adders() -> tuple[FnGraph, Claim, Claim]:
    c1, k1 = adder(2, 100, 1000)
    c2, k2 = adder(2, 200, 2000)
    pis = tuple(n for k in (k1, k2) for _, ns in k.inputs for n in ns)
    pos = tuple(n for k in (k1, k2) for _, ns in k.outputs for n in ns)
    return graph_of(c1 + c2, pis, pos), k1, k2


def hyp(ov: Overlay, graph: FnGraph, claim: Claim, cells: set[int]) -> str:
    nets = {p: ns for p, ns in claim.outputs}
    cand = Candidate("adder", frozenset(cells), nets, {}, {}, claim)
    return ov.add(cand, "arith", 1).id


class FeatureGraphTest(unittest.TestCase):
    def test_feature_graph_from_fngraph(self) -> None:
        g = add2()
        ff = Cell(12, "", "ff", "$_DFF_P_", (5,), (8,), 0, 0, 9, 12, {})
        cells = {**g.cells, 12: ff}
        driver = {**g.driver, 8: 12}
        names = {1: "a0", 2: "a1", 3: "b0", 4: "b1", 5: "y0", 7: "y1", 8: "q", 9: "clk"}
        g = dataclasses.replace(g, cells=cells, driver=driver, names=names,
                                pis=(1, 2, 3, 4, 9), pos=(5, 7, 8))
        fg = feature_graph(g)
        self.assertEqual(validate_feature_graph(fg), [])
        self.assertEqual(fg.node_ids[:4], ("c9", "c10", "c11", "c12"))
        self.assertEqual(fg.kind[:4], ("lut", "lut", "lut", "ff"))
        self.assertEqual(fg.node_ids[4:], ("pi:a0", "pi:a1", "pi:b0", "pi:b1", "pi:clk",
                                           "po:y0", "po:y1", "po:q"))
        self.assertEqual(fg.table[:4], (XOR2, AND2, XOR3, -1))
        self.assertEqual(fg.width[:4], (2, 2, 3, 0))
        edges = {(fg.node_ids[fg.src[e]], fg.node_ids[fg.dst[e]], fg.pin[e], fg.net[e])
                 for e in range(fg.n_edges)}
        self.assertIn(("pi:a0", "c9", "I0", 1), edges)
        self.assertIn(("pi:b1", "c11", "I1", 4), edges)
        self.assertIn(("c10", "c11", "I2", 6), edges)
        self.assertIn(("c9", "c12", "D", 5), edges)
        self.assertIn(("pi:clk", "c12", "CLK", 9), edges)
        self.assertIn(("c12", "po:q", "I", 8), edges)
        self.assertIn(("c11", "po:y1", "I", 7), edges)
        self.assertEqual(len(edges), 12)

    def test_feature_graph_hard_pins_and_latch(self) -> None:
        named = Cell(7, "", "hard", "adder", (1, 2, 0), (3,), 0, 0, 0, 7, {},
                     ("a[0]", "b[0]", "cin"))
        bare = Cell(8, "", "hard", "mult", (1, 2), (4,), 0, 0, 0, 8, {})
        latch = Cell(9, "", "latch", "$_DLATCH_P_", (3,), (5,), 0, 0, 6, 9, {})
        cells = {c.id: c for c in (named, bare, latch)}
        g = FnGraph(cells, {3: 7, 4: 8, 5: 9}, {}, {}, (1, 2, 6), (5,), {}, "")
        fg = feature_graph(g)
        pins = {(fg.node_ids[fg.dst[e]], fg.pin[e]) for e in range(fg.n_edges)}
        self.assertEqual(pins, {("c7", "a[0]"), ("c7", "b[0]"), ("c8", "I0"), ("c8", "I1"),
                                ("c9", "D"), ("c9", "EN"), ("po:n5", "I")})
        self.assertEqual(fg.type[:3], ("adder", "mult", "latch"))
        self.assertEqual(fg.kind[2], "latch")

    @unittest.skipUnless(odin_available() and can_run_f2(), "needs Odin III and ABC")
    def test_feature_graph_matches_graph_json(self) -> None:
        root = odin3_root()
        assert root is not None
        name = "bm_DL_four_bit_adder_continuous_assign"
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            res = build_floor("d", [micro(name)], None, "f2", f2_arch(), out, root)
            self.assertEqual(res.status, "ok")
            fdir = out / "d" / "f2"
            jg = from_graph_json(json.loads((fdir / "graph.json").read_text(encoding="utf-8")))
            design = load_level0(fdir / "netlist.blif", "f2", None, None)
            self.addCleanup(design.close)
            fg = feature_graph(from_design(design))
        self.assertEqual((fg.n_nodes, fg.n_edges), (jg.n_nodes, jg.n_edges))
        # graph.json names PI/PO nodes by their own ids: map pi:<net>/po:<net> through the nets
        by_net_pi: dict[str, str] = {}
        by_net_po: dict[str, str] = {}
        for e in range(jg.n_edges):
            net = f"n{jg.net[e]}"
            if jg.kind[jg.src[e]] == "pi":
                by_net_pi[net] = jg.node_ids[jg.src[e]]
            if jg.kind[jg.dst[e]] == "po":
                by_net_po[net] = jg.node_ids[jg.dst[e]]

        def jid(nid: str) -> str:
            if nid.startswith("pi:"):
                return by_net_pi[nid[3:]]
            if nid.startswith("po:"):
                return by_net_po[nid[3:]]
            return nid

        jnodes = {jg.node_ids[i]: (jg.kind[i], jg.type[i], jg.width[i], jg.table[i])
                  for i in range(jg.n_nodes)}
        fnodes = {jid(fg.node_ids[i]): (fg.kind[i], fg.type[i], fg.width[i], fg.table[i])
                  for i in range(fg.n_nodes)}
        self.assertEqual(fnodes, jnodes)
        fedges = sorted((jid(fg.node_ids[fg.src[e]]), jid(fg.node_ids[fg.dst[e]]), fg.pin[e])
                        for e in range(fg.n_edges))
        jedges = sorted((jg.node_ids[jg.src[e]], jg.node_ids[jg.dst[e]], jg.pin[e])
                        for e in range(jg.n_edges))
        self.assertEqual(fedges, jedges)


class FeaturesTest(unittest.TestCase):
    def test_build_features_variants(self) -> None:
        g = add2()
        sf = build_features(g)
        self.assertEqual(sorted(sf.wl), ["npn/both", "npn/in", "table/in"])
        for cid in (9, 10, 11):
            self.assertIsNotNone(sf.npn_of(cid))
        self.assertEqual(class_name(sf.npn_of(9) or NAMED["const"]), "xor2")
        self.assertEqual(class_name(sf.npn_of(10) or NAMED["const"]), "and2")
        self.assertEqual(class_name(sf.npn_of(11) or NAMED["const"]), "xor3")
        self.assertIsNone(sf.npn_of(999))
        for variant in sf.wl:
            self.assertEqual(len(sf.wl[variant].colours), 5)
            self.assertRegex(sf.colour(9, variant, 4), re.compile(r"^[0-9a-f]{16}$"))
        self.assertGreaterEqual(sf.seconds, 0.0)
        rep = sf.report()
        self.assertEqual(rep["enabled"], True)
        npn = rep["npn"]
        assert isinstance(npn, dict)
        self.assertEqual((npn["distinct_tables"], npn["classes"], npn["exact"]), (3, 3, True))
        wl = rep["wl"]
        assert isinstance(wl, dict)
        self.assertEqual(sorted(wl), ["npn/both", "npn/in", "table/in"])
        self.assertEqual(json.loads(json.dumps(rep)), rep)

    def test_wide_lut_has_no_class(self) -> None:
        wide = lut(5, tuple(range(1, 8)), 20, sum(((bin(x).count("1") & 1) << x)
                                                  for x in range(128)))
        sf = build_features(graph_of([wide], tuple(range(1, 8)), (20,)))
        self.assertIsNone(sf.npn_of(5))

    def test_cell_keys_backoff_order(self) -> None:
        sf = build_features(add2())
        keys = sf.cell_keys(11)
        self.assertEqual(keys, tuple(f"{d}:{sf.colour(11, 'npn/both', d)}" for d in (2, 1, 0)))
        self.assertEqual([k.split(":")[0] for k in keys], ["2", "1", "0"])
        self.assertEqual(sf.cell_keys(999), ())

    def test_class_depth(self) -> None:
        g, _, _ = two_adders()
        sf = build_features(g)
        # the sum bit-0 cells of two adders on disjoint inputs stay in one class to the end
        self.assertEqual(sf.class_depth([100, 200], "table/in"), 4)
        self.assertEqual(sf.class_depth([100, 101], "table/in"), -1)
        chain = graph_of([lut(1, (10, 11), 12, XOR2), lut(2, (12, 13), 14, XOR2)],
                         (10, 11, 13), (14,))
        self.assertEqual(build_features(chain).class_depth([1, 2], "table/in"), 0)
        self.assertEqual(sf.class_depth([], "table/in"), -1)


class ConeMatchTest(unittest.TestCase):
    def test_cone_match_isomorphic(self) -> None:
        g, k1, k2 = two_adders()
        self.assertTrue(cone_match(g, k1, k2))
        self.assertTrue(cone_match(g, k1, k1))

    def test_cone_match_rejects_reconvergence(self) -> None:
        x, y, z = 1, 2, 3
        g = graph_of([lut(10, (x, x), 11, XOR2), lut(20, (y, z), 21, XOR2)],
                     (x, y, z), (11, 21))
        c0 = Claim("t", (), (("A", (x,)), ("B", (x,))), (("Y", (11,)),))
        c1 = Claim("t", (), (("A", (y,)), ("B", (z,))), (("Y", (21,)),))
        sf = build_features(g)
        self.assertEqual(sf.colour(10, "table/in", 4), sf.colour(20, "table/in", 4))
        self.assertFalse(cone_match(g, c0, c1))
        self.assertFalse(cone_match(g, c1, c0))

    def test_cone_match_rejects_different_table(self) -> None:
        c1, k1 = adder(2, 100, 1000)
        c2, k2 = adder(2, 200, 2000, table=0b01101001)
        pis = tuple(n for k in (k1, k2) for _, ns in k.inputs for n in ns)
        g = graph_of(c1 + c2, pis, ())
        self.assertFalse(cone_match(g, k1, k2))

    def test_cone_match_rejects_side_input(self) -> None:
        c1, k1 = adder(2, 100, 1000)
        c2, k2 = adder(2, 200, 2000)
        side = 5000
        patched = [lut(c.id, (*c.ins, side), c.outs[0], c.table) if c.id == 202 else c
                   for c in c2]
        pis = tuple(n for k in (k1, k2) for _, ns in k.inputs for n in ns) + (side,)
        g = graph_of(c1 + patched, pis, ())
        self.assertFalse(cone_match(g, k1, k2))

    def test_cone_match_rejects_claim_shape(self) -> None:
        g, k1, k2 = two_adders()
        other = Claim("sub", k2.params, k2.inputs, k2.outputs)
        self.assertFalse(cone_match(g, k1, other))
        swapped = Claim("add", k2.params, (k2.inputs[1], k2.inputs[0]), k2.outputs)
        self.assertFalse(cone_match(g, k1, swapped))
        narrow = Claim("add", k2.params, (("A", k2.inputs[0][1][:1]), k2.inputs[1]), k2.outputs)
        self.assertFalse(cone_match(g, k1, narrow))

    def test_cone_match_rejects_permuted_pins(self) -> None:
        # the same cones with the two operands exchanged on one side: the table pairs differ
        g, k1, k2 = two_adders()
        a, b = k2.inputs[0][1], k2.inputs[1][1]
        crossed = Claim("add", k2.params, (("A", (a[0], b[1])), ("B", (b[0], a[1]))), k2.outputs)
        self.assertFalse(cone_match(g, k1, crossed))


class TransferKeyTest(unittest.TestCase):
    def test_transfer_key_groups(self) -> None:
        c1, k1 = adder(2, 100, 1000)
        c2, k2 = adder(2, 200, 2000)
        c3, k3 = adder(3, 300, 3000)
        pis = tuple(n for k in (k1, k2, k3) for _, ns in k.inputs for n in ns)
        g = graph_of(c1 + c2 + c3, pis, ())
        sf = build_features(g)
        ov = Overlay()
        h1 = ov.get(hyp(ov, g, k1, {c.id for c in c1}))
        h2 = ov.get(hyp(ov, g, k2, {c.id for c in c2}))
        h3 = ov.get(hyp(ov, g, k3, {c.id for c in c3}))
        key1, key2, key3 = (transfer_key(h, sf, g) for h in (h1, h2, h3))
        self.assertIsNotNone(key1)
        self.assertEqual(key1, key2)
        self.assertNotEqual(key1, key3)
        assert key1 is not None
        self.assertEqual(key1[:2], ("adder", "add"))
        self.assertEqual(len(key1), 3 + 2)
        bare = ov.add(Candidate("adder", frozenset({1}), {}, {}, {}), "arith", 1)
        self.assertIsNone(transfer_key(bare, sf, g))

    def test_transfer_key_distinguishes_functions(self) -> None:
        c1, k1 = adder(2, 100, 1000)
        c2, k2 = adder(2, 200, 2000, table=0b01101001)
        pis = tuple(n for k in (k1, k2) for _, ns in k.inputs for n in ns)
        g = graph_of(c1 + c2, pis, ())
        sf = build_features(g)
        ov = Overlay()
        h1 = ov.get(hyp(ov, g, k1, {c.id for c in c1}))
        h2 = ov.get(hyp(ov, g, k2, {c.id for c in c2}))
        self.assertNotEqual(transfer_key(h1, sf, g), transfer_key(h2, sf, g))


if __name__ == "__main__":
    unittest.main()
