"""Odin III builds of the census designs: ``python -I build_odin.py CELL [NAME_FILTER]``.

CELL is O-gate (f3), O-lut (f2) or O-hard (f1-k6). Writes OUT/build/CELL/<design>/<floor>/.
Smallest source first; resumes (a design with a status file is skipped).
"""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
lib: Any = importlib.import_module("l3lib")
bd: Any = importlib.import_module("loki.build")


def main(cell: str, only: str) -> int:
    floor = lib.ODIN_CELLS[cell]
    base = lib.OUT / "build" / cell
    rows = sorted(lib.manifest(), key=lambda r: (Path(r["src"]).stat().st_size, r["design"]))
    n = 0
    for r in rows:
        if only and only not in r["design"]:
            continue
        ddir = base / r["design"]
        done = ddir / "status.json"
        if done.is_file():
            continue
        arch = None if floor == "f3" else lib.ARCH
        src = Path(r.get("osrc", r["src"]))
        res = bd.build_floor(r["design"], [src], r["top"] or None, floor, arch, base, lib.ODIN)
        ddir.mkdir(parents=True, exist_ok=True)
        done.write_text(json.dumps({"status": res.status, "reason": res.reason}, sort_keys=True),
                        encoding="utf-8")
        n += 1
    print(cell, "built", n)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else ""))
