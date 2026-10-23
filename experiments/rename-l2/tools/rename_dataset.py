"""Build a naming-decoupled copy of an assembled L0 dataset.

Every identifier Loki's own numbering produced (net names, ``.cname`` node ids, design module
names) and every floor directory name is replaced by a seeded opaque token.  Library cell and
port names (``.subckt`` cell types, pin names, ``.blackbox`` model bodies) are BLIF semantics and
stay.  The forward rename map is written to ``rename-map.json``; the ground truth itself is never
copied, so it stays only in the original-named dataset.
"""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import re
import shutil
from pathlib import Path

SEED = 20261022
IDENT = re.compile(r"n\d+\Z")
CONTROL_TYPES = frozenset({"re", "fe", "ah", "al", "as"})
PREFIX = {"net": "a", "cell": "c", "module": "m"}


def token(design: str, kind: str, original: str) -> str:
    msg = f"{design}\0{kind}\0{original}".encode()
    digest = hmac.new(str(SEED).encode(), msg, hashlib.sha256).hexdigest()[:10]
    return PREFIX[kind] + digest


def floor_alias(floor: str) -> str:
    digest = hmac.new(str(SEED).encode(), f"floor\0{floor}".encode(), hashlib.sha256).hexdigest()
    return "z" + digest[:10]


def _blocks(lines: list[str]) -> tuple[set[str], set[str], list[tuple[int, int]]]:
    """Design module names, blackbox (library) model names and the blackbox line ranges.

    A BLIF block is ``.model NAME`` .. ``.end`` and a library block carries ``.blackbox`` inside
    that range, so the marker comes *after* the model line: classification follows the block, not
    a "next model" flag (the first run's script renamed the library cell types this way).
    """
    design: set[str] = set()
    black: set[str] = set()
    ranges: list[tuple[int, int]] = []
    current: str | None = None
    start = 0
    is_black = False
    for i, raw in enumerate(lines):
        s = raw.strip()
        if s.startswith(".model"):
            current = s.split()[1]
            start = i
            is_black = False
        elif s.startswith(".blackbox"):
            is_black = True
        elif s.startswith(".end") and current is not None:
            (black if is_black else design).add(current)
            if is_black:
                ranges.append((start, i))
            current = None
    return design, black, ranges


def rename_blif(path: Path, design: str, cells: dict[str, str], nets: dict[str, str],
                modules: dict[str, str]) -> str:
    lines = path.read_text(encoding="utf-8").splitlines()
    design_models, _black, ranges = _blocks(lines)
    library_lines: set[int] = set()
    for first, last in ranges:
        library_lines.update(range(first, last + 1))
    out: list[str] = []
    for i, raw in enumerate(lines):
        s = raw.strip()
        if i in library_lines or not s:
            out.append(raw)
            continue
        if s.startswith(".model"):
            name = s.split()[1]
            new = modules[name] if name in design_models else name
            out.append(f".model {new}")
            continue
        head = s.split(None, 1)
        key = head[0]
        rest = head[1] if len(head) > 1 else ""
        if key in (".inputs", ".outputs", ".names"):
            out.append(" ".join([key] + [nets.get(t, t) for t in rest.split()]))
        elif key == ".latch":
            toks = rest.split()
            for i in (0, 1):
                toks[i] = nets.get(toks[i], toks[i])
            if len(toks) > 3 and toks[2] in CONTROL_TYPES:
                toks[3] = nets.get(toks[3], toks[3])
            out.append(" ".join([key] + toks))
        elif key == ".subckt":
            toks = rest.split()
            if toks[0] in design_models:
                toks[0] = modules.get(toks[0], toks[0])
            for i, t in enumerate(toks[1:], start=1):
                if "=" in t:
                    pin, net = t.split("=", 1)
                    toks[i] = f"{pin}={nets.get(net, net)}"
                elif IDENT.match(t):
                    toks[i] = cells.get(t, t)
            out.append(" ".join([key] + toks))
        elif key == ".cname":
            val = rest.split()[0]
            out.append(f".cname {cells.get(val, val)}")
        else:
            out.append(raw)  # truth-table rows and anything else
    return "\n".join(out) + "\n"


