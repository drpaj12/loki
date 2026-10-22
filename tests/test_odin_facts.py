"""Probes of the Odin III provenance facts the labels rest on (spec 5.1). A failing probe means
a fact in the spec changed: edit spec 5.1 with the observed fact before going on."""

import unittest
from pathlib import Path
from typing import Any

from loki import snapshot
from loki.labels import module_path
from loki.odin import floor_script, open_front
from loki.snapshot import take_snapshot
from tests.helpers import DATA, can_run_f2, can_run_flow, f2_arch, micro, vtr_arch

COMPARATOR = "bm_DL_4_bit_comparator"


def front(path: Path, floor: str = "f2", arch: str | None = None) -> tuple[Any, Any, Any]:
    arch_xml = vtr_arch(arch) if arch else f2_arch()
    design, instances = open_front(floor, [path], None, arch_xml, None)
    return design, instances, take_snapshot(design, instances)


def run(design: Any, script: str) -> None:
    design.run_script(script)


def cells(design: Any) -> list[Any]:
    return [n for n in design.top().nodes() if not str(n.type_name).startswith("$port_")]


def spans_of(node: Any) -> tuple[Any, ...]:
    return snapshot.node_spans(node)


@unittest.skipUnless(can_run_f2(), "needs Odin III")
class OdinFactsTest(unittest.TestCase):
    def test_sources_have_columns(self) -> None:
        _, _, snap = front(micro(COMPARATOR))
        eq = [w for w in snap.words if w.type == "$eq"]
        self.assertEqual(len(eq), 1)
        self.assertEqual(len(eq[0].spans), 1)
        s = eq[0].spans[0]
        self.assertEqual(s.line, 12)
        self.assertLess(s.col, s.end_col)

    def test_lower_keeps_spans(self) -> None:
        d, _, snap = front(micro(COMPARATOR))
        run(d, "lower")
        word_spans = {w.spans for w in snap.words}
        gates = [
            c for c in cells(d) if str(c.type_name).startswith("$_") and "CONST" not in c.type_name
        ]
        self.assertTrue(gates)
        for g in gates:
            self.assertIn(spans_of(g), word_spans, g.name)

    def test_lut_span_union(self) -> None:
        d, _, snap = front(micro(COMPARATOR))
        run(d, "lower; abc --lut 6")
        word_spans = {s for w in snap.words for s in w.spans}
        luts = [c for c in cells(d) if c.type_name == "$lut"]
        self.assertTrue(luts)
        for lut in luts:
            sp = spans_of(lut)
            self.assertEqual(len(sp), len(set(sp)))
            self.assertTrue(set(sp) <= word_spans)
        self.assertTrue(any(len(spans_of(lut)) >= 2 for lut in luts))

    def test_flatten_instance_spans(self) -> None:
        d, inst, snap = front(DATA / "two_inst.v")
        s1 = next(i.span for i in inst if i.name == "u1")
        s2 = next(i.span for i in inst if i.name == "u2")
        self.assertNotEqual(s1, s2)
        adds = [w for w in snap.words if w.type == "$add"]
        self.assertEqual(len(adds), 2)
        by_inst = {w.spans[-1]: w.spans for w in adds}
        self.assertEqual(set(by_inst), {s1, s2})
        for spans in by_inst.values():
            self.assertEqual(len(spans), 2)
            self.assertNotIn(spans[0], (s1, s2))

    def test_nested_span_order(self) -> None:
        d, inst, snap = front(DATA / "nested.v")
        sub = next(w for w in snap.words if w.type == "$sub")
        sites = {i.name: i.span for i in inst}
        order = [next((n for n, s in sites.items() if s == sp), "-") for sp in sub.spans]
        path = module_path(sub.spans, inst, snap.top)
        self.assertEqual(path, "nested/m1/l1", f"span order {order}")

    def test_nested_ambiguous_instances(self) -> None:
        _, inst, snap = front(DATA / "nested2.v")
        subs = [w for w in snap.words if w.type == "$sub"]
        self.assertEqual(len(subs), 2)
        self.assertEqual(subs[0].spans, subs[1].spans)  # m1.l1 and m2.l1 look the same
        self.assertEqual(module_path(subs[0].spans, inst, snap.top), "nested2/*/l1")

    def test_attr_does_not_survive_lower(self) -> None:
        d, _, _ = front(micro(COMPARATOR))
        for n in cells(d):
            n.set_attr("loki_t", "x")
        run(d, "lower")
        gates = [c for c in cells(d) if str(c.type_name).startswith("$_")]
        self.assertTrue(gates)
        self.assertTrue(all(g.attr("loki_t") is None for g in gates))

    def test_net_alias_names(self) -> None:
        d, _, _ = front(micro(COMPARATOR))
        run(d, "lower; abc --lut 6")
        names = {a for net in d.top().nets() for a in net.aliases()}
        self.assertIn("AeqB[0]", names)

    def test_fsm_carrier(self) -> None:
        d, _, snap = front(DATA / "fsm2.v")
        self.assertEqual(snapshot.FSM_CARRIER, "node:odin3_fsm_encoding")
        flagged = [w for w in snap.words if w.fsm]
        self.assertEqual(len(flagged), 1)
        self.assertTrue(flagged[0].type.startswith("$dff"))

    @unittest.skipUnless(can_run_flow(), "needs a VTR architecture")
    def test_hardmap_keeps_spans(self) -> None:
        d, _, snap = front(micro("bm_base_multiply"), "f1-k6", "k6_frac_N10_frac_chain_mem32K_40nm")
        run(d, "hardmap")
        hard = [c for c in cells(d) if str(c.granularity) == "hard"]
        self.assertTrue(hard)
        word_spans = {w.spans for w in snap.words}
        for h in hard:
            self.assertIn(spans_of(h), word_spans, h.type_name)

    @unittest.skipUnless(can_run_flow(), "needs a VTR architecture")
    def test_hard_port_names(self) -> None:
        d, _, _ = front(micro("bm_base_multiply"), "f1-k6", "k6_frac_N10_frac_chain_mem32K_40nm")
        run(d, "hardmap")
        hard = [c for c in cells(d) if str(c.granularity) == "hard"]
        ports = {str(c.type_name): [p.name for p in c.ports()] for c in hard}
        self.assertEqual(ports["multiply"], ["a", "b", "out"])

    def test_floor_scripts(self) -> None:
        front_s, map_s = floor_script("f2", [Path("/x/a.v")], Path("/x/arch.xml"), None)
        self.assertIn('read_verilog --nolatches --vtr-compat "/x/a.v"', front_s)
        self.assertEqual(map_s, "lower; abc --lut 6")
        f1 = floor_script("f1-k6", [], Path("a"), None)
        self.assertEqual(f1[1], "hardmap; lower; abc --lut 6")
        with self.assertRaises(NotImplementedError):
            floor_script("f3", [], None, None)


if __name__ == "__main__":
    unittest.main()
