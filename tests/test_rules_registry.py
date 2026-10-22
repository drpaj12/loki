"""The rule tables against Odin III's real port names and word types (plan Task 3 step 6)."""

import unittest

from loki.odin import OdinSkip, open_front
from loki.rules import CONTROL_PORTS, DATA_FORCED, NEUTRAL
from loki.snapshot import take_snapshot
from tests.helpers import DATA, can_run_f2, f2_arch, odin3_root


@unittest.skipUnless(can_run_f2(), "needs Odin III")
class RegistryTest(unittest.TestCase):
    def test_control_ports_exist(self) -> None:
        d, inst = open_front("f2", [DATA / "ctrl_ports.v"], None, f2_arch(), None)
        snap = take_snapshot(d, inst)
        checked = set()
        for w in snap.words:
            if w.type in CONTROL_PORTS:
                have = {p.name for p in (*w.inputs, *w.outputs)}
                self.assertTrue(CONTROL_PORTS[w.type] <= have, (w.type, have))
                checked.add(w.type)
        # $dlatch never appears: the flow reads with --nolatches.
        self.assertTrue({"$mux", "$dffe", "$adff", "$sdff"} <= checked)

    def test_types_in_micros_are_listed(self) -> None:
        root = odin3_root()
        assert root is not None
        listed = NEUTRAL | DATA_FORCED | set(CONTROL_PORTS)
        found: dict[str, str] = {}
        unread: list[str] = []
        micros = sorted((root / "tests" / "micro" / "verilog" / "micro").glob("*.v"))
        self.assertEqual(len(micros), 68)
        for path in micros:
            try:
                d, inst = open_front("f2", [path], None, f2_arch(), None)
            except OdinSkip:
                unread.append(path.name)
                continue
            for w in take_snapshot(d, inst).words:
                found.setdefault(w.type, path.name)
        missing = {t: f for t, f in found.items() if t not in listed and t.startswith("$")}
        self.assertEqual(missing, {})
        self.assertLessEqual(len(unread), 6, unread)


if __name__ == "__main__":
    unittest.main()
