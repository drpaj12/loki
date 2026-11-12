"""The extracted cell netlist ("gds" endpoint) as a Loki L0 netlist: a BLIF and a label file.

Connectivity: the hierarchical Magic SPICE of the flow (``ext_hier.spice``: one ``X`` instance per
standard cell, nets named by Magic, no Odin III name). Cell functions: the sky130 library data
``lib/sky130hd.o3lib`` (sum-of-products ``fn`` lines, flip-flop ``seq`` line); a resized master
(``_2``, ``_4`` ...) takes the function of its ``_1`` cell; buffers (``buf``, ``clkbuf``,
``dlygate`` ...) and inverters (``inv``, ``clkinv``) by name. Cells with no signal pin (tap, fill,
decap) are not in the netlist. Written BLIF: one ``.names`` per output pin (``.latch`` for the
flip-flop), ``.cname`` = the extracted cell's ``ext_id``, nets ``n<k>``.

Labels (the answer key): per cell, from the provenance chain of its ``extracted`` object
(``ql13_chain.full_chain``, never guessed): the first source span of its own ``gates`` object
(HDL line and column); a cell with no chain is ``unknown``.
"""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from pathlib import Path

import ql13_chain as ch
import ql13_env as env

from loki.prov_steps import ProvRun

POWER = {"VGND", "VPWR", "VPB", "VNB", "VDD", "VSS"}
BUF_RE = re.compile(r"__(clkbuf|buf|dlygate|dlymetal|clkdlybuf)\d*[a-z]*_\d+$")
INV_RE = re.compile(r"__(inv|clkinv|clkinvlp)_\d+$")
DRIVE_RE = re.compile(r"_\d+$")
LIBCELL_RE = re.compile(r"^cell (\S+) gate")


class Unsupported(ValueError):
    """A master or a SPICE line the converter does not handle."""


@dataclass
class LibCell:
    ins: list[str]
    outs: list[str]
    fn: dict[str, str]  # output pin -> sum-of-products text
    seq: bool = False
    clock: str = ""


def read_lib(path: Path | None = None) -> dict[str, LibCell]:
    lib: dict[str, LibCell] = {}
    cur: LibCell | None = None
    name = ""
    lib_path = path or (env.ODIN / "lib" / "sky130hd.o3lib")
    for line in lib_path.read_text(encoding="utf-8").splitlines():
        m = LIBCELL_RE.match(line)
        if m:
            name, cur = m.group(1), LibCell([], [], {})
            lib[name] = cur
        elif cur is not None and line.startswith("  in "):
            for part in line.strip().split(";"):
                tok = part.split()
                if tok[:1] == ["in"]:
                    cur.ins.append(tok[1])
                    if "clock" in tok:
                        cur.clock = tok[1]
                elif tok[:1] == ["out"]:
                    cur.outs.append(tok[1])
        elif cur is not None and line.startswith("  fn "):
            pin, _, expr = line.strip()[3:].partition("=")
            cur.fn[pin.strip()] = expr.strip()
        elif cur is not None and line.startswith("  seq "):
            cur.seq = True
    return lib


def cover(expr: str, ins: list[str]) -> list[str]:
    """ON-set rows ("pattern 1") of a sum of products over the inputs ``ins``."""
    rows: list[str] = []
    for term in expr.split("|"):
        pat = ["-"] * len(ins)
        for lit in term.replace("(", " ").replace(")", " ").split("&"):
            tok = lit.split()
            if not tok:
                continue
            neg = tok[0] == "~"
            var = tok[-1]
            if var not in ins:
                raise Unsupported(f"literal {lit.strip()!r}")
            pat[ins.index(var)] = "0" if neg else "1"
        rows.append("".join(pat) + " 1")
    return rows


def logical_lines(text: str) -> list[list[str]]:
    out: list[list[str]] = []
    for raw in text.splitlines():
        if raw.startswith("+") and out:
            out[-1] += raw[1:].split()
        elif raw.strip() and not raw.startswith("*"):
            out.append(raw.split())
    return out


@dataclass
class Inst:
    ext_id: str
    master: str
    nets: list[str]


def read_spice(path: Path) -> tuple[str, list[str], dict[str, list[str]], list[Inst]]:
    """(top name, top ports, master -> pin order, instances of the top)."""
    pins: dict[str, list[str]] = {}
    top, top_ports = "", []
    insts: list[Inst] = []
    in_top = False
    for tok in logical_lines(path.read_text(encoding="utf-8")):
        if tok[0] == ".subckt":
            pins[tok[1]] = tok[2:]
            in_top = not tok[1].startswith("sky130_fd_sc_hd__")
            if in_top:
                top, top_ports = tok[1], tok[2:]
        elif tok[0] == ".ends":
            in_top = False
        elif in_top and tok[0][0] == "X":
            insts.append(Inst(tok[0][1:], tok[-1], tok[1:-1]))
    return top, top_ports, pins, insts


