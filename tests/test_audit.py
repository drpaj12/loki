"""The round-6 loss audit: pure core on hand-built objects, two micros with a known loss."""

from __future__ import annotations

import os
import unittest
from pathlib import Path
from typing import Any

from loki.audit.loss import UnitRow, audit, hw_kind, null_losses, reason_of, separable
from loki.audit.units import ObjView, UnitKey
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
        self.assertEqual(reason_of("fsm", False, False, False), "fsm-recode")
        self.assertEqual(reason_of("opt", True, True, True), "instance-join")
        self.assertEqual(reason_of("wreduce", True, True, False), "width-reduce")
        self.assertEqual(reason_of("lower", True, True, False), "lower-share")
        self.assertEqual(hw_kind(["$and", "$sdffe"]), "register")
        self.assertEqual(hw_kind(["$eq", "$mux"]), "mux")
        self.assertEqual(hw_kind(["$and"]), "logic")

    def test_null_is_deterministic(self) -> None:
        s1 = [obj(f"o{i}", "$and", u(i)) for i in range(6)]
        s2 = [obj("x", "$lut", u(0), u(1)), obj("y", "$and", u(2)), obj("z", "$and", u(3))]
        a = null_losses([("p", s1), ("q", s2)], "d")
        b = null_losses([("p", s1), ("q", s2)], "d")
        self.assertEqual(a, b)
        self.assertEqual(a[0], {})
        self.assertEqual(set(a[1]), {u(i) for i in range(6)})


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
