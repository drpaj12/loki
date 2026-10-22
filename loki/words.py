"""words.json: word-level cells with connectivity, anonymised (L1 spec 12.1, L0 spec 6.10)."""

from __future__ import annotations

from collections.abc import Iterable

from loki.anon import Numbering
from loki.model import Snapshot, WordCell
from loki.schemas import SCHEMA

CONST_TYPES = frozenset({"$const", "$_CONST0_", "$_CONST1_", "$_CONSTX_"})


def _const_nets(snap: Snapshot) -> frozenset[int]:
    """Nets driven by a constant cell; net 0 (unconnected) counts as constant too."""
    nets = {0}
    for w in snap.words:
        if w.type in CONST_TYPES:
            nets.update(n for p in w.outputs for n in p.nets)
    return frozenset(nets)


def _const_ports(word: WordCell, const: frozenset[int]) -> list[str]:
    return sorted(p.name for p in word.inputs if p.nets and all(n in const for n in p.nets))


def _drivers(words: Iterable[WordCell]) -> dict[int, list[tuple[int, str]]]:
    out: dict[int, list[tuple[int, str]]] = {}
    for w in words:
        for p in w.outputs:
            for n in p.nets:
                if n:
                    out.setdefault(n, []).append((w.id, p.name))
    return out


def _edges(snap: Snapshot) -> list[dict[str, object]]:
    drivers = _drivers(snap.words)
    seen: set[tuple[int, str, int, str]] = set()
    for w in snap.words:
        for p in w.inputs:
            for n in p.nets:
                for src, src_port in drivers.get(n, ()):
                    seen.add((src, src_port, w.id, p.name))
    return [
        {"src": s, "src_port": sp, "dst": d, "dst_port": dp} for s, sp, d, dp in sorted(seen)
    ]


def build_words(
    snap: Snapshot,
    matched: dict[int, tuple[int, ...]],
    num: Numbering,
    word_roles: dict[int, str],
) -> dict[str, object]:
    """The words.json object: no original name, footprints as anonymised cell names."""
    footprint: dict[int, list[str]] = {}
    for cell_id, ids in sorted(matched.items()):
        for wid in ids:
            footprint.setdefault(wid, []).append(num.cell[cell_id])
    const = _const_nets(snap)
    words = [
        {
            "id": w.id,
            "type": w.type,
            "params": dict(w.params),
            "fsm": w.fsm,
            "role": word_roles.get(w.id, "unknown"),
            "const_ports": _const_ports(w, const),
            "footprint": footprint.get(w.id, []),
        }
        for w in sorted(snap.words, key=lambda x: x.id)
    ]
    return {"schema": SCHEMA, "words": words, "edges": _edges(snap)}
