"""A small reader for ``.o3lib`` technology libraries: cell ports and gate functions (spec 3, F3).

The Odin III binding does not expose a library cell's function, so the gate covers of the F3
BLIF come from the library text itself (``fn Y = ~(A & B)``). Only what the shipped libraries use
is parsed: ``~ & ^ | ?:``, parentheses, names and ``1'b0``/``1'b1``.
"""

from __future__ import annotations

import itertools
import re
from dataclasses import dataclass, field
from pathlib import Path


class TechlibError(ValueError):
    """The library text is not in the supported subset."""


@dataclass(frozen=True)
class LibCell:
    name: str
    kind: str  # gate | blackbox
    inputs: tuple[str, ...]
    outputs: tuple[str, ...]
    functions: dict[str, str] = field(default_factory=dict)
    sequential: bool = False
    seq_kind: str = ""  # re | fe | ah | al, from the ``seq`` line
    clock: str = ""  # clock (level-sensitive: enable) input of the ``seq`` line


@dataclass(frozen=True)
class TechLib:
    name: str
    cells: dict[str, LibCell]

    def gate_names(self) -> frozenset[str]:
        """Combinational cells (a ``fn`` and no ``seq``)."""
        return frozenset(n for n, c in self.cells.items() if c.functions and not c.sequential)

    def state_names(self) -> frozenset[str]:
        """Cells with a ``seq`` line (flip-flops, latches)."""
        return frozenset(n for n, c in self.cells.items() if c.sequential)

    def cover(self, cell: str) -> tuple[tuple[str, ...], list[str]]:
        """(input names, on-set rows) of a one-output gate; each row is a pattern in input order."""
        c = self.cells[cell]
        if len(c.outputs) != 1 or c.outputs[0] not in c.functions:
            raise TechlibError(f"{cell}: not a one-output gate")
        expr = c.functions[c.outputs[0]]
        rows = []
        for bits in itertools.product((0, 1), repeat=len(c.inputs)):
            if _eval(expr, dict(zip(c.inputs, bits, strict=True))):
                rows.append("".join(str(b) for b in bits))
        return c.inputs, rows


_TOKEN = re.compile(r"\s*(1'b[01]|[A-Za-z_]\w*|[~&^|?:()])")


def _tokens(expr: str) -> list[str]:
    out: list[str] = []
    pos = 0
    text = expr.strip()
    while pos < len(text):
        m = _TOKEN.match(text, pos)
        if not m:
            raise TechlibError(f"cannot parse function {expr!r} at {text[pos:]!r}")
        out.append(m.group(1))
        pos = m.end()
        while pos < len(text) and text[pos].isspace():
            pos += 1
    return out


class _Parser:
    def __init__(self, expr: str, env: dict[str, int]) -> None:
        self.toks = _tokens(expr)
        self.pos = 0
        self.env = env

    def _peek(self) -> str:
        return self.toks[self.pos] if self.pos < len(self.toks) else ""

    def _take(self) -> str:
        tok = self._peek()
        self.pos += 1
        return tok

    def parse(self) -> int:
        value = self._ternary()
        if self._peek():
            raise TechlibError(f"trailing token {self._peek()!r}")
        return value

    def _ternary(self) -> int:
        cond = self._or()
        if self._peek() != "?":
            return cond
        self._take()
        yes = self._ternary()
        if self._take() != ":":
            raise TechlibError("expected ':'")
        no = self._ternary()
        return yes if cond else no

    def _or(self) -> int:
        v = self._xor()
        while self._peek() == "|":
            self._take()
            v |= self._xor()
        return v

    def _xor(self) -> int:
        v = self._and()
        while self._peek() == "^":
            self._take()
            v ^= self._and()
        return v

    def _and(self) -> int:
        v = self._unary()
        while self._peek() == "&":
            self._take()
            v &= self._unary()
        return v

    def _unary(self) -> int:
        tok = self._take()
        if tok == "~":
            return 1 - self._unary()
        if tok == "(":
            v = self._ternary()
            if self._take() != ")":
                raise TechlibError("expected ')'")
            return v
        if tok in ("1'b0", "1'b1"):
            return int(tok[-1])
        if tok in self.env:
            return self.env[tok]
        raise TechlibError(f"unknown name {tok!r}")


def _eval(expr: str, env: dict[str, int]) -> int:
    return _Parser(expr, env).parse()


@dataclass
class _Builder:
    name: str
    kind: str
    inputs: list[str] = field(default_factory=list)
    outputs: list[str] = field(default_factory=list)
    functions: dict[str, str] = field(default_factory=dict)
    sequential: bool = False
    seq_kind: str = ""
    clock: str = ""

    def line(self, text: str) -> None:
        for part in text.split(";"):
            words = part.split()
            if not words:
                continue
            kw = words[0]
            if kw in ("in", "out"):
                if len(words) < 2:
                    raise TechlibError(f"cell {self.name}: '{kw}' line has no port name")
                (self.inputs if kw == "in" else self.outputs).append(words[1])
            elif kw == "fn":
                lhs, _, rhs = part.strip()[2:].partition("=")
                if not lhs.strip() or not rhs.strip():
                    raise TechlibError(f"cell {self.name}: malformed 'fn' line {part.strip()!r}")
                self.functions[lhs.strip()] = rhs.strip()
            elif kw == "seq":
                self.sequential = True
                self._seq(words)
            elif kw == "area":
                continue  # a mapping cost, not used by L0
            else:
                raise TechlibError(f"cell {self.name}: unknown keyword {kw!r}")

    def _seq(self, words: list[str]) -> None:
        edges = {"posedge": "re", "negedge": "fe", "high": "ah", "low": "al"}
        at = words.index("@") if "@" in words else -1
        if at < 0 or len(words) < at + 3 or words[at + 1] not in edges:
            raise TechlibError(f"cell {self.name}: 'seq' line has no '@ edge clock'")
        self.seq_kind = edges[words[at + 1]]
        self.clock = words[at + 2]

    def done(self) -> LibCell:
        return LibCell(
            self.name, self.kind, tuple(self.inputs), tuple(self.outputs),
            dict(self.functions), self.sequential, self.seq_kind, self.clock,
        )


def parse_techlib(text: str) -> TechLib:
    """Parse ``.o3lib`` text (comments start with ``#``)."""
    name = ""
    cells: dict[str, LibCell] = {}
    cur: _Builder | None = None
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        words = line.split()
        if words[0] == "library" and cur is None:
            if len(words) < 2:
                raise TechlibError("malformed 'library' line")
            name = words[1]
        elif words[0] == "cell":
            if len(words) < 3:
                raise TechlibError(f"malformed 'cell' line {line!r}")
            cur = _Builder(words[1], words[2])
        elif cur is None:
            continue
        elif words[0] == "end":
            cells[cur.name] = cur.done()
            cur = None
        else:
            cur.line(line)
    if not name:
        raise TechlibError("no 'library' line")
    return TechLib(name, cells)


def load_techlib(path: Path) -> TechLib:
    """Read a ``.o3lib`` file."""
    return parse_techlib(path.read_text(encoding="utf-8"))
