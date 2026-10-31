"""Tests of the graphlet library generators and database (no synthesis tools needed)."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import db  # noqa: E402
import gen  # noqa: E402
import live  # noqa: E402


class GenTests(unittest.TestCase):
    def test_counts_and_widths(self) -> None:
        insts = list(gen.instances())
        self.assertEqual(len(insts), 700)
        self.assertEqual(len({i.name for i in insts}), 700)
        for p in ("counter", "shift", "register", "timer", "glue", "regfile"):
            self.assertEqual({i.width for i in insts if i.pattern == p}, set(range(1, 33)))
        self.assertEqual({i.width for i in insts if i.pattern == "fsm"}, set(range(2, 33)))

    def test_all_render_and_wide(self) -> None:
        for i in gen.instances():
            src = gen.verilog(i)
            self.assertIn("module top", src)
        self.assertIn("[63:0]", gen.verilog(gen.Inst("counter", "up", 64)))
        self.assertIn("S47", gen.verilog(gen.Inst("fsm", "onehot", 48)))

    def test_lfsr_full_period(self) -> None:
        for w in range(2, 17):
            self.assertEqual(gen.lfsr_period(w), 2**w - 1)

    def test_unknown_lfsr_width(self) -> None:
        with self.assertRaises(ValueError):
            gen.verilog(gen.Inst("lfsr", "fib", 40))


class DbTests(unittest.TestCase):
    def test_round_trip_and_export(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            con = db.open_db(Path(td) / "lib.sqlite")
            k = db.Key("counter", "up", 33, 0, "O-gate")
            kw = {"input_sha256": "a", "tool_commit": "b", "script_hash": "c",
                  "measurer_version": "v", "origin": "rtl/x.v"}
            db.put_signature(con, k, "live", "undirected", {0: 3.0, 1: 5.0}, **kw)
            db.put_signature(con, k, "live", "undirected", {0: 4.0, 1: 5.0}, **kw)  # idempotent
            sig, prov = db.get_signature(con, k, "undirected")
            self.assertEqual((sig, prov), ({0: 4.0, 1: 5.0}, "live"))
            self.assertEqual(db.get_signature(con, k, "directed"), ({}, ""))
            self.assertEqual(db.export_csv(con, Path(td) / "r.csv"), 2)
            with self.assertRaises(ValueError):
                db.put_signature(con, k, "live", "bogus", {0: 1.0}, **kw)

    def test_live_path_with_fake_signer(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            con = db.open_db(Path(td) / "lib.sqlite")
            inst = gen.Inst("counter", "up", 48)
            orig = live.build_one
            live.build_one = lambda i, c: "ok"  # type: ignore[assignment]
            try:
                res = live.live_entry(con, inst, "O-gate", lambda p, m: {0: 1.0})
                none = live.live_entry(con, inst, "O-lut")
            finally:
                live.build_one = orig  # type: ignore[assignment]
            self.assertEqual(res["signature"], "stored")
            self.assertTrue(none["signature"].startswith("pending"))
            sig, prov = db.get_signature(con, live.key_of(inst, "O-gate"), "undirected")
            self.assertEqual((sig, prov), ({0: 1.0}, "live"))


if __name__ == "__main__":
    unittest.main()
