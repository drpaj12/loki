"""RQ-L1 support: parse plain BLIF and map the LUT cells of a re-mapped netlist back to the
gate cells of the f3 netlist they cover.

Odin III's ``abc --lut 6`` keeps the port and flip-flop net names but renames internal nets and
drops ``.cname`` (its provenance for a BLIF-read netlist is ``DERIVED`` with no source cells), so
the cover is recovered functionally: every net gets a bit-parallel simulation signature over
random values of the primary inputs and flip-flop outputs; a LUT output is matched to the f3 net
with the same signature, and its cover is the cone of that net back to the nets whose signatures
equal the LUT's input signatures.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from pathlib import Path

VECTORS = 512
SEED = 20261024


@dataclass
class Names:
    ins: tuple[str, ...]
    out: str
    rows: tuple[tuple[str, str], ...]
    cname: str = ""


@dataclass
class Blif:
    inputs: list[str] = field(default_factory=list)
    outputs: list[str] = field(default_factory=list)
    names: list[Names] = field(default_factory=list)
    latches: list[tuple[str, str, str]] = field(default_factory=list)  # (d, q, cname)


def parse_blif(text: str) -> Blif:
    """The ``.names``, ``.latch``, ``.inputs`` and ``.outputs`` of a one-model plain BLIF."""
    lines = text.replace("\\\n", " ").splitlines()
    blif = Blif()
    last = ""
    i = 0
    while i < len(lines):
        tok = lines[i].split()
        i += 1
        if not tok:
            continue
        head = tok[0]
        if head == ".inputs":
            blif.inputs += tok[1:]
        elif head == ".outputs":
            blif.outputs += tok[1:]
        elif head == ".latch":
            blif.latches.append((tok[1], tok[2], ""))
            last = "latch"
        elif head == ".names":
            rows: list[tuple[str, str]] = []
            while i < len(lines) and lines[i].strip() and not lines[i].startswith("."):
                parts = lines[i].split()
                rows.append((parts[0], parts[1]) if len(parts) == 2 else ("", parts[0]))
                i += 1
            blif.names.append(Names(tuple(tok[1:-1]), tok[-1], tuple(rows)))
            last = "names"
        elif head == ".cname" and last == "names":
            blif.names[-1].cname = tok[1]
        elif head == ".cname" and last == "latch":
            d, q, _ = blif.latches[-1]
            blif.latches[-1] = (d, q, tok[1])
    return blif


def _eval(cell: Names, sig: dict[str, int], mask: int) -> int:
    on = 0
    for pattern, _val in cell.rows:
        term = mask
        for net, ch in zip(cell.ins, pattern, strict=True):
            if ch == "1":
                term &= sig[net]
            elif ch == "0":
                term &= ~sig[net] & mask
        on |= term
    off_set = bool(cell.rows) and all(v == "0" for _, v in cell.rows)
    return (~on & mask) if off_set else on


def signatures(blif: Blif, order: list[Names], seeds: dict[str, int], mask: int) -> dict[str, int]:
    """Signature of every net: free nets from ``seeds``, then the ``.names`` in ``order``."""
    sig = dict(seeds)
    for cell in order:
        sig[cell.out] = _eval(cell, sig, mask)
    return sig


def topo(blif: Blif) -> list[Names]:
    """``.names`` in dependency order (flip-flop outputs and inputs are sources)."""
    by_out = {c.out: c for c in blif.names}
    done: set[str] = set()
    order: list[Names] = []

    def visit(cell: Names) -> None:
        stack = [(cell, iter(cell.ins))]
        onpath = {cell.out}
        while stack:
            cur, it = stack[-1]
            nxt = next(it, None)
            if nxt is None:
                stack.pop()
                onpath.discard(cur.out)
                if cur.out not in done:
                    done.add(cur.out)
                    order.append(cur)
                continue
            dep = by_out.get(nxt)
            if dep is not None and dep.out not in done and dep.out not in onpath:
                onpath.add(dep.out)
                stack.append((dep, iter(dep.ins)))

    for c in blif.names:
        visit(c)
    return order


def free_seeds(blif: Blif, flops: dict[str, int], pis: dict[str, int]) -> dict[str, int]:
    """Values of the free nets: primary inputs by name, flip-flop outputs by flip-flop cname."""
    seeds = {n: pis[n] for n in blif.inputs}
    for _d, q, cname in blif.latches:
        seeds[q] = flops[cname]
    return seeds


def random_values(a: Blif, b: Blif) -> tuple[dict[str, int], dict[str, int]]:
    rng = random.Random(SEED)
    pis = {n: rng.getrandbits(VECTORS) for n in sorted({*a.inputs, *b.inputs})}
    flops = {c: rng.getrandbits(VECTORS)
             for c in sorted({c for _, _, c in a.latches} | {c for _, _, c in b.latches})}
    return pis, flops


def cover_map(gate: Blif, lut: Blif) -> tuple[dict[str, frozenset[str]], dict[str, str], int]:
    """(LUT cname -> f3 gate cnames, LUT output net -> f3 net, unmatched LUT count)."""
    mask = (1 << VECTORS) - 1
    pis, flops = random_values(gate, lut)
    gsig = signatures(gate, topo(gate), free_seeds(gate, flops, pis), mask)
    lsig = signatures(lut, topo(lut), free_seeds(lut, flops, pis), mask)
    by_sig: dict[int, list[str]] = {}
    drivers = {c.out: c for c in gate.names}
    position = {c.out: k for k, c in enumerate(topo(gate))}
    for net, s in gsig.items():
        if net in drivers:
            by_sig.setdefault(s, []).append(net)
    for nets in by_sig.values():
        nets.sort(key=lambda n: (position[n], n))
    cover: dict[str, frozenset[str]] = {}
    netmap: dict[str, str] = {}
    unmatched = 0
    for cell in lut.names:
        cands = by_sig.get(lsig[cell.out], [])
        if not cands:
            cover[cell.cname] = frozenset()
            unmatched += 1
            continue
        root = cands[-1]  # the last of equal-signature nets: its cone holds the earlier copies
        netmap[cell.out] = root
        bound = {lsig[i] for i in cell.ins}
        cover[cell.cname] = _cone(root, drivers, gsig, bound)
    _latch_cover(gate, lut, gsig, cover, drivers)
    if unmatched:
        _fill_unmatched(gate, lut, cover, drivers)
    return cover, netmap, unmatched


def _supports(blif: Blif, index: dict[str, int]) -> dict[str, int]:
    """Bit set of the primary inputs and flip-flop cnames each net depends on."""
    sup: dict[str, int] = {}
    for n in blif.inputs:
        sup[n] = 1 << index[n]
    for _d, q, c in blif.latches:
        sup[q] = 1 << index["ff:" + c]
    for cell in topo(blif):
        acc = 0
        for i in cell.ins:
            acc |= sup.get(i, 0)
        sup[cell.out] = acc
    return sup


def _fill_unmatched(
    gate: Blif, lut: Blif, cover: dict[str, frozenset[str]], drivers: dict[str, Names]
) -> None:
    """Cover of a LUT whose function is no f3 net (ABC resynthesised it): the gates of its
    consumers' covers whose support lies inside its own, minus what the LUTs below it cover."""
    index: dict[str, int] = {}
    for n in sorted({*gate.inputs, *lut.inputs}):
        index[n] = len(index)
    for c in sorted({c for _, _, c in gate.latches} | {c for _, _, c in lut.latches}):
        index["ff:" + c] = len(index)
    gsup, lsup = _supports(gate, index), _supports(lut, index)
    gate_sup = {c.cname: gsup[n] for n, c in drivers.items()}
    by_out = {c.out: c for c in lut.names}
    consumers: dict[str, list[Names]] = {}
    for lc in lut.names:
        for i in lc.ins:
            consumers.setdefault(i, []).append(lc)
    original = dict(cover)
    for cell in topo(lut):
        if cover[cell.cname]:
            continue
        pool: set[str] = set()
        for v in consumers.get(cell.out, ()):
            pool |= original[v.cname]
        below: set[str] = set()
        for i in cell.ins:
            src = by_out.get(i)
            if src is not None:
                below |= cover[src.cname]
        mine = lsup[cell.out]
        cover[cell.cname] = frozenset(
            g for g in pool - below if gate_sup[g] & ~mine == 0)
    for cell in lut.names:  # a matched LUT gives up what an unmatched input LUT now holds
        owed: set[str] = set()
        for i in cell.ins:
            src = by_out.get(i)
            if src is not None and not original[src.cname]:
                owed |= cover[src.cname]
        if owed and original[cell.cname]:
            cover[cell.cname] = frozenset(original[cell.cname] - owed) or original[cell.cname]


