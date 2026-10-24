"""Control: flatten each L1-stop design.v and recompute AST/CFG similarity.

The paper's Algorithm 2/3 read the top module only; Loki's raise/submodule commits move the
recovered logic into instances, which neither metric inlines. This script writes a flattened
copy of each L1-stop design (Odin III ``flatten; write_verilog``) and reports the same AST and
CFG similarities, as a control, not as the requested L1-stop number.

Usage: flatten_astcfg.py RUNS_DIR DATASET REF_DIR SANITIZED_DIR OUT_JSON
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path("/home/jamiespa/odin3-ws/work/odin3-cfg/tools/cfg-probe")))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import astcfg  # noqa: E402
import odin3_cfg  # noqa: E402

ODIN3 = "/home/jamiespa/odin3-ws/odin3/build/release/odin3"


def flatten(source: Path, target: Path) -> None:
    """CLI flatten with the top named: the Python reader's implicit top resolution refuses the
    uninstantiated committed function modules; ``--top`` wins over it (same build)."""
    script = (f'read_verilog "{source}"; hierarchy --top top; proc; flatten; '
              f'write_verilog "{target}"')
    subprocess.run([ODIN3, "--top", "top", "-p", script], check=True, capture_output=True,
                   text=True)
    # flatten cannot remove a dead module from the IR, so write_verilog emits the uninstantiated
    # committed modules after the flattened top; keep the top module alone for the metrics.
    text = target.read_text(encoding="utf-8")
    starts = [m.start() for m in re.finditer(r"(?m)^module\s", text)]
    if len(starts) > 1:
        cut = text[: starts[1]]
        last = cut.rfind("endmodule")
        if last >= 0:
            cut = cut[: last + len("endmodule")] + "\n"
        target.write_text(cut, encoding="utf-8")


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
            flatten(l1, flat)
            ast_flat, _ = astcfg.ast_pair(ref, flat, flat, str(key.get("top") or ""))
            row["simast_flat"] = round(ast_flat, 6)
            try:
                cfg_ref = astcfg.cfg_pair(binding, ref, flat, flat)
                row["simcfg_flat"] = round(cfg_ref[0], 6)
            except ValueError as err:
                row["cfg_error"] = str(err)[:120]
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
