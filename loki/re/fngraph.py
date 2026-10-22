"""FnGraph: Loki's read-only Python view of level 0 (L1 spec 4). Pure except ``from_design``."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

KINDS = ("lut", "ff", "latch", "const", "hard")
_PORT_IN = "$port_in"
_PORT_OUT = "$port_out"


@dataclass(frozen=True)
class Cell:
    """A level-0 cell. ``id`` is the node ID (the cell id used everywhere in L1)."""

    id: int
    name: str
    kind: str
    type: str
    ins: tuple[int, ...]
    outs: tuple[int, ...]
    table: int
    width: int
    clock: int
    line: int
    params: dict[str, int | str]


@dataclass(frozen=True)
class FnGraph:
    cells: dict[int, Cell]
    driver: dict[int, int]
    readers: dict[int, tuple[tuple[int, int], ...]]
    names: dict[int, str]
    pis: tuple[int, ...]
    pos: tuple[int, ...]
    line_to_cell: dict[int, int]
    source_file: str

    def sources(self) -> frozenset[int]:
        """Nets that start combinational logic: PIs and every non-LUT cell output."""
        out = set(self.pis)
        for cell in self.cells.values():
            if cell.kind != "lut":
                out.update(cell.outs)
        return frozenset(out)

    def label(self, cell_id: int) -> str:
        """The cell's ``.cname`` or ``c<id>`` when it has none."""
        return self.cells[cell_id].name or f"c{cell_id}"


def _on_minterms(pattern: str, width: int) -> list[int]:
    """Minterms of one cover pattern: char ``i`` is input ``i``, ``-`` any value."""
    base = 0
    dashes: list[int] = []
    for i, ch in enumerate(pattern):
        if ch == "-":
            dashes.append(i)
        elif ch == "1":
            base |= 1 << i
        elif ch != "0":
            raise ValueError(f"bad cover pattern {pattern!r}")
    if len(pattern) != width:
        raise ValueError(f"cover pattern {pattern!r} is not {width} wide")
    out = []
    for sub in range(1 << len(dashes)):
        x = base
        for j, pos in enumerate(dashes):
            if (sub >> j) & 1:
                x |= 1 << pos
        out.append(x)
    return out


def cover_to_table(cover: str, width: int) -> int:
    """Truth table of a ``$sop`` COVER (bit ``x`` is the output for input pattern ``x``).

    Rows with output 1 are the on-set; rows with output 0 are the off-set, so the table is the
    complement of their union. An empty cover is constant 0.
    """
    full = (1 << (1 << width)) - 1
    ones = 0
    zeros = 0
    seen: set[str] = set()
    for line in cover.splitlines():
        parts = line.split()
        if not parts:
            continue
        pattern, value = ("", parts[0]) if len(parts) == 1 else (parts[0], parts[1])
        seen.add(value)
        bits = 0
        for x in _on_minterms(pattern, width):
            bits |= 1 << x
        if value == "1":
            ones |= bits
        elif value == "0":
            zeros |= bits
        else:
            raise ValueError(f"bad cover output {value!r}")
    if seen == {"0", "1"}:
        raise ValueError("cover mixes on-set and off-set rows")
    return (full & ~zeros) if seen == {"0"} else ones


def _net_id(pin: Any) -> int:
    net = pin.net()
    return int(net.id) if net is not None else 0


def _kind(typ: str, params: dict[str, int | str]) -> str:
    if typ == "$sop":
        return "const" if params.get("WIDTH") == 0 else "lut"
    if typ.startswith("$_DFF_") or typ == "$_FF_":
        return "ff"
    if typ.startswith("$_DLATCH_"):
        return "latch"
    return "hard"


def _read_cell(node: Any, names: dict[int, str]) -> Cell:
    typ = str(node.type_name)
    params = dict(node.params())
    kind = _kind(typ, params)
    ins: list[int] = []
    outs: list[int] = []
    clock = 0
    for port in node.ports():
        nets = tuple(_net_id(p) for p in port.pins)
        for pin in port.pins:
            net = pin.net()
            if net is not None:
                names[int(net.id)] = str(net.name)
        if kind in ("ff", "latch") and port.name in ("C", "E"):
            clock = nets[0] if nets else 0
        elif port.direction == "out":
            outs.extend(nets)
        else:
            ins.extend(nets)
    table = 0
    width = 0
    if kind in ("lut", "const"):
        width = int(params["WIDTH"])
        table = cover_to_table(str(params["COVER"]), width)
    src = node.sources()
    return Cell(int(node.id), str(node.name), kind, typ, tuple(ins), tuple(outs), table, width,
                clock, int(src[0].line) if src else 0, params)


def _port_nets(module: Any, names: dict[int, str]) -> tuple[tuple[int, ...], tuple[int, ...]]:
    pis: list[int] = []
    pos: list[int] = []
    for mp in module.ports():
        typ = str(mp.node.type_name)
        for pin in mp.node.pins():
            net = pin.net()
            if net is None:
                continue
            names[int(net.id)] = str(net.name)
            if typ == _PORT_IN:
                pis.append(int(net.id))
            elif typ == _PORT_OUT:
                pos.append(int(net.id))
    return tuple(pis), tuple(pos)


def from_design(design: Any) -> FnGraph:
    """Read level 0 once: one walk of ``top().nodes()``, then the module's ports."""
    module = design.top()
    names: dict[int, str] = {}
    cells: dict[int, Cell] = {}
    source_file = ""
    line_to_cell: dict[int, int] = {}
    for node in module.nodes():
        if str(node.type_name).startswith("$port_"):
            continue
        cell = _read_cell(node, names)
        cells[cell.id] = cell
        src = node.sources()
        if src:
            source_file = source_file or str(src[0].file)
            line_to_cell[cell.line] = cell.id
    driver: dict[int, int] = {}
    readers: dict[int, list[tuple[int, int]]] = {}
    for cid in sorted(cells):
        cell = cells[cid]
        for net in cell.outs:
            if net:
                driver[net] = cid
        for pin, net in enumerate(cell.ins):
            if net:
                readers.setdefault(net, []).append((cid, pin))
    pis, pos = _port_nets(module, names)
    return FnGraph(cells, driver, {n: tuple(r) for n, r in readers.items()}, names, pis, pos,
                   line_to_cell, source_file)
