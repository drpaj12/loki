"""The join and split steps and their orders (EXPERIMENT.md "Join rules", "Split rule", "Order")."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import q9_env as env
import q9_net as nt
from q9_units import Blk

ORDERS = ("JOIN", "SPLIT", "JS", "SJ", "FIX")
JOIN_GRIDS: dict[str, tuple[float, ...]] = {
    "bf": (-8, -4, -2, -1, 0, 1, 2, 4), "cond": (0.1, 0.2, 0.3, 0.5, 0.7),
    "ctrl": (0.25, 0.5, 0.75, 1.0)}
SPLIT_GRID = (0.0, 2.0, 4.0, 8.0, 16.0)


class EvidLike(Protocol):
    def ev(self, src: str, cells: frozenset[int]) -> float: ...


@dataclass(frozen=True)
class Config:
    """One setting: join rule (bf | cond | ctrl | '') with evidence source and threshold, split
    threshold (None = no split), and the order."""

    name: str
    order: str
    jrule: str = ""
    jsrc: str = "E73"
    jt: float = 0.0
    ssrc: str = "E73"
    st: float | None = None

    @property
    def sources(self) -> tuple[str, ...]:
        s = set()
        if self.jrule == "bf":
            s.add(self.jsrc)
        if self.st is not None:
            s.add(self.ssrc)
        return tuple(sorted(s))


class Stepper:
    """Applies a config to the blocks of one unit (counts joins and splits)."""

    def __init__(self, cfg: Config, links: nt.Links, evid: EvidLike) -> None:
        self.cfg, self.links, self.evid = cfg, links, evid
        self.joins = 0
        self.splits = 0

    def score(self, a: frozenset[int], b: frozenset[int], n_links: int) -> float:
        c = self.cfg
        if c.jrule == "bf":
            return (self.evid.ev(c.jsrc, a | b) - self.evid.ev(c.jsrc, a)
                    - self.evid.ev(c.jsrc, b))
        if c.jrule == "cond":
            return n_links / max(min(self.links.block_deg(a), self.links.block_deg(b)), 1)
        ga, gb = self.links.block_ctrl(a), self.links.block_ctrl(b)
        return len(ga & gb) / len(ga | gb) if ga | gb else 0.0

    def best_pair(self, blocks: list[Blk]) -> tuple[float, int, int] | None:
        owner = {c: i for i, b in enumerate(blocks) for c in b.cells}
        best: tuple[float, int, int] | None = None
        for (i, j), n_links in sorted(self.links.between(owner).items()):
            a, b = blocks[i].cells, blocks[j].cells
            if len(a) + len(b) > env.CAP:
                continue
            s = self.score(a, b, n_links)
            if best is None or s > best[0] + 1e-12:
                best = (s, i, j)
        return best

    def join(self, blocks: list[Blk]) -> list[Blk]:
        if not self.cfg.jrule:
            return blocks
        for _ in range(env.MAX_MERGES):
            best = self.best_pair(blocks)
            if best is None or best[0] < self.cfg.jt:
                break
            _, i, j = best
            merged = Blk(blocks[i].cells | blocks[j].cells, "join")
            blocks = [b for k, b in enumerate(blocks) if k not in (i, j)] + [merged]
            self.joins += 1
        return blocks

    def split_one(self, b: Blk) -> list[Blk]:
        c = self.cfg
        if c.st is None or b.kind == "const" or len(b.cells) < env.MIN_SPLIT:
            return [b]
        cut = nt.fiedler_cut(self.links, b.cells, env.MIN_SIDE)
        if cut is None:
            return [b]
        x, y = cut
        s = (self.evid.ev(c.ssrc, x) + self.evid.ev(c.ssrc, y) - self.evid.ev(c.ssrc, b.cells))
        if s < c.st:
            return [b]
        self.splits += 1
        return [Blk(x, "split"), Blk(y, "split")]

    def split_round(self, blocks: list[Blk]) -> list[Blk]:
        out: list[Blk] = []
        for b in blocks:
            out.extend(self.split_one(b))
        return out

    def run(self, blocks: list[Blk]) -> list[Blk]:
        o = self.cfg.order
        if o == "JOIN":
            return self.join(blocks)
        if o == "SPLIT":
            return self.split_round(blocks)
        if o == "JS":
            return self.join(self.split_round(blocks))
        if o == "SJ":
            return self.split_round(self.join(blocks))
        for _ in range(env.FIX_ROUNDS):
            before = {b.cells for b in blocks}
            blocks = self.split_round(self.join(blocks))
            if {b.cells for b in blocks} == before:
                break
        return blocks


def apply(cfg: Config, blocks: list[Blk], links: nt.Links, evid: EvidLike
          ) -> tuple[list[Blk], int, int]:
    """(blocks after the step, joins made, splits made)."""
    sp = Stepper(cfg, links, evid)
    out = sp.run(list(blocks))
    return out, sp.joins, sp.splits
