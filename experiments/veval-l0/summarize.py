"""Summaries of the veval-L0 dataset: ceiling, sizes, feature matrix, benchmark table, stats.

Reads the assembled dataset (manifest.json, <design>/<floor>/{graph,key,words}.json, labels.csv),
complexity.csv, and the reference sources. Writes l0-ceiling-veval.csv, sizes.csv, features.csv,
benchmark.csv and stats.json into OUT_DIR. Deterministic: designs sorted by id, floats rounded
to 6 places, LF line ends.

Feature rules (counts of distinct instances per design, from the f3 floor):
  arithmetic  words of type $add $sub $mul $div $mod $neg $pos $pow $alu $macc
  select      words of type $mux $pmux $bmux $demux
  storage     register words: $dff $dffe $adff $adffe $sdff $sdffe $sdffce $dffsr $aldff
              $dlatch $adlatch
  fsm         1 if any word carries the snapshot fsm flag, else 0
  control     1 if any labels.csv row has role control or mixed, else 0
  buses       distinct non-empty bus_name values in labels.csv
  buses_wide  distinct bus_name values that have a bit_index >= 1 (multi-bit buses)
The paper maps count 0 to x, 1 to check, 2 or more to check-check.

Usage: summarize.py DATASET REF_DIR COMPLEXITY_CSV OUT_DIR
"""

from __future__ import annotations

import csv
import importlib
import json
import math
import re
import statistics
import sys
from collections import Counter
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "f3-recovery" / "tools"))

l0_ceiling = importlib.import_module("l0_ceiling")
floor_counts = l0_ceiling.floor_counts
ref_counts = l0_ceiling.ref_counts

FLOORS = ("f1-k6", "f2", "f3")
QUARTILES = ("Q1", "Q2", "Q3", "Q4")
ARITH = {"$add", "$sub", "$mul", "$div", "$mod", "$neg", "$pos", "$pow", "$alu", "$macc"}
SELECT = {"$mux", "$pmux", "$bmux", "$demux"}
STORAGE = {"$dff", "$dffe", "$adff", "$adffe", "$sdff", "$sdffe", "$sdffce", "$dffsr",
           "$aldff", "$dlatch", "$adlatch"}
