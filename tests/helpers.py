"""Shared test helpers: Odin III availability and location."""

from __future__ import annotations

import importlib
import os
import shutil
from pathlib import Path

from loki.anon import build_key, number
from loki.blifout import anon_naming, write_blif
from loki.graph import build_graph
from loki.labels import build_labels, labels_to_csv
from loki.model import FinalCell, Net, Netlist, Port, PortBit, Snapshot, Span
from loki.schemas import dump_json


def odin_available() -> bool:
    """True when the odin3 module imports and the shared library loads."""
    try:
        mod = importlib.import_module("odin3")
        mod.Odin3()
    except Exception:
        return False
    return True


def odin3_root() -> Path | None:
    """The Odin III checkout from $ODIN3_ROOT, or None when it lacks equiv-check."""
    raw = os.environ.get("ODIN3_ROOT")
    if not raw:
        return None
    root = Path(raw)
    if not (root / "tools" / "equiv-check" / "equiv-check").is_file():
        return None
    return root


def lut_cell(
    cid: int, ins: list[int], out: int, table: str, spans: tuple[Span, ...] = ()
) -> FinalCell:
    """A hand-built $lut cell."""
    return FinalCell(
        id=cid, kind="lut", type="$lut", name="", params={"WIDTH": len(ins), "LUT": table},
        spans=spans, inputs=(Port("A", len(ins), tuple(ins)),), outputs=(Port("Y", 1, (out,)),),
    )


def and_netlist() -> Netlist:
    """PIs A[0], A[1]; one AND LUT; PO X."""
    nets = {i: Net(i, ()) for i in (1, 2, 3)}
    pbs = (PortBit("A[0]", "in", 1), PortBit("A[1]", "in", 2), PortBit("X", "out", 3))
    return Netlist("t", nets, (lut_cell(10, [1, 2], 3, "1000"),), pbs)


DATA = Path(__file__).resolve().parent / "data"


def vtr_arch(name: str = "k6_frac_N10_frac_chain_mem32K_40nm") -> Path | None:
    """The VPR architecture xml under $VTR_ROOT, or None."""
    raw = os.environ.get("VTR_ROOT")
    if not raw:
        return None
    path = Path(raw) / "vtr_flow" / "arch" / "timing" / f"{name}.xml"
    return path if path.is_file() else None


def micro(name: str) -> Path:
    """A micro benchmark of the Odin III checkout ($ODIN3_ROOT)."""
    root = odin3_root()
    if root is None:
        raise FileNotFoundError("ODIN3_ROOT")
    return root / "tests" / "micro" / "verilog" / "micro" / f"{name}.v"


def f2_arch() -> Path | None:
    """The VPR architecture for soft-logic floors: the VTR one, else Odin III's placeholder.

    Floor F2 only records the path (Odin III does no VPR XML import), so the placeholder under
    ``$ODIN3_ROOT/tests/golden`` serves when VTR is absent (CI).
    """
    real = vtr_arch()
    if real is not None:
        return real
    root = odin3_root()
    if root is None:
        return None
    path = root / "tests" / "golden" / "projects" / "odin2_arch" / "arch" / "k6_tiny.xml"
    return path if path.is_file() else None


def can_run_flow() -> bool:
    """Odin III, ABC for equiv-check and a real VTR architecture (hard floors, acceptance)."""
    root = odin3_root()
    return odin_available() and root is not None and abc_available(root) and vtr_arch() is not None


def abc_available(root: Path) -> bool:
    """True when equiv-check under root can find ABC (its own search order, equiv_check.py)."""
    env = os.environ.get("ODIN3_ABC")
    if env:
        return os.access(env, os.X_OK)
    if any(os.access(p, os.X_OK) for p in root.glob("build/*/third_party/abc/abc")):
        return True
    vtr = os.environ.get("VTR_ROOT")
    if vtr and os.access(Path(vtr) / "build" / "abc" / "abc", os.X_OK):
        return True
    return shutil.which("abc") is not None


def can_run_f2() -> bool:
    """Odin III binding, its checkout with ABC for equiv-check, and an F2 architecture file."""
    root = odin3_root()
    return odin_available() and root is not None and abc_available(root) and f2_arch() is not None


def have_f3() -> bool:
    """Odin III, ABC, ``lib/cmos6.o3lib`` and the gate-mapping passes of F3."""
    root = odin3_root()
    if root is None or not odin_available() or not abc_available(root):
        return False
    if not (root / "lib" / "cmos6.o3lib").is_file():
        return False
    try:
        passes = set(importlib.import_module("odin3").default().passes())
    except Exception:
        return False
    return {"read_techlib", "dfflibmap"} <= passes


def fake_netlist() -> Netlist:
    """PIs A[0], A[1]; one AND LUT; PO X; the ports carry spans like real ones."""
    span = (Span("/p/d.v", 1, 1, 1, 9),)
    nets = {i: Net(i, ()) for i in (1, 2, 3)}
    pbs = (
        PortBit("A[0]", "in", 1, span),
        PortBit("A[1]", "in", 2, span),
        PortBit("X", "out", 3, span),
    )
    return Netlist("top", nets, (lut_cell(10, [1, 2], 3, "1000"),), pbs)


def write_fake_floor(root: Path, design: str, floor: str) -> Path:
    """Write the six files of a floor directory from a hand-built netlist; returns its path."""
    nl = fake_netlist()
    num = number(nl)
    labels, word_ids = build_labels(nl, Snapshot((), (), "top"), num, {}, "/p")
    graph, loops = build_graph(nl, labels, num, design, floor)
    meta = {
        "schema": 1, "design": design, "floor": floor, "odin3_version": "1.0.0", "abi_version": 5,
        "script": ["lower"], "loki_version": "0.1.0", "loops_cut": loops, "unmatched": 1,
        "counts": {"nodes": 4, "pi": 2, "po": 1, "lut": 1, "ff": 0, "const": 0, "hard": 0,
                   "edges": 3},
        "equiv": {"writer": {"status": "equivalent", "tool_exit": 0, "mode": "full"}},
    }
    out = root / design / floor
    out.mkdir(parents=True, exist_ok=True)
    files = {
        "netlist.blif": write_blif(nl, anon_naming(num, nl)),
        "netlist.v": "module top();\nendmodule\n",
        "graph.json": dump_json(graph),
        "labels.csv": labels_to_csv(labels),
        "key.json": dump_json(build_key(nl, num, design, floor, word_ids)),
        "meta.json": dump_json(meta),
    }
    for name, text in files.items():
        (out / name).write_text(text, encoding="utf-8")
    return out
