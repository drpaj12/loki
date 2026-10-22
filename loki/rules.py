"""The role rule table and the fixpoint that assigns roles to word cells (spec section 7)."""

from __future__ import annotations

from collections.abc import Sequence

from loki.model import WordCell

_STORAGE_CTRL = {"CLK"}
CONTROL_PORTS: dict[str, frozenset[str]] = {
    "$mux": frozenset({"S"}),
    "$pmux": frozenset({"S"}),
    "$bmux": frozenset({"S"}),
    "$demux": frozenset({"S"}),
    "$dff": frozenset(_STORAGE_CTRL),
    "$dffe": frozenset({"EN", "CLK"}),
    "$adff": frozenset({"ARST", "CLK"}),
    "$adffe": frozenset({"ARST", "EN", "CLK"}),
    "$sdff": frozenset({"SRST", "CLK"}),
    "$sdffe": frozenset({"SRST", "EN", "CLK"}),
    "$sdffce": frozenset({"SRST", "EN", "CLK"}),
    "$dffsr": frozenset({"SET", "CLR", "CLK"}),
    "$dffsre": frozenset({"SET", "CLR", "EN", "CLK"}),
    "$aldff": frozenset({"ALOAD", "CLK"}),
    "$aldffe": frozenset({"ALOAD", "EN", "CLK"}),
    "$dlatch": frozenset({"EN"}),
    "$adlatch": frozenset({"EN", "ARST"}),
    "$dlatchsr": frozenset({"EN", "SET", "CLR"}),
    "$mem": frozenset({"RD_EN", "WR_EN", "RD_CLK", "WR_CLK"}),
    "$mem_v2": frozenset({"RD_EN", "WR_EN", "RD_CLK", "WR_CLK"}),
    "$memrd": frozenset({"EN", "CLK"}),
    "$memwr": frozenset({"EN", "CLK"}),
}

# Types whose every non-control input is data (spec 7.2). Memory cells appear here too: their
# control ports are tested first. A type that does not start with "$" is a hard cell and is
# data-forced as well (see _is_data_forced).
DATA_FORCED: frozenset[str] = frozenset(
    {
        "$add", "$sub", "$mul", "$div", "$mod", "$neg", "$pos", "$pow", "$alu", "$macc",
        "$shl", "$shr", "$sshl", "$sshr", "$shift", "$shiftx",
        "$mem", "$mem_v2", "$memrd", "$memwr",
    }
)

NEUTRAL: frozenset[str] = frozenset(
    {
        "$eq", "$ne", "$eqx", "$nex", "$lt", "$le", "$gt", "$ge",
        "$and", "$or", "$xor", "$xnor", "$not",
        "$reduce_and", "$reduce_or", "$reduce_xor", "$reduce_xnor", "$reduce_bool",
        "$logic_not", "$logic_and", "$logic_or",
        "$mux", "$pmux", "$bmux", "$demux",
        "$dff", "$dffe", "$adff", "$adffe", "$sdff", "$sdffe", "$sdffce", "$dffsr", "$dffsre",
        "$aldff", "$aldffe", "$dlatch", "$adlatch", "$dlatchsr",
        "$const", "$_CONST0_", "$_CONST1_", "$_CONSTX_",
    }
)

_CONTROL = "control"
_DATA = "data"


class UnlistedWordType(ValueError):
    """A word cell type that is in no rule list (the lists are closed on purpose)."""


def _is_data_forced(typ: str) -> bool:
    return typ in DATA_FORCED or not typ.startswith("$")


def _listed(typ: str) -> bool:
    return typ in NEUTRAL or typ in CONTROL_PORTS or _is_data_forced(typ)


def _sink_kind(reader: WordCell, port: str) -> str | None:
    """The kind a sink hands to its driver, or None when the reader is neutral for it."""
    if port in CONTROL_PORTS.get(reader.type, frozenset()):
        return _CONTROL
    if _is_data_forced(reader.type):
        return _DATA
    return None


def _readers(words: Sequence[WordCell]) -> dict[int, list[tuple[WordCell, str]]]:
    readers: dict[int, list[tuple[WordCell, str]]] = {}
    for w in words:
        for port in w.inputs:
            for net in port.nets:
                if net:
                    readers.setdefault(net, []).append((w, port.name))
    return readers


def _step(
    w: WordCell,
    kinds: dict[int, set[str]],
    readers: dict[int, list[tuple[WordCell, str]]],
    po_nets: frozenset[int],
) -> bool:
    """One pass over the sinks of w; True when its kind set grew."""
    mine = kinds[w.id]
    before = len(mine)
    for port in w.outputs:
        for net in port.nets:
            if net in po_nets:
                mine.add(_DATA)
            for reader, rport in readers.get(net, ()):
                kind = _sink_kind(reader, rport)
                if kind is not None:
                    mine.add(kind)
                else:
                    mine |= kinds[reader.id]
    return len(mine) != before


def assign_roles(words: Sequence[WordCell], po_nets: frozenset[int]) -> dict[int, str]:
    """Roles of word cells by the fixpoint of spec 7.5."""
    for w in words:
        if not _listed(w.type):
            raise UnlistedWordType(f"unlisted word type {w.type}")
    readers = _readers(words)
    kinds: dict[int, set[str]] = {w.id: ({_CONTROL} if w.fsm else set()) for w in words}
    changed = True
    while changed:
        changed = False
        for w in words:
            if _step(w, kinds, readers, po_nets):
                changed = True
    return {w.id: _role_of(kinds[w.id]) for w in words}


def _role_of(kinds: set[str]) -> str:
    if kinds == {_CONTROL}:
        return "control"
    if kinds == {_DATA}:
        return "datapath"
    return "mixed" if kinds else "unknown"


def combine_roles(roles: Sequence[str]) -> str:
    """Role of a final cell from the roles of its matched word cells (spec 7.5)."""
    known = {r for r in roles if r != "unknown"}
    if not known:
        return "unknown"
    if "mixed" in known or len(known) > 1:
        return "mixed"
    return next(iter(known))
