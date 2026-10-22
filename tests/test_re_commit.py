import tempfile
import unittest
from pathlib import Path
from typing import Any

from loki.re.claims import Claim
from loki.re.commit import commit, fn_text, proof_label, reject_failed
from loki.re.detectors import Candidate
from loki.re.fngraph import FnGraph, from_design
from loki.re.normalise import load_level0
from loki.re.overlay import Hypothesis, Overlay
from loki.re.provers import Verdict
from loki.re.view import View
from tests.helpers import DATA, can_run_f2

ADD2 = DATA / "re" / "add2.blif"
ADD2X4 = DATA / "re" / "add2x4.blif"
ADD_P = (("A_WIDTH", 2), ("B_WIDTH", 2), ("Y_WIDTH", 2))
EQC = ".model eqc\n.inputs a0 a1\n.outputs y\n.names a0 a1 y\n10 1\n.cname n10\n.end\n"
READ_OUT = (
    ".model rd\n.inputs a0 a1 b0 b1\n.outputs y0 y1 z\n"
    ".names a0 b0 y0\n01 1\n10 1\n.cname n10\n"
    ".names a0 b0 c0\n11 1\n.cname n11\n"
    ".names a1 b1 c0 y1\n001 1\n010 1\n100 1\n111 1\n.cname n12\n"
    ".names c0 z\n1 1\n.cname n13\n.end\n"
)


def net_ids(graph: FnGraph) -> dict[str, int]:
    return {name: net for net, name in graph.names.items()}


def cell_ids(graph: FnGraph, *names: str) -> frozenset[int]:
    by_name = {c.name: c.id for c in graph.cells.values()}
    return frozenset(by_name[n] for n in names)


def adder_cand(graph: FnGraph, sfx: str, cells: frozenset[int]) -> Candidate:
    n = net_ids(graph)
    a = (n[f"a0{sfx}"], n[f"a1{sfx}"])
    b = (n[f"b0{sfx}"], n[f"b1{sfx}"])
    y = (n[f"y0{sfx}"], n[f"y1{sfx}"])
    claim = Claim("add", ADD_P, (("A", a), ("B", b)), (("Y", y),))
    return Candidate("adder", cells, {"A": a, "B": b, "Y": y}, {"width": 2}, {}, claim)


def confirmed(ov: Overlay, cand: Candidate, engine: str = "cone_check") -> Hypothesis:
    h = ov.add(cand, "arith", 1)
    ov.apply_verdict(h.id, Verdict("equivalent", engine, ""), 1)
    h.p_comp = 0.99
    return h


def read(path: Path) -> Any:
    return load_level0(path, "f2", None, None)


def read_text(text: str) -> tuple[Any, tempfile.TemporaryDirectory[str]]:
    tmp = tempfile.TemporaryDirectory()
    path = Path(tmp.name) / "d.blif"
    path.write_text(text, encoding="utf-8")
    return read(path), tmp


def real_nodes(module: Any) -> list[Any]:
    return [n for n in module.nodes() if not str(n.type_name).startswith("$port")]


def types(module: Any) -> list[str]:
    return sorted(str(n.type_name) for n in real_nodes(module))


class FnTextTest(unittest.TestCase):
    def hyp(self, kind: str, params: dict[str, int | str]) -> Hypothesis:
        return Hypothesis("h1", kind, "x", 1, frozenset({1}), {}, params, None)

    def test_counter_text(self) -> None:
        h = self.hyp("counter", {"dir": "up", "modulus": 10, "wrap": 0, "width": 4, "en": 0})
        self.assertEqual(fn_text(h), "Q <= (Q == 9) ? 0 : Q + 1")

    def test_fsm_text(self) -> None:
        self.assertEqual(fn_text(self.hyp("fsm", {"states": 5})), "fsm: 5 states")

    def test_proof_label(self) -> None:
        h = self.hyp("adder", {})
        self.assertEqual(proof_label(h), "none")
        h.proof = {"engine": "transfer", "verdict": "equivalent", "template": "", "cex": "",
                   "from": "h2"}
        self.assertEqual(proof_label(h), "derived")


