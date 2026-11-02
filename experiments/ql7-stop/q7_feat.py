"""Per-prefix features and answer-key hits of every grown block: ``python -B q7_feat.py [JOBS]``.

Reads the paths (q7_paths.py for TRAIN and VALIDATION, #73's blocks_nostop for TEST) and writes
$QL7_OUT/feat_<split>.pkl (a list of UnitData). Nothing here uses a fitted number.
"""

from __future__ import annotations

import json
import pickle
import sys
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from typing import Any

import numpy as np
import q7_env as env

qn = env.mod("q6_net")
qt = env.mod("q6_truth")
qm = env.mod("q6_model")

NO_EV_CLIP = -50.0
N_KINDS = len(env.KINDS)
GLUE = env.KINDS.index("glue")


@dataclass
class BlockPath:
    bid: int
    anchor_kind: str
    size: np.ndarray  # (K,) cells in each prefix
    post: np.ndarray  # (K, 6) #73 posterior over the six kinds
    ev: np.ndarray  # (K,) #73 log odds known construct vs glue (NO_EVIDENCE when no edges)
    phi: np.ndarray  # (K,) conductance
    fan_in: np.ndarray
    fan_out: np.ndarray
    ff: np.ndarray  # flip-flop share
    inter: np.ndarray  # (C, K) cells of the prefix inside each construct
    ntrue: np.ndarray  # (C,) true block sizes
    end: str  # path end: "frontier" or "cap"

    @property
    def n(self) -> int:
        return len(self.size)

    @property
    def jaccard(self) -> np.ndarray:
        """(C, K) Jaccard of every prefix with every construct."""
        nt = self.ntrue[:, None]
        return np.asarray(self.inter / (self.size[None, :] + nt - self.inter))

    @property
    def coverage(self) -> np.ndarray:
        return np.asarray(self.inter / self.ntrue[:, None])

    @property
    def right(self) -> np.ndarray:
        """(C, K) the #72 rule: coverage >= 0.8 and Jaccard >= 0.5."""
        return np.asarray((self.coverage >= 0.8) & (self.jaccard >= 0.5))

    def has_signal(self) -> np.ndarray:
        return self.ev > qm.NO_EVIDENCE / 2


@dataclass
class UnitData:
    set: str
    design: str
    cell: str
    n_cells: int
    cons: list[tuple[int, str, int]]  # (part index, kind, true size), non-glue with cells
    blocks: list[BlockPath]

    @property
    def key(self) -> tuple[str, str, str]:
        return (self.set, self.design, self.cell)


class Geometry:
    """Incremental conductance, volume and frontier fan-in / fan-out of a growing block."""

    def __init__(self, g: Any) -> None:
        self.g = g
        self.nets_of: list[list[str]] = []
        self.members: dict[str, set[int]] = {}
        for i in range(g.b.n):
            nets = [n for n in dict.fromkeys([*g.b.ins[i], *g.b.outs[i]]) if not g.is_cut(n)]
            self.nets_of.append(nets)
            for n in nets:
                self.members.setdefault(n, set()).add(i)
        for n in self.members:  # the producer counts as a pin of its net
            p = g.b.producer.get(n)
            if p is not None:
                self.members[n].add(p)
        self.total = {n: len(m) for n, m in self.members.items()}
        self.inside: dict[str, int] = {}
        self.cut = 0
        self.vol = 0
        self.block: set[int] = set()
        self.pin: dict[int, int] = {}
        self.pout: dict[int, int] = {}
        self.n_ff = 0

    def add(self, c: int) -> None:
        g = self.g
        self.block.add(c)
        self.n_ff += 1 if g.b.latch[c] else 0
        for n in self.nets_of[c]:
            k = self.inside.get(n, 0)
            t = self.total[n]
            before = 0 < k < t
            k += 1
            self.inside[n] = k
            self.cut += (0 < k < t) - before
        self.vol += len(self.nets_of[c])
        self.pin.pop(c, None)
        self.pout.pop(c, None)
        for n in g.b.ins[c]:
            p = g.b.producer.get(n)
            if p is not None and p not in self.block and not g.is_cut(n):
                self.pin[p] = self.pin.get(p, 0) + 1
        for n in g.b.outs[c]:
            if g.is_cut(n):
                continue
            for r in g.readers.get(n, ()):
                if r not in self.block:
                    self.pout[r] = self.pout.get(r, 0) + 1

    def phi(self) -> float:
        return self.cut / self.vol if self.vol else 0.0


