"""Write ``labels_rtl.csv``: RTL-side pattern counts per design: ``python -B label.py``.

Reads OUT/build/O-gate/<design>/f3/words.json (word-level IR of the HDL) and the source.
Designs with no words.json (Odin III skipped them) are written with ``status`` = ``no-words``.
"""

from __future__ import annotations

import csv
import importlib
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
lib: Any = importlib.import_module("l3lib")
lab: Any = importlib.import_module("labels_rtl")


def main() -> int:
    rows = []
    for r in lib.manifest():
        wf = lib.OUT / "build" / "O-gate" / r["design"] / "f3" / "words.json"
        row = {"corpus": r["corpus"], "design": r["design"]}
        if not wf.is_file():
            rows.append({**row, "status": "no-words", **{p: "" for p in lab.PATTERNS}})
            continue
        words = json.loads(wf.read_text(encoding="utf-8"))
        text = Path(r["src"]).read_text(encoding="utf-8", errors="replace")
        rows.append({**row, "status": "ok", **lab.label_design(words, text)})
    cols = ["corpus", "design", "status", *lab.PATTERNS]
    with (Path(__file__).resolve().parent / "results" / "labels_rtl.csv").open(
            "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, cols, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    print(len(rows), "designs")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
