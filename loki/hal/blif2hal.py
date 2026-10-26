"""BLIF to HAL structural Verilog for the L0 floors f2 (LUT6) and f3 (cmos6).

Every ``.names`` and ``.latch`` becomes one instance of a cell of the matching ``.hgl`` library
(``loki.hal.hgl``). The instance name is the ``.cname`` node id of the L0 answer key, so a HAL
gate name is an L0 node id. A cell without a ``.cname`` gets ``_c<index>``. Nets keep their BLIF
names (``n<k>``). ``python -m loki.hal.blif2hal --floor f2 netlist.blif out.v``.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from loki.hal.blif import IDENT, Blif, BlifError, Gate, Latch, Subckt, read_blif

FLOORS = {"f2": "lut6", "f3": "cmos6"}
CMOS_TABLES = {(1, 0b10): "BUF", (1, 0b01): "INV", (2, 0b0111): "NAND2", (2, 0b0001): "NOR2"}


class ConvertError(ValueError):
    """The netlist has a cell the floor's library cannot express."""


def _name(cell_name: str, index: int) -> str:
    return cell_name if cell_name else f"_c{index}"


def _gate_f2(g: Gate, inst: str) -> str:
    k = len(g.inputs)
    if k == 0:
        cell = "VCC" if g.table() else "GND"
        return f"  {cell} {inst} (.O({g.output}));"
    if k > 6:
        raise ConvertError(f"{g.output}: {k}-input cover, the f2 floor has LUT1..LUT6")
    width = 1 << k
    init = f"{width}'h{g.table():0{(width + 3) // 4}X}"
    pins = ", ".join(f".I{j}({n})" for j, n in enumerate(g.inputs))
    return f"  LUT{k} #(.INIT({init})) {inst} ({pins}, .O({g.output}));"


def _gate_f3(g: Gate, inst: str) -> str:
    k = len(g.inputs)
    if k == 0:
        cell = "VCC" if g.table() else "GND"
        return f"  {cell} {inst} (.O({g.output}));"
    found = CMOS_TABLES.get((k, g.table()))
    if found is None:
        raise ConvertError(f"{g.output}: cover is not BUF, INV, NAND2 or NOR2 (cmos6 floor)")
    cell = found
    pins = ", ".join(f".{p}({n})" for p, n in zip("AB", g.inputs, strict=False))
    return f"  {cell} {inst} ({pins}, .Y({g.output}));"


def _latch(lt: Latch, inst: str, cell: str) -> str:
    if lt.kind != "re":
        raise ConvertError(f"{lt.q}: latch type {lt.kind!r}, only rising-edge flip-flops")
    param = f" #(.INIT(1'b{lt.init}))" if lt.init in ("0", "1") else ""
    return f"  {cell}{param} {inst} (.C({lt.clock}), .D({lt.d}), .Q({lt.q}));"


def _subckt(s: Subckt, inst: str, floor: str) -> str:
    if floor != "f3" or s.model != "DFFSR":
        raise ConvertError(f"unsupported .subckt {s.model} on floor {floor}")
    pins = dict(s.pins)
    if set(pins) != {"C", "D", "S", "R", "Q"}:
        raise ConvertError(f"DFFSR pins {sorted(pins)}")
    conn = ", ".join(f".{p}({pins[p]})" for p in ("C", "D", "S", "R", "Q"))
    return f"  DFFSR {inst} ({conn});"


def _nets(b: Blif) -> list[str]:
    ports = set(b.inputs) | set(b.outputs)
    seen: dict[str, None] = {}
    for c in b.cells:
        if isinstance(c, Gate):
            names = (*c.inputs, c.output)
        elif isinstance(c, Latch):
            names = (c.d, c.q, c.clock)
        else:
            names = tuple(n for _, n in c.pins)
        for n in names:
            if n not in ports:
                seen.setdefault(n)
    return list(seen)


def convert(b: Blif, floor: str) -> str:
    """The structural Verilog of ``b`` for ``floor`` (``f2`` or ``f3``)."""
    if floor not in FLOORS:
        raise ConvertError(f"floor {floor!r}: expected f2 or f3")
    names = [b.model, *b.inputs, *b.outputs, *_nets(b)]
    bad = [n for n in names if not IDENT.match(n)]
    if bad:
        raise ConvertError(f"names that are not plain Verilog identifiers: {bad[:3]}")
    flop = "FF" if floor == "f2" else "DFF"
    lines = [f"module {b.model} ({', '.join([*b.inputs, *b.outputs])});"]
    lines += [f"  input {n};" for n in b.inputs] + [f"  output {n};" for n in b.outputs]
    lines += [f"  wire {n};" for n in _nets(b)]
    used = {c.cname for c in b.cells if c.cname}
    if len(used) != len([c for c in b.cells if c.cname]):
        raise ConvertError("duplicate .cname")
    for i, c in enumerate(b.cells):
        inst = _name(c.cname, i)
        if isinstance(c, Gate):
            lines.append(_gate_f2(c, inst) if floor == "f2" else _gate_f3(c, inst))
        elif isinstance(c, Latch):
            lines.append(_latch(c, inst, flop))
        else:
            lines.append(_subckt(c, inst, floor))
    lines.append("endmodule")
    return "\n".join(lines) + "\n"


def convert_file(blif: Path, floor: str) -> str:
    try:
        return convert(read_blif(blif), floor)
    except BlifError as exc:
        raise ConvertError(str(exc)) from exc


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="loki.hal.blif2hal", description=__doc__)
    ap.add_argument("--floor", choices=sorted(FLOORS), required=True)
    ap.add_argument("blif", type=Path)
    ap.add_argument("out", type=Path)
    args = ap.parse_args(argv)
    try:
        text = convert_file(args.blif, args.floor)
    except ConvertError as exc:
        sys.stderr.write(f"blif2hal: {args.blif}: {exc}\n")
        return 1
    args.out.write_text(text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
