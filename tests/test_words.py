import json
import unittest

from loki.anon import Numbering
from loki.model import Port, Snapshot, Span, WordCell
from loki.schemas import validate_words
from loki.words import build_words

SPAN = (Span("/p/d.v", 3, 1, 3, 9),)


def word(
    wid: int, typ: str, ins: dict[str, tuple[int, ...]], outs: dict[str, tuple[int, ...]],
    name: str = "", fsm: bool = False,
) -> WordCell:
    return WordCell(
        id=wid, type=typ, name=name, params={"Y_WIDTH": 5}, spans=SPAN,
        inputs=tuple(Port(k, len(v), v) for k, v in ins.items()),
        outputs=tuple(Port(k, len(v), v) for k, v in outs.items()), fsm=fsm,
    )


def numbering() -> Numbering:
    return Numbering(net={}, cell={17: "n17", 18: "n18", 19: "n19"}, pi={}, po={})


def snapshot() -> Snapshot:
    words = (
        word(5, "$_CONST1_", {}, {"Y": (30,)}),
        word(6, "$add", {"A": (1, 2), "B": (30, 0)}, {"Y": (10, 11)}, name="secret_add"),
        word(9, "$dff", {"D": (10, 11), "C": (3,)}, {"Q": (12, 13)}, fsm=True),
    )
    return Snapshot(words, (), "top")


class BuildWordsTest(unittest.TestCase):
    def build(self) -> dict[str, object]:
        matched = {17: (6,), 18: (6, 9), 19: ()}
        return build_words(snapshot(), matched, numbering(), {5: "const", 6: "datapath"})

    def words(self) -> dict[int, dict[str, object]]:
        out = self.build()["words"]
        assert isinstance(out, list)
        return {w["id"]: w for w in out}

    def test_footprint_from_matches(self) -> None:
        self.assertEqual(self.words()[6]["footprint"], ["n17", "n18"])
        self.assertEqual(self.words()[9]["footprint"], ["n18"])

    def test_const_ports(self) -> None:
        self.assertEqual(self.words()[6]["const_ports"], ["B"])
        self.assertEqual(self.words()[9]["const_ports"], [])

    def test_roles_and_fsm(self) -> None:
        self.assertEqual(self.words()[6]["role"], "datapath")
        self.assertEqual(self.words()[9]["role"], "unknown")
        self.assertTrue(self.words()[9]["fsm"])

    def test_edges_sorted_and_deduplicated(self) -> None:
        # nets 10 and 11 both run from word 6 Y to word 9 D: one edge
        edges = self.build()["edges"]
        self.assertEqual(edges, [{"src": 5, "src_port": "Y", "dst": 6, "dst_port": "B"},
                                 {"src": 6, "src_port": "Y", "dst": 9, "dst_port": "D"}])

    def test_no_original_names(self) -> None:
        self.assertNotIn("secret_add", json.dumps(self.build()))
        self.assertNotIn("/p/d.v", json.dumps(self.build()))


class ValidateWordsTest(unittest.TestCase):
    def good(self) -> dict[str, object]:
        return {
            "schema": 1,
            "words": [
                {"id": 6, "type": "$add", "params": {"A_WIDTH": 4}, "fsm": False,
                 "role": "datapath", "const_ports": ["B"], "footprint": ["n17", "n18"]},
                {"id": 9, "type": "$dff", "params": {}, "fsm": False, "role": "control",
                 "const_ports": [], "footprint": []},
            ],
            "edges": [{"src": 6, "src_port": "Y", "dst": 9, "dst_port": "D"}],
        }

    def test_validate_words(self) -> None:
        self.assertEqual(validate_words(self.good()), [])
        self.assertEqual(validate_words(json.loads(json.dumps(self.build_good()))), [])

    def build_good(self) -> dict[str, object]:
        matched = {17: (6,), 18: (6, 9)}
        return build_words(snapshot(), matched, numbering(), {})

    def test_unknown_key(self) -> None:
        obj = self.good()
        obj["extra"] = 1
        self.assertTrue(validate_words(obj))

    def test_non_int_id(self) -> None:
        obj = self.good()
        words = obj["words"]
        assert isinstance(words, list)
        words[0]["id"] = "6"
        self.assertTrue(validate_words(obj))

    def test_edge_to_missing_word(self) -> None:
        obj = self.good()
        obj["edges"] = [{"src": 6, "src_port": "Y", "dst": 77, "dst_port": "D"}]
        self.assertTrue(any("not a word" in e for e in validate_words(obj)))


if __name__ == "__main__":
    unittest.main()
