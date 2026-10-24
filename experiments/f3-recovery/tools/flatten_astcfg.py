"""Control: flatten each L1-stop design.v and recompute AST/CFG similarity.

The paper's Algorithm 2/3 read the top module only; Loki's raise/submodule commits move the
recovered logic into instances, which neither metric inlines. This script writes a flattened
copy of each L1-stop design (Odin III ``flatten; write_verilog``) and reports the same AST and
CFG similarities, as a control, not as the requested L1-stop number.

Usage: flatten_astcfg.py RUNS_DIR DATASET REF_DIR SANITIZED_DIR OUT_JSON
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path("/home/jamiespa/odin3-ws/work/odin3-cfg/tools/cfg-probe")))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import astcfg  # noqa: E402
import odin3_cfg  # noqa: E402


def flatten(binding: object, source: Path, target: Path) -> None:
    design = odin3_cfg.read_design(binding, source)
    try:
        design.run_script(f'flatten; write_verilog "{target}"')
    finally:
        design.close()


def main() -> int:
    runs, dataset, ref_dir, sanitized, out_path = (Path(a) for a in sys.argv[1:6])
    flat_dir = Path("/tmp/claude-1000/f3-l1-flat")
    flat_dir.mkdir(parents=True, exist_ok=True)
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
        ref, ref_method = astcfg.ref_path(stem, ref_dir, sanitized)
        l1 = runs / f"{design}__f3" / "re" / "design.v"
        row: dict[str, object] = {
            "design": design, "nodes": nodes, "quartile": min(3, rank * 4 // len(designs)),
            "ref_method": ref_method}
        if not l1.is_file():
            row["error"] = "no L1 design.v"
            rows.append(row)
            continue
        flat = flat_dir / f"{design}.v"
        try:
            flatten(binding, l1, flat)
            ast_flat, _ = astcfg.ast_pair(ref, flat, flat, str(key.get("top") or ""))
            cfg_ref = astcfg.cfg_pair(binding, ref, flat, flat)
            row.update(simast_flat=round(ast_flat, 6), simcfg_flat=round(cfg_ref[0], 6))
        except Exception as err:  # noqa: BLE001 - reported per design
            row["error"] = f"{type(err).__name__}: {str(err)[:120]}"
        rows.append(row)
        print(design, json.dumps({k: v for k, v in row.items()
                                  if k not in ("design", "nodes")}), flush=True)
    out_path.write_text(json.dumps(rows, sort_keys=True, indent=1) + "\n", encoding="utf-8")
    for metric in ("simast", "simcfg"):
        sel = [r for r in rows if f"{metric}_flat" in r]
        if sel:
            print(metric, "flat mean",
                  round(sum(float(r[f"{metric}_flat"]) for r in sel) / len(sel), 6),
                  "designs", len(sel))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
