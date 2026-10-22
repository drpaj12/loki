"""Assemble finished Wyrd runs into ``dataset/``; manifest, split and invariants (spec 8.3, 10)."""

from __future__ import annotations

import csv
import io
import json
import re
import shutil
import sqlite3
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import loki
from loki.bench import VERILOG_EVAL
from loki.schemas import (
    FLOORS,
    SCHEMA,
    SPLIT_SEED,
    dump_json,
    equiv_warnings,
    short_arch,
    split_of,
    validate_design,
    validate_graph,
    validate_key,
    validate_labels_csv,
    validate_manifest,
    validate_meta,
    validate_words,
)

FLOOR_FILES = ("netlist.blif", "netlist.v", "graph.json", "labels.csv", "key.json", "meta.json",
               "words.json")
SPLIT_RULE = "sha256(seed + ':' + design) first 8 bytes, big-endian, mod 100 < 80 is train"
_NAME = re.compile(r"^n[0-9]+$")
_STEP_GLOB = "*-loki-dataset"


@dataclass
class DesignEntry:
    benchmark: str
    floors: dict[str, dict[str, object]] = field(default_factory=dict)


def benchmark_of(design: str) -> str:
    """The benchmark a design id belongs to (``micro_``, ``ve_`` or ``vtr_`` prefix)."""
    for prefix, name in (("micro_", "micro"), ("ve_", "verilog-eval"), ("vtr_", "vtr")):
        if design.startswith(prefix):
            return name
    return "micro"


def build_manifest(
    designs: Mapping[str, DesignEntry], odin3_version: str = ""
) -> dict[str, object]:
    """The manifest.json object (spec 6.9): designs sorted by id, floors by name."""
    entries = [
        {
            "design": name,
            "benchmark": entry.benchmark,
            "split": split_of(name),
            "floors": {f: entry.floors[f] for f in sorted(entry.floors)},
        }
        for name, entry in sorted(designs.items())
    ]
    manifest: dict[str, object] = {
        "schema": SCHEMA,
        "created_by": f"loki {loki.__version__}",
        "odin3_version": odin3_version,
        "split_seed": SPLIT_SEED,
        "split_rule": SPLIT_RULE,
        "designs": entries,
    }
    if any(e.benchmark == "verilog-eval" for e in designs.values()):
        manifest["sources"] = {"verilog-eval": dict(VERILOG_EVAL)}
    return manifest


def _runs(project: Path) -> list[tuple[str, str, str, str, Path]]:
    db = project / "wyrd.db"
    if not db.is_file():
        raise ValueError(f"{db} does not exist")
    con = sqlite3.connect(db)
    try:
        rows = con.execute(
            "SELECT key, design, arch, status, run_dir FROM runs ORDER BY design, arch, key"
        ).fetchall()
    finally:
        con.close()
    out = []
    for key, design, arch, status, run_dir in rows:
        path = Path(str(run_dir))
        out.append((str(key), str(design), str(arch), str(status), path if path.is_absolute()
                    else project / path))
    return out


def _dataset_dirs(run_dir: Path) -> list[Path]:
    return sorted(run_dir.glob(_STEP_GLOB))


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _floor_files(floor_dir: Path) -> dict[str, bytes]:
    return {n: (floor_dir / n).read_bytes() for n in FLOOR_FILES}


@dataclass
class _Source:
    arch: str
    design_dir: Path


def _ok_sources(
    project: Path,
) -> tuple[dict[str, list[_Source]], dict[str, list[tuple[str, str]]]]:
    """Per design: dataset dirs of ok runs (arch order), and (arch, message) of runs not ok."""
    ok: dict[str, list[_Source]] = {}
    bad: dict[str, list[tuple[str, str]]] = {}
    for key, design, arch, status, run_dir in _runs(project):
        steps = _dataset_dirs(run_dir)
        if status == "ok" and steps:
            ok.setdefault(design, []).append(_Source(arch, steps[0] / "dataset" / design))
        elif status != "ok":
            bad.setdefault(design, []).append((arch, f"run {key[:12]} ({arch}) status {status}"))
    for srcs in ok.values():
        srcs.sort(key=lambda s: s.arch)
    return ok, bad


def _floors_of(src: _Source) -> list[str]:
    if not src.design_dir.is_dir():
        return []
    return sorted(p.name for p in src.design_dir.iterdir() if p.is_dir())


def _skipped(src: _Source) -> dict[str, str]:
    path = src.design_dir / "skipped.json"
    if not path.is_file():
        return {}
    floors = _read_json(path).get("floors", {})
    return {str(k): str(v) for k, v in floors.items()}


def _arch_dependent(floor: str) -> bool:
    return floor.startswith("f1-")


