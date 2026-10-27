"""Resolve Loki-internal net names (``$nN``, ``cN``) to wires of the original netlist.

Ported from the reviewer's read-only prototype (``yield.py``, review of dispatch 1, 2026-10-26),
changed to return a mapping and helper-net definitions. Method: evaluate the original netlist and
Loki's re-mapped netlist on the same 512 random vectors (ports and flip-flop outputs are free
inputs, seeded by their shared name); a Loki net whose 512-bit signature equals the signature of an
original wire gets that wire's name. Equal signatures over 512 vectors are a strong, not a
formal, equivalence. A net with no equal wire becomes a helper net ``wK`` (``h`` is taken by claim
ids), defined from the Loki LUT that drives it.

Pure helpers (``bits_of``, ``orig_signatures``, ``expr``) are unit tested; ``loki_names`` needs the
Odin III library (see ``make_hints.py``).
"""

from __future__ import annotations

import importlib
import random
import re
from pathlib import Path
from typing import Any

N = 512
MASK = (1 << N) - 1
_DECL = re.compile(r"^\s*(input|output|wire)\s*(?:\[(\d+):(\d+)\])?\s*([A-Za-z_]\w*)\s*;", re.M)
_INST = re.compile(r"^\s*(NOT|NAND|NOR|BUF|DFFSR|DFF)\s+\S+\s*\((.*?)\);", re.M | re.S)
_PIN = re.compile(r"\.(\w+)\(\s*([^()]*?)\s*\)")
_ASSIGN = re.compile(r"^\s*assign\s+(.*?)=\s*(.*?);", re.M)
_NUM = re.compile(r"(\d+)'([hbd])([0-9a-fA-F]+)")
_VEC = re.compile(r"([A-Za-z_]\w*)\s*\[(\d+):(\d+)\]")
INTERNAL = re.compile(r"^(\$n\d+|c\d+)$")


def vec(name: str) -> int:
    return random.Random("v:" + name).getrandbits(N)


def split_top(text: str) -> list[str]:
    out: list[str] = []
    depth = 0
    cur = ""
    for ch in text:
        depth += ch == "{"
        depth -= ch == "}"
        if ch == "," and depth == 0:
            out.append(cur)
            cur = ""
        else:
            cur += ch
    out.append(cur)
    return out


def decl_bits(name: str, msb: str | None, lsb: str | None) -> list[str]:
    if msb is None or lsb is None:
        return [name]
    lo, hi = sorted((int(msb), int(lsb)))
    return [f"{name}[{i}]" for i in range(lo, hi + 1)]


def bits_of(expr: str) -> list[str]:
    """Bit names of an assign operand, msb first (``{}``, sized constants, ranges, plain names)."""
    expr = expr.strip()
    if expr.startswith("{"):
        out: list[str] = []
        for part in split_top(expr[1:-1]):
            out += bits_of(part)
        return out
    m = _NUM.fullmatch(expr)
    if m:
        base = {"h": 16, "b": 2, "d": 10}[m.group(2)]
        val = int(m.group(3), base)
        return [f"#{(val >> i) & 1}" for i in range(int(m.group(1)) - 1, -1, -1)]
    m = _VEC.fullmatch(expr)
    if m:
        a, b = int(m.group(2)), int(m.group(3))
        step = -1 if a >= b else 1
        return [f"{m.group(1)}[{i}]" for i in range(a, b + step, step)]
    return [expr]


def declared(text: str) -> dict[str, str]:
    """Bit name to kind (``input``/``output``/``wire``); a port wins over its ``wire`` line."""
    decl: dict[str, str] = {}
    for kind, msb, lsb, name in _DECL.findall(text):
        for b in decl_bits(name, msb or None, lsb or None):
            decl[b] = decl[b] if decl.get(b) in ("input", "output") else kind
    return decl


def orig_signatures(text: str) -> dict[str, int]:
    """512-vector signature per original wire; leaves are inputs and DFF Q nets."""
    decl = declared(text)
    val: dict[str, int] = {b: vec(b) for b, k in decl.items() if k == "input"}
    parsed: list[tuple[str, dict[str, str]]] = []
    for typ, body in _INST.findall(text):
        pins = dict(_PIN.findall(body))
        parsed.append((typ, pins))
        if typ.startswith("DFF"):
            val[pins["Q"]] = vec(pins["Q"])
    assigns: list[tuple[str, str]] = []
    for lhs, rhs in _ASSIGN.findall(text):
        left, right = bits_of(lhs), bits_of(rhs)
        if len(left) == len(right):
            assigns += list(zip(left, right, strict=True))
    val["#0"], val["#1"] = 0, MASK
    todo = [p for p in parsed if not p[0].startswith("DFF")]
    for _ in range(len(todo) + len(assigns) + 5):
        progress = False
        for typ, p in todo:
            if p["Y"] in val:
                continue
            ins = [p[k] for k in ("A", "B") if k in p]
            if all(i in val for i in ins):
                a = val[ins[0]]
                b = val[ins[1]] if len(ins) > 1 else 0
                val[p["Y"]] = {"NOT": ~a, "BUF": a, "NAND": ~(a & b), "NOR": ~(a | b)}[typ] & MASK
                progress = True
        for left, right in assigns:
            if left not in val and right in val:
                val[left] = val[right]
                progress = True
        if not progress:
            break
    return val