@unittest.skipUnless(can_run_f2(), "needs Odin III and ABC")
class CommitTest(unittest.TestCase):
    def setUp(self) -> None:
        self.level0 = read(ADD2)
        self.graph = from_design(self.level0)
        self.ov = Overlay()

    def adder(self) -> Hypothesis:
        cells = cell_ids(self.graph, "n10", "n11", "n12")
        return confirmed(self.ov, adder_cand(self.graph, "", cells))

    def test_raise_and_submod_adder(self) -> None:
        before = types(self.level0.top())
        h = self.adder()
        res = commit(self.level0, [h], self.ov, self.graph, 30)
        self.assertEqual(res.forms, {"h1": "raise+submod"})
        self.assertEqual(res.failed, ())
        module = res.design.module("adder_h1")
        self.assertEqual(types(module), ["$add"])
        inst = next(n for n in res.design.top().nodes() if n.name == "adder_h1_i")
        self.assertEqual(inst.attr("loki_hid"), "h1")
        self.assertEqual(inst.attr("loki_conf"), "0.9900")
        self.assertEqual(inst.attr("loki_proof"), "equivalent")
        self.assertEqual(inst.attr("loki_fn"), "Y = A + B")
        self.assertEqual(inst.attr("loki_kind"), "adder")
        self.assertEqual(module.attr("loki_fn"), "Y = A + B")
        self.assertEqual(types(self.level0.top()), before)

    def test_submod_only_for_const_claim(self) -> None:
        level0, tmp = read_text(EQC)
        with tmp:
            graph = from_design(level0)
            n = net_ids(graph)
            a = (n["a0"], n["a1"])
            claim = Claim("eq_const", (("C", 1), ("width", 2)), (("A", a),), (("Y", (n["y"],)),))
            cand = Candidate("eq_const", cell_ids(graph, "n10"), {"A": a, "Y": (n["y"],)},
                             {"C": 1}, {}, claim)
            ov = Overlay()
            h = confirmed(ov, cand, "truth_table")
            res = commit(level0, [h], ov, graph, 30)
        self.assertEqual(res.forms, {"h1": "submod"})
        self.assertEqual(types(res.design.module("eq_const_h1")), ["$sop"])
        self.assertEqual(fn_text(h), "Y = (A == 1)")

    def test_commit_falls_back_to_submod(self) -> None:
        level0, tmp = read_text(READ_OUT)
        with tmp:
            graph = from_design(level0)
            ov = Overlay()
            cells = cell_ids(graph, "n10", "n11", "n12")
            n = net_ids(graph)
            cand = adder_cand(graph, "", cells)
            self.assertIn(n["c0"], graph.names)
            h = confirmed(ov, cand)
            res = commit(level0, [h], ov, graph, 30)
        self.assertEqual(res.forms, {"h1": "submod"})
        self.assertEqual(types(res.design.module("adder_h1")), ["$sop", "$sop", "$sop"])

    def test_nested_commit(self) -> None:
        child = self.adder()
        first = commit(self.level0, [child], self.ov, self.graph, 30)
        child.status = "committed"
        cells = cell_ids(self.graph, "n10", "n11", "n12", "n13")
        parent = self.ov.add(
            Candidate("datapath_unit", cells, {}, {}, {}), "unit", 2)
        parent.p_comp = 0.95
        res = commit(first.design, [parent], self.ov, self.graph, 30)
        self.assertEqual(res.forms, {parent.id: "submod"})
        inner = res.design.module(f"datapath_unit_{parent.id}")
        names = sorted(str(n.name) for n in real_nodes(inner))
        self.assertIn("adder_h1_i", names)
        self.assertEqual(len(names), 2)

    def test_commit_retry_without_offender(self) -> None:
        level0 = read(ADD2X4)
        graph = from_design(level0)
        ov = Overlay()
        sets = {k: cell_ids(graph, *(f"n{10 + 3 * k + i}" for i in range(3))) for k in range(4)}
        h1 = confirmed(ov, adder_cand(graph, "_1", sets[1]))
        h2 = confirmed(ov, adder_cand(graph, "_2", sets[2]))
        working = level0.copy()
        for node in working.top().nodes():
            lines = {int(s.line) for s in node.sources()}
            if lines & {graph.cells[c].line for c in sets[0]}:
                node.set_attr("loki_sm", "adder_h1")
        working.run_pass("submod", "-attr loki_sm")
        res = commit(working, [h1, h2], ov, graph, 30)
        self.assertEqual(res.failed, ("h1",))
        self.assertEqual(res.forms, {"h2": "raise+submod"})
        self.assertIsNotNone(res.design.module("adder_h2"))
        reject_failed(ov, res, 3)
        self.assertEqual(h1.status, "rejected")
        self.assertEqual(h1.evidence[-1].source, "commit")
        self.assertEqual(h1.evidence[-1].round, 3)

    def test_bus_attrs_on_nets(self) -> None:
        n = net_ids(self.graph)
        cand = Candidate("bus", cell_ids(self.graph, "n10", "n12"),
                         {"slice0": (n["y0"],), "slice1": (n["y1"],), "ctrl": ()},
                         {"k": 2, "order_source": "net_id"}, {})
        bus = self.ov.add(cand, "bus", 1)
        bus.p_comp = 0.95
        res = commit(self.level0, [bus], self.ov, self.graph, 30)
        self.assertEqual(res.forms, {"h1": "attrs"})
        self.assertEqual(res.design.top().net("y0").attr("loki_bus"), "h1[0]")
        self.assertEqual(res.design.top().net("y1").attr("loki_bus"), "h1[1]")

    def test_view_build_footprints(self) -> None:
        h = self.adder()
        res = commit(self.level0, [h], self.ov, self.graph, 30)
        h.status = "committed"
        view = View.build(res.design, self.graph, self.ov)
        self.assertEqual(len(view.pieces), 1)
        self.assertEqual(view.pieces[0].cells, h.cells)
        self.assertEqual(view.absorbed, h.cells)
        add = next(n for n in res.design.module("adder_h1").nodes() if n.type_name == "$add")
        lines = {int(s.line) for s in add.sources()}
        self.assertEqual(lines, {4, 8, 11})


if __name__ == "__main__":
    unittest.main()
