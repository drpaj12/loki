"""A Gate-Breaker gate-level netlist (Yosys cmos cells) as cells and nets, and its BLIF.

Cells: NOT, BUF, NAND, NOR (A, B, Y), DFF (C, D, Q), DFFSR (C, D, Q, R, S). Nets are bits named
``x`` or ``x[3]`` (an escaped identifier such as ``\\pht[0] `` keeps its text as the base name).
Constants are ``#0`` and ``#1``. Anything else in the file (behavioural ``always``, ``reg``,
``initial``) raises ``Unsupported``: that design is left out and the reason is logged.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import q10_env as env

netmap: Any = env.mod("netmap")

CELL_PINS = {"NOT": ("A", "Y"), "BUF": ("A", "Y"), "NAND": ("A", "B", "Y"),
             "NOR": ("A", "B", "Y"), "DFF": ("C", "D", "Q"),
             "DFFSR": ("C", "D", "Q", "R", "S")}
OUT_PIN = {"NOT": "Y", "BUF": "Y", "NAND": "Y", "NOR": "Y", "DFF": "Q", "DFFSR": "Q"}
_COMMENT = re.compile(r"/\*.*?\*/|//[^\n]*", re.S)
_ESC = re.compile(r"\\(\S+)\s")
_INST = re.compile(r"^(NOT|NAND|NOR|BUF|DFFSR|DFF)\s+(\S+)\s*\((.*)\)$", re.S)
_PIN = re.compile(r"\.(\w+)\(\s*([^()]*?)\s*\)")
_DECL = re.compile(r"^(input|output|wire)\s*(?:\[(\d+):(\d+)\])?\s*(\S+)$")
_CONST = re.compile(r"^(\d+)'([hbd])([0-9a-fA-F]+)$")


class Unsupported(ValueError):
    """A construct of the netlist file that the reader does not handle."""


@dataclass
class Cell:
    idx: int
    typ: str
    name: str
    pins: dict[str, str]  # pin -> net bit key or '#0' / '#1'

    @property
    def out(self) -> str:
        return self.pins[OUT_PIN[self.typ]]

    @property
    def ins(self) -> list[str]:
        return [v for k, v in self.pins.items() if k != OUT_PIN[self.typ]]


@dataclass
class Netlist:
    module: str
    header: list[str]  # port names in header order
    decl: dict[str, tuple[str, int | None, int | None]] = field(default_factory=dict)
    bits: dict[str, str] = field(default_factory=dict)  # bit key -> input | output | wire
    cells: list[Cell] = field(default_factory=list)
    assigns: list[tuple[str, str]] = field(default_factory=list)  # (lhs bit, rhs bit or const)
    san: dict[str, str] = field(default_factory=dict)  # bit key -> identifier

    def port_bits(self, kind: str) -> list[str]:
        return [b for b, k in self.bits.items() if k == kind]


def _unescape(text: str) -> tuple[str, dict[str, str]]:
    names: dict[str, str] = {}

    def sub(m: re.Match[str]) -> str:
        tag = f"ESC{len(names)}Q"
        names[tag] = m.group(1)
        return tag + " "

    return _ESC.sub(sub, text), names


def _bit(expr: str, esc: dict[str, str], decl: dict[str, tuple[str, int | None, int | None]]
         ) -> str:
    """Net bit key of a pin expression (a bit select, a scalar name or a constant)."""
    e = expr.strip()
    m = _CONST.match(e)
    if m:
        val = int(m.group(3), {"h": 16, "b": 2, "d": 10}[m.group(2)])
        if int(m.group(1)) != 1 or val not in (0, 1):
            raise Unsupported(f"multi-bit constant in a pin: {e}")
        return f"#{val}"
    m = re.fullmatch(r"(\S+?)\s*\[(\d+)\]", e)
    base, idx = (m.group(1), m.group(2)) if m else (e, None)
    base = esc.get(base, base)
    if idx is None:
        if base in decl and decl[base][1] is not None:
            raise Unsupported(f"vector {base} used without a bit select")
        return base
    return f"{base}[{idx}]"


def _parse_decl(text: str, esc: dict[str, str], nl: Netlist) -> None:
    m = _DECL.match(text.strip())
    if not m:
        raise Unsupported(f"declaration: {text.strip()[:60]}")
    kind, msb, lsb, name = m.group(1), m.group(2), m.group(3), m.group(4)
    name = esc.get(name, name)
    hi = int(msb) if msb is not None else None
    lo = int(lsb) if lsb is not None else None
    if name in nl.decl and nl.decl[name][0] in ("input", "output"):
        return
    nl.decl[name] = (kind, hi, lo)
    for b in netmap.decl_bits(name, msb, lsb):
        if nl.bits.get(b) not in ("input", "output"):
            nl.bits[b] = kind


def _expand(expr: str, decl: dict[str, tuple[str, int | None, int | None]]) -> list[str]:
    """Bit keys of an assign operand, msb first (concatenation, sized constants, ranges, bit
    selects and bare names of declared vectors)."""
    e = expr.strip()
    if e.startswith("{"):
        out: list[str] = []
        for part in netmap.split_top(e[1:-1]):
            out += _expand(part, decl)
        return out
    if re.fullmatch(r"1'[hbd][xXzZ]", e):
        return ["#x"]
    bits = netmap.bits_of(e)
    if len(bits) == 1 and bits[0] in decl and decl[bits[0]][1] is not None:
        name = bits[0]
        hi, lo = decl[name][1], decl[name][2]
        assert hi is not None and lo is not None
        step = -1 if hi >= lo else 1
        return [f"{name}[{i}]" for i in range(hi, lo + step, step)]
    return [str(x) for x in bits]


def _assign_pairs(lhs: str, rhs: str, esc: dict[str, str],
                  decl: dict[str, tuple[str, int | None, int | None]]) -> list[tuple[str, str]]:
    def fix(s: str) -> str:
        for tag, orig in esc.items():
            s = s.replace(tag, orig)
        return s

    left, right = _expand(fix(lhs), decl), _expand(fix(rhs), decl)
    if len(left) != len(right):
        raise Unsupported(f"assign widths differ: {lhs.strip()[:40]}")
    return list(zip(left, right, strict=True))


def is_const(key: str) -> bool:
    return key.startswith("#")


def parse(text: str) -> Netlist:
    body, esc = _unescape(_COMMENT.sub(" ", text))
    stmts = [s.strip() for s in body.split(";")]
    head = re.match(r"module\s+(\S+?)\s*\((.*)\)\s*$", stmts[0], re.S)
    if not head:
        raise Unsupported("no module header")
    names = [esc.get(n.strip(), n.strip()) for n in head.group(2).split(",") if n.strip()]
    nl = Netlist(head.group(1), names)
    insts: list[tuple[str, str]] = []
    for st in stmts[1:]:
        s = re.sub(r"\s+", " ", st).strip()
        if not s or s == "endmodule":
            continue
        if s.endswith("endmodule"):
            s = s[: -len("endmodule")].strip()
        word = s.split(" ", 1)[0]
        if word in ("input", "output", "wire"):
            _parse_decl(s, esc, nl)
        elif word == "assign":
            lhs, rhs = s[len("assign"):].split("=", 1)
            nl.assigns += _assign_pairs(lhs, rhs, esc, nl.decl)
        elif _INST.match(st.strip()):
            insts.append((st.strip(), s))
        else:
            raise Unsupported(f"statement: {s[:60]}")
    for raw, _ in insts:
        m = _INST.match(raw)
        assert m is not None
        typ, name, pins = m.group(1), m.group(2), dict(_PIN.findall(m.group(3)))
        if set(pins) != set(CELL_PINS[typ]):
            raise Unsupported(f"pins of {name}: {sorted(pins)}")
        nl.cells.append(Cell(len(nl.cells), typ, esc.get(name, name),
                             {p: _bit(v, esc, nl.decl) for p, v in pins.items()}))
    nl.san = sanitize(nl)
    return nl


def sanitize(nl: Netlist) -> dict[str, str]:
    """Identifier for every net bit (deterministic; collisions get a numeric suffix)."""
    keys = sorted(set(nl.bits) | {b for c in nl.cells for b in c.pins.values()
                                  if not b.startswith("#")})
    taken: set[str] = set()
    out: dict[str, str] = {}
    for k in keys:
        s = re.sub(r"[^A-Za-z0-9_]", "_", k)
        if not s or s[0].isdigit():
            s = "w" + s
        base, n = s, 0
        while s in taken:
            n += 1
            s = f"{base}_x{n}"
        taken.add(s)
        out[k] = s
    return out


def read(path: Path) -> Netlist:
    return parse(path.read_text(encoding="utf-8"))
