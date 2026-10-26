"""Arm B hints: run ``loki re`` on a renamed scratch copy and translate the result to netlist names.

Usage: ``python -I make_hints.py [--problems P ...]`` (default: all of selection.csv).
Needs ``ODIN3_ROOT`` (default ``<workspace>/odin3``; its release library is used as built) and a
Python with cffi. Writes ``run/hints/<problem>/{f3/netlist.v,out/,hints.md,hints_stats.json}`` and
``hints_stats.csv``.
"""

from __future__ import annotations

import argparse
import copy
import csv
import importlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
common = importlib.import_module("common")

DETECTORS = "wordfirst,hard,ff_pattern,mux,arith,seqfn,fsm,bus,unit,role,wordgroup"
MAX_CHARS = 8000
RENAMES = {"NOT": "INV", "NAND": "NAND2", "NOR": "NOR2"}
_CELL = re.compile(r"^(  )(NOT|NAND|NOR) (_[0-9a-z_]+_ \()", re.M)
_LEFT = re.compile(r"^\s*(NOT|NAND|NOR)\s", re.M)
_DECL = re.compile(r"^\s*(input|output|wire)\s*(?:\[(\d+):(\d+)\])?\s*([A-Za-z_]\w*)\s*;", re.M)
_INST = re.compile(r"^\s*(DFF|DFFSR)\s+\S+\s*\((.*?)\);", re.M | re.S)
_PIN = re.compile(r"\.\w+\(\s*([^()]*?)\s*\)")


def rename_cells(text: str) -> str:
    """Yosys cell names to the cmos6 names at the start of each instantiation line."""
    out = _CELL.sub(lambda m: m.group(1) + RENAMES[m.group(2)] + " " + m.group(3), text)
    if _LEFT.search(out):
        raise ValueError("unrenamed NOT/NAND/NOR cell line left")
    return out


def _bits(name: str, msb: str | None, lsb: str | None) -> list[str]:
    if msb is None or lsb is None:
        return [name]
    lo, hi = sorted((int(msb), int(lsb)))
    return [f"{name}[{i}]" for i in range(lo, hi + 1)]


def mappable_nets(text: str) -> set[str]:
    """Port bits and flip-flop pin nets of the original netlist (names Loki keeps)."""
    ports: set[str] = set()
    declared: set[str] = set()
    for kind, msb, lsb, name in _DECL.findall(text):
        bits = _bits(name, msb or None, lsb or None)
        declared.update(bits)
        if kind in ("input", "output"):
            ports.update(bits)
    pins: set[str] = set()
    for _cell, body in _INST.findall(text):
        pins.update(p for p in _PIN.findall(body) if p in declared)
    return ports | pins


def flat(groups: dict[str, list[str]]) -> list[str]:
    return [n for names in groups.values() for n in names]


def nets_of(el: dict[str, Any]) -> list[str]:
    ports = el["ports"]
    return flat(ports["inputs"]) + flat(ports["outputs"]) + flat(el.get("nets", {}))


def row_nets(row: dict[str, Any]) -> list[str]:
    if "bits" in row:
        return [n for bit in row["bits"] for n in bit]
    return list(row["state_nets"]) + list(row["control_nets"]) + list(row["reset_net"])


def _show_nets(el: dict[str, Any]) -> None:
    """Flip-flop style claims carry ``nets`` only: show them as ports (q out, others in)."""
    if el["ports"]["inputs"] or el["ports"]["outputs"] or not el.get("nets"):
        return
    for key, names in sorted(el["nets"].items()):
        el["ports"]["outputs" if key == "q" else "inputs"][key] = list(names)


