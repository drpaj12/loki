"""L2 Task 9 step 5: the classifier on real F2 graphs of three micros (L2 spec 8.1)."""

from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from loki.analysis.graphio import Graph, load_graph
from loki.analysis.graphlets.signals import (
    CLASS_NAMES,
    SignalConfig,
    SignalInfo,
    classify_signals,
)
from loki.build import build_floor
from tests.helpers import can_run_f2, f2_arch, have, micro, odin3_root

DESIGNS = ("bm_DL_Dff_w_synch_reset", "bm_DL_4_bit_shift_register", "bm_if_reset")
MIN_ONE = SignalConfig(min_fanout=1)


def _port_nets(fdir: Path) -> dict[str, int]:
    """Input port name -> net number, from the answer key (a test, never an analysis)."""
    key = json.loads((fdir / "key.json").read_text(encoding="utf-8"))
    return {
        str(port["orig"]): int(str(port["net"])[1:])
        for port in key["ports"] if port["dir"] == "in"
    }


def _net_class(g: Graph, info: SignalInfo, net: int) -> str:
    """The class of every edge of ``net``; fails when the edges disagree."""
    classes = {CLASS_NAMES[int(info.edge_class[e])] for e in range(g.n_edges)
               if int(g.net[e][1:]) == net}
    assert len(classes) == 1, f"net n{net} carries {sorted(classes)}"
    return classes.pop()


@unittest.skipUnless(
    have("numpy") and can_run_f2(), "needs numpy, Odin III, ABC and an F2 architecture"
)
class SignalsMicrosTest(unittest.TestCase):
    graphs: dict[str, Graph]
    ports: dict[str, dict[str, int]]

    @classmethod
    def setUpClass(cls) -> None:
        root = odin3_root()
        arch = f2_arch()
        assert root is not None and arch is not None
        tmp = tempfile.mkdtemp(prefix="loki-t9-micros-")
        cls.addClassCleanup(shutil.rmtree, tmp, True)
        cls.graphs = {}
        cls.ports = {}
        for name in DESIGNS:
            out = Path(tmp)
            result = build_floor(name, [micro(name)], None, "f2", arch, out, root)
            if result.status == "skipped":
                raise unittest.SkipTest(f"{name}: {result.reason}")
            if result.status != "ok":
                raise AssertionError(f"{name}: {result.status} {result.reason}")
            fdir = out / name / "f2"
            cls.graphs[name] = load_graph(fdir / "graph.json")
            cls.ports[name] = _port_nets(fdir)

    def test_dff_w_synch_reset(self) -> None:
        name = "bm_DL_Dff_w_synch_reset"
        g, ports = self.graphs[name], self.ports[name]
        info = classify_signals(g)
        self.assertEqual((info.classified["clock"], info.clock_domains), (1, 1))
        ffs = [row for row, kind in enumerate(g.kind) if kind == "ff"]
        self.assertEqual(len(ffs), 1)
        self.assertEqual(int(info.roles[ffs[0], 0]), 1)
        self.assertEqual(_net_class(g, info, ports["Clock"]), "clock")
        small = classify_signals(g, MIN_ONE)
        self.assertEqual(_net_class(g, small, ports["Resetn"]), "reset")
        self.assertEqual(int(small.roles[ffs[0], 1]), 1)

    def test_shift_register(self) -> None:
        name = "bm_DL_4_bit_shift_register"
        g, ports = self.graphs[name], self.ports[name]
        info = classify_signals(g)
        self.assertEqual((info.classified["clock"], info.clock_domains), (1, 1))
        ffs = [row for row, kind in enumerate(g.kind) if kind == "ff"]
        self.assertEqual(len(ffs), 4)
        self.assertEqual([int(info.roles[row, 0]) for row in ffs], [1, 1, 1, 1])
        small = classify_signals(g, MIN_ONE)
        self.assertEqual(_net_class(g, small, ports["Clock"]), "clock")
        select = [e for e in range(g.n_edges) if int(g.net[e][1:]) == ports["L"]]
        self.assertEqual(len(select), 4)  # L reaches the mux of every stage
        self.assertEqual(_net_class(g, small, ports["L"]), "signal")

    def test_if_reset(self) -> None:
        # Read the Verilog: the registered output of module `a` is unused, so after ABC the
        # design keeps three flip-flops (out0[0], out0[1], out1) behind three AND-D-LUTs.
        name = "bm_if_reset"
        g, ports = self.graphs[name], self.ports[name]
        info = classify_signals(g)
        self.assertEqual((info.classified["clock"], info.clock_domains), (1, 1))
        ffs = [row for row, kind in enumerate(g.kind) if kind == "ff"]
        self.assertEqual(len(ffs), 3)
        self.assertEqual([int(info.roles[row, 0]) for row in ffs], [1, 1, 1])
        self.assertEqual(_net_class(g, info, ports["clock"]), "clock")
        small = classify_signals(g, MIN_ONE)
        self.assertEqual(_net_class(g, small, ports["reset_n"]), "reset")
