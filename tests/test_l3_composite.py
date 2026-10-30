"""L3 v0 composite detector: parts, wires and components."""

from __future__ import annotations

import unittest

from loki.l3.composite import composites_of, parts_of, wires_of
from loki.l3.detect import Detection, Instance
from loki.l3.netlist import Netlist

# fsm state q0 -> gate g -> counter enable en; a second counter (q9) is unrelated
BLIF = """.model m
.inputs clk
.names q0 g
1 1
.latch g qd re clk 3
.latch en c0 re clk 3
.names g en
1 1
.latch c0 q9 re clk 3
.end
"""


def inst(entry: str, q: str, inputs: list[str], p: float = 0.99) -> Instance:
    return Instance(entry, [entry[0]], frozenset({q}), frozenset(inputs), p)


def detection() -> Detection:
    found = {"fsm": [inst("fsm", "q0", ["x"])], "counter": [inst("counter", "c0", ["en"])],
             "shift": [inst("shift", "q9", ["zz"])]}
    return Detection("gate", found, {})


class CompositeTest(unittest.TestCase):
    def test_wire_and_component(self) -> None:
        parts = parts_of(detection())
        self.assertEqual({p.family for p in parts}, {"fsm", "counter", "shift"})
        wires = wires_of(parts, Netlist(BLIF), 4)
        self.assertEqual([(parts[w.src].family, parts[w.dst].family, w.depth) for w in wires],
                         [("fsm", "counter", 2)])
        comps = composites_of(parts, wires)
        self.assertEqual([c.pattern for c in comps], ["counter+fsm"])

    def test_depth_cap(self) -> None:
        parts = parts_of(detection())
        self.assertEqual(wires_of(parts, Netlist(BLIF), 1), [])

    def test_timer_replaces_counter(self) -> None:
        det = detection()
        det.instances["timer"] = [inst("timer", "c0", ["en"])]
        parts = parts_of(det)
        self.assertEqual(sorted(p.entry for p in parts), ["fsm", "shift", "timer"])


if __name__ == "__main__":
    unittest.main()
