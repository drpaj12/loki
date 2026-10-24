"""L0 provenance ceiling on the f3 floor (Gate-Breaker cmos6 gate netlist).

For every design with an f3 floor in the rebuilt dataset (work/loki-rename-exp/dataset-rebuild)
report what the L0 answer key still exposes after gate mapping:

  nodes, labelled rows, cell_type rows, HDL-span rows,
  distinct module_path scopes, distinct original signal names (key.json ports + nets),
  and the reference RTL's module / instance / signal counts (pyverilog over the micro source).

Usage: l0_ceiling.py DATASET REF_RTL_DIR OUT_JSON OUT_CSV
"""

from __future__ import annotations

import csv
import json
import re
import sys
from collections import Counter
from pathlib import Path

from pyverilog.vparser.ast import (
    Inout,
    Input,
    Instance,
    ModuleDef,
    Output,
    Reg,
    Wire,
)
from pyverilog.vparser.parser import parse

BIT = re.compile(r"\[\d+(?::\d+)?\]$")


def base_name(name: str) -> str:
    """Leaf signal name: drop a hierarchical instance prefix and a trailing bit/range select."""
    return BIT.sub("", name.rsplit(".", 1)[-1])


DECL = re.compile(r"^\s*(?:input|output|inout|wire|reg)\b([^;]*);", re.M)
INST = re.compile(
    r"^\s*(?!module\b|input\b|output\b|wire\b|reg\b|assign\b|always\b|if\b|for\b|case\b)"
    r"(\w+)\s+(?:#\s*\([^;]*\)\s*)?(\w+)\s*\(", re.M)


def ref_counts_regex(source: Path) -> dict[str, int]:
    """Approximate counts for a source pyverilog cannot parse even after sanitizing."""
    text = source.read_text(encoding="utf-8")
    names: set[str] = set()
    for decl in DECL.findall(text):
        for part in decl.split(","):
            word = re.search(r"(\w+)\s*(?:\[[^\]]*\])?\s*$", part.strip())
            if word:
                names.add(word.group(1))
    return {"ref_modules": len(re.findall(r"^\s*module\s+\w+", text, flags=re.M)),
            "ref_instances": len(INST.findall(text)), "ref_signals": len(names),
            "ref_method": "regex"}


def ref_counts(source: Path, sanitized_dir: Path) -> dict[str, object]:
    try:
        tree, _ = parse([str(source)], preprocess_include=[], preprocess_define=[])
        method = "original"
    except Exception:  # pyverilog rejects a handful of micro sources; see sanitize_refs.py
        try:
            tree, _ = parse([str(sanitized_dir / source.name)], preprocess_include=[],
                            preprocess_define=[])
            method = "sanitized"
        except Exception:
            return ref_counts_regex(source)
    modules = instances = 0
    signals: set[str] = set()
    stack = [tree]
    while stack:
        node = stack.pop()
        if isinstance(node, ModuleDef):
            modules += 1
        elif isinstance(node, Instance):
            instances += 1
        elif isinstance(node, (Input, Output, Inout, Reg, Wire)):
            signals.add(base_name(node.name))
        stack.extend(node.children())
    return {"ref_modules": modules, "ref_instances": instances,
            "ref_signals": len(signals), "ref_method": method}


def floor_counts(floor: Path) -> dict[str, object]:
    graph = json.loads((floor / "graph.json").read_text(encoding="utf-8"))
    key = json.loads((floor / "key.json").read_text(encoding="utf-8"))
    with (floor / "labels.csv").open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    modules = Counter(r["module_path"] for r in rows if r["module_path"])
    scopes = {part for path in modules for part in path.split("/") if part not in ("", "*")}
    names = {base_name(v["orig"]) for v in key["ports"]}
    for net in key["nets"].values():
        names.update(base_name(n) for n in net["names"])
    return {
        "nodes": len(graph["nodes"]),
        "rows": len(rows),
        "cell_type_rows": sum(1 for r in rows if r["cell_type"]),
        "hdl_rows": sum(1 for r in rows if r["hdl_file"]),
        "module_paths": len(modules),
        "module_scopes": len(scopes),
        "signals": len(names),
    }


def main() -> int:
    dataset, ref_dir, sanitized_dir, out_json, out_csv = (Path(a) for a in sys.argv[1:6])
    manifest = json.loads((dataset / "manifest.json").read_text(encoding="utf-8"))
    designs = [d for d in manifest["designs"]
               if d["floors"].get("f3", {}).get("status") == "ok"]
    out: list[dict[str, object]] = []
    for entry in designs:
        design = str(entry["design"])
        floor = dataset / design / "f3"
        row: dict[str, object] = {"design": design, "split": entry["split"]}
        row.update(floor_counts(floor))
        row.update(ref_counts(ref_dir / f"{design.removeprefix('micro_')}.v", sanitized_dir))
        row["label_cov"] = round(int(row["rows"]) / int(row["nodes"]), 6)
        row["cell_type_cov"] = round(int(row["cell_type_rows"]) / int(row["rows"]), 6)
        row["hdl_cov"] = round(int(row["hdl_rows"]) / int(row["rows"]), 6)
        row["signal_cov"] = round(int(row["signals"]) / int(row["ref_signals"]), 6)
        row["module_cov"] = round(int(row["module_scopes"]) / int(row["ref_modules"]), 6)
        out.append(row)
    totals: dict[str, int] = {}
    for key in ("nodes", "rows", "cell_type_rows", "hdl_rows", "module_paths",
                "module_scopes", "signals", "ref_modules", "ref_instances", "ref_signals"):
        totals[key] = sum(int(row[key]) for row in out)
    summary = {
        "designs": len(out),
        "totals": totals,
        "label_cov": round(totals["rows"] / totals["nodes"], 6),
        "cell_type_cov": round(totals["cell_type_rows"] / totals["rows"], 6),
        "hdl_cov": round(totals["hdl_rows"] / totals["rows"], 6),
        "signal_cov": round(totals["signals"] / totals["ref_signals"], 6),
        "module_cov": round(totals["module_scopes"] / totals["ref_modules"], 6),
        "worst_label_cov": sorted(out, key=lambda r: float(r["label_cov"]))[:5],
        "worst_signal_cov": sorted(out, key=lambda r: float(r["signal_cov"]))[:5],
    }
    out_json.write_text(json.dumps({"summary": summary, "designs": out}, sort_keys=True,
                                   indent=1) + "\n", encoding="utf-8")
    with out_csv.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(out[0]))
        writer.writeheader()
        writer.writerows(out)
    print(json.dumps(summary["totals"], sort_keys=True))
    for key in ("label_cov", "cell_type_cov", "hdl_cov", "signal_cov", "module_cov"):
        print(key, summary[key])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