def _prune(nodes: list[dict[str, Any]], keep: set[str]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for n in nodes:
        kids = _prune(n["children"], keep)
        if n["id"] in keep:
            out.append({**n, "children": kids})
        else:
            out += kids
    return out


def translate(rp: dict[str, Any], mappable: set[str]) -> tuple[dict[str, Any], dict[str, int]]:
    """Drop objects that name an unmappable net; return the new file and the counts."""
    new = copy.deepcopy(rp)
    rows = {r["id"]: r for r in rp["buses"] + rp["fsms"]}
    empty: dict[str, Any] = {"bits": []}
    drop = {el["id"] for el in rp["elements"]
            if any(n not in mappable
                   for n in nets_of(el) + row_nets(rows.get(el["id"], empty)))}
    keep = {el["id"] for el in rp["elements"]} - drop
    new["elements"] = [e for e in new["elements"] if e["id"] in keep]
    for el in new["elements"]:
        lost = [c for c in el["conflicts"] if c in drop]
        el["conflicts"] = [c for c in el["conflicts"] if c in keep]
        el["links_outside"]["conflicts"] += len(lost)
        el["children"] = [c for c in el["children"] if c in keep]
        el["parents"] = [c for c in el["parents"] if c in keep]
        _show_nets(el)
    new["buses"] = [r for r in new["buses"] if r["id"] in keep]
    new["fsms"] = [r for r in new["fsms"] if r["id"] in keep]
    new["hierarchy"] = _prune(new["hierarchy"], keep)
    stats = {"claims": len(rp["elements"]), "claims_kept": len(keep),
             "buses": len(rp["buses"]), "buses_kept": len(new["buses"]),
             "fsms": len(rp["fsms"]), "fsms_kept": len(new["fsms"])}
    return new, stats


def _drop_lines(text: str) -> str:
    """Remove section 2, the per-cell note and lines that name Loki-internal cells or nets."""
    out: list[str] = []
    skipping = False
    for line in text.split("\n"):
        if line.startswith("## 2."):
            skipping = True
        elif line.startswith("## 3."):
            skipping = False
        if skipping or line.startswith("- Cells covered by no claim") \
                or line.startswith("- Nets driven by those cells"):
            continue
        if line.startswith("> Omitted to fit") and line.endswith(": per-cell lists."):
            continue
        if line.startswith("Input cells:"):
            n = re.match(r"Input cells: (\d+)", line)
            line = f"Input cells (in Loki's re-mapped netlist): {n.group(1) if n else '?'}."
        if not line and out and not out[-1]:
            continue
        out.append(line.replace(", per-cell lists", ""))
    return "\n".join(out)


def render_hints(rp: dict[str, Any], max_chars: int = MAX_CHARS) -> str:
    """The Loki document for a translated file (no per-cell lists, no section 2)."""
    doc = importlib.import_module("loki.rp.doc")
    limit = max(max_chars, doc.min_chars(rp, True))
    steps = [(True, True, False), (False, True, False), (False, False, False)]
    for step in steps:
        head, tail = doc._text(rp, step, True, limit)
        text = doc._join([*head, *tail])
        if len(text) <= limit:
            return _drop_lines(text)
    return _drop_lines(doc._cut(head, tail, limit, max_chars))


def hints_block(doc: str, dropped: int, total: int) -> str:
    """The text inserted into the arm B question (brief 6.2 with the decision-8 preface)."""
    body = doc.strip("\n") + "\n"
    return common.HINTS_PREFACE.format(dropped=dropped, total=total) + body + common.HINTS_POSTFACE


def loki_env(odin: Path) -> dict[str, str]:
    env = dict(os.environ)
    env["ODIN3_ROOT"] = str(odin)
    env["ODIN3_LIB"] = str(odin / "build" / "release" / "libodin3.so")
    env["PYTHONPATH"] = os.pathsep.join([str(common.REPO), str(odin / "plugins" / "python")])
    return env


def run_loki(netlist: Path, out: Path, odin: Path) -> None:
    cmd = [sys.executable, "-B", "-m", "loki.re.main", str(netlist), "--floor", "f3",
           "--calib", "none", "--detectors", DETECTORS, "--out", str(out)]
    done = subprocess.run(cmd, env=loki_env(odin), capture_output=True, text=True,
                          cwd=str(common.run_dir()), check=False)
    if done.returncode != 0:
        raise RuntimeError(f"loki re failed ({done.returncode}): {done.stderr.strip()[-300:]}")


def make_one(problem: str, odin: Path) -> dict[str, Any]:
    work = common.run_dir() / "hints" / problem
    (work / "f3").mkdir(parents=True, exist_ok=True)
    text = (common.dataset_dir() / f"{problem}_netlist.v").read_text(encoding="utf-8")
    scratch = work / "f3" / "netlist.v"
    scratch.write_text(rename_cells(text), encoding="utf-8", newline="\n")
    run_loki(scratch, work / "out", odin)
    rp = json.loads((work / "out" / "reverse-provenance.json").read_text(encoding="utf-8"))
    new, stats = translate(rp, mappable_nets(text))
    (work / "out" / "translated.json").write_text(
        json.dumps(new, sort_keys=True, indent=1) + "\n", encoding="utf-8")
    doc = render_hints(new)
    block = hints_block(doc, stats["claims"] - stats["claims_kept"], stats["claims"])
    (work / "hints.md").write_text(block + "\n", encoding="utf-8", newline="\n")
    stats = {"problem": problem, **stats, "doc_bytes": len(doc.encode("utf-8")),
             "block_bytes": len(block.encode("utf-8")), "loki": 1}
    (work / "hints_stats.json").write_text(json.dumps(stats, sort_keys=True) + "\n",
                                           encoding="utf-8")
    return stats


FIELDS = ["problem", "claims", "claims_kept", "buses", "buses_kept", "fsms", "fsms_kept",
          "doc_bytes", "block_bytes", "loki"]


def selected() -> list[str]:
    with (common.HERE / "selection.csv").open(encoding="utf-8", newline="") as fh:
        return [r["problem"] for r in csv.DictReader(fh)]


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--problems", nargs="+", default=None, metavar="P",
                    help="subset of selection.csv (default: all; the stats csv is then rewritten)")
    args = ap.parse_args(argv)
    odin = Path(os.environ.get("ODIN3_ROOT", str(common.workspace() / "odin3")))
    names = args.problems or selected()
    common.run_dir().mkdir(parents=True, exist_ok=True)
    rows = []
    for name in names:
        rows.append(make_one(name, odin))
        print(f"{name}: claims {rows[-1]['claims_kept']}/{rows[-1]['claims']}", flush=True)
    if not argv:
        with (common.HERE / "hints_stats.csv").open("w", encoding="utf-8", newline="") as fh:
            w = csv.DictWriter(fh, FIELDS, lineterminator="\n")
            w.writeheader()
            w.writerows({k: r[k] for k in FIELDS} for r in rows)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