def _latch_cover(
    gate: Blif, lut: Blif, gsig: dict[str, int], cover: dict[str, frozenset[str]],
    drivers: dict[str, Names],
) -> None:
    """A flip-flop covers itself and the f3 gates that only copy its output (buffers)."""
    q_of = {c: q for _, q, c in gate.latches}
    for _d, _q, cname in lut.latches:
        q = q_of.get(cname)
        copies = {c.cname for n, c in drivers.items() if q is not None and gsig[n] == gsig[q]}
        cover[cname] = frozenset({cname} | copies)


def _cone(
    root: str, drivers: dict[str, Names], gsig: dict[str, int], bound: set[int]
) -> frozenset[str]:
    seen: set[str] = set()
    cells: set[str] = set()
    work = [root]
    while work:
        net = work.pop()
        if net in seen or net not in drivers:
            continue
        seen.add(net)
        if net != root and gsig[net] in bound:
            continue
        cell = drivers[net]
        cells.add(cell.cname)
        work.extend(cell.ins)
    return frozenset(cells)


def add_cnames(text: str, prefix: str = "L") -> str:
    """Append ``.cname <prefix><k>`` after every ``.names`` block of ``text`` (k counts from 0)."""
    out: list[str] = []
    lines = text.splitlines()
    k = 0
    in_names = False
    for line in lines:
        if in_names and (line.startswith(".") or not line.strip()):
            if not line.startswith(".cname"):
                out.append(f".cname {prefix}{k}")
                k += 1
            in_names = False
        out.append(line)
        if line.startswith(".names"):
            in_names = True
    return "\n".join(out) + "\n"


def read(path: Path) -> Blif:
    return parse_blif(path.read_text(encoding="utf-8"))
