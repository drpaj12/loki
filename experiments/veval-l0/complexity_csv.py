"""Per-ref complexity score and quartile (Gate-Breaker eq. 2) as complexity.csv.

Reuses work/gatebreaker-exp2/scripts/complexity.py unchanged (pyverilog AST where the ref
parses, regex fallback otherwise: the documented deviation). Columns: design, problem,
ref_lines, score, quartile, method.

Usage: complexity_csv.py REF_DIR GB_SCRIPTS_DIR OUT_CSV
"""

from __future__ import annotations

import csv
import importlib
import sys
from pathlib import Path


def main() -> int:
    ref_dir, scripts, out = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
    sys.path.insert(0, str(scripts))
    complexity = importlib.import_module("complexity")

    rows = []
    for ref in sorted(ref_dir.glob("*_ref.sv")):
        problem = ref.stem.removesuffix("_ref")
        c = complexity.score_file(str(ref))
        lines = len(ref.read_text(encoding="utf-8").splitlines())
        rows.append({"design": f"ve_{problem}", "problem": problem, "ref_lines": lines,
                     "score": c.score, "quartile": complexity.quartile(c.score),
                     "method": c.method})
    with out.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    print(len(rows), "designs")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
