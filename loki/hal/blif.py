"""A small BLIF reader for the L0 floor netlists: ``.names .latch .subckt .cname``."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class BlifError(ValueError):
    """The text is not in the supported BLIF subset."""


@dataclass(frozen=True)
class Gate:
    """A ``.names`` block: ``inputs`` and one ``output``; ``rows`` are (pattern, out) pairs."""

    inputs: tuple[str, ...]
    output: str
    rows: tuple[tuple[str, str], ...]
    cname: str = ""

    def table(self) -> int:
        """Truth table as an integer: bit ``i`` is the output for the assignment in which input
        ``j`` has value ``(i >> j) & 1``. Rows with output 0 are an off-set cover."""
        k = len(self.inputs)
        outs = {o for _, o in self.rows}
        if len(outs) > 1:
            raise BlifError(f"{self.output}: mixed on-set and off-set rows")
        off = outs == {"0"}
        table = 0
        for i in range(1 << k):
            hit = any(_matches(p, i) for p, _ in self.rows)
            if hit != off:
                table |= 1 << i
        return table


@dataclass(frozen=True)
class Latch:
    d: str
    q: str
    kind: str
    clock: str
    init: str
    cname: str = ""


@dataclass(frozen=True)
class Subckt:
    model: str
    pins: tuple[tuple[str, str], ...]
    cname: str = ""


Cell = Gate | Latch | Subckt


@dataclass(frozen=True)
class Blif:
    model: str
    inputs: tuple[str, ...]
    outputs: tuple[str, ...]
    cells: tuple[Cell, ...]


def _matches(pattern: str, i: int) -> bool:
    return all(ch == "-" or int(ch) == (i >> j) & 1 for j, ch in enumerate(pattern))


def _logical_lines(text: str) -> list[list[str]]:
    out: list[list[str]] = []
    pending = ""
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].rstrip()
        if line.endswith("\\"):
            pending += line[:-1] + " "
            continue
        line = (pending + line).strip()
        pending = ""
        if line:
            out.append(line.split())
    return out


def _with_cname(cell: Cell, name: str) -> Cell:
    if isinstance(cell, Gate):
        return Gate(cell.inputs, cell.output, cell.rows, name)
    if isinstance(cell, Latch):
        return Latch(cell.d, cell.q, cell.kind, cell.clock, cell.init, name)
    return Subckt(cell.model, cell.pins, name)


def _latch(tok: list[str]) -> Latch:
    if len(tok) not in (4, 6):
        raise BlifError(f"unsupported .latch form: {' '.join(tok)}")
    if len(tok) == 4:
        return Latch(tok[1], tok[2], "", "", tok[3])
    return Latch(tok[1], tok[2], tok[3], tok[4], tok[5])


def _subckt(tok: list[str]) -> Subckt:
    pins = []
    for item in tok[2:]:
        port, sep, net = item.partition("=")
        if not sep:
            raise BlifError(f"bad .subckt pin {item!r}")
        pins.append((port, net))
    return Subckt(tok[1], tuple(pins))


def parse_blif(text: str) -> Blif:
    """The first model of ``text``."""
    model, inputs, outputs = "", [], []
    cells: list[Cell] = []
    gate: tuple[list[str], list[tuple[str, str]]] | None = None

    def close() -> None:
        nonlocal gate
        if gate is not None:
            names, rows = gate
            cells.append(Gate(tuple(names[:-1]), names[-1], tuple(rows)))
            gate = None

    for tok in _logical_lines(text):
        head = tok[0]
        if not head.startswith("."):
            if gate is None:
                raise BlifError(f"cover row outside .names: {' '.join(tok)}")
            if len(gate[0]) == 1:
                gate[1].append(("", tok[0]))
            else:
                gate[1].append((tok[0], tok[1]))
            continue
        close()
        if head == ".model" and not model:
            model = tok[1]
        elif head == ".inputs":
            inputs += tok[1:]
        elif head == ".outputs":
            outputs += tok[1:]
        elif head == ".names":
            gate = (tok[1:], [])
        elif head == ".latch":
            cells.append(_latch(tok))
        elif head == ".subckt":
            cells.append(_subckt(tok))
        elif head == ".cname":
            if not cells:
                raise BlifError(".cname before any cell")
            cells[-1] = _with_cname(cells[-1], tok[1])
        elif head == ".end":
            break
    close()
    if not model:
        raise BlifError("no .model")
    return Blif(model, tuple(inputs), tuple(outputs), tuple(cells))


def read_blif(path: Path) -> Blif:
    return parse_blif(path.read_text(encoding="utf-8"))
