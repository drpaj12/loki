"""Loki's joined blocks of a gate-level netlist (the #78 headline: anchors bank+loop+const, grown
to the end, one JCOND join at 0.2) and the kind guess of each block (the #75 M2 posterior).

The netlist is written as BLIF (``to_blif``; a gate is a ``.names`` cell, a DFF a ``.latch``, a
DFFSR a ``.names`` for its set/reset next-state plus a ``.latch``; an ``assign`` is a buffer or a
constant cell; a constant pin is the net of a constant cell). A block is a set of BLIF cells; it is
mapped back to the cells of the netlist (``Block.cells``); assign and constant cells are glue of
the top module and belong to no block. Cells no block holds are grouped by connected component
(chunks of at most 300 cells) into ``residual`` blocks, so every netlist cell is in exactly one
block.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import q10_env as env
from q10_nl import OUT_PIN, Netlist

q9rules: Any = env.mod("q9_rules")
q9net: Any = env.mod("q9_net")
q9units: Any = env.mod("q9_units")
q9evid: Any = env.mod("q9_evid")
qn: Any = env.mod("q6_net")
qs: Any = env.mod("q6_sig")
q6m: Any = env.mod("q6_model")
qa: Any = env.mod("q8b_anchors")
q8bg: Any = env.mod("q8b_grow")

GND, VCC = "gnd", "vcc"
TABLES = {"NOT": "0 1", "BUF": "1 1", "NAND": "0- 1\n-0 1", "NOR": "00 1"}


@dataclass
class Blif:
    text: str
    owner: list[int]  # BLIF cell index -> netlist cell index, -1 for glue (assign, constant)
    halves: dict[int, list[int]]  # netlist cell index -> its BLIF cells


def _net(nl: Netlist, key: str) -> str:
    return VCC if key == "#1" else GND if key in ("#0", "#x") else nl.san[key]


def to_blif(nl: Netlist) -> Blif:
    """BLIF of the netlist; cells appear in the order constants, assigns, then netlist cells."""
    lines: list[str] = []
    owner: list[int] = []
    halves: dict[int, list[int]] = defaultdict(list)

    def add(i: int, text: str) -> None:
        owner.append(i)
        if i >= 0:
            halves[i].append(len(owner) - 1)
        lines.append(text)

    used = {b for c in nl.cells for b in c.pins.values()} | {r for _, r in nl.assigns}
    if "#0" in used or "#x" in used:
        add(-1, f".names {GND}")
    if "#1" in used:
        add(-1, f".names {VCC}\n1")
    for lhs, rhs in nl.assigns:
        add(-1, f".names {_net(nl, rhs)} {nl.san[lhs]}\n1 1")
    for c in nl.cells:
        p = {k: _net(nl, v) for k, v in c.pins.items()}
        if c.typ == "DFF":
            add(c.idx, f".latch {p['D']} {p['Q']} re {p['C']} 3")
        elif c.typ == "DFFSR":
            dn = f"{p['Q']}__dn{c.idx}"
            add(c.idx, f".names {p['D']} {p['S']} {p['R']} {dn}\n1-0 1\n-1- 1")
            add(c.idx, f".latch {dn} {p['Q']} re {p['C']} 3")
        else:
            ins = " ".join(p[k] for k in ("A", "B") if k in p)
            add(c.idx, f".names {ins} {p[OUT_PIN[c.typ]]}\n{TABLES[c.typ]}")
    ins_ = " ".join(nl.san[b] for b in nl.port_bits("input"))
    outs = " ".join(nl.san[b] for b in nl.port_bits("output"))
    text = f".model top\n.inputs {ins_}\n.outputs {outs}\n" + "\n".join(lines) + "\n.end\n"
    return Blif(text, owner, dict(halves))


@dataclass
class Block:
    bid: int
    kind: str  # anchor class, 'join' for a joined block, 'residual'
    cells: list[int]  # netlist cell indices, sorted
    guess: str = ""  # M2 kind guess, '' = no claim
    post: list[float] = field(default_factory=list)


def _residual(nl: Netlist, left: set[int]) -> list[list[int]]:
    """Components of the uncovered cells (undirected over any net), chunks of <= 300 cells."""
    drv = {c.out: c.idx for c in nl.cells}
    rd: dict[str, list[int]] = defaultdict(list)
    for c in nl.cells:
        for n in c.ins:
            rd[n].append(c.idx)
    seen: set[int] = set()
    out: list[list[int]] = []
    for s in sorted(left):
        if s in seen:
            continue
        comp, todo = [], [s]
        seen.add(s)
        while todo:
            x = todo.pop()
            comp.append(x)
            nb = [drv[n] for n in nl.cells[x].ins if n in drv] + rd.get(nl.cells[x].out, [])
            for y in sorted(nb):
                if y in left and y not in seen:
                    seen.add(y)
                    todo.append(y)
        comp.sort()
        out += [comp[i:i + env.MAX_BLOCK_CELLS] for i in range(0, len(comp), env.MAX_BLOCK_CELLS)]
    return out


def to_blocks(nl: Netlist, bl: Blif, sets: list[Any], posts: list[Any]) -> list[Block]:
    """Map BLIF-cell blocks to netlist cells, drop glue, add residual blocks, number them."""
    blocks: list[Block] = []
    taken: set[int] = set()
    for b, post in zip(sets, posts, strict=True):
        cells = sorted({bl.owner[i] for i in b.cells if bl.owner[i] >= 0} - taken)
        # a DFFSR belongs to the block of its latch half
        cells = [c for c in cells if bl.halves[c][-1] in b.cells]
        if not cells:
            continue
        taken.update(cells)
        blocks.append(Block(len(blocks), b.kind, cells, "", [float(x) for x in post]))
    left = set(range(len(nl.cells))) - taken
    for comp in _residual(nl, left):
        blocks.append(Block(len(blocks), "residual", comp))
    return blocks


def kind_guess(post: list[float], n_cells: int) -> str:
    """The claim of the M2 posterior: its argmax kind unless glue or the block is under 4 cells."""
    if not post or n_cells < env.MIN_CLAIM:
        return ""
    k = max(range(len(post)), key=lambda i: post[i])
    return "" if k == q9rules.env.GLUE else str(env.q6env.KINDS[k])


def build(nl: Netlist, workdir: Path, want_kind: bool = True) -> list[Block]:
    """Loki's joined blocks of the netlist (runs the Odin III graphlets pass: needs libodin3)."""
    workdir.mkdir(parents=True, exist_ok=True)
    bl = to_blif(nl)
    path = workdir / "design.blif"
    path.write_text(bl.text, encoding="utf-8", newline="\n")
    g = qn.Graph.read(path)
    old = qn.anchors(g)
    anc = old + qa.extra_anchors(g, old, ("bank", "loop", "const"))
    sc = qs.SigCounter(path, g.b)
    try:
        grown = q8bg.Frozen(g, sc, q6m.load(env.q9env.OUT6 / "model.json"), env.CELL).grow(anc)
        start = [q9units.Blk(frozenset(b.anchor) | frozenset(b.order), b.kind) for b in grown]
        cfg = q9rules.Config("HEAD", "JOIN", "cond", "E73", env.JOIN_T)
        joined, _nj, _ns = q9rules.apply(cfg, start, q9net.Links(g), None)
        posts: list[Any] = [[] for _ in joined]
        if want_kind:
            ev = q9evid.Evid(g, sc, env.CELL, q9evid.load_m2())
            posts = [ev.post("EM2", b.cells) for b in joined]
    finally:
        sc.close()
    blocks = to_blocks(nl, bl, joined, posts)
    for b in blocks:
        if b.kind != "residual":
            b.guess = kind_guess(b.post, len(b.cells))
    return blocks
