"""Census analysis: per design x cell rows and per pattern x cell tables.

``python -B analyze.py`` reads results/labels_rtl.csv, OUT/build and OUT/re, writes
results/per_design.csv, results/pattern_cell.csv, results/frequency.csv, results/fsm_encoding.csv.
"""

from __future__ import annotations

import csv
import importlib
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
lib: Any = importlib.import_module("l3lib")
bg: Any = importlib.import_module("blifgraph")
lab: Any = importlib.import_module("labels_rtl")
RES = Path(__file__).resolve().parent / "results"
SEQ = ("fsm", "counter", "shift_reg", "lfsr", "register", "ff_en", "ff_srst")
COMPARE = ("eq_const", "comparator")
DEPTH = 6


def q_nets(claim: dict[str, Any]) -> list[str]:
    facts = claim.get("facts", {})
    nets = claim.get("nets", {})
    return list(facts.get("q") or nets.get("q") or nets.get("Q") or [])


def kinds(claims: list[dict[str, Any]]) -> Counter[str]:
    return Counter(c["kind"] for c in claims)


def link(g: Any, a: list[dict[str, Any]], b: list[dict[str, Any]]) -> int:
    """Smallest combinational depth between a claim of ``a`` and one of ``b`` (either way)."""
    best = -1
    for x in a:
        for y in b:
            for s, d in ((x, y), (y, x)):
                dep = g.min_depth(q_nets(s), q_nets(d))
                if dep >= 0 and (best < 0 or dep < best):
                    best = dep
    return best


def timer_hit(claims: list[dict[str, Any]]) -> bool:
    for c in claims:
        if c["kind"] != "counter":
            continue
        q = set(q_nets(c))
        for k in claims:
            if k["kind"] in COMPARE and q & {n for v in k["nets"].values() for n in v}:
                return True
    return False


def expected(pattern: str, claims: list[dict[str, Any]], g: Any) -> tuple[bool, int]:
    """(expected L1 claims appear, link depth for composites; -2 = not a composite)."""
    by: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for c in claims:
        by[c["kind"]].append(c)
    shift = by["shift_reg"] + by["lfsr"]
    if pattern == "fsm":
        return bool(by["fsm"]), -2
    if pattern == "counter":
        return bool(by["counter"]), -2
    if pattern == "shift":
        return bool(shift), -2
    if pattern == "lfsr":
        return bool(by["lfsr"]), -2
    if pattern == "timer":
        return timer_hit(claims), -2
    if pattern == "fsm_counter":
        return bool(by["fsm"] and by["counter"]), link(g, by["fsm"], by["counter"])
    if pattern == "fsm_shift":
        return bool(by["fsm"] and shift), link(g, by["fsm"], shift)
    if pattern in ("regfile", "register"):
        return bool(by["register"] or by["ff_en"] or by["ff_srst"]), -2
    return not any(by[k] for k in SEQ), -2


def load_labels() -> dict[str, dict[str, Any]]:
    with (RES / "labels_rtl.csv").open(encoding="utf-8", newline="") as fh:
        return {r["design"]: r for r in csv.DictReader(fh) if r["status"] in ("ok", "manual")}


def chain_depth(cell: str, design: str) -> float:
    """Mean number of distinct construct types per labelled cell (Odin III cells only)."""
    if cell not in lib.ODIN_CELLS:
        return 0.0
    f = lib.netlist(cell, design).parent / "labels.csv"
    if not f.is_file():
        return 0.0
    with f.open(encoding="utf-8", newline="") as fh:
        rows = [r for r in csv.DictReader(fh) if r["kind"] in ("gate", "lut", "ff", "hard")]
    if not rows:
        return 0.0
    return sum(len(r["construct_types"].split("|")) for r in rows) / len(rows)


