import json
import unittest
from collections.abc import Mapping
from dataclasses import replace
from types import SimpleNamespace

from loki.re.detectors import Candidate
from loki.re.detectors.ff_pattern import FfPatternDetector
from loki.re.detectors.fsm import FsmDetector, _decoder_of, fsm_detect_marks
from loki.re.overlay import Overlay
from tests.re_fixtures import GB, make_ctx, table_of
from tests.seq_fixtures import up_counter


def three_state(g: GB) -> tuple[int, int, int, int]:
    """A 2-bit state register (A = 0, B = 1, C = 2) with input ``go`` and sync reset ``rst``;
    decoders on the state. With go: A to B to C to A; without: A and B go to A, C stays."""
    clk, rst, go = g.pi("clk"), g.pi("rst"), g.pi("go")
    q0, q1 = g.net("s0"), g.net("s1")
    is_a = g.lut(table_of(2, lambda v: int(v[0] == 0 and v[1] == 0)), (q0, q1))
    is_b = g.lut(table_of(2, lambda v: int(v[0] == 1 and v[1] == 0)), (q0, q1))
    is_c = g.lut(table_of(2, lambda v: int(v[0] == 0 and v[1] == 1)), (q0, q1))
    d0 = g.lut(table_of(3, lambda v: int(v[0] and v[1] and not v[2])), (is_a, go, rst))
    d1 = g.lut(
        table_of(4, lambda v: int(((v[0] and v[2]) or (v[1] and not v[2])) and not v[3])),
        (is_b, is_c, go, rst),
    )
    g.ff(d0, clk, q0)
    g.ff(d1, clk, q1)
    g.pos.extend((is_a, is_b, is_c))
    return q0, q1, rst, go


def with_srst(g: GB) -> Overlay:
    graph = g.build()
    ov = Overlay()
    for c in FfPatternDetector().propose(make_ctx(graph)):
        if c.kind == "ff_srst":
            ov.add(c, "ff_pattern", 1)
    return ov


def propose(g: GB, ov: Overlay | None = None, marks: Mapping[frozenset[int], str] | None = None
            ) -> list[Candidate]:
    ctx = make_ctx(g.build(), ov)
    if marks is not None:
        ctx = replace(ctx, fsm_marks=marks)
    return FsmDetector().propose(ctx)


class FsmTest(unittest.TestCase):
    def test_fsm_three_states(self) -> None:
        g = GB()
        q0, q1, rst, go = three_state(g)
        got = propose(g, with_srst(g))
        self.assertEqual(len(got), 1)
        c = got[0]
        self.assertEqual(c.kind, "fsm")
        self.assertEqual(c.nets["Q"], (q0, q1))
        self.assertEqual(c.features["decoder_readers"], ">=0.5")
        self.assertEqual(c.features["counter_like"], "no")
        self.assertEqual(c.features["reset_found"], "yes")
        self.assertEqual(c.features["ctrl_inputs"], "1-4")
        self.assertEqual(c.features["self_reset"], "yes")
        self.assertEqual(c.params["states"], 3)
        self.assertEqual(c.nets["RST"], (rst,))
        rows = json.loads(str(c.params["rows"]))
        self.assertEqual(len(rows), c.params["rows_n"])
        # from state 0 with go (control bit 0 is the smaller net id: rst, then go)
        self.assertIn([0, 0b10, 1], rows)  # rst = 0, go = 1: A to B
        self.assertIn([1, 0b10, 2], rows)  # B to C
        self.assertIn([2, 0b10, 0], rows)  # C to A
        self.assertIn([2, 0b00, 2], rows)  # C stays without go
        self.assertIn([2, 0b01, 0], rows)  # reset

    def test_fsm_without_reset(self) -> None:
        g = GB()
        three_state(g)
        got = propose(g)
        self.assertEqual(got[0].features["reset_found"], "no")
        self.assertEqual(got[0].params["start"], 0)
        self.assertNotIn("RST", got[0].nets)

    def test_fsm_counter_like_penalised(self) -> None:
        g = GB()
        up_counter(g, g.pi("clk"), 3, en=g.pi("en"))
        got = propose(g)
        self.assertEqual(len(got), 1)
        self.assertEqual(got[0].features["counter_like"], "yes")
        self.assertEqual(got[0].params["states"], 8)

    def test_fsm_detect_marks_feature(self) -> None:
        g = GB()
        q0, q1, _, _ = three_state(g)
        plain = propose(g)
        self.assertNotIn("fsm_detect", plain[0].features)
        marked = propose(g, marks={frozenset({q0, q1}): "onehot"})
        self.assertEqual(marked[0].features["fsm_detect"], "marked")
        other = propose(g, marks={frozenset({q0}): "onehot"})
        self.assertNotIn("fsm_detect", other[0].features)

    def test_deterministic(self) -> None:
        g = GB()
        three_state(g)
        a = propose(g)
        b = propose(g)
        self.assertEqual(a, b)

    def test_no_fsm_without_feedback(self) -> None:
        g = GB()
        clk = g.pi("clk")
        for _ in range(3):
            g.ff(g.lut(0b01, (g.pi(),)), clk)
        self.assertEqual(propose(g), [])


class DecoderSupportTest(unittest.TestCase):
    def test_wide_reader_not_a_decoder(self) -> None:
        """Spec 7.8: a reader of the Q nets counts as a decoder only with support <= 12; a
        wider equality LUT would cost 2^|other inputs| per pattern."""
        g = GB()
        q0, q1 = g.pi("q0"), g.pi("q1")
        group = frozenset({q0, q1})
        nets = []
        for width in (12, 13):
            others = [g.pi(f"o{i}") for i in range(width - 2)]
            one = table_of(width, lambda v: int(v[0] == 1 and v[1] == 1 and not any(v[2:])))
            nets.append(g.lut(one, (q0, q1, *others)))
        cells = g.build().cells
        narrow, wide = (cells[g.cell_of(n)] for n in nets)
        self.assertIsNotNone(_decoder_of(narrow, group))
        self.assertIsNone(_decoder_of(wide, group))


class MarksTest(unittest.TestCase):
    def test_fsm_detect_marks_reads_wires(self) -> None:
        def net(i: int, name: str) -> SimpleNamespace:
            return SimpleNamespace(id=i, name=name)

        class Wire:
            def __init__(self, name: str, enc: str | None) -> None:
                self.name, self._enc = name, enc

            def attr(self, key: str) -> str | None:
                return self._enc if key == "fsm_encoding" else None

        module = SimpleNamespace(
            nets=lambda: [net(1, "state[0]"), net(2, "state[1]"), net(3, "other"), net(4, "st2")],
            wires=lambda: [Wire("state", "onehot"), Wire("other", None), Wire("st2", "none")],
        )
        got = fsm_detect_marks(SimpleNamespace(top=lambda: module))
        self.assertEqual(got, {frozenset({1, 2}): "onehot"})


if __name__ == "__main__":
    unittest.main()