IO_KINDS = ("pi", "po", "const")
CLASS_KINDS = ("lut", "ff", "hard", "gate")


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def ok_floors(manifest: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """design -> entry for designs with at least one ok floor."""
    return {d["design"]: d for d in manifest["designs"]
            if any(f["status"] == "ok" for f in d["floors"].values())}


_COMMENT = re.compile(r"//[^\n]*|/\*.*?\*/", re.S)
_HEADER = re.compile(r"\bmodule\s+\w+\s*(?:#\s*\(.*?\)\s*)?\((.*?)\)\s*;", re.S)
_BODY = re.compile(r"\b(?:input|output|inout|wire|reg|logic)\b([^;]*);")


def _names(chunk: str) -> set[str]:
    """Declared identifiers of one header or declaration chunk (comma separated)."""
    found = set()
    for part in re.split(r",", re.sub(r"\[[^\]]*\]", " ", chunk)):
        words = re.findall(r"[A-Za-z_]\w*", part.split("=")[0])
        if words:
            found.add(words[-1])
    return found


def ref_signals_regex(source: Path) -> int:
    """Distinct declared signal names by regex, for refs pyverilog cannot parse (ANSI headers)."""
    text = _COMMENT.sub(" ", source.read_text(encoding="utf-8"))
    names: set[str] = set()
    for header in _HEADER.findall(text):
        names |= _names(header)
    for decl in _BODY.findall(text):
        names |= _names(decl)
    return len(names - {"input", "output", "inout", "wire", "reg", "logic", "signed"})


def ceiling_rows(dataset: Path, ref_dir: Path, designs: dict[str, dict[str, Any]],
                 ) -> list[dict[str, Any]]:
    out = []
    for name in sorted(designs):
        if designs[name]["floors"].get("f3", {}).get("status") != "ok":
            continue
        row: dict[str, Any] = {"design": name, "split": designs[name]["split"]}
        row.update(floor_counts(dataset / name / "f3"))
        ref = ref_dir / f"{name.removeprefix('ve_')}_ref.sv"
        row.update(ref_counts(ref, ref_dir / "no-sanitized-copies"))
        if row["ref_method"] == "regex":
            row["ref_signals"] = ref_signals_regex(ref)
        row["label_cov"] = round(row["rows"] / row["nodes"], 6)
        row["cell_type_cov"] = round(row["cell_type_rows"] / row["rows"], 6)
        row["hdl_cov"] = round(row["hdl_rows"] / row["rows"], 6)
        row["signal_cov"] = round(row["signals"] / row["ref_signals"], 6)
        row["module_cov"] = round(row["module_scopes"] / row["ref_modules"], 6)
        out.append(row)
    return out


def size_row(dataset: Path, name: str, floor: str, quartile: str) -> dict[str, Any]:
    graph = read_json(dataset / name / floor / "graph.json")
    key = read_json(dataset / name / floor / "key.json")
    kinds = Counter(n["kind"] for n in graph["nodes"])
    types = Counter(n["labels"]["cell_type"] for n in graph["nodes"]
                    if n["kind"] not in IO_KINDS)
    cells = sum(v for k, v in kinds.items() if k not in IO_KINDS)
    row: dict[str, Any] = {"design": name, "quartile": quartile, "floor": floor,
                           "nodes": len(graph["nodes"]), "edges": len(graph["edges"]),
                           "nets": len(key["nets"]), "pi": kinds["pi"], "po": kinds["po"],
                           "const": kinds["const"], "cells": cells}
    for kind in CLASS_KINDS:
        row[kind] = kinds[kind]
    row["cell_types"] = "|".join(f"{t}:{n}" for t, n in sorted(types.items()))
    return row


def feature_row(dataset: Path, name: str, quartile: str) -> dict[str, Any]:
    floor = dataset / name / "f3"
    words = read_json(floor / "words.json")["words"]
    rows = read_rows(floor / "labels.csv")
    by_type = Counter(w["type"] for w in words)
    wide = {r["bus_name"] for r in rows if r["bus_name"] and int(r["bit_index"]) >= 1}
    return {
        "design": name, "quartile": quartile,
        "arithmetic": sum(n for t, n in by_type.items() if t in ARITH),
        "select": sum(n for t, n in by_type.items() if t in SELECT),
        "storage": sum(n for t, n in by_type.items() if t in STORAGE),
        "fsm": int(any(w["fsm"] for w in words)),
        "control": int(any(r["role"] in ("control", "mixed") for r in rows)),
        "buses": len({r["bus_name"] for r in rows if r["bus_name"]}),
        "buses_wide": len(wide),
    }


def mean_median(values: list[float]) -> dict[str, float]:
    if not values:
        return {"n": 0, "mean": 0.0, "median": 0.0}
    return {"n": len(values), "mean": round(statistics.fmean(values), 6),
            "median": round(float(statistics.median(values)), 6)}


def geomean(values: list[float]) -> float:
    return round(math.exp(sum(math.log(v) for v in values) / len(values)), 6) if values else 0.0


def stats(sizes: list[dict[str, Any]], ceiling: list[dict[str, Any]],
          features: list[dict[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {"sizes": {}, "ceiling": {}, "feature_coverage": {}}
    for floor in FLOORS:
        rows = [r for r in sizes if r["floor"] == floor]
        out["sizes"][floor] = {
            metric: {"all": mean_median([r[metric] for r in rows]),
                     **{q: mean_median([r[metric] for r in rows if r["quartile"] == q])
                        for q in QUARTILES}}
            for metric in ("nodes", "cells", "nets")}
    for col in ("label_cov", "cell_type_cov", "hdl_cov", "module_cov", "signal_cov"):
        out["ceiling"][col] = {"geomean": geomean([r[col] for r in ceiling]),
                               "mean": mean_median([r[col] for r in ceiling])["mean"]}
    out["ceiling"]["designs"] = len(ceiling)
    for col in ("arithmetic", "select", "storage", "fsm", "control", "buses", "buses_wide"):
        out["feature_coverage"][col] = {
            "ge1": sum(1 for r in features if r[col] >= 1),
            "ge2": sum(1 for r in features if r[col] >= 2),
            **{q: sum(1 for r in features if r["quartile"] == q and r[col] >= 1)
               for q in QUARTILES}}
    out["feature_coverage"]["designs"] = len(features)
    out["feature_coverage"]["by_quartile"] = {
        q: sum(1 for r in features if r["quartile"] == q) for q in QUARTILES}
    return out


def main() -> int:
    dataset, ref_dir, cx_csv, out = (Path(a) for a in sys.argv[1:5])
    manifest = read_json(dataset / "manifest.json")
    designs = ok_floors(manifest)
    cx = {r["design"]: r for r in read_rows(cx_csv)}
    sizes = [size_row(dataset, n, f, cx[n]["quartile"]) for n in sorted(designs)
             for f in FLOORS if designs[n]["floors"].get(f, {}).get("status") == "ok"]
    ceiling = ceiling_rows(dataset, ref_dir, designs)
    f3 = [r["design"] for r in ceiling]
    features = [feature_row(dataset, n, cx[n]["quartile"]) for n in f3]
    f3_nodes = {r["design"]: r["nodes"] for r in sizes if r["floor"] == "f3"}
    bench = [{"design": n, "problem": cx[n]["problem"], "quartile": cx[n]["quartile"],
              "ref_lines": cx[n]["ref_lines"], "f3_nodes": f3_nodes[n]} for n in f3]
    out.mkdir(parents=True, exist_ok=True)
    write_csv(out / "l0-ceiling-veval.csv", ceiling)
    write_csv(out / "sizes.csv", sizes)
    write_csv(out / "features.csv", features)
    write_csv(out / "benchmark.csv", bench)
    (out / "stats.json").write_text(
        json.dumps(stats(sizes, ceiling, features), sort_keys=True, indent=1) + "\n",
        encoding="utf-8")
    print(f"{len(ceiling)} f3 designs, {len(sizes)} size rows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
