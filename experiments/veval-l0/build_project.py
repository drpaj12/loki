"""Write the Wyrd project for the veval-L0 run (loki bench layout, local VerilogEval refs).

Same layout as ``loki bench init --suite verilog-eval`` (design.json per design, top RefModule)
but: refs come from a local directory (no clone), only the k6 architecture is swept (floors
f1-k6, f2, f3; f1-earch is skipped), and the sweep lists designs smallest source first.

Usage: build_project.py REF_DIR OUT_DIR
"""

from __future__ import annotations

import sys
from pathlib import Path

from loki.bench import VERILOG_EVAL, ARCHS, _copy_design, _q

FLOORS = '[{ use = "loki-dataset", floors = ["f1", "f2", "f3"] }]'


def main() -> int:
    ref_dir, out = Path(sys.argv[1]), Path(sys.argv[2])
    refs = sorted(ref_dir.glob("*_ref.sv"))
    if len(refs) != 156:
        raise SystemExit(f"expected 156 refs in {ref_dir}, found {len(refs)}")
    size = {r: len(r.read_text(encoding="utf-8").splitlines()) for r in refs}
    ordered = sorted(refs, key=lambda r: (size[r], r.name))
    ids = [_copy_design(r, "verilog-eval", out, dict(VERILOG_EVAL)) for r in ordered]
    lines = ['[project]', 'name = "loki-l0"', ""]
    for did in ids:
        lines += ["[[design]]", f"name = {_q(did)}",
                  f"files = [{_q(f'designs/{did}/{did}.sv')}]", 'top = "RefModule"', ""]
    lines += ["[recipe.l0]", f"steps = {FLOORS}", "", "[sweep]", 'recipe = ["l0"]',
              "design = [" + ", ".join(_q(i) for i in ids) + "]",
              f"arch = [{_q(ARCHS[0])}]", ""]
    (out / "wyrd.toml").write_text("\n".join(lines), encoding="utf-8")
    print(f"{len(ids)} designs -> {out}/wyrd.toml")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