def _gather(sources: list[_Source]) -> tuple[dict[str, Path], dict[str, str]]:
    """Floor dirs to copy and skipped reasons for one design (f2/f3 from the first arch)."""
    chosen: dict[str, Path] = {}
    skipped: dict[str, str] = {}
    for src in sources:
        for floor in _floors_of(src):
            if floor not in chosen:
                chosen[floor] = src.design_dir / floor
            elif not _arch_dependent(floor) and _floor_files(chosen[floor]) != _floor_files(
                src.design_dir / floor
            ):
                raise ValueError(f"{floor} differs between architectures ({src.arch})")
        for floor, reason in _skipped(src).items():
            skipped.setdefault(floor, reason)
    for floor in chosen:
        skipped.pop(floor, None)
    return chosen, skipped


def _nodes_of(floor_dir: Path) -> int:
    meta = _read_json(floor_dir / "meta.json")
    return int(meta["counts"]["nodes"])


def _record_failures(entry: DesignEntry, failed: list[tuple[str, str]]) -> None:
    """A run that is not ok fails the floors of its architecture that no ok run supplied."""
    for arch, message in failed:
        for floor in (f"f1-{short_arch(arch)}", "f2"):
            if floor not in entry.floors:
                entry.floors[floor] = {"status": "fail", "message": message}


def assemble(project: Path, out: Path) -> dict[str, object]:
    """Copy the floors of ok runs into ``out`` and write ``manifest.json``; returns it."""
    ok, bad = _ok_sources(project)
    if out.exists() and any(out.iterdir()):
        if not (out / "manifest.json").is_file():
            raise ValueError(f"{out} is not empty and holds no manifest.json")
        shutil.rmtree(out)
    out.mkdir(parents=True, exist_ok=True)
    entries: dict[str, DesignEntry] = {}
    version = ""
    for design in sorted(set(ok) | set(bad)):
        entry = DesignEntry(benchmark_of(design))
        chosen, skipped = _gather(ok.get(design, []))
        if design in ok:
            _copy_design(project, out, design, chosen)
        for floor, src_dir in chosen.items():
            entry.floors[floor] = {"status": "ok", "nodes": _nodes_of(src_dir)}
            version = version or str(_read_json(src_dir / "meta.json")["odin3_version"])
        for floor, reason in skipped.items():
            entry.floors[floor] = {"status": "skipped", "reason": reason}
        _record_failures(entry, bad.get(design, []))
        entries[design] = entry
    manifest = build_manifest(entries, version)
    (out / "manifest.json").write_text(dump_json(manifest), encoding="utf-8")
    return manifest


def _copy_design(project: Path, out: Path, design: str, chosen: dict[str, Path]) -> None:
    ddir = out / design
    ddir.mkdir(parents=True)
    spec = project / "designs" / design / "design.json"
    if not spec.is_file():
        raise ValueError(f"{spec} does not exist")
    shutil.copyfile(spec, ddir / "design.json")
    for floor, src in sorted(chosen.items()):
        shutil.copytree(src, ddir / floor)


# --- loki check -------------------------------------------------------------------------------


def _load(path: Path, errs: list[str]) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as err:
        errs.append(f"{path}: cannot read ({err})")
        return None


def _prefixed(errs: list[str], where: str, new: list[str]) -> None:
    errs.extend(f"{where}: {e}" for e in new)


def check_dataset(root: Path) -> list[str]:
    """Errors against the schemas and the invariants of spec 10; empty when the dataset is valid."""
    errs: list[str] = []
    manifest = _load(root / "manifest.json", errs)
    if manifest is None:
        return errs
    _prefixed(errs, "manifest.json", validate_manifest(manifest))
    listed = {d["design"]: d for d in manifest.get("designs", []) if isinstance(d, dict)}
    present = {p.name for p in root.iterdir() if p.is_dir()}
    for name in sorted(present - set(listed)):
        errs.append(f"{name}: design directory is not in the manifest")
    for name in sorted(set(listed) - present):
        if any(f.get("status") == "ok" for f in listed[name].get("floors", {}).values()):
            errs.append(f"{name}: listed as ok but has no directory")
    for name in sorted(present & set(listed)):
        _check_design(root / name, listed[name], errs)
    return errs


