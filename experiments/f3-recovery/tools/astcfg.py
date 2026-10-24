"""AST (Gate-Breaker Algorithm 2) and CFG (Algorithm 3) similarity at L0-stop and L1-stop.

L0-stop Verilog is the f3 gate netlist the dataset ships (``netlist.v``, the cmos6 structural
netlist L1 starts from). L1-stop Verilog is ``design.v`` written by ``loki re`` after its
raise/submodule commits. References are the micro RTL sources (sanitized copies for the few
pyverilog rejects).

AST: pyverilog 1.3 over both modules, identifiers kind-normalized, every unique depth-3
subtree, best Jaccard per reference subtree, mean over reference subtrees
(work/gatebreaker-exp2/scripts/metrics.py, read-only import).
CFG: the odin3 CFG probe (Algorithm 3, common width, sigma 0.5) over Odin III's elaborated
AST (work/odin3-cfg/tools/cfg-probe/odin3_cfg.py, read-only import).

Usage: astcfg.py RUNS_DIR DATASET REF_DIR SANITIZED_DIR OUT_JSON
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

SCRIPTS = Path("/home/jamiespa/odin3-ws/work/gatebreaker-exp2/scripts")
PROBE = Path("/home/jamiespa/odin3-ws/work/odin3-cfg/tools/cfg-probe")
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(PROBE))
os.environ.setdefault("ODIN3_LIB", "/home/jamiespa/odin3-ws/odin3/build/release/libodin3.so")

import metrics  # noqa: E402
import odin3_cfg  # noqa: E402


def ref_path(name: str, ref_dir: Path, sanitized: Path) -> tuple[Path, str]:
    original = ref_dir / f"{name}.v"
    try:
        metrics.parse_module(str(original))
        return original, "original"
    except metrics.ParseFail:
        return sanitized / f"{name}.v", "sanitized"


CLEAN_DIR = Path("/tmp/claude-1000/f3-ast-clean")


def _parse_clean(path: Path) -> object:
    """Parse with pyverilog after stripping (* ... *) attributes (metadata; strings break it)."""
    CLEAN_DIR.mkdir(parents=True, exist_ok=True)
    clean = CLEAN_DIR / f"{path.parent.name}__{path.name}"
    clean.write_text(re.sub(r"\(\*.*?\*\)", "", path.read_text(encoding="utf-8"), flags=re.S),
                     encoding="utf-8")
    return metrics.parse_module(str(clean))


def ast_pair(ref: Path, l0: Path, l1: Path, top: str) -> tuple[float, float]:
    ref_mod = metrics.parse_module(str(ref), top) if top else metrics.parse_module(str(ref))
    sims = []
    for generated in (l0, l1):
        sims.append(metrics.ast_similarity(ref_mod, _parse_clean(generated), depth=3))
    return sims[0], sims[1]


def cfg_pair(binding: object, ref: Path, l0: Path, l1: Path) -> tuple[float, float]:
    cfgs = []
    for path in (ref, l0, l1):
        design = odin3_cfg.read_design(binding, Path(path))
        try:
            cfgs.append(odin3_cfg.design_cfg(design))
        finally:
            design.close()
    sims = []
    for cfg in cfgs[1:]:
        sims.append(odin3_cfg.cfg_similarity(cfgs[0], cfg))
    return sims[0], sims[1]


def main() -> int:
    runs, dataset, ref_dir, sanitized, out_path = (
        Path(a) for a in sys.argv[1:6])
    manifest = json.loads((dataset / "manifest.json").read_text(encoding="utf-8"))
    designs = [(str(e["design"]), int(e["floors"]["f3"]["nodes"]))
               for e in manifest["designs"]
               if e["split"] == "test" and e["floors"].get("f3", {}).get("status") == "ok"]
    designs.sort(key=lambda x: (x[1], x[0]))
    binding = odin3_cfg.load_binding()
    odin3_cfg.ensure_sanitizer_preload(binding)
    rows = []
    for rank, (design, nodes) in enumerate(designs):
        stem = design.removeprefix("micro_")
        key = json.loads((dataset / design / "f3" / "key.json").read_text(encoding="utf-8"))
        top = str(key.get("top") or "")
        ref, ref_method = ref_path(stem, ref_dir, sanitized)
        l0 = dataset / design / "f3" / "netlist.v"
        l1 = runs / f"{design}__f3" / "re" / "design.v"
        row: dict[str, object] = {
            "design": design, "nodes": nodes, "quartile": min(3, rank * 4 // len(designs)),
            "ref_method": ref_method}
        if not l1.is_file():
            row["error"] = "no L1 design.v"
            rows.append(row)
            continue
        try:
            ast_l0, ast_l1 = ast_pair(ref, l0, l1, top)
            row.update(simast_l0=round(ast_l0, 6), simast_l1=round(ast_l1, 6),
                       simast_delta=round(ast_l1 - ast_l0, 6))
        except Exception as err:  # noqa: BLE001 - reported per design
            row["ast_error"] = f"{type(err).__name__}: {str(err)[:120]}"
        try:
            cfg_l0, cfg_l1 = cfg_pair(binding, ref, l0, l1)
            row.update(simcfg_l0=round(cfg_l0, 6), simcfg_l1=round(cfg_l1, 6),
                       simcfg_delta=round(cfg_l1 - cfg_l0, 6))
        except Exception as err:  # noqa: BLE001 - reported per design
            row["cfg_error"] = f"{type(err).__name__}: {str(err)[:120]}"
        rows.append(row)
        print(design, json.dumps({k: v for k, v in row.items()
                                  if k not in ("design", "nodes")}), flush=True)
    summary: dict[str, object] = {}
    for metric in ("simast", "simcfg"):
        per_q: dict[str, dict[str, float]] = {}
        for q in range(4):
            sel = [r for r in rows if r["quartile"] == q and f"{metric}_l0" in r]
            per_q[str(q)] = {
                "designs": len(sel),
                "mean_l0": round(sum(float(r[f"{metric}_l0"]) for r in sel) / len(sel), 6)
                if sel else 0.0,
                "mean_l1": round(sum(float(r[f"{metric}_l1"]) for r in sel) / len(sel), 6)
                if sel else 0.0,
                "mean_delta": round(sum(float(r[f"{metric}_delta"]) for r in sel) / len(sel), 6)
                if sel else 0.0,
            }
        sel = [r for r in rows if f"{metric}_l0" in r]
        summary[metric] = {
            "quartiles": per_q,
            "designs": len(sel),
            "mean_l0": round(sum(float(r[f"{metric}_l0"]) for r in sel) / len(sel), 6)
            if sel else 0.0,
            "mean_l1": round(sum(float(r[f"{metric}_l1"]) for r in sel) / len(sel), 6)
            if sel else 0.0,
            "mean_delta": round(sum(float(r[f"{metric}_delta"]) for r in sel) / len(sel), 6)
            if sel else 0.0,
        }
    out_path.write_text(json.dumps({"summary": summary, "designs": rows}, sort_keys=True,
                                   indent=1) + "\n", encoding="utf-8")
    print(json.dumps(summary, sort_keys=True, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
