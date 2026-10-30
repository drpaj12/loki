import unittest
from typing import Any

from loki.intent.buses import find_buses, index_groups


def seq(hid: str, kind: str, q: list[str], p: float, **extra: Any) -> dict[str, Any]:
    return {"id": hid, "kind": kind, "source": "seq", "p": p,
            "nets": {"q": q, "d": [f"d{i}" for i in range(len(q))]}, "facts": extra}


class IndexGroupsTest(unittest.TestCase):
    def test_consecutive_indices_form_a_bus_lsb_first(self) -> None:
        got = index_groups(["q[2]", "q[0]", "q[1]", "x", "a[0]", "b[3]", "b[5]"])
        self.assertEqual(got, {"q": ["q[0]", "q[1]", "q[2]"]})

    def test_longest_trailing_run_wins(self) -> None:
        got = index_groups(["s[0]", "s[2]", "s[3]", "s[4]"])
        self.assertEqual(got["s"], ["s[2]", "s[3]", "s[4]"])


class FindBusesTest(unittest.TestCase):
    def test_state_bus_links_to_its_fsm(self) -> None:
        claims = [seq("h2", "fsm", ["state[0]", "state[1]"], 0.97)]
        buses = find_buses(claims, [])
        by = {b["base"] or "+".join(b["bits"]): b for b in buses}
        state = by["state"]
        self.assertEqual(state["bits"], ["state[0]", "state[1]"])
        self.assertEqual(state["order_source"], "index")
        self.assertEqual(state["links"][0]["text"], "state of the state machine h2")
        self.assertEqual(state["p"], 0.97)
        self.assertEqual(state["evidence"], "declared")

    def test_next_state_bus_from_claim_order(self) -> None:
        claims = [seq("h7", "counter", ["_1_", "_2_"], 0.9)]
        buses = find_buses(claims, [])
        texts = {b["links"][0]["text"] for b in buses}
        self.assertEqual(texts, {"value of the counter h7", "next-state input of h7"})
        self.assertTrue(all(b["order_source"] == "claim" for b in buses))

    def test_same_bits_are_one_bus_and_ids_count_up(self) -> None:
        claims = [seq("h1", "counter", ["q[0]", "q[1]"], 0.9)]
        buses = find_buses(claims, ["q[0]", "q[1]"])
        bits = [tuple(b["bits"]) for b in buses]
        self.assertEqual(len(bits), len(set(bits)))
        self.assertEqual([b["id"] for b in buses], [f"b{i + 1}" for i in range(len(buses))])

    def test_load_word_and_arithmetic_operand_purposes(self) -> None:
        shift = seq("h3", "shift_reg", ["q0", "q1"], 0.8,
                    modes=[{"label": "load-const", "cond": [], "data": ["d[0]", "d[1]"]}])
        add = {"id": "h9", "kind": "adder", "source": "overlay", "p": 0.6,
               "nets": {"A": ["a[0]", "a[1]"], "B": ["b[0]", "b[1]"], "Y": ["y[0]", "y[1]"]},
               "facts": {}}
        buses = {b["base"]: b for b in find_buses([shift, add], [])}
        self.assertEqual(buses["d"]["links"][0]["text"], "parallel load word of h3")
        self.assertEqual(buses["a"]["links"][0]["text"], "operand A of adder h9")
        self.assertEqual(buses["y"]["links"][0]["text"], "result of adder h9")
        self.assertEqual(buses["a"]["p"], 0.6)

    def test_overlay_bus_slices(self) -> None:
        bus = {"id": "h25", "kind": "bus", "source": "overlay", "p": 0.9, "facts": {},
               "nets": {"slice0": ["_12_"], "slice1": ["w3"], "ctrl": ["_04_"]}}
        (b,) = find_buses([bus], [])
        self.assertEqual((b["bits"], b["order_source"]), (["_12_", "w3"], "slices"))


if __name__ == "__main__":
    unittest.main()
