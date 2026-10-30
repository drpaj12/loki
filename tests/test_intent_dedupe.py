import unittest
from typing import Any

from loki.intent.dedupe import covers, merge_duplicates


def claim(hid: str, kind: str, nets: dict[str, list[str]], p: float,
          **params: int | str) -> dict[str, Any]:
    return {"id": hid, "kind": kind, "nets": nets, "p": p, "params": params, "wires": list(nets)}


class DedupeTest(unittest.TestCase):
    def test_identical_claims_merge_and_keep_the_highest_p(self) -> None:
        a = claim("h6", "ff_srst", {"d": ["_01_"], "q": ["q[1]"], "rst": ["r"]}, 0.75, active=0)
        b = claim("h59", "ff_srst", {"d": ["_01_"], "q": ["q[1]"], "rst": ["r"]}, 0.80, active=0)
        out = merge_duplicates([a, b])
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["id"], "h6")
        self.assertEqual(out[0]["p"], 0.80)
        self.assertEqual(out[0]["merged"], ["h59"])

    def test_nested_claim_merges_into_the_larger(self) -> None:
        big = claim("h1", "ff_srst", {"d": ["a", "b", "c"], "q": ["x", "y", "z"], "rst": ["r"]},
                    0.5, active=0, value=0, width=3)
        small = claim("h8", "ff_srst", {"d": ["b"], "q": ["y"], "rst": ["r"]}, 0.75,
                      active=0, value=0)
        out = merge_duplicates([small, big])
        self.assertEqual([c["id"] for c in out], ["h1"])
        self.assertEqual(out[0]["p"], 0.75)
        self.assertEqual(out[0]["merged"], ["h8"])

    def test_different_kind_params_or_nets_do_not_merge(self) -> None:
        base = claim("h1", "ff_srst", {"q": ["x"], "rst": ["r"]}, 0.5, active=0)
        other_kind = claim("h2", "register", {"q": ["x"], "rst": ["r"]}, 0.5, active=0)
        other_level = claim("h3", "ff_srst", {"q": ["x"], "rst": ["r"]}, 0.5, active=1)
        other_net = claim("h4", "ff_srst", {"q": ["w"], "rst": ["r"]}, 0.5, active=0)
        self.assertEqual(len(merge_duplicates([base, other_kind, other_level, other_net])), 4)

    def test_input_is_not_changed_and_result_sorted_by_id(self) -> None:
        a = claim("h10", "bus", {"s0": ["a"]}, 0.6)
        b = claim("h2", "mux", {"s0": ["z"]}, 0.6)
        out = merge_duplicates([a, b])
        self.assertEqual([c["id"] for c in out], ["h2", "h10"])
        self.assertNotIn("merged", a)

    def test_empty_nets_cover_nothing(self) -> None:
        self.assertFalse(covers(claim("h1", "bus", {"a": ["x"]}, 1.0), claim("h2", "bus", {}, 1.0)))


if __name__ == "__main__":
    unittest.main()