def build(source: Path, out: Path) -> dict[str, object]:
    if out.exists():
        shutil.rmtree(out)
    manifest = json.loads((source / "manifest.json").read_text(encoding="utf-8"))
    floors = sorted({f for d in manifest["designs"] for f in d["floors"]})
    aliases = {f: floor_alias(f) for f in floors}
    rename: dict[str, dict[str, dict[str, str]]] = {}
    copied = 0
    for d in sorted(manifest["designs"], key=lambda x: x["design"]):
        design = d["design"]
        cell_map: dict[str, str] = {}
        net_map: dict[str, str] = {}
        module_map: dict[str, str] = {}
        for floor in floors:
            status = d["floors"].get(floor, {}).get("status")
            src = source / design / floor / "netlist.blif"
            if status != "ok" or not src.is_file():
                continue
            lines = src.read_text(encoding="utf-8").splitlines()
            design_models, _black, ranges = _blocks(lines)
            library_lines: set[int] = set()
            for first, last in ranges:
                library_lines.update(range(first, last + 1))
            for name in design_models:
                module_map.setdefault(name, token(design, "module", name))
            for i, line in enumerate(lines):
                s = line.strip()
                if i in library_lines or not s:
                    continue
                # collect every n<k> identifier used as a net, a cell, or a subckt instance
                if s.startswith((".inputs", ".outputs", ".names")):
                    for t in s.split()[1:]:
                        if IDENT.match(t):
                            net_map.setdefault(t, token(design, "net", t))
                elif s.startswith(".latch"):
                    toks = s.split()[1:]
                    idx = [0, 1]
                    if len(toks) > 3 and toks[2] in CONTROL_TYPES:
                        idx.append(3)
                    for i in idx:
                        if IDENT.match(toks[i]):
                            net_map.setdefault(toks[i], token(design, "net", toks[i]))
                elif s.startswith(".subckt"):
                    toks = s.split()[1:]
                    for t in toks[1:]:
                        if "=" in t:
                            v = t.split("=", 1)[1]
                            if IDENT.match(v):
                                net_map.setdefault(v, token(design, "net", v))
                        elif IDENT.match(t):
                            cell_map.setdefault(t, token(design, "cell", t))
                elif s.startswith(".cname"):
                    v = s.split()[1]
                    if IDENT.match(v):
                        cell_map.setdefault(v, token(design, "cell", v))
            assert len(set(cell_map.values())) == len(cell_map)
            assert len(set(net_map.values())) == len(net_map)
            dest = out / design / aliases[floor]
            dest.mkdir(parents=True, exist_ok=True)
            (dest / "netlist.blif").write_text(
                rename_blif(src, design, cell_map, net_map, module_map), encoding="utf-8")
            copied += 1
        rename[design] = {"cells": cell_map, "nets": net_map, "modules": module_map}
    obj: dict[str, object] = {
        "schema": 1,
        "seed": SEED,
        "scheme": ("HMAC-SHA256(seed|design|kind|original)[:10 hex], prefix a=net c=cell "
                   "m=module z=floor; library cell, pin and blackbox names unchanged"),
        "floors": aliases,
        "designs": rename,
        "stats": {"netlists": copied,
                  "identifiers": sum(len(v["cells"]) + len(v["nets"]) + len(v["modules"])
                                     for v in rename.values())},
    }
    (out / "rename-map.json").write_text(
        json.dumps(obj, sort_keys=True, indent=1) + "\n", encoding="utf-8")
    renamed_manifest = {
        "schema": 1,
        "name": source.name + "-renamed",
        "floors": aliases,
        "designs": [
            {"design": d["design"],
             "split": d.get("split"),
             "benchmark": d.get("benchmark"),
             "floors": {f: {"status": "ok", "dir": aliases[f]}
                        for f, st in sorted(d["floors"].items()) if st["status"] == "ok"}}
            for d in sorted(manifest["designs"], key=lambda x: x["design"])
            if any(st["status"] == "ok" for st in d["floors"].values())
        ],
    }
    (out / "manifest.json").write_text(
        json.dumps(renamed_manifest, sort_keys=True, indent=1) + "\n", encoding="utf-8")
    return obj


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    args = ap.parse_args()
    obj = build(args.source, args.out)
    print(f"renamed {obj['stats']['netlists']} netlists, "
          f"{obj['stats']['identifiers']} identifiers into {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
