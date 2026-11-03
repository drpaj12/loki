"""A LUT-level netlist of the census (Odin III BLIF, nets ``n<k>``) as cells and nets.

Cells are the BLIF logic elements in file order (the cell index of ``ql6-grow`` ``q6_net.Graph``):
``.names`` (a LUT cover; no input = a constant), ``.latch`` (rising-edge flip-flop, one clock) and
``.subckt`` (a hard block; here ``adder``). The top ports of the design come from ``key.json``
(``ports``: the original bit name of each primary input and output net, e.g. ``d[3]``); the prompt
sees those bit names as identifiers (``d_3_``) and every other net as ``w<k>``. No other field of
``key.json`` (names of cells or internal nets) is read.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import q12_env as env

nlm: Any = env.mod("loki.l3.netlist")
NAMED_OUT = {"adder": ("cout", "sumout")}  # hard-block model -> its output pins
ADDER_IN = ("a", "b", "cin")


class Unsupported(ValueError):
    """A BLIF construct the reader does not handle."""


@dataclass
class Cell:
    idx: int
    kind: str  # lut | ff | hard
    ins: list[str]  # nets read as data (a latch: its D net)
    outs: list[str]
    cover: list[str] = field(default_factory=list)  # lut: rows "pattern 1"
    clock: str = ""  # ff
    model: str = ""  # hard
    pins: list[tuple[str, str]] = field(default_factory=list)  # hard: (pin, net)
    cname: str = ""

    @property
    def glue(self) -> bool:
        """A constant or a buffer (``.names a y`` with the row ``1 1``): an ``assign`` of the top
        module, in no block (as the assign and constant cells of the gate netlists in Q-L10)."""
        return self.kind == "lut" and (not self.ins or (len(self.ins) == 1
                                                        and self.cover == ["1 1"]))

    @property
    def reads(self) -> list[str]:
        return self.ins + ([self.clock] if self.clock else [])


@dataclass
class Netlist:
    cells: list[Cell]
    inputs: list[str]  # primary input nets in file order
    outputs: list[str]
    ident: dict[str, str]  # net -> identifier of the prompt
    orig: dict[str, str]  # primary net -> original bit name (the design interface)

    def driver(self) -> dict[str, int]:
        return {o: c.idx for c in self.cells for o in c.outs}

    def logic(self) -> list[int]:
        """Indices of the cells that belong to blocks (not glue)."""
        return [c.idx for c in self.cells if not c.glue]


def sanitize(bit: str) -> str:
    s = re.sub(r"[^A-Za-z0-9_]", "_", bit)
    return s if s and not s[0].isdigit() else "p" + s


def _ident(net: str) -> str:
    m = re.fullmatch(r"n(\d+)", net)
    return f"w{m.group(1)}" if m else "w_" + re.sub(r"[^A-Za-z0-9_]", "_", net)


def parse(text: str, ports: list[dict[str, str]]) -> Netlist:
    cells: list[Cell] = []
    inputs: list[str] = []
    outputs: list[str] = []
    n_models = 0
    for tok in nlm._logical_lines(text):
        head = tok[0]
        n_models += head == ".model"
        if n_models > 1:
            break  # the blackbox models of the hard blocks follow the top model
        if head == ".inputs":
            inputs += tok[1:]
        elif head == ".outputs":
            outputs += tok[1:]
        elif head == ".names":
            cells.append(Cell(len(cells), "lut", tok[1:-1], [tok[-1]]))
        elif head == ".latch":
            if len(tok) < 6 or tok[3] != "re":
                raise Unsupported(f"latch: {' '.join(tok)}")
            cells.append(Cell(len(cells), "ff", [tok[1]], [tok[2]], clock=tok[4]))
        elif head == ".subckt":
            model = tok[1]
            if model not in NAMED_OUT:
                raise Unsupported(f"hard block {model}")
            pins = [(p.partition("=")[0], p.partition("=")[2]) for p in tok[2:]]
            outs = [n for p, n in pins if p in NAMED_OUT[model]]
            ins = [n for p, n in pins if p not in NAMED_OUT[model]]
            cells.append(Cell(len(cells), "hard", ins, outs, model=model, pins=pins))
        elif head == ".cname" and cells:
            cells[-1].cname = tok[1]
        elif cells and cells[-1].kind == "lut" and head[0] in "01-":
            if tok[-1] != "1":
                raise Unsupported("off-set cover row")
            cells[-1].cover.append(" ".join(tok))
        elif head not in (".model", ".end", ".blackbox", ".cname"):
            raise Unsupported(f"line: {' '.join(tok)[:40]}")
    orig = _orig_names(cells, inputs, outputs, ports)
    nets = {n for c in cells for n in c.reads + c.outs} | set(inputs) | set(outputs)
    ident = {n: sanitize(orig[n]) if n in orig else _ident(n) for n in sorted(nets)}
    if len(set(ident.values())) != len(ident):
        raise Unsupported("identifier collision")
    return Netlist(cells, inputs, outputs, ident, orig)


def _orig_names(cells: list[Cell], inputs: list[str], outputs: list[str],
                ports: list[dict[str, str]]) -> dict[str, str]:
    """Original bit name of every primary net. An input port is the input net; an output port is
    the output net itself, or the output of the buffer the BLIF writer puts after a net that is
    also an input or drives several outputs (the k-th output port is the k-th BLIF output)."""
    orig = {p["net"]: p["orig"] for p in ports if p["dir"] == "in" and p["net"] in inputs}
    outp = [p for p in ports if p["dir"] == "out"]
    if len(outp) != len(outputs):
        raise Unsupported("output port count differs from .outputs")
    drv = {o: c for c in cells for o in c.outs}
    for p, o in zip(outp, outputs, strict=True):
        c = drv.get(o)
        if p["net"] != o and not (c is not None and c.kind == "lut" and c.ins == [p["net"]]
                                  and c.cover == ["1 1"]):
            raise Unsupported(f"output {p['orig']} does not match .outputs")
        orig[o] = p["orig"]
    return orig


EXT_PREFIXES = ("picorv32_", "tinyriscv_")


def is_ext(problem: str) -> bool:
    return problem.startswith(EXT_PREFIXES)


def census_dir(endpoint: str, problem: str) -> Path:
    """Directory of the netlist of a problem at an endpoint: the l3-census for a VerilogEval
    problem (design ``ve_<problem>``), this lane's own build for a processor module."""
    cell, floor = env.ENDPOINTS[endpoint]
    if is_ext(problem):
        return env.RUN / "census" / cell / problem / floor
    return env.CENSUS / cell / f"ve_{problem}" / floor


def read(endpoint: str, problem: str) -> Netlist:
    d = census_dir(endpoint, problem)
    key = json.loads((d / "key.json").read_text(encoding="utf-8"))
    return parse((d / "netlist.blif").read_text(encoding="utf-8"), key["ports"])


def blif_path(endpoint: str, problem: str) -> Path:
    return census_dir(endpoint, problem) / "netlist.blif"
