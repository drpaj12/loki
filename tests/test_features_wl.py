import re
import unittest

from loki.features.roles import classify_nets
from loki.features.wl import (
    WLConfig,
    classes,
    quotient,
    refine,
    stable_partition,
    start_label,
)
from tests.features_fixtures import (
    AND2,
    Builder,
    random_fg,
    reconvergent_pair_fg,
    relabelled,
    ripple_adder_fg,
    sync_fg,
    table_of,
)

HEX16 = re.compile(r"^[0-9a-f]{16}$")


def partition_sets(groups: dict[str, tuple[int, ...]]) -> set[frozenset[int]]:
    return {frozenset(g) for g in groups.values()}


class WLTest(unittest.TestCase):
    def test_config(self) -> None:
        self.assertEqual(WLConfig().name, "npn/both")
        self.assertEqual(WLConfig("table", "in").name, "table/in")
        with self.assertRaises(ValueError):
            WLConfig("x")
        with self.assertRaises(ValueError):
            WLConfig("npn", "sideways")

    def test_colours_are_sha_strings(self) -> None:
        fg = ripple_adder_fg(3)
        roles = classify_nets(fg)
        a = refine(fg, roles, WLConfig())
        b = refine(fg, roles, WLConfig())
        self.assertEqual(a, b)
        self.assertEqual(len(a.colours), 5)
        for r in a.colours:
            self.assertEqual(len(r), fg.n_nodes)
            self.assertTrue(all(HEX16.match(c) for c in r))

    def test_cross_graph_comparable(self) -> None:
        fg1 = ripple_adder_fg(4)
        fg2, new_of = relabelled(ripple_adder_fg(4, prefix="x_"), 9)
        self.assertNotEqual(fg1.node_ids, fg2.node_ids)
        for cfg in (WLConfig("npn", "both"), WLConfig("table", "in"), WLConfig("npn", "out")):
            r1 = refine(fg1, classify_nets(fg1), cfg)
            r2 = refine(fg2, classify_nets(fg2), cfg)
            for rnd in range(5):
                for v in range(fg1.n_nodes):
                    self.assertEqual(r1.colours[rnd][v], r2.colours[rnd][new_of[v]])

    def test_stable_round(self) -> None:
        b = Builder()
        prev = b.node("in", "pi")
        for i in range(6):
            prev = b.lut(f"l{i}", 0b01, [prev])
        b.edge(prev, b.node("out", "po"), "I")
        fg = b.build()
        roles = classify_nets(fg)
        res = refine(fg, roles, WLConfig("npn", "both", 8))
        self.assertIsNotNone(res.stable_round)
        assert res.stable_round is not None
        self.assertEqual(len(res.colours), 9)
        base = partition_sets(classes(res, res.stable_round))
        for r in range(res.stable_round, 9):
            self.assertEqual(partition_sets(classes(res, r)), base)
        self.assertEqual(refine(fg, roles, WLConfig("npn", "both", 1)).stable_round, None)

    def test_directions_differ(self) -> None:
        b = Builder()
        a, c = b.node("a", "pi"), b.node("b", "pi")
        g1 = b.lut("g1", AND2, [a, c])
        g2 = b.lut("g2", AND2, [a, c])
        h = b.lut("h", 0b01, [g2])
        b.edge(g1, b.node("p1", "po"), "I")
        b.edge(h, b.node("p2", "po"), "I")
        fg = b.build()
        roles = classify_nets(fg)
        cin = refine(fg, roles, WLConfig("table", "in", 3))
        cboth = refine(fg, roles, WLConfig("table", "both", 3))
        for r in range(4):
            self.assertEqual(cin.colours[r][g1], cin.colours[r][g2])
        self.assertEqual(cboth.colours[0][g1], cboth.colours[0][g2])
        for r in range(1, 4):
            self.assertNotEqual(cboth.colours[r][g1], cboth.colours[r][g2])

    def test_npn_variant_ignores_pin_order(self) -> None:
        b = Builder()
        x, y = b.node("x", "pi"), b.node("y", "pi")
        g1 = b.lut("g1", table_of(2, lambda v: v[0] & (1 - v[1])), [x, y])
        g2 = b.lut("g2", table_of(2, lambda v: (1 - v[0]) & v[1]), [x, y])
        fg = b.build()
        roles = classify_nets(fg)
        npn = refine(fg, roles, WLConfig("npn", "in", 2))
        tab = refine(fg, roles, WLConfig("table", "in", 2))
        self.assertEqual(npn.colours[0][g1], npn.colours[0][g2])
        self.assertEqual(npn.colours[2][g1], npn.colours[2][g2])
        self.assertNotEqual(tab.colours[0][g1], tab.colours[0][g2])
        self.assertNotEqual(tab.colours[2][g1], tab.colours[2][g2])

    def test_role_edges_removed(self) -> None:
        cfg = WLConfig("npn", "both")
        fg1 = sync_fg(20, reset=True)
        fg2 = sync_fg(20, reset=True, rst_from_lut=True)
        roles1, roles2 = classify_nets(fg1), classify_nets(fg2)
        self.assertEqual(roles2.classified["reset"], 1)
        r1, r2 = refine(fg1, roles1, cfg), refine(fg2, roles2, cfg)
        for node in ("ff0", "dl0", "d0"):
            for rnd in range(5):
                self.assertEqual(r1.colours[rnd][fg1.node_ids.index(node)],
                                 r2.colours[rnd][fg2.node_ids.index(node)])
        rst_colours = (r1.colours[0][fg1.node_ids.index("rst")],
                       r2.colours[0][fg2.node_ids.index("rst")])
        self.assertNotEqual(*rst_colours)
        ff = fg1.node_ids.index("ff0")
        self.assertIn("rst=1", start_label(fg1, roles1, ff, cfg))
        plain = sync_fg(20)
        self.assertIn("rst=0", start_label(plain, classify_nets(plain), ff, cfg))
        rp = refine(plain, classify_nets(plain), cfg)
        self.assertNotEqual(r1.colours[0][ff], rp.colours[0][ff])

    def test_const_inputs_in_start_label(self) -> None:
        b = Builder()
        one = b.node("one", "const", 0, 1)
        zero = b.node("zero", "const", 0, 0)
        a = b.node("a", "pi")
        g1 = b.lut("g1", AND2, [a, one])
        g2 = b.lut("g2", AND2, [a, zero])
        fg = b.build()
        roles = classify_nets(fg)
        self.assertEqual(roles.nodes[g1].const_inputs, 1)
        t = WLConfig("table", "in")
        self.assertIn("I1=1", start_label(fg, roles, g1, t))
        self.assertIn("I1=0", start_label(fg, roles, g2, t))
        self.assertIn("c=1", start_label(fg, roles, g1, WLConfig("npn", "in")))

    def test_reconvergence_same_colour(self) -> None:
        fg = reconvergent_pair_fg()
        roles = classify_nets(fg)
        res = refine(fg, roles, WLConfig("table", "in", 6))
        g1, g2 = fg.node_ids.index("g1"), fg.node_ids.index("g2")
        for r in range(7):
            self.assertEqual(res.colours[r][g1], res.colours[r][g2])

    def test_stable_partition_equals_refine(self) -> None:
        for seed in range(50):
            n = 5 + (seed * 7) % 36
            fg = random_fg(n, seed)
            roles = classify_nets(fg)
            for start in ("table", "npn"):
                for direction in ("in", "out", "both"):
                    cfg = WLConfig(start, direction, n + 2)
                    res = refine(fg, roles, cfg)
                    want = partition_sets(classes(res, n + 2))
                    part = stable_partition(fg, roles, cfg)
                    got: dict[int, set[int]] = {}
                    for v, c in enumerate(part.class_of):
                        got.setdefault(c, set()).add(v)
                    self.assertEqual({frozenset(s) for s in got.values()}, want,
                                     f"seed {seed} {cfg.name}")
                    self.assertEqual(part.n_classes, len(got))

    def test_stable_partition_regular_graphs(self) -> None:
        b = Builder()
        ring = [b.node(f"r{i}", "lut", 1, 0b01) for i in range(8)]
        for i, v in enumerate(ring):
            b.edge(ring[i - 1], v, "I0")
        graphs = [b.build(), ripple_adder_fg(5), sync_fg(30, reset=True, clocks=2)]
        for fg in graphs:
            roles = classify_nets(fg)
            for direction in ("in", "out", "both"):
                cfg = WLConfig("npn", direction, fg.n_nodes + 2)
                want = partition_sets(classes(refine(fg, roles, cfg), fg.n_nodes + 2))
                part = stable_partition(fg, roles, cfg)
                got: dict[int, set[int]] = {}
                for v, c in enumerate(part.class_of):
                    got.setdefault(c, set()).add(v)
                self.assertEqual({frozenset(x) for x in got.values()}, want)
        ring_fg = graphs[0]
        ring_part = stable_partition(ring_fg, classify_nets(ring_fg), WLConfig())
        self.assertEqual(ring_part.n_classes, 1)

    def test_partition_numbering(self) -> None:
        fg = ripple_adder_fg(3)
        part = stable_partition(fg, classify_nets(fg), WLConfig())
        seen: list[int] = []
        for c in part.class_of:
            if c not in seen:
                seen.append(c)
        self.assertEqual(seen, list(range(part.n_classes)))

    def test_quotient_equitable(self) -> None:
        for seed in range(20):
            fg = random_fg(5 + seed, seed)
            roles = classify_nets(fg)
            for direction in ("in", "both"):
                cfg = WLConfig("npn", direction)
                part = stable_partition(fg, roles, cfg)
                q = quotient(fg, roles, part, cfg)
                self.assertEqual(sum(q.size), fg.n_nodes)
                self.assertEqual(len(q.label), part.n_classes)
                want: dict[tuple[int, int, str], int] = {(c, d, lab): k for c, d, lab, k in q.edges}
                ins = fg.adjacency()[0]
                for v in range(fg.n_nodes):
                    got: dict[tuple[int, int, str], int] = {}
                    for e in ins[v]:
                        if roles.edge_class[e] != "signal":
                            continue
                        lab = "I" if fg.kind[v] in ("lut", "gate") else fg.pin[e]
                        key = (part.class_of[fg.src[e]], part.class_of[v], lab)
                        got[key] = got.get(key, 0) + 1
                    mine = {k: n for k, n in want.items() if k[1] == part.class_of[v]}
                    self.assertEqual(got, mine)
        with self.assertRaises(ValueError):
            quotient(fg, roles, part, WLConfig("npn", "out"))


if __name__ == "__main__":
    unittest.main()
