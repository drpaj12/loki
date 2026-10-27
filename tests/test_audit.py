"""The round-6 loss audit: pure core on hand-built objects, two micros with a known loss."""

from __future__ import annotations

import importlib
import os
import random
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from loki.audit.loss import (
    PERSIST_DRAWS,
    UnitRow,
    audit,
    hw_kind,
    null_losses,
    persistence_draw,
    persistence_losses,
    reason_of,
    separable,
)
from loki.audit.units import (
    ObjView,
    UnitKey,
    anchor,
    branch_unit,
    leaf_constructs,
    reduce_units,
    run_matches,
    view_map,
)
from tests.helpers import odin_available

DATA = Path(__file__).parent / "data" / "audit"
WORK = Path(os.environ.get("LOKI_AUDIT_TEST_DIR", "/tmp/claude-1000/le6-test"))


def u(n: int) -> UnitKey:
    return ("f.v", "NET_ASSIGN", f"{n}.1-{n}.9", "")


def obj(name: str, typ: str, *units: UnitKey, joined: tuple[UnitKey, ...] = (),
        anchors: tuple[UnitKey, ...] = ()) -> ObjView:
    return ObjView(name, typ, frozenset(units), frozenset(joined), False, frozenset(),
                   frozenset(anchors) or frozenset(units))


def reason(rows: dict[UnitKey, UnitRow], key: UnitKey) -> str:
    loss = rows[key].loss
    return loss.reason if loss else ""


def fake_map() -> Any:
    """A hand-built v2 map: module > always(block) > if-arm(branch) > assign(stmt) > expr, and
    two continuous assigns. Runs: t1 proc, t2 opt."""
    def c(level: str, parent: int, kind: str, span: str) -> Any:
        return SimpleNamespace(file=1, kind=kind, span=span, name="", level=level, parent=parent)

    def r(num: int, kind: str, parents: tuple[int, ...] = (), cons: tuple[int, ...] = (),
          step: str = "t1.1", flags: tuple[str, ...] = ()) -> Any:
        return SimpleNamespace(number=num, kind=kind, parents=parents, constructs=cons,
                               step=step, flags=flags)

    constructs = [c("module", 0, "MODULE", "1.1-9.1"), c("block", 1, "ALWAYS", "2.1-4.9"),
                  c("branch", 2, "IF_THEN", "3.1-4.9"),
                  c("stmt", 3, "NONBLOCKING_ASSIGN", "4.1-4.9"),
                  c("stmt", 1, "NET_ASSIGN", "5.1-5.9"), c("stmt", 1, "NET_ASSIGN", "6.1-6.9"),
                  c("expr", 4, "ID", "4.5-4.6")]
    recs = [r(1, "S", cons=(7,)), r(2, "S", cons=(5,)), r(3, "S", cons=(6,)),
            r(4, "D", (1,), step="t1.1"),
            r(5, "D", (2, 3), (5, 6), "t2.1", ("join",)),
            r(6, "D", (2, 3, 1), (5,), "t2.1", ("join=instance", "join", "ctx=1")),
            r(8, "D", (2, 3), step="t1.1"),
            r(7, "D", (8, 2), step="t2.1"),
            r(9, "D", (2,), step="t2.1", flags=("lossy=cap",))]
    obj = [SimpleNamespace(name=n, kind=k, records=(rec,)) for n, k, rec in (
        ("hjoin", "node", 5), ("hinst", "node", 6), ("hinh", "node", 7), ("hcap", "node", 9),
        ("hconst", "node", 2), ("hwire", "wire", 2), ("hmiss", "node", 2), ("hdead", "node", 4))]
    return SimpleNamespace(constructs=constructs, files=["f.v"], records=recs, objects=obj,
                           runs=[("proc", ""), ("opt", "")])


TYPES = {"hjoin": "$lut", "hinst": "$lut", "hinh": "$and", "hcap": "$and", "hconst": "$const",
         "hwire": "$and", "hdead": "$and"}


def key(nm: Any, n: int) -> UnitKey:
    c = nm.constructs[n - 1]
    return ("f.v", c.kind, c.span, c.name)


