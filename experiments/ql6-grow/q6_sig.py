"""Directed graphlet signature of a block of cells, from the Odin III ``graphlets`` pass.

No second graphlet counter: every signature is a pass run (``cells=`` file, directed, Odin III
global rule), about 1 ms for the block sizes used here. A block is a set of cell indices; the
primary-input ports that feed it are added to the induced subgraph (as in ql4-misses/tsig.py).
Results are cached per block, so the signature the grower uses is the pass's own full count.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import numpy as np

from q6_env import OUT, sigs

N_ORBITS = 129
MAX_WORK = 300_000_000


class SigCounter:
    def __init__(self, netlist: Path, blif: Any) -> None:
        import odin3

        self.b = blif
        self._design = odin3.Design.read_blif(netlist, techlibs=[sigs.VTR_LIB])
        mod = self._design.top()
        self.node: list[int | None] = []
        for outs in blif.outs:
            net = mod.net(outs[0]) if outs else None
            pin = net.driver() if net is not None else None
            self.node.append(pin.node().id if pin is not None else None)
        self.pi: dict[str, int] = {}
        for ins in blif.ins:
            for n in ins:
                if n in blif.inputs and n not in self.pi:
                    net = mod.net(n)
                    pin = net.driver() if net is not None else None
                    if pin is not None:
                        self.pi[n] = pin.node().id
        self.cells_file = OUT / "tmp" / f"cells_{os.getpid()}.txt"
        self.cells_file.parent.mkdir(parents=True, exist_ok=True)
        self.cache: dict[frozenset[int], np.ndarray] = {}
        self.calls = 0

    def close(self) -> None:
        self._design.close()

    def node_ids(self, block: frozenset[int]) -> list[int]:
        ids = {self.node[i] for i in block}
        for i in block:
            ids.update(self.pi[n] for n in self.b.ins[i] if n in self.pi)
        return sorted(x for x in ids if x is not None)

    def orbits(self, block: frozenset[int]) -> np.ndarray:
        """Directed orbit totals (129,) of the induced subgraph of ``block`` (cached)."""
        hit = self.cache.get(block)
        if hit is not None:
            return hit
        ids = self.node_ids(block)
        out = np.zeros(N_ORBITS)
        if ids:
            self.cells_file.write_text("@p\n" + "\n".join(map(str, ids)) + "\n",
                                       encoding="utf-8")
            res = self._design.graphlets(exclude_global=True, directed=True,
                                         cells=self.cells_file, max_work=MAX_WORK)
            self.calls += 1
            out = np.array(res["groups"][0]["orbit_totals"], dtype=float)
        self.cache[block] = out
        return out


def feature(totals: np.ndarray) -> np.ndarray:
    """Hellinger-scaled orbit frequencies (sqrt of the share of each orbit)."""
    s = totals.sum()
    return np.sqrt(totals / s) if s > 0 else np.zeros_like(totals)