def lib_cell(lib: dict[str, LibCell], master: str, pins: list[str]) -> tuple[str, LibCell]:
    """(kind, library cell) of a master: ``lut``, ``ff`` or ``buf``/``inv`` (synthesised)."""
    if master in lib:
        return ("ff" if lib[master].seq else "lut"), lib[master]
    sig = [p for p in pins if p not in POWER]
    if BUF_RE.search(master) and len(sig) == 2:
        out = "X" if "X" in sig else sig[-1]
        i = next(p for p in sig if p != out)
        return "lut", LibCell([i], [out], {out: i})
    if INV_RE.search(master) and len(sig) == 2:
        out = "Y" if "Y" in sig else sig[-1]
        i = next(p for p in sig if p != out)
        return "lut", LibCell([i], [out], {out: f"~ {i}"})
    base = DRIVE_RE.sub("_1", master)
    if base in lib:
        return ("ff" if lib[base].seq else "lut"), lib[base]
    raise Unsupported(f"master {master}")


def convert(spice: Path, lib: dict[str, LibCell]) -> tuple[str, list[dict[str, str]],
                                                           dict[str, str]]:
    """(BLIF text, ports for ``q12_nl.parse``, cell name -> kind). Raises ``Unsupported``."""
    top, top_ports, pins, insts = read_spice(spice)
    ids: dict[str, str] = {}

    def net(n: str) -> str:
        if n not in ids:
            ids[n] = f"n{len(ids)}"
        return ids[n]

    cells: list[str] = []
    kinds: dict[str, str] = {}
    driven: set[str] = set()
    read: set[str] = set()
    for ins in insts:
        order = pins.get(ins.master)
        if order is None or len(order) != len(ins.nets):
            raise Unsupported(f"instance {ins.ext_id}: pin list of {ins.master}")
        pin_net = dict(zip(order, ins.nets, strict=True))
        sig = {p: n for p, n in pin_net.items() if p not in POWER}
        if not sig:
            continue  # tap, fill, decap
        if ins.master.endswith("conb_1"):
            for pin, n in sig.items():
                cells.append(f".names {net(n)}\n{'1' if pin == 'HI' else ''}".rstrip("\n")
                             + f"\n.cname {ins.ext_id}_{pin}")  # HI and LO: two BLIF cells
                driven.add(n)
            kinds[ins.ext_id] = "const"
            continue
        kind, lc = lib_cell(lib, ins.master, order)
        kinds[ins.ext_id] = "ff" if kind == "ff" else "lut"
        for o in lc.outs:
            if o not in sig:
                continue
            driven.add(sig[o])
            if kind == "ff":
                cells.append(f".latch {net(sig['D'])} {net(sig[o])} re {net(sig[lc.clock])} 3\n"
                             f".cname {ins.ext_id}")
                read.update((sig["D"], sig[lc.clock]))
            else:
                rows = cover(lc.fn[o], lc.ins)
                read.update(sig[i] for i in lc.ins)
                cells.append(f".names {' '.join(net(sig[i]) for i in lc.ins)} {net(sig[o])}\n"
                             + "\n".join(rows) + f"\n.cname {ins.ext_id}")
    port_nets = [p for p in top_ports if p not in POWER]
    outs = [p for p in port_nets if p in driven]
    inputs = [p for p in port_nets if p not in driven]
    for p in port_nets:
        net(p)
    text = (f".model top\n.inputs {' '.join(net(p) for p in inputs)}\n"
            f".outputs {' '.join(net(p) for p in outs)}\n" + "\n".join(cells) + "\n.end\n")
    ports = ([{"net": net(p), "orig": p, "dir": "in"} for p in inputs]
             + [{"net": net(p), "orig": p, "dir": "out"} for p in outs])
    return text, ports, kinds


def labels(run: ProvRun, kinds: dict[str, str]) -> list[dict[str, str]]:
    """Answer key per netlist cell from the chain of its extracted object."""
    rows: list[dict[str, str]] = []
    for obj in run.stage_objects("extracted"):
        ext_id = str(obj.attrs.get("ext_id", ""))
        if ext_id not in kinds:
            continue
        cls = ch.cell_class(run, obj)
        c = ch.full_chain(run, obj, cls)
        line = col = ""
        if c.reached and c.own_span:
            line, _, rest = c.own_span.partition(".")
            col = rest.partition("-")[0]
        rows.append({"node_id": ext_id, "kind": kinds[ext_id], "cls": cls,
                     "construct_type": "hdl" if line else "unknown", "hdl_line": line,
                     "hdl_col": col})
    return rows


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["node_id", "kind", "cls", "construct_type", "hdl_line",
                                           "hdl_col"])
        w.writeheader()
        w.writerows(rows)