class UnitsTests(unittest.TestCase):
    def test_anchor_branch_and_reduce(self) -> None:
        nm = fake_map()
        self.assertEqual(anchor(nm, 7), 4)  # expr -> its statement
        self.assertEqual(anchor(nm, 4), 4)
        self.assertEqual(branch_unit(nm, 7), 3)  # stmt under an if arm -> the arm
        self.assertEqual(branch_unit(nm, 5), 5)  # no branch ancestor: the anchor
        self.assertEqual(reduce_units(nm, {2, 4, 5}), {4, 5})  # ancestor 2 of 4 dropped

    def test_leaf_constructs_skips_context_parents(self) -> None:
        nm = fake_map()
        recs = {r.number: r for r in nm.records}
        self.assertEqual(leaf_constructs(nm, recs, 5), {5, 6})
        # r6 has ctx=1: its last parent r1 (construct 7) is skipped
        self.assertEqual(leaf_constructs(nm, recs, 6), {5, 6})
        self.assertEqual(leaf_constructs(nm, recs, 99), set())

    def test_run_matches(self) -> None:
        nm = fake_map()
        self.assertTrue(run_matches(nm, "t2.1", "opt", ""))
        self.assertFalse(run_matches(nm, "t1.1", "opt", ""))
        self.assertFalse(run_matches(nm, "t2.1", "opt", "-full"))
        self.assertFalse(run_matches(nm, "t9.1", "opt", ""))
        self.assertFalse(run_matches(nm, "origin", "opt", ""))

    def test_view_map_hand_built(self) -> None:
        nm = fake_map()
        views = {v.name: v for v in view_map(nm, TYPES, "stmt", "opt", "")}
        self.assertEqual(set(views), {"hjoin", "hinst", "hinh", "hcap", "hdead"})
        k5, k6, k4 = key(nm, 5), key(nm, 6), key(nm, 4)
        self.assertEqual(views["hjoin"].units, {k5, k6})
        self.assertEqual(views["hjoin"].joined, {k5, k6})
        self.assertEqual(views["hinst"].instance_join, {k5})
        self.assertEqual(views["hinst"].units, {k5, k6})
        self.assertTrue(views["hcap"].capped)
        self.assertEqual(views["hdead"].units, {k4})  # expr leaf anchored at its statement
        # the opt-run D records of the pass are walked through; the frontier is r2 and r8
        self.assertEqual(sorted(len(p) for p in views["hinh"].parents), [1, 2])
        self.assertIn(frozenset({k5}), views["hinh"].parents)
        self.assertIn(frozenset({k5, k6}), views["hinh"].parents)
        # a record of another pass is not a join of this pass
        other = {v.name: v for v in view_map(nm, TYPES, "stmt", "opt", "-full")}
        self.assertEqual(other["hjoin"].joined, frozenset())

    def test_view_map_branch_level(self) -> None:
        nm = fake_map()
        views = {v.name: v for v in view_map(nm, TYPES, "branch", "opt", "")}
        # the statement under the if arm becomes the arm; the continuous assigns stay
        self.assertEqual(views["hdead"].units, {key(nm, 3)})
        self.assertEqual(views["hjoin"].units, {key(nm, 5), key(nm, 6)})


