"""The #77 blocks of a unit as cell sets, and the unit's graph, signatures and answer key."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import q9_env as env

q7f = env.mod("q7_feat")
qn = env.mod("q6_net")
qs = env.mod("q6_sig")
qt = env.mod("q6_truth")


@dataclass(frozen=True)
class Blk:
    """A block: its cells and the class of its anchor ('join' and 'split' mark made blocks)."""

    cells: frozenset[int]
    kind: str


def path_file(split: str, u: Any) -> Path:
    """The #77 path of a unit: regrown here, #77's own (TEST), else the #74 path."""
    name = f"{u.set}__{u.design}__{u.cell}.json"
    for root in (env.OUT8B, env.PREV8B):
        p = root / f"paths_{env.VARIANT}" / split / name
        if p.is_file():
            return p
    return Path(env.q7env.paths_dir(split)) / name


def blocks_of(rec: dict[str, Any]) -> list[Blk]:
    return [Blk(frozenset(b["anchor"]) | frozenset(b["order"]), b["anchor_kind"])
            for b in rec["blocks"]]


def units(split: str) -> list[Any]:
    return sorted(q7f.split_units(split), key=lambda u: u.net.stat().st_size)


def start_blocks(split: str, u: Any) -> list[Blk]:
    return blocks_of(json.loads(path_file(split, u).read_text(encoding="utf-8")))


def answer_key(u: Any, g: Any) -> list[tuple[int, str, frozenset[int]]]:
    """(part, kind, cells) of the non-glue constructs with cells."""
    return [(c.idx, c.kind, c.cells) for c in qt.constructs(u, g)
            if c.kind != "glue" and c.cells]