def design_rows(labels: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for m in lib.manifest():
        d = m["design"]
        for cell in lib.CELLS:
            net = lib.netlist(cell, d)
            ij = lib.OUT / "re" / cell / d / "intent.json"
            row: dict[str, Any] = {"corpus": m["corpus"], "design": d, "cell": cell,
                                   "built": int(net.is_file()), "re": int(ij.is_file())}
            if d in labels and net.is_file():
                row.update(measure(cell, d, net, ij, labels[d]))
            rows.append(row)
    return rows


def measure(cell: str, d: str, net: Path, ij: Path, lab_row: dict[str, Any]) -> dict[str, Any]:
    g = bg.Blif(net)
    out: dict[str, Any] = {k: v for k, v in g.counts().items() if not k.startswith("hard:")}
    out["chain"] = round(chain_depth(cell, d), 3)
    if not ij.is_file():
        return out
    claims = json.loads(ij.read_text(encoding="utf-8"))["claims"]
    out["claims"] = json.dumps(dict(sorted(kinds(claims).items())))
    out["fsm_enc"] = "|".join(sorted(c["facts"].get("encoding", "?")
                                     for c in claims if c["kind"] == "fsm"))
    for p in lab.PATTERNS:
        if lab_row[p] not in ("", "0"):
            hit, dep = expected(p, claims, g)
            out[f"hit_{p}"] = int(hit)
            if p in ("counter", "timer", "fsm_counter"):
                out[f"alt_{p}"] = int(any(c["kind"] == "hard_add" for c in claims))
            if dep != -2:
                out[f"depth_{p}"] = dep
    return out


def write(name: str, cols: list[str], rows: list[dict[str, Any]]) -> None:
    with (RES / name).open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, cols, lineterminator="\n", extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def tables(labels: dict[str, dict[str, Any]], rows: list[dict[str, Any]]) -> None:
    freq = []
    for corp in ("veval", "r4", "vtr", "all"):
        ds = [r for r in labels.values() if corp in ("all", r["corpus"])]
        for p in lab.PATTERNS:
            n = sum(1 for r in ds if r[p] not in ("", "0"))
            inst = sum(int(r[p]) for r in ds if r[p] not in ("", "0"))
            freq.append({"corpus": corp, "pattern": p, "designs": n, "instances": inst,
                         "of": len(ds), "fraction": round(n / len(ds), 3) if ds else 0})
    write("frequency.csv", ["corpus", "pattern", "designs", "instances", "of", "fraction"], freq)
    out = []
    enc: Counter[tuple[str, str, str]] = Counter()
    for p in lab.PATTERNS:
        for cell in lib.CELLS:
            rs = [r for r in rows if r["cell"] == cell and f"hit_{p}" in r]
            if not rs:
                continue
            comp = [r for r in rs if f"depth_{p}" in r]
            conn = [r for r in comp if r[f"hit_{p}"] and 0 <= r[f"depth_{p}"] <= DEPTH]
            out.append({
                "pattern": p, "cell": cell, "n": len(rs),
                "hit": sum(r[f"hit_{p}"] for r in rs),
                "hit_fraction": round(sum(r[f"hit_{p}"] for r in rs) / len(rs), 3),
                "alt_hard_add": sum(r.get(f"alt_{p}", 0) for r in rs),
                "composite_n": len(comp), "connected": len(conn),
                "mean_names": _mean(rs, "names"), "mean_latches": _mean(rs, "latches"),
                "mean_hard": _mean(rs, "hard"), "mean_chain": _mean(rs, "chain")})
            if p == "fsm":
                for r in rs:
                    enc[(cell, p, r.get("fsm_enc", "") or "none")] += 1
    write("pattern_cell.csv", ["pattern", "cell", "n", "hit", "hit_fraction", "alt_hard_add",
                               "composite_n", "connected", "mean_names", "mean_latches",
                               "mean_hard", "mean_chain"], out)
    write("fsm_encoding.csv", ["cell", "pattern", "encoding", "designs"],
          [{"cell": c, "pattern": p, "encoding": e, "designs": n}
           for (c, p, e), n in sorted(enc.items())])


def _mean(rs: list[dict[str, Any]], key: str) -> float:
    vals = [float(r[key]) for r in rs if key in r]
    return round(sum(vals) / len(vals), 2) if vals else 0.0


def main() -> int:
    labels = load_labels()
    rows = design_rows(labels)
    cols = ["corpus", "design", "cell", "built", "re", "names", "latches", "hard", "chain",
            "claims", "fsm_enc"]
    cols += [f"{k}_{p}" for p in lab.PATTERNS for k in ("hit", "depth", "alt")]
    write("per_design.csv", cols, rows)
    tables(labels, rows)
    print(len(rows), "rows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
