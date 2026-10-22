"""Build one design's floors into dataset directories (spec 4); ``python -m loki.build``."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import tempfile
import time
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import loki
from loki.anon import Numbering, build_key, number
from loki.blifout import anon_naming, deanonymise, identity_naming, write_blif
from loki.equiv import EquivResult, check_equiv
from loki.extract import Unsupported, extract_netlist
from loki.graph import build_graph
from loki.labels import Label, build_labels, labels_to_csv
from loki.model import Netlist, Snapshot
from loki.odin import OdinSkip, floor_script, odin_module, open_front
from loki.rules import UnlistedWordType, assign_roles
from loki.schemas import FLOORS, SCHEMA, dump_json
from loki.snapshot import take_snapshot
from loki.techlib import TechLib, TechlibError, load_techlib

_HARD_KINDS = ("hard",)  # gates are written as .names, so they need no soft matching
_EQUIV_OK = ("equivalent", "skipped:blackbox-names")


@dataclass(frozen=True)
class FloorResult:
    status: str
    reason: str = ""
    counts: dict[str, int] = field(default_factory=dict)
    equiv: dict[str, EquivResult] = field(default_factory=dict)
    unmatched: int = 0


def common_root(files: Sequence[Path]) -> str:
    """The design root: the common parent directory of the (absolute) files."""
    return os.path.commonpath([str(f.parent) for f in files])


def cmos6_path(odin3_root: Path) -> Path:
    """The six-cell library of floor F3 in an Odin III checkout."""
    return odin3_root / "lib" / "cmos6.o3lib"


def display_script(
    floor: str, files: Sequence[Path], arch_xml: Path | None, cmos6_lib: Path | None = None
) -> list[str]:
    """The script commands for meta.json, without machine paths (spec 6.7)."""
    names = " ".join(f.name for f in files)
    if floor == "f3":
        if cmos6_lib is None:
            raise ValueError("floor f3 needs the cmos6.o3lib path")
        reader = f"read_techlib {cmos6_lib.name}; read_verilog --nolatches --vtr-compat {names}"
    else:
        arch = arch_xml.stem if floor.startswith("f1-") and arch_xml else "<arch>"
        reader = f"read_arch {arch}; read_verilog --nolatches --vtr-compat {names}"
    front, mapping = floor_script(floor, [], Path("x"), cmos6_lib)
    tail = front.split("--vtr-compat", 1)[1].split(";", 1)[1].strip()
    return [reader, *(c.strip() for c in tail.split(";")), *(c.strip() for c in mapping.split(";"))]


def _counts(graph: dict[str, Any]) -> dict[str, int]:
    counts = {k: 0 for k in ("pi", "po", "lut", "ff", "const", "hard")}
    for node in graph["nodes"]:
        counts[node["kind"]] = counts.get(node["kind"], 0) + 1
    counts["nodes"] = len(graph["nodes"])
    counts["edges"] = len(graph["edges"])
    return counts


def _clear_floor(design_dir: Path, floor: str) -> None:
    """Remove the records of an earlier run of this floor: its directory and skipped entry."""
    shutil.rmtree(design_dir / floor, ignore_errors=True)
    path = design_dir / "skipped.json"
    if not path.is_file():
        return
    floors = json.loads(path.read_text(encoding="utf-8")).get("floors", {})
    if floor not in floors:
        return
    del floors[floor]
    if floors:
        path.write_text(dump_json({"schema": SCHEMA, "floors": floors}), encoding="utf-8")
    else:
        path.unlink()


def _write_skipped(design_dir: Path, floor: str, reason: str) -> None:
    """Record a skipped floor in ``<design>/skipped.json`` (floor name -> reason)."""
    path = design_dir / "skipped.json"
    floors: dict[str, str] = {}
    if path.is_file():
        floors = json.loads(path.read_text(encoding="utf-8")).get("floors", {})
    floors[floor] = reason
    design_dir.mkdir(parents=True, exist_ok=True)
    path.write_text(dump_json({"schema": SCHEMA, "floors": floors}), encoding="utf-8")


def _odin_blif(design: Any, tmp: Path, gates: bool) -> str:
    path = tmp / "odin.blif"
    # --gates-as-names is for the plain dialect (refused with --vtr): library gates as .names
    opt = "--gates-as-names" if gates else "--vtr"
    design.run_script(f'write_blif {opt} "{path}"')
    return path.read_text(encoding="utf-8")


def _verilog(blif_path: Path, v_path: Path, arch_xml: Path | None) -> str:
    mod = odin_module()
    design = mod.Design(mod.default())
    pre = f'read_arch "{arch_xml}"; ' if arch_xml else ""
    design.run_script(f'{pre}read_blif "{blif_path}"; write_verilog "{v_path}"')
    return v_path.read_text(encoding="utf-8")


def _equivalences(
    run: _Run, nl: Netlist, num: Numbering, key: dict[str, object], tmp: Path
) -> tuple[dict[str, EquivResult], str, str]:
    ident = write_blif(nl, identity_naming(nl), run.lib)
    anon = write_blif(nl, anon_naming(num, nl), run.lib)
    soft = any(c.kind in _HARD_KINDS for c in nl.cells)
    odin_text = _odin_blif(run.odin, tmp, run.floor == "f3")
    writer = check_equiv(odin_text, ident, run.odin3_root, soft)
    back = check_equiv(ident, deanonymise(anon, key), run.odin3_root, soft)
    return {"writer": writer, "anon": back}, anon, ident


def _equiv_json(results: dict[str, EquivResult], soft: bool) -> dict[str, object]:
    mode = "soft-only" if soft else "full"
    return {
        name: {"status": r.status, "tool_exit": r.tool_exit, "mode": mode}
        for name, r in results.items()
    }


def _write_files(out: Path, floor_files: dict[str, str]) -> None:
    out.mkdir(parents=True, exist_ok=True)
    for name, text in floor_files.items():
        (out / name).write_bytes(text.encode("utf-8"))


def build_floor(
    design: str,
    files: Sequence[Path],
    top: str | None,
    floor: str,
    arch_xml: Path | None,
    out_dir: Path,
    odin3_root: Path,
) -> FloorResult:
    """Run the pipeline of spec 4 for one (design, floor); write ``out_dir/<design>/<floor>``."""
    if floor not in FLOORS:
        raise ValueError(f"unknown floor {floor!r}")
    files = [f.resolve() for f in files]
    design_dir = out_dir / design
    _clear_floor(design_dir, floor)
    cmos6 = cmos6_path(odin3_root) if floor == "f3" else None
    lib: TechLib | None = None
    try:
        if cmos6 is not None:
            if not cmos6.is_file():
                raise OdinSkip(f"missing technology library {cmos6}")
            try:
                lib = load_techlib(cmos6)
            except TechlibError as err:
                raise OdinSkip(f"bad technology library {cmos6}: {err}") from err
        odin, instances = open_front(floor, files, top, arch_xml, cmos6)
    except OdinSkip as skip:
        _write_skipped(design_dir, floor, str(skip))
        return FloorResult("skipped", str(skip))
    snap = take_snapshot(odin, instances)
    try:
        roles = assign_roles(snap.words, snap.po_nets)
    except UnlistedWordType as err:
        return FloorResult("fail", f"fail: {err}")
    odin.run_script(floor_script(floor, files, arch_xml, cmos6)[1])
    try:
        nl = extract_netlist(odin, snap.top, lib)
    except Unsupported as err:
        reason = f"unsupported: {err}"
        _write_skipped(design_dir, floor, reason)
        return FloorResult("skipped", reason)
    run = _Run(design, floor, files, arch_xml, odin3_root, odin, cmos6, lib)
    return _finish(run, nl, snap, roles, design_dir / floor)


@dataclass(frozen=True)
class _Run:
    design: str
    floor: str
    files: Sequence[Path]
    arch_xml: Path | None
    odin3_root: Path
    odin: Any
    cmos6: Path | None = None
    lib: TechLib | None = None


def _finish(
    run: _Run, nl: Netlist, snap: Snapshot, roles: dict[int, str], out: Path
) -> FloorResult:
    num = number(nl)
    labels, word_ids = build_labels(nl, snap, num, roles, common_root(run.files))
    graph, loops = build_graph(nl, labels, num, run.design, run.floor)
    key = build_key(nl, num, run.design, run.floor, word_ids)
    with tempfile.TemporaryDirectory(prefix="loki-build-") as tmpname:
        tmp = Path(tmpname)
        results, anon, _ = _equivalences(run, nl, num, key, tmp)
        (tmp / "netlist.blif").write_text(anon, encoding="utf-8")
        arch = None if run.floor == "f3" else run.arch_xml  # F3 reads no architecture (spec 3)
        verilog = _verilog(tmp / "netlist.blif", tmp / "netlist.v", arch)
    counts = _counts(graph)
    soft = any(c.kind in _HARD_KINDS for c in nl.cells)
    unmatched = sum(1 for lab in labels if _is_unmatched(lab))
    meta = _meta(run, counts, unmatched, loops, results, soft)
    _write_files(
        out,
        {
            "netlist.blif": anon,
            "netlist.v": verilog,
            "graph.json": dump_json(graph),
            "labels.csv": labels_to_csv(labels),
            "key.json": dump_json(key),
            "meta.json": dump_json(meta),
        },
    )
    bad = floor_failures(results)
    if bad:
        reason = f"equivalence failed: {', '.join(bad)}"
        return FloorResult("fail", reason, counts, results, unmatched)
    return FloorResult("ok", "", counts, results, unmatched)


def floor_failures(results: dict[str, EquivResult]) -> list[str]:
    """``name=status`` of every equivalence check that failed the floor (differs or error)."""
    return [f"{n}={r.status}" for n, r in results.items() if r.status in ("differs", "error")]


def _is_unmatched(lab: Label) -> bool:
    return lab.kind not in ("pi", "po") and lab.n_construct_cells == 0


def _meta(
    run: _Run,
    counts: dict[str, int],
    unmatched: int,
    loops: int,
    results: dict[str, EquivResult],
    soft: bool,
) -> dict[str, object]:
    o = odin_module().default()
    return {
        "schema": SCHEMA,
        "design": run.design,
        "floor": run.floor,
        "odin3_version": o.version(),
        "abi_version": o.abi_version(),
        "script": display_script(run.floor, run.files, run.arch_xml, run.cmos6),
        "loki_version": loki.__version__,
        "counts": counts,
        "unmatched": unmatched,
        "loops_cut": loops,
        "equiv": _equiv_json(results, soft),
    }


def _parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="python -m loki.build")
    ap.add_argument("--design", required=True)
    ap.add_argument("--files", nargs="+", required=True)
    ap.add_argument("--top", default="")
    ap.add_argument("--arch-xml", default="")
    ap.add_argument("--floors", required=True, help="comma separated floor names")
    ap.add_argument("--out", required=True)
    return ap


def _metrics(results: dict[str, FloorResult], seconds: float) -> dict[str, object]:
    ok = [r for r in results.values() if r.status == "ok"]
    first = ok[0].counts if ok else {}
    return {
        "nodes": first.get("nodes", 0),
        "luts": first.get("lut", 0),
        "ffs": first.get("ff", 0),
        "hard": first.get("hard", 0),
        "unmatched": sum(r.unmatched for r in ok),
        "skipped_floors": sum(1 for r in results.values() if r.status == "skipped"),
        "equiv_bad": sum(1 for r in ok for e in r.equiv.values() if e.status not in _EQUIV_OK),
        "seconds": round(seconds, 3),
    }


def main(argv: Sequence[str] | None = None) -> int:
    """CLI of spec 8.1. Exit 0 when every floor is ok or skipped, 1 on a fail."""
    args = _parser().parse_args(argv)
    root_env = os.environ.get("ODIN3_ROOT")
    if not root_env:
        print("loki.build: ODIN3_ROOT is not set", file=sys.stderr)
        return 2
    out = Path(args.out)
    arch = Path(args.arch_xml) if args.arch_xml else None
    start = time.monotonic()
    results: dict[str, FloorResult] = {}
    for floor in [f for f in args.floors.split(",") if f]:
        try:
            results[floor] = build_floor(
                args.design, [Path(f) for f in args.files], args.top or None, floor, arch, out,
                Path(root_env),
            )
        except Exception as err:
            results[floor] = FloorResult("fail", f"internal: {type(err).__name__}: {err}")
        res = results[floor]
        print(f"{args.design} {floor}: {res.status} {res.reason}".rstrip())
    out.parent.mkdir(parents=True, exist_ok=True)
    metrics = _metrics(results, time.monotonic() - start)
    (out.parent / "metrics.json").write_text(dump_json(metrics), encoding="utf-8")
    return 1 if any(r.status == "fail" for r in results.values()) else 0


if __name__ == "__main__":
    sys.exit(main())