def _implicants(minterms: set[int], width: int) -> list[tuple[int, int]]:
    """Prime implicants as (value, dash-mask) pairs by Quine-McCluskey merging."""
    cur = {(m, 0) for m in minterms}
    primes: set[tuple[int, int]] = set()
    while cur:
        nxt: set[tuple[int, int]] = set()
        used: set[tuple[int, int]] = set()
        items = sorted(cur)
        for i, (v1, d1) in enumerate(items):
            for v2, d2 in items[i + 1:]:
                diff = v1 ^ v2
                if d1 == d2 and diff and diff & (diff - 1) == 0:
                    nxt.add((v1 & ~diff, d1 | diff))
                    used.update({(v1, d1), (v2, d2)})
        primes |= cur - used
        cur = nxt
    return sorted(primes)


def _covers(imp: tuple[int, int], m: int) -> bool:
    return (m & ~imp[1]) == imp[0]


def expr(table: int, names: list[str]) -> str:
    """A readable expression for a LUT truth table (bit x = output for input pattern x)."""
    width = len(names)
    ons = {x for x in range(1 << width) if (table >> x) & 1}
    if not ons:
        return "0"
    if len(ons) == 1 << width:
        return "1"
    left = set(ons)
    chosen: list[tuple[int, int]] = []
    primes = _implicants(ons, width)
    while left:
        best = max(primes, key=lambda p: (sum(_covers(p, m) for m in left), -bin(p[1]).count("1")))
        chosen.append(best)
        left -= {m for m in left if _covers(best, m)}
    terms = []
    for val, dash in sorted(chosen):
        lits = [names[i] if (val >> i) & 1 else f"NOT({names[i]})"
                for i in range(width) if not (dash >> i) & 1]
        terms.append(lits[0] if len(lits) == 1 else "AND(" + ", ".join(lits) + ")")
    return terms[0] if len(terms) == 1 else "OR(" + ", ".join(terms) + ")"


def order_key(name: str) -> tuple[int, int, str]:
    """``$nN`` by integer first, then ``cN`` by name (stable helper numbering)."""
    if name.startswith("$n") and name[2:].isdigit():
        return 0, int(name[2:]), name
    return 1, 0, name


def loki_graph(scratch: Path, odin: Path) -> Any:
    """Loki's FnGraph of the renamed scratch netlist (needs the Odin III library)."""
    norm = importlib.import_module("loki.re.normalise")
    fng = importlib.import_module("loki.re.fngraph")
    return fng.from_design(norm.load_level0(scratch, "f3", odin, None))


def loki_signatures(graph: Any) -> dict[int, int]:
    """Signature of every Loki net (sources seeded by name, LUTs and constants evaluated)."""
    sim = importlib.import_module("loki.re.sim")
    seed = {net: vec(graph.names.get(net, f"?{net}")) for net in graph.sources()}
    cells = [c for c, x in graph.cells.items() if x.kind in ("lut", "const")]
    return sim.simulate(graph, cells, seed, N)


def resolve(graph: Any, text: str, wanted: set[str]) -> tuple[dict[str, str], dict[str, int]]:
    """Map each wanted Loki name to an original wire; return (mapping, name to Loki net id).

    Preference among equal-signature wires: ports, then flip-flop pins, then sorted names.
    """
    decl = declared(text)
    sig = orig_signatures(text)
    nets = loki_signatures(graph)
    rank = {k: i for i, k in enumerate(("input", "output", "wire"))}
    by_sig: dict[int, list[str]] = {}
    for wire, s in sig.items():
        if wire in decl:
            by_sig.setdefault(s, []).append(wire)
    ids = {nm: net for net, nm in graph.names.items() if nm in wanted}
    mapping: dict[str, str] = {}
    for nm, net in ids.items():
        cands = sorted(by_sig.get(nets.get(net, -1), []),
                       key=lambda w: (rank[decl[w]], w))
        if cands:
            mapping[nm] = cands[0]
    return mapping, ids


def helper_definitions(graph: Any, ids: dict[str, int], mapping: dict[str, str]
                       ) -> tuple[dict[str, str], list[tuple[str, str]]]:
    """Name the unresolved nets ``w1``... and define each from its driving LUT.

    Inputs of a defining LUT that are themselves unresolved become helper nets too (closure).
    Returns (Loki name to helper name, [(helper name, definition)] in numbering order).
    """
    pending = {nm: net for nm, net in ids.items() if nm not in mapping}
    by_id = {net: nm for nm, net in ids.items()}

    def label(net: int) -> str:
        nm = graph.names.get(net, f"n{net}")
        if nm in mapping:
            return mapping[nm]
        if graph.names.get(net) is not None and nm not in pending and not INTERNAL.match(nm):
            return nm
        pending.setdefault(nm, net)
        by_id[net] = nm
        return nm

    defs_in: dict[str, list[str]] = {}
    done: set[str] = set()
    while True:
        todo = sorted((n for n in pending if n not in done), key=order_key)
        if not todo:
            break
        for nm in todo:
            done.add(nm)
            cell = graph.cells.get(graph.driver.get(pending[nm], 0))
            defs_in[nm] = [] if cell is None or cell.kind not in ("lut", "const") \
                else [label(i) for i in cell.ins]
    order = sorted(pending, key=order_key)
    helper = {nm: f"w{i}" for i, nm in enumerate(order, start=1)}
    out: list[tuple[str, str]] = []
    for nm in order:
        cell = graph.cells.get(graph.driver.get(pending[nm], 0))
        if cell is not None and cell.kind in ("lut", "const"):
            args = [helper.get(a, mapping.get(a, a)) for a in defs_in[nm]]
            out.append((helper[nm], expr(cell.table, args)))
        else:
            kind = cell.kind if cell is not None else "source"
            out.append((helper[nm], f"output of a {kind} element Loki does not expand"))
    return helper, out
