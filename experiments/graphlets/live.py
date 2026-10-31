"""Catalogue the precomputed library and run the live path: ``python -B live.py catalog|live ...``.

catalog                      register every width 1..32 instance x cell in the database
live PATTERN VARIANT WIDTH [DEPTH]   build widths above 32 on demand, register with provenance
                             live; the signature is added when the Odin III ``graphlets`` pass is
                             available (``odin_signer``), else the entry is kept without one.
"""

from __future__ import annotations

import importlib
import json
import os
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

HERE = Path(__file__).resolve().parent
WS = Path(os.environ.get("L3_WS", str(HERE.parent.parent.parent.parent)))
OUT = Path(os.environ.get("GLET_OUT", str(WS / "work" / "glet-out")))
os.environ["L3_OUT"] = str(OUT)
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "l3-census"))

import db  # noqa: E402
import gen  # noqa: E402

CELLS = ("O-gate", "O-lut", "O-hard", "Y-gate", "Y-lut")
FLOOR = {"O-gate": "f3", "O-lut": "f2", "O-hard": "f1-k6"}
ODIN = Path(os.environ.get("ODIN3_ROOT", str(WS / "odin3")))
YOSYS = WS / "external" / "yosys" / "build" / "yosys"
DB_PATH = Path(os.environ.get("GLET_DB", str(OUT / "graphlet_library.sqlite")))

Signer = Callable[[Path, str], dict[int, float]]


class PassMissing(RuntimeError):
    """The Odin III ``graphlets`` pass is not available (Loki does not implement it)."""


def odin_signer(netlist: Path, mode: str) -> dict[int, float]:
    """Orbit totals of the netlist from the Odin III ``graphlets`` pass (mode: see sigs.MODES)."""
    try:
        import sigs
    except ImportError as exc:  # pragma: no cover
        raise PassMissing(str(exc)) from exc
    try:
        grp = sigs.signature(netlist, mode)
    except Exception as exc:
        if "graphlets" in str(exc) and "unknown" in str(exc):
            raise PassMissing(str(exc)) from exc
        raise
    return {o: float(v) for o, v in enumerate(grp["orbit_totals"])}


def _run(cmd: list[str]) -> str:
    p = subprocess.run(cmd, capture_output=True, text=True, check=False)
    return p.stdout.strip().splitlines()[0] if p.stdout.strip() else ""


def tool_versions() -> dict[str, str]:
    return {"odin3_commit": _run(["git", "-C", str(ODIN), "rev-parse", "HEAD"]),
            "yosys_version": _run([str(YOSYS), "-V"]),
            "gen_hash": db.sha256_file(HERE / "gen.py")[:16]}


def netlist_of(inst: gen.Inst, cell: str) -> Path:
    base = OUT / "build" / cell / inst.name
    return base / FLOOR[cell] / "netlist.blif" if cell in FLOOR else base / "netlist.blif"


def status_of(inst: gen.Inst, cell: str) -> str:
    sp = OUT / "build" / cell / inst.name / "status.json"
    if not sp.is_file():
        return "missing"
    st = str(json.loads(sp.read_text(encoding="utf-8")).get("status", ""))
    return st if st != "ok" or netlist_of(inst, cell).is_file() else "no-netlist"


def key_of(inst: gen.Inst, cell: str) -> db.Key:
    return db.Key(inst.pattern, inst.variant, inst.width, inst.depth, cell)


def register(con: object, inst: gen.Inst, cell: str, provenance: str,
             ver: dict[str, str]) -> str:
    import sqlite3
    assert isinstance(con, sqlite3.Connection)
    st = status_of(inst, cell)
    db.put_entry(con, key_of(inst, cell), provenance, {
        "rtl_sha256": db.sha256_file(OUT / "rtl" / f"{inst.name}.v"),
        "netlist_sha256": db.sha256_file(netlist_of(inst, cell)), "build_status": st,
        "loki_version": "exp/graphlets-directed", **ver})
    return st


def build_one(inst: gen.Inst, cell: str) -> str:
    """Write the RTL of ``inst`` and synthesise it in ``cell`` (reuses the census builders)."""
    (OUT / "rtl").mkdir(parents=True, exist_ok=True)
    src = OUT / "rtl" / f"{inst.name}.v"
    src.write_text(gen.verilog(inst), encoding="utf-8")
    l3lib = importlib.import_module("l3lib")
    l3lib.manifest = lambda: [{"corpus": "glet", "design": inst.name, "src": str(src),
                               "top": gen.TOP}]
    if cell in FLOOR:
        importlib.import_module("build_odin").main(cell, "")
    else:
        importlib.import_module("build_yosys").main(cell)
    return status_of(inst, cell)


def live_entry(con: object, inst: gen.Inst, cell: str, signer: Signer = odin_signer,
               modes: tuple[str, ...] = ("undirected", "directed")) -> dict[str, str]:
    """Live path: build at the inferred width, cache entry (+ signature if the pass exists)."""
    import sqlite3
    assert isinstance(con, sqlite3.Connection)
    ver = tool_versions()
    st = build_one(inst, cell)
    register(con, inst, cell, "live", ver)
    res = {"build": st, "signature": "none"}
    if st != "ok":
        return res
    for m in modes:
        try:
            sig = signer(netlist_of(inst, cell), m)
        except PassMissing as e:
            res["signature"] = f"pending: {e}"
            continue
        db.put_signature(con, key_of(inst, cell), "live", m, sig,
                         input_sha256=db.sha256_file(netlist_of(inst, cell)),
                         tool_commit=ver["odin3_commit"], script_hash=ver["gen_hash"],
                         measurer_version="graphlets-pass", origin=f"rtl/{inst.name}.v")
        res["signature"] = "stored"
    return res


def main(argv: list[str]) -> int:
    con = db.open_db(DB_PATH)
    if argv[0] == "catalog":
        ver = tool_versions()
        counts: dict[tuple[str, str], int] = {}
        for inst in gen.instances():
            for cell in CELLS:
                st = register(con, inst, cell, "precomputed", ver)
                ck = (inst.pattern, f"{cell}:{st}")
                counts[ck] = counts.get(ck, 0) + 1
        for (pat, cs), n in sorted(counts.items()):
            print(pat, cs, n)
        return 0
    pat, var, w = argv[1], argv[2], int(argv[3])
    depth = int(argv[4]) if len(argv) > 4 else 0
    inst = gen.Inst(pat, var, w, depth)
    for cell in CELLS:
        print(inst.name, cell, live_entry(con, inst, cell))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
