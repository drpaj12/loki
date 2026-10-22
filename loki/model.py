"""Plain data values shared by the pure core (spec section 5 and plan Task 2)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Span:
    """An HDL source span (line and column, 1-based as Odin III reports them)."""

    file: str
    line: int
    col: int
    end_line: int
    end_col: int


@dataclass(frozen=True)
class Net:
    id: int
    names: tuple[str, ...]


@dataclass(frozen=True)
class Port:
    """A cell port: net ids LSB first, 0 for an unconnected bit."""

    name: str
    width: int
    nets: tuple[int, ...]


@dataclass(frozen=True)
class WordCell:
    """A word-level node recorded before mapping."""

    id: int
    type: str
    name: str
    params: dict[str, int | str]
    spans: tuple[Span, ...]
    inputs: tuple[Port, ...]
    outputs: tuple[Port, ...]
    fsm: bool


@dataclass(frozen=True)
class InstanceSite:
    """An instance of a user module in the pre-flatten hierarchy."""

    span: Span
    name: str
    module: str
    parent_module: str


@dataclass(frozen=True)
class FinalCell:
    """A cell of the final mapped netlist (LUT, flip-flop, constant, hard cell, gate, port)."""

    id: int
    kind: str
    type: str
    name: str
    params: dict[str, int | str]
    spans: tuple[Span, ...]
    inputs: tuple[Port, ...]
    outputs: tuple[Port, ...]


@dataclass(frozen=True)
class PortBit:
    """One bit of a top-level port: ``A[0]`` (bits LSB first), direction ``in`` or ``out``."""

    name: str
    direction: str
    net: int
    spans: tuple[Span, ...] = ()


@dataclass(frozen=True)
class Netlist:
    top: str
    nets: dict[int, Net]
    cells: tuple[FinalCell, ...]
    port_bits: tuple[PortBit, ...]


@dataclass(frozen=True)
class Snapshot:
    words: tuple[WordCell, ...]
    instances: tuple[InstanceSite, ...]
    top: str
    po_nets: frozenset[int] = frozenset()