def dataset_warnings(root: Path) -> list[str]:
    """Equivalence entries that are unproven or skipped (spec 9), as ``design/floor: ...``."""
    out: list[str] = []
    for meta in sorted(root.glob("*/*/meta.json")):
        try:
            data = json.loads(meta.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        out += [f"{meta.parent.parent.name}/{meta.parent.name}: {w}" for w in equiv_warnings(data)]
    return out


def _check_design(ddir: Path, entry: dict[str, Any], errs: list[str]) -> None:
    name = ddir.name
    if entry.get("split") != split_of(name):
        errs.append(f"{name}: split {entry.get('split')!r} differs from the split rule")
    spec = _load(ddir / "design.json", errs)
    if spec is not None:
        _prefixed(errs, f"{name}/design.json", validate_design(spec))
    floors = {p.name for p in ddir.iterdir() if p.is_dir()}
    for floor in sorted(floors):
        info = entry.get("floors", {}).get(floor)
        if floor not in FLOORS or info is None or info.get("status") != "ok":
            errs.append(f"{name}/{floor}: floor directory is not an ok floor of the manifest")
            continue
        _check_floor(ddir / floor, errs)
    for floor, info in entry.get("floors", {}).items():
        if info.get("status") == "ok" and floor not in floors:
            errs.append(f"{name}/{floor}: ok floor has no directory")


def _check_floor(fdir: Path, errs: list[str]) -> None:
    where = f"{fdir.parent.name}/{fdir.name}"
    missing = [n for n in FLOOR_FILES if not (fdir / n).is_file()]
    if missing:
        errs.append(f"{where}: missing files {missing}")
        return
    graph = _load(fdir / "graph.json", errs)
    key = _load(fdir / "key.json", errs)
    meta = _load(fdir / "meta.json", errs)
    words = _load(fdir / "words.json", errs)
    csv_text = (fdir / "labels.csv").read_text(encoding="utf-8")
    blif = (fdir / "netlist.blif").read_text(encoding="utf-8")
    sub: list[str] = []
    sub += [f"graph.json: {e}" for e in validate_graph(graph)]
    sub += [f"key.json: {e}" for e in validate_key(key)]
    sub += [f"meta.json: {e}" for e in validate_meta(meta)]
    sub += [f"words.json: {e}" for e in validate_words(words)]
    sub += validate_labels_csv(csv_text)
    if not sub and isinstance(graph, dict) and isinstance(key, dict):
        sub += _graph_label_errors(graph, csv_text)
        sub += _blif_errors(blif, key)
    _prefixed(errs, where, sub)


def _graph_label_errors(graph: dict[str, Any], csv_text: str) -> list[str]:
    errs: list[str] = []
    rows = list(csv.DictReader(io.StringIO(csv_text, newline="")))
    nodes = graph["nodes"]
    if [n["id"] for n in nodes] != [r["node_id"] for r in rows]:
        errs.append("node ids of graph.json and labels.csv differ")
        return errs
    incoming: dict[str, int] = {}
    for e in graph["edges"]:
        incoming[e["dst"]] = incoming.get(e["dst"], 0) + 1
    for node in nodes:
        errs.extend(_node_errors(node, incoming.get(node["id"], 0)))
    return errs


def _node_errors(node: dict[str, Any], incoming: int) -> list[str]:
    errs: list[str] = []
    feats, labs, nid = node["features"], node["labels"], node["id"]
    if node["kind"] != "pi" and incoming != feats["fan_in"]:
        errs.append(f"{nid}: {incoming} incoming edges but fan_in {feats['fan_in']}")
    has_hdl = bool(labs["hdl_file"]) and labs["hdl_line"] > 0
    unknown = labs["construct_type"] == "" and labs["role"] == "unknown"
    if node["kind"] != "const" and not has_hdl and not unknown:
        errs.append(f"{nid}: no hdl_file or hdl_line")
    return errs


def _blif_signals(blif: str) -> tuple[list[str], list[str]]:
    """Signal names and ``.cname`` names of the top model (black-box models after ``.end``)."""
    signals: list[str] = []
    cnames: list[str] = []
    for line in blif.splitlines():
        tok = line.split()
        if not tok:
            continue
        if tok[0] == ".end":
            break
        if tok[0] in (".inputs", ".outputs", ".names"):
            signals += tok[1:]
        elif tok[0] == ".latch":
            signals += [tok[1], tok[2], tok[4]]
        elif tok[0] == ".subckt":
            signals += [t.partition("=")[2] for t in tok[2:]]
        elif tok[0] == ".cname":
            cnames.append(tok[1])
    return signals, cnames


def _blif_errors(blif: str, key: dict[str, Any]) -> list[str]:
    errs: list[str] = []
    signals, cnames = _blif_signals(blif)
    known = set(key["nets"]) | {p["anon"] for p in key["ports"]}
    for s in sorted(set(signals)):
        if not _NAME.match(s):
            errs.append(f"netlist.blif: signal {s!r} is not n<k>")
        elif s not in known:
            errs.append(f"netlist.blif: signal {s} is not in key.json")
    if len(set(cnames)) != len(cnames):
        errs.append("netlist.blif: a .cname is used twice")
    for c in sorted(set(cnames)):
        if not _NAME.match(c) or c not in key["cells"]:
            errs.append(f"netlist.blif: .cname {c!r} is not a key.json cell")
    for name in key["nets"]:
        if name not in set(signals):
            errs.append(f"key.json: net {name} does not occur in netlist.blif")
    return errs
