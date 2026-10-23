"""L2 scale test: the time and peak-memory budgets of spec 3 (plan Task 15).

Enabled by ``LOKI_SCALE=1`` (the spec-3 benchmark graph: 100k nodes, 306k undirected edges,
a 20k-fan-out hub) or ``LOKI_SCALE=2`` (820k nodes, 1.6M edges, plus the golden LU64PEEng
``graph.json`` when ``$LOKI_BIG_GRAPH`` points at one). Every analysis runs in a fresh
interpreter, on a ``graph.json`` written from :func:`tests.analysis_fixtures.big_synthetic`,
so ``ru_maxrss`` is that analysis's own peak instead of the test process's.

``BUDGETS`` holds the spec-3 rows as ``(seconds, MB)``; a run fails above twice its budget,
the spec's own rule. The two structural rows compose the spec-3 table: colour refinement
(30 s, 1 GB) plus NPN classes (60 s, 0.5 GB), and the quotient run adds the coarsest equitable
partition (60 s, 1 GB). The graphlet rows are budgeted at ORCA's 820k measurements and are
only run when ORCA is installed (``loki tools fetch-orca``). The graphlet tests are the heavy
ones: do not run this file while Odin III sweeps run (the WSL VM memory limit, plan Task 15).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

from loki.analysis.graphio import Graph
from loki.analysis.graphlets import BACKENDS
from loki.analysis.graphlets.ext import find_orca
from tests.analysis_fixtures import big_synthetic
from tests.helpers import skip_without

ROOT = Path(__file__).resolve().parent.parent
SCALE = os.environ.get("LOKI_SCALE", "")
ANALYSIS = ("numpy", "scipy", "sklearn", "networkx")
ORCA_SKIP = "run: loki tools fetch-orca"

#: Spec 3 rows at 100k nodes / 306k undirected edges: (seconds, MB). Fails above twice these.
BUDGETS: dict[str, tuple[float, float]] = {
    "load": (30.0, 2048.0),               # graph.json load + featurize
    "louvain": (120.0, 2048.0),
    "spectral": (60.0, 2048.0),           # 8 embedding vectors
    "kmeans": (30.0, 1024.0),             # 12-column features, minibatch above 20k
    "affinity": (10.0, 1024.0),           # sample of 3000 points
    "classify_signals": (60.0, 2048.0),   # spec 3 row at 820k; the same row applies here
    "structural": (90.0, 1024.0),         # refinement 30 s/1 GB + NPN 60 s/0.5 GB
    "structural_quotient": (150.0, 1024.0),  # + coarsest equitable partition 60 s/1 GB
    "export_pyg": (60.0, 3072.0),
    "graphlets4_global": (10.0, 2048.0),  # measured at LU64PEEng 819k (spike)
    "graphlets5_global": (60.0, 3072.0),
    "graphlets4_none": (180.0, 3072.0),   # mcml measured at 56 s; budget 3 min
}

#: The 820k-node rows: spec 3's extrapolation and open questions 6, 7 and 10.
BUDGETS_820K: dict[str, tuple[float, float]] = {
    "load": (120.0, 8192.0),              # open question 6: 8 GB, 120 s
    "louvain": (900.0, 4096.0),           # open question 7: 15 minutes is the rule
    "spectral": (480.0, 4096.0),          # linear extrapolation of 60 s / 2 GB
    "kmeans": (60.0, 2048.0),
    "affinity": (10.0, 1024.0),           # the sample stays 3000 points
    "classify_signals": (60.0, 2048.0),   # spec 3 row at 820k nodes
    "structural": (300.0, 8192.0),        # refinement 240 s/8 GB + NPN 60 s/0.5 GB
    "structural_quotient": (780.0, 8192.0),  # + stable partition 480 s/8 GB
    "export_pyg": (500.0, 8192.0),        # linear extrapolation of 60 s / 3 GB
    "graphlets4_global": (10.0, 2048.0),
    "graphlets5_global": (60.0, 3072.0),
    "graphlets4_none": (1800.0, 3072.0),  # LU64PEEng measured at 12 min 54 s
}

#: Five fixed LUT tables per width; a real netlist holds few distinct tables, and NPN
#: classification cost grows with the distinct-table count, not the node count.
_TABLES: dict[int, tuple[int, ...]] = {
    2: (0x0, 0x8, 0x6, 0xE, 0x9),
    3: (0x00, 0x80, 0xE8, 0x96, 0xCA),
    4: (0x0000, 0x8000, 0xE880, 0x9669, 0xCACA),
}
_LABELS = (
    '{"construct_type": "", "construct_types": "", "n_construct_cells": -1, '
    '"module_path": "", "bus_name": "", "bit_index": -1, "role": "unknown", '
    '"hdl_file": "", "hdl_line": -1, "hdl_col": -1, "hdl_end_line": -1, '
    '"hdl_end_col": -1, "n_spans": 0}'
)

_CLI_CHILD = """
import json, resource, sys, time
from loki.analysis.run import main
t0 = time.monotonic()
rc = main(sys.argv[1:])
print(json.dumps({"rc": rc, "seconds": time.monotonic() - t0,
                  "rss_mb": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024}))