class PureCoreTests(unittest.TestCase):
    def test_separable_needs_a_pure_object(self) -> None:
        objs = [obj("a", "$and", u(1)), obj("b", "$or", u(2), u(3))]
        self.assertEqual(set(separable(objs)), {u(1)})

    def test_first_loss_partner_and_label(self) -> None:
        s1 = [obj("a", "$and", u(1)), obj("b", "$or", u(2))]
        s2 = [obj("c", "$lut", u(1), u(2), joined=(u(1), u(2)))]
        rows = audit([("opt", s1), ("abc", s2)])
        loss = rows[u(1)].loss
        assert loss is not None
        self.assertEqual((loss.pass_name, loss.reason, loss.explained), ("abc", "lut-cone", True))
        self.assertEqual(loss.partners, (u(2),))
        self.assertEqual(rows[u(1)].status, "lost")

    def test_unlabelled_merge_and_removed_and_subsumed(self) -> None:
        s1 = [obj("a", "$and", u(1)), obj("b", "$or", u(2)), obj("d", "$xor", u(3))]
        s2 = [obj("c", "$lut", u(1), u(2)), obj("e", "$xor", u(4), anchors=(u(4), u(3)))]
        rows = audit([("opt", s1), ("opt", s2)])
        self.assertEqual(reason(rows, u(1)), "unlabelled-merge")
        self.assertEqual(reason(rows, u(3)), "subsumed")
        s3 = [obj("a", "$and", u(1))]
        rows = audit([("opt", s1), ("wreduce", s3)])
        self.assertEqual(reason(rows, u(2)), "removed")

    def test_late_transient_and_born_joined(self) -> None:
        s1 = [obj("a", "$and", u(1), u(2))]
        s2 = [obj("b", "$and", u(1)), obj("c", "$or", u(2))]
        s3 = [obj("d", "$lut", u(1), u(2))]
        s4 = [obj("e", "$and", u(1))]
        rows = audit([("a", s1), ("b", s2), ("c", s3), ("d", s4)])
        self.assertEqual(rows[u(1)].first, 1)
        loss = rows[u(1)].loss
        self.assertTrue(loss is not None and loss.transient)
        self.assertEqual(rows[u(2)].status, "lost")
        rows = audit([("a", s1), ("b", s1)])
        self.assertEqual(rows[u(1)].status, "born-joined")

    def test_reason_table_and_kind(self) -> None:
        self.assertEqual(reason_of("fsm", True, False, False), "fsm-recode")
        self.assertEqual(reason_of("fsm", False, False, False), "removed")
        self.assertEqual(reason_of("opt", True, True, True), "instance-join")
        self.assertEqual(reason_of("wreduce", True, True, False), "width-reduce")
        self.assertEqual(reason_of("lower", True, True, False), "lower-share")
        self.assertEqual(hw_kind(["$and", "$sdffe"]), "register")
        self.assertEqual(hw_kind(["$eq", "$mux"]), "mux")
        self.assertEqual(hw_kind(["$and"]), "logic")

    def test_inherited_capped_instance_and_fsm_paths(self) -> None:
        a = obj("a", "$and", u(1))
        # inherited: the remaining object's frontier record already blended u1 with u2
        inh = ObjView("x", "$lut", frozenset({u(1), u(2)}), frozenset(), False, frozenset(),
                      frozenset({u(1), u(2)}), (frozenset({u(1), u(2)}),))
        fresh = ObjView("y", "$lut", frozenset({u(1), u(2)}), frozenset(), False, frozenset(),
                        frozenset({u(1), u(2)}), (frozenset({u(1)}), frozenset({u(2)})))
        rows = audit([("opt", [a, obj("b", "$or", u(2))]), ("opt", [inh])])
        loss = rows[u(1)].loss
        assert loss is not None
        self.assertEqual((loss.reason, loss.inherited, loss.inherited_subset),
                         ("unlabelled-merge", True, False))
        rows = audit([("opt", [a, obj("b", "$or", u(2))]), ("opt", [fresh])])
        loss = rows[u(1)].loss
        assert loss is not None
        self.assertFalse(loss.inherited)
        # capped: a lossy=cap record whose visible join lacks u is not an explanation
        capped = ObjView("c", "$lut", frozenset({u(1), u(2)}), frozenset({u(2)}), True)
        rows = audit([("abc", [a, obj("b", "$or", u(2))]), ("abc", [capped])])
        loss = rows[u(1)].loss
        assert loss is not None
        self.assertEqual((loss.capped, loss.explained, loss.reason), (True, False,
                                                                      "unlabelled-merge"))
        # instance join
        ij = ObjView("d", "$lut", frozenset({u(1), u(2)}), frozenset({u(1)}), False,
                     frozenset({u(1)}))
        rows = audit([("flatten", [a, obj("b", "$or", u(2))]), ("flatten", [ij])])
        self.assertEqual(reason(rows, u(1)), "instance-join")
        # a merged loss at fsm is fsm-recode; a removed loss there is `removed` (first match)
        rows = audit([("fsm", [a, obj("b", "$or", u(2))]), ("fsm", [obj("c", "$lut", u(1), u(2))])])
        self.assertEqual(reason(rows, u(1)), "fsm-recode")
        rows = audit([("fsm", [a, obj("b", "$or", u(2))]), ("fsm", [a])])
        self.assertEqual(reason(rows, u(2)), "removed")

    def test_persistence_null_noop_is_zero_and_stage0_is_not(self) -> None:
        s1 = [obj(f"o{i}", "$and", u(i)) for i in range(6)]
        s2 = [obj(f"p{i}", "$and", u(i)) for i in range(6)]
        masks, mad = persistence_losses([("p", s1), ("q", s2)], "d")
        self.assertEqual(masks[1], dict.fromkeys((u(i) for i in range(6)), 0))
        self.assertEqual(mad, [0.0, 0.0])
        stage0 = null_losses([("p", s1), ("q", s2)], "d")
        self.assertGreater(sum(stage0[1].values()), 0.0)  # the flaw of the Stage-0 null

    def test_persistence_null_known_merge(self) -> None:
        s1 = [obj("a", "$and", u(1)), obj("b", "$and", u(2)), obj("c", "$and", u(3))]
        s2 = [obj("x", "$lut", u(1), u(2)), obj("c", "$and", u(3))]
        masks, mad = persistence_losses([("p", s1), ("q", s2)], "d")
        # one merge per draw; the size cap forbids nothing here, so exactly two units are lost
        total = [sum((m >> d) & 1 for m in masks[1].values()) for d in range(PERSIST_DRAWS)]
        self.assertEqual(total, [2] * PERSIST_DRAWS)
        self.assertEqual(mad[1], 0.0)

    def test_persistence_draw_counts_and_size_cap(self) -> None:
        prev = [frozenset({u(i)}) for i in range(8)]
        cur = persistence_draw(prev, [2, 2, 2, 2], random.Random(1))
        self.assertEqual(len(cur), 4)
        self.assertEqual(sorted(len(x) for x in cur), [2, 2, 2, 2])
        self.assertEqual(len(persistence_draw(prev, [1] * 9, random.Random(1))), 8)  # no split
        self.assertEqual(len(persistence_draw(prev, [], random.Random(1))), 1)

    def test_null_is_deterministic(self) -> None:
        s1 = [obj(f"o{i}", "$and", u(i)) for i in range(6)]
        s2 = [obj("x", "$lut", u(0), u(1)), obj("y", "$and", u(2)), obj("z", "$and", u(3))]
        a = null_losses([("p", s1), ("q", s2)], "d")
        b = null_losses([("p", s1), ("q", s2)], "d")
        self.assertEqual(a, b)
        self.assertEqual(a[0], {})
        self.assertEqual(set(a[1]), {u(i) for i in range(6)})