def block_path(g: Any, b: dict[str, Any], truths: list[frozenset[int]], end: str) -> BlockPath:
    geo = Geometry(g)
    cells = list(b["anchor"])
    inter = np.zeros((len(truths), len(b["order"]) + 1), dtype=np.int32)
    phi, fin, fout, ff = [], [], [], []
    run = np.zeros(len(truths), dtype=np.int32)
    for c in cells:
        geo.add(c)
    for j, t in enumerate(truths):
        run[j] = sum(1 for c in cells if c in t)

    def snap(k: int) -> None:
        inter[:, k] = run
        phi.append(geo.phi())
        fin.append(len(geo.pin))
        fout.append(len(geo.pout))
        ff.append(geo.n_ff / len(geo.block))

    snap(0)
    for k, c in enumerate(b["order"], start=1):
        geo.add(c)
        for j, t in enumerate(truths):
            run[j] += c in t
        snap(k)
    traj = np.array(b["traj"], dtype=float)
    size = traj[:, 0].astype(int)
    if len(size) != len(phi) or int(size[0]) != len(b["anchor"]):
        raise ValueError("trajectory does not match the path")
    return BlockPath(b["bid"], b["anchor_kind"], size, traj[:, 2:2 + N_KINDS],
                     np.array(b["evs"], dtype=float), np.array(phi), np.array(fin, dtype=float),
                     np.array(fout, dtype=float), np.array(ff), inter,
                     np.array([len(t) for t in truths], dtype=float), end)


def unit_data(u: Any, rec: dict[str, Any]) -> UnitData:
    g = qn.Graph.read(u.net)
    cons = [c for c in qt.constructs(u, g) if c.kind != "glue" and c.cells]
    truths = [c.cells for c in cons]
    blocks = []
    for b in rec["blocks"]:
        end = "cap" if len(b["anchor"]) + len(b["order"]) >= env.CAP else "frontier"
        blocks.append(block_path(g, b, truths, end))
    return UnitData(u.set, u.design, u.cell, g.b.n,
                    [(c.idx, c.kind, len(c.cells)) for c in cons], blocks)


def split_units(split: str) -> list[Any]:
    if split == "TEST":
        us = list(qt.units("TEST"))
    else:
        us = [u for u in qt.units("TUNE") if env.stop_split(u.design) == split]
    pdir = env.paths_dir(split)
    return [u for u in us if qt.has_labels(u) and
            (pdir / f"{u.set}__{u.design}__{u.cell}.json").is_file()]


def one(args: tuple[str, str, str, str, str]) -> UnitData:
    kind, design, cell, tsplit, split = args
    u = next(x for x in qt.units(tsplit, (cell,)) if x.set == kind and x.design == design)
    p = env.paths_dir(split) / f"{kind}__{design}__{cell}.json"
    return unit_data(u, json.loads(p.read_text(encoding="utf-8")))


def collect(split: str, n_jobs: int) -> list[UnitData]:
    us = split_units(split)
    us.sort(key=lambda u: u.net.stat().st_size)
    keys = [(u.set, u.design, u.cell, u.split, split) for u in us]
    with ProcessPoolExecutor(n_jobs) as pool:
        return list(pool.map(one, keys, chunksize=4))


def load(split: str) -> list[UnitData]:
    with (env.OUT7 / f"feat_{split}.pkl").open("rb") as fh:
        data: list[UnitData] = pickle.load(fh)
    return data


def main(argv: list[str]) -> int:
    n_jobs = min(int(argv[0]) if argv else 4, 4)
    splits = argv[1:] or ["TRAIN", "VALIDATION"]
    env.OUT7.mkdir(parents=True, exist_ok=True)
    for split in splits:
        data = collect(split, n_jobs)
        with (env.OUT7 / f"feat_{split}.pkl").open("wb") as fh:
            pickle.dump(data, fh)
        print(split, len(data), "units", sum(len(d.blocks) for d in data), "blocks",
              sum(len(d.cons) for d in data), "constructs")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