"""

_LOAD_CHILD = """
import json, resource, sys, time
from pathlib import Path
from loki.analysis.graphio import featurize, load_graph
t0 = time.monotonic()
g = load_graph(Path(sys.argv[1]))
matrix = featurize(g)
print(json.dumps({"rc": 0, "seconds": time.monotonic() - t0,
                  "rss_mb": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024,
                  "nodes": g.n_nodes, "edges": g.n_edges, "columns": matrix.x.shape[1]}))
"""

_SIGNALS_CHILD = """
import json, resource, sys, time
import numpy as np
from tests.test_scale_l2 import synthetic_graph
with np.load(sys.argv[1]) as data:
    n = int(data["n"])
    src, dst = data["src"], data["dst"]
g = synthetic_graph(n, src, dst)
from loki.analysis.graphlets.signals import classify_signals
t0 = time.monotonic()
info = classify_signals(g)
print(json.dumps({"rc": 0, "seconds": time.monotonic() - t0,
                  "rss_mb": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024,
                  "clock_domains": info.clock_domains}))
"""


def synthetic_graph(n: int, src: Any, dst: Any, design: str = "synthetic") -> Graph:
    """A :class:`Graph` over the ``big_synthetic`` arrays, as the analyses see the file.

    Every node is a LUT of width 2 to 4 with one of :data:`_TABLES`; fan-in and fan-out come
    from the arrays, every other numeric feature is constant. Net ``e`` is written ``n<e>``
    like in a ``graph.json``; the arrays are one directed edge per undirected pair.
    """
    import numpy as np

    sources = np.asarray(src, dtype=np.int32)
    sinks = np.asarray(dst, dtype=np.int32)
    zeros = np.zeros(n, dtype=np.int64)
    tables = [format(_TABLES[2 + (row % 3)][row % 5], "x") for row in range(n)]
    num: dict[str, Any] = {
        "fan_in": np.bincount(sinks, minlength=n).astype(np.int64),
        "fan_out": np.bincount(sources, minlength=n).astype(np.int64),
        "level": zeros.copy(),
        "lut_width": np.asarray([2 + (row % 3) for row in range(n)], dtype=np.int64),
        "is_seq": zeros.copy(),
        "is_const": zeros.copy(),
        "hard_ports": zeros.copy(),
        "lut_ones": np.asarray([int(text, 16).bit_count() for text in tables], dtype=np.int64),
    }
    return Graph(
        design=design,
        floor="f2",
        node_ids=tuple(f"n{row}" for row in range(n)),
        kind=tuple("lut" for _ in range(n)),
        num=num,
        table=tuple(int(text, 16) for text in tables),
        src=sources,
        dst=sinks,
        pin=tuple("I0" for _ in range(sources.size)),
        net=tuple(f"n{edge}" for edge in range(sources.size)),
        labels=None,
        sha256="0" * 64,
    )


def write_synthetic_graph(path: Path, n: int, src: Any, dst: Any) -> Path:
    """Write the ``big_synthetic`` arrays as a valid L0 ``graph.json``; return its path.

    Streamed node by node so the 820k-node scale-2 graph never exists as one Python object
    (the spec-3 memory note). Every node carries the valid all-empty labels of an unlabelled
    design, so the file also exercises the unlabelled path of the analyses.
    """
    import numpy as np

    sources = np.asarray(src, dtype=np.int64)
    sinks = np.asarray(dst, dtype=np.int64)
    fan_in = np.bincount(sinks, minlength=n)
    fan_out = np.bincount(sources, minlength=n)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write('{"schema": 1, "design": "synthetic", "floor": "f2", "nodes": [')
        for row in range(n):
            width = 2 + (row % 3)
            table = format(_TABLES[width][row % 5], "x")
            if row:
                handle.write(",")
            handle.write(
                f'\n{{"id": "n{row}", "kind": "lut", "features": {{"fan_in": '
                f'{int(fan_in[row])}, "fan_out": {int(fan_out[row])}, "level": 0, '
                f'"lut_width": {width}, "lut_table": "{table}", "is_seq": 0, '
                f'"is_const": 0, "hard_ports": 0}}, "labels": {_LABELS}}}'
            )
        handle.write('\n], "edges": [')
        for edge in range(sources.size):
            if edge:
                handle.write(",")
            handle.write(
                f'\n{{"src": "n{int(sources[edge])}", "dst": "n{int(sinks[edge])}", '
                f'"net": "n{edge}", "pin": "I0"}}'
            )
        handle.write("\n]}\n")
    return path


@unittest.skipUnless(SCALE in ("1", "2"), "set LOKI_SCALE=1 (or 2) for scale tests")
@skip_without(*ANALYSIS)
class ScaleTest(unittest.TestCase):
    """One test per spec-3 row; each analysis in its own interpreter, time and peak RSS."""

    tmp: tempfile.TemporaryDirectory[str]
    sources: list[tuple[str, Path, Path | None]]
    budget: dict[str, tuple[float, float]]

    @classmethod
    def setUpClass(cls) -> None:
        cls.tmp = tempfile.TemporaryDirectory(prefix=f"loki-l2-scale{SCALE}-")
        root = Path(cls.tmp.name)
        n, m = (100_000, 306_000) if SCALE == "1" else (820_000, 1_600_000)
        src, dst = big_synthetic(n, m)
        source_dir = root / "synthetic"
        graph = write_synthetic_graph(source_dir / "graph.json", n, src, dst)
        arrays = source_dir / "arrays.npz"
        import numpy as np

        np.savez(arrays, n=np.int64(n), src=src, dst=dst)
        cls.sources = [("synthetic", graph, arrays)]
        big = os.environ.get("LOKI_BIG_GRAPH", "")
        if SCALE == "2" and big:
            cls.sources.append(("golden", Path(big), None))
        cls.budget = BUDGETS if SCALE == "1" else BUDGETS_820K

    @classmethod
    def tearDownClass(cls) -> None:
        cls.tmp.cleanup()

    def out(self, label: str, name: str) -> Path:
        """A fresh output directory for one analysis of one source."""
        return Path(self.tmp.name) / "out" / label / name

    def check(self, name: str, result: dict[str, float], label: str) -> None:
        """The spec-3 rule: fail above twice the row's time or peak memory."""
        seconds_budget, memory_budget = self.budget[name]
        seconds = float(result["seconds"])
        memory = float(result["rss_mb"])
        print(
            f"{label}/{name}: {seconds:.1f} s, {memory:.0f} MB "
            f"(spec 3 budget {seconds_budget:g} s, {memory_budget:g} MB; fail above 2x)"
        )
        self.assertLess(seconds, 2.0 * seconds_budget, f"{label}/{name}: {seconds:.1f} s")
        self.assertLess(memory, 2.0 * memory_budget, f"{label}/{name}: {memory:.0f} MB")

    def measure(self, name: str, argv: list[str], label: str) -> dict[str, float]:
        """Run one ``loki analyze`` command in a fresh interpreter and check its budget."""
        proc = subprocess.run(
            [sys.executable, "-c", _CLI_CHILD, *argv], cwd=ROOT, capture_output=True,
            text=True, check=False,
        )
        lines = proc.stdout.strip().splitlines()
        if proc.returncode != 0 or not lines:
            self.fail(f"{label}/{name}: exit {proc.returncode}: {proc.stderr.strip()[-800:]}")
        result: dict[str, float] = json.loads(lines[-1])
        if result["rc"] != 0:
            self.fail(f"{label}/{name}: loki analyze exit {result['rc']:g}: "
                      f"{proc.stderr.strip()[-800:]}")
        self.check(name, result, label)
        return result

    def measure_load(self, label: str, graph: Path) -> None:
        proc = subprocess.run(
            [sys.executable, "-c", _LOAD_CHILD, str(graph)], cwd=ROOT, capture_output=True,
            text=True, check=False,
        )
        lines = proc.stdout.strip().splitlines()
        if proc.returncode != 0 or not lines:
            self.fail(f"{label}/load: exit {proc.returncode}: {proc.stderr.strip()[-800:]}")
        result: dict[str, float] = json.loads(lines[-1])
        self.check("load", result, label)

    def test_load(self) -> None:
        for label, graph, _arrays in self.sources:
            self.measure_load(label, graph)

    def test_louvain(self) -> None:
        for label, graph, _arrays in self.sources:
            self.measure("louvain", [
                "cluster", "--graph", str(graph), "--method", "louvain",
                "--out", str(self.out(label, "louvain")),
            ], label)

    def test_spectral(self) -> None:
        # k = 8: the spec-3 row measured the embedding with 8 vectors.
        for label, graph, _arrays in self.sources:
            self.measure("spectral", [
                "cluster", "--graph", str(graph), "--method", "spectral", "--k", "8",
                "--out", str(self.out(label, "spectral")),
            ], label)

    def test_kmeans(self) -> None:
        for label, graph, _arrays in self.sources:
            self.measure("kmeans", [
                "cluster", "--graph", str(graph), "--method", "kmeans",
                "--out", str(self.out(label, "kmeans")),
            ], label)

    def test_affinity(self) -> None:
        for label, graph, _arrays in self.sources:
            self.measure("affinity", [
                "cluster", "--graph", str(graph), "--method", "affinity",
                "--max-points", "3000", "--out", str(self.out(label, "affinity")),
            ], label)

    def test_classify_signals(self) -> None:
        # The synthetic graph has the arrays for a direct classifier run; the golden file is
        # loaded through the CLI kinds, whose timings include the load.
        for label, _graph, arrays in self.sources:
            if arrays is None:
                continue
            proc = subprocess.run(
                [sys.executable, "-c", _SIGNALS_CHILD, str(arrays)], cwd=ROOT,
                capture_output=True, text=True, check=False,
            )
            lines = proc.stdout.strip().splitlines()
            if proc.returncode != 0 or not lines:
                self.fail(f"{label}/classify_signals: exit {proc.returncode}: "
                          f"{proc.stderr.strip()[-800:]}")
            self.check("classify_signals", json.loads(lines[-1]), label)

    def test_structural(self) -> None:
        for label, graph, _arrays in self.sources:
            self.measure("structural", [
                "structural", "--graph", str(graph), "--rounds", "4",
                "--out", str(self.out(label, "structural")),
            ], label)

    def test_structural_quotient(self) -> None:
        for label, graph, _arrays in self.sources:
            self.measure("structural_quotient", [
                "structural", "--graph", str(graph), "--rounds", "4", "--quotient",
                "--out", str(self.out(label, "structural-quotient")),
            ], label)

    @skip_without("torch", "torch_geometric")
    def test_export_pyg(self) -> None:
        for label, graph, _arrays in self.sources:
            self.measure("export_pyg", [
                "export", "--graph", str(graph), "--format", "pyg",
                "--out", str(self.out(label, "export")),
            ], label)

    def test_graphlets_size4_global(self) -> None:
        if find_orca() is None:
            self.skipTest(ORCA_SKIP)
        for label, graph, _arrays in self.sources:
            self.measure("graphlets4_global", [
                "graphlets", "--graph", str(graph), "--backend", "ext", "--size", "4",
                "--removal", "global", "--out", str(self.out(label, "graphlets4")),
            ], label)

    def test_graphlets_size5_global(self) -> None:
        if find_orca() is None:
            self.skipTest(ORCA_SKIP)
        for label, graph, _arrays in self.sources:
            self.measure("graphlets5_global", [
                "graphlets", "--graph", str(graph), "--backend", "ext", "--size", "5",
                "--removal", "global", "--out", str(self.out(label, "graphlets5")),
            ], label)

    @unittest.skipUnless(SCALE == "2", "the full 4-node count is a LOKI_SCALE=2 run")
    def test_graphlets_size4_none(self) -> None:
        if find_orca() is None:
            self.skipTest(ORCA_SKIP)
        for label, graph, _arrays in self.sources:
            self.measure("graphlets4_none", [
                "graphlets", "--graph", str(graph), "--backend", "ext", "--size", "4",
                "--removal", "none", "--out", str(self.out(label, "graphlets4-none")),
            ], label)

    def test_own_backend_when_present(self) -> None:
        if "own" not in BACKENDS:
            self.skipTest("the optional own 4-node backend is not built (spec 8.5, later)")
        for label, graph, _arrays in self.sources:
            self.measure("graphlets4_global", [
                "graphlets", "--graph", str(graph), "--backend", "own", "--size", "4",
                "--removal", "global", "--out", str(self.out(label, "graphlets4-own")),
            ], label)


if __name__ == "__main__":
    unittest.main()
