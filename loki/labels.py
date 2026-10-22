"""Labels: join of final cells to word cells by source span, module path, bus, bit (spec 5)."""

from __future__ import annotations

import csv
import io
import re
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import PurePosixPath

from loki.anon import Numbering, logic_cells
from loki.model import FinalCell, InstanceSite, Netlist, PortBit, Snapshot, Span, WordCell
from loki.rules import combine_roles
from loki.schemas import LABEL_COLUMNS

_BUS_RE = re.compile(r"^(.+)\[(\d+)\]$")


@dataclass(frozen=True)
class Label:
    node_id: str
    kind: str
    cell_type: str
    construct_type: str
    construct_types: str
    n_construct_cells: int
    module_path: str
    bus_name: str
    bit_index: int
    role: str
    hdl_file: str
    hdl_line: int
    hdl_col: int
    hdl_end_line: int
    hdl_end_col: int
    n_spans: int


def match_words(cell: FinalCell, words: Sequence[WordCell]) -> list[WordCell]:
    """Word cells whose spans are a non-empty subset of the cell's spans (spec 5.3)."""
    have = set(cell.spans)
    hits = [w for w in words if w.spans and set(w.spans) <= have]
    return sorted(hits, key=lambda w: (-len(w.spans), w.id))


def _reachable(instances: Sequence[InstanceSite], top: str) -> set[str]:
    """Modules instantiated, directly or not, from the top (unused modules are left out)."""
    seen = {top}
    todo = [top]
    while todo:
        cur = todo.pop()
        for site in instances:
            if site.parent_module == cur and site.module not in seen:
                seen.add(site.module)
                todo.append(site.module)
    return seen


def _chain(sites: Sequence[InstanceSite]) -> list[InstanceSite]:
    """The sites linked parent to child, outermost first (a site whose parent is no child)."""
    children = {s.module for s in sites}
    chain = [s for s in sites if s.parent_module not in children][:1]
    while chain:
        nxt = next(
            (s for s in sites if s.parent_module == chain[-1].module and s not in chain), None
        )
        if nxt is None:
            break
        chain.append(nxt)
    return chain


def module_path(spans: Sequence[Span], instances: Sequence[InstanceSite], top: str) -> str:
    """``top/<i1>/<i2>``, outermost first (spec 5.2).

    Odin III lists only the innermost instantiation span on a flattened cell, so the outer
    instances are found by climbing from it: one instantiating site is taken, several give
    ``*`` (the path above is ambiguous; no instance is guessed).
    """
    have = set(spans)
    hit = [s for s in instances if s.span in have]
    chain = _chain(hit)
    if not chain:
        return top
    reach = _reachable(instances, top)
    names = [s.name for s in chain]
    cur = chain[0].parent_module
    while cur != top:
        parents = [s for s in instances if s.module == cur and s.parent_module in reach]
        if len(parents) != 1:
            return "/".join([top, "*", *names])
        names.insert(0, parents[0].name)
        cur = parents[0].parent_module
    return "/".join([top, *names])


def _split_bus(name: str) -> tuple[str, int] | None:
    m = _BUS_RE.match(name)
    return (m.group(1), int(m.group(2))) if m else None


def bus_bit(cell: FinalCell, nl: Netlist) -> tuple[str, int]:
    """Bus name and bit index from the first output net's names (spec 5.4)."""
    names: tuple[str, ...] = ()
    for port in cell.outputs:
        net = next((n for n in port.nets if n), 0)
        if net:
            names = nl.nets[net].names if net in nl.nets else ()
            break
    for name in names:
        hit = _split_bus(name)
        if hit:
            return hit
    for name in names:
        if name:
            return (name, -1)
    return ("", -1)


def _rel_file(file: str, root: str) -> str:
    path = PurePosixPath(file.replace("\\", "/"))
    try:
        return str(path.relative_to(PurePosixPath(root.replace("\\", "/"))))
    except ValueError:
        return path.name


def _first_span(spans: Sequence[Span], root: str) -> tuple[str, int, int, int, int]:
    if not spans:
        return ("", -1, -1, -1, -1)
    s = spans[0]
    return (_rel_file(s.file, root), s.line, s.col, s.end_line, s.end_col)


def _primary(cell: FinalCell, matches: Sequence[WordCell]) -> str:
    if not matches:
        return ""
    first = cell.spans[0] if cell.spans else None
    for w in matches:
        if first is not None and w.spans[0] == first:
            return w.type
    return matches[0].type


def _distinct(types: Sequence[str]) -> str:
    return "|".join(dict.fromkeys(types))


def _cell_label(
    c: FinalCell, nl: Netlist, snap: Snapshot, num: Numbering, roles: dict[int, str], root: str
) -> tuple[Label, tuple[int, ...]]:
    matches = match_words(c, snap.words)
    bus, bit = bus_bit(c, nl)
    spans = matches[0].spans if matches else c.spans
    role = "const" if c.kind == "const" else combine_roles([roles[w.id] for w in matches])
    hdl = _first_span(c.spans, root)
    label = Label(
        node_id=num.cell[c.id],
        kind=c.kind,
        cell_type=c.type,
        construct_type=_primary(c, matches),
        construct_types=_distinct([w.type for w in matches]),
        n_construct_cells=len(matches),
        module_path=module_path(spans, snap.instances, snap.top),
        bus_name=bus,
        bit_index=bit,
        role=role,
        hdl_file=hdl[0],
        hdl_line=hdl[1],
        hdl_col=hdl[2],
        hdl_end_line=hdl[3],
        hdl_end_col=hdl[4],
        n_spans=len(c.spans),
    )
    return label, tuple(w.id for w in matches)


def _port_label(pb: PortBit, num: Numbering, snap: Snapshot, root: str) -> Label:
    is_in = pb.direction == "in"
    split = _split_bus(pb.name)
    bus, bit = split if split else (pb.name, 0)
    hdl = _first_span(pb.spans, root)
    ctype = "$port_in" if is_in else "$port_out"
    return Label(
        node_id=(num.pi if is_in else num.po)[pb.name],
        kind="pi" if is_in else "po",
        cell_type=ctype,
        construct_type=ctype,
        construct_types=ctype,
        n_construct_cells=0,
        module_path=snap.top,
        bus_name=bus,
        bit_index=bit,
        role="io",
        hdl_file=hdl[0],
        hdl_line=hdl[1],
        hdl_col=hdl[2],
        hdl_end_line=hdl[3],
        hdl_end_col=hdl[4],
        n_spans=len(pb.spans),
    )


def build_labels(
    nl: Netlist, snap: Snapshot, num: Numbering, word_roles: dict[int, str], root: str
) -> tuple[list[Label], dict[int, tuple[int, ...]]]:
    """One label per graph node (cells in id order, then port bits) and matched word ids."""
    labels: list[Label] = []
    matched: dict[int, tuple[int, ...]] = {}
    for c in logic_cells(nl):
        label, ids = _cell_label(c, nl, snap, num, word_roles, root)
        labels.append(label)
        matched[c.id] = ids
    labels.extend(_port_label(pb, num, snap, root) for pb in nl.port_bits)
    return labels, matched


def labels_to_csv(labels: Sequence[Label]) -> str:
    """labels.csv text: header from LABEL_COLUMNS, csv defaults, ``\\n`` line ends."""
    buf = io.StringIO(newline="")
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(LABEL_COLUMNS)
    for lab in labels:
        w.writerow([getattr(lab, col) for col in LABEL_COLUMNS])
    return buf.getvalue()