class PaperTablesTests(unittest.TestCase):
    def test_pass_tables_header_matches_cells(self) -> None:
        sys.path.insert(0, str(Path(__file__).parent.parent / "experiments" / "round6"))
        try:
            pt: Any = importlib.import_module("paper_tables")
        finally:
            sys.path.pop(0)
        for name in ("kind_pass", "reasons"):
            lines = getattr(pt, name)().splitlines()
            at = lines.index(r"\toprule") + 1
            head = [x.strip() for x in lines[at].removesuffix(r"\\").split("&")]
            rows = [[x.strip() for x in ln.removesuffix(r"\\").split("&")]
                    for ln in lines[at + 2:lines.index(r"\bottomrule")]]
            self.assertTrue(rows)
            for row in rows:
                self.assertEqual(len(row), len(head), (name, row))
            self.assertEqual(head[-len(pt.ALLP):][0], "fsm")
            self.assertEqual(head[-1], "abc")
        # alignment: the cell under a pass header is that pass's data in the CSV
        lines = pt.kind_pass().splitlines()
        at = lines.index(r"\toprule") + 1
        head = [x.strip() for x in lines[at].removesuffix(r"\\").split("&")]
        row = next([x.strip() for x in ln.removesuffix(r"\\").split("&")]
                   for ln in lines[at + 2:] if ln.startswith("mux "))
        want = next(r for r in pt.read_csv(pt.HERE / "l15_kind_pass.csv")
                    if (r["set"], r["level"], r["axis"], r["kind"], r["pass"])
                    == ("ALL", "stmt", "hw", "mux", "S3_opt"))
        self.assertEqual(row[head.index("opt")].split("/")[0], want["first_losses"])


@unittest.skipUnless(odin_available() and os.environ.get("ARCH"), "needs Odin III and $ARCH")
class MicroTests(unittest.TestCase):
    def _run(self, name: str) -> list[dict[str, Any]]:
        from loki.audit.report import audit_design
        from loki.audit.snap import run_snapshots

        out = WORK / name
        run_snapshots([DATA / f"{name}.v"], Path(os.environ["ARCH"]), out, detect=False)
        res = audit_design(out, name, "stmt")
        units = res["units"]
        assert isinstance(units, list)
        return units

    def test_lut_merge_and_dead_logic(self) -> None:
        units = {u_["span"]: u_ for u_ in self._run("lut_merge_dead")}
        for span in ("4.10-4.20", "5.10-5.21"):
            self.assertEqual(units[span]["loss"]["pass"], "abc")
            self.assertEqual(units[span]["loss"]["reason"], "lut-cone")
            self.assertTrue(units[span]["loss"]["explained"])
        self.assertEqual(units["6.10-6.22"]["loss"]["pass"], "opt")
        self.assertEqual(units["6.10-6.22"]["loss"]["reason"], "removed")

    def test_adder_is_kept(self) -> None:
        units = self._run("adder_keep")
        self.assertEqual([x["status"] for x in units], ["kept"])
        self.assertEqual(units[0]["hw"], "arith")


if __name__ == "__main__":
    unittest.main()
