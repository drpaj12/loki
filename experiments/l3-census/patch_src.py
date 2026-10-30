"""Write the two patched VerilogEval references (enum cast removed, state variables plain
logic): ``python -B patch_src.py``."""

from __future__ import annotations

import importlib
import re
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
lib: Any = importlib.import_module("l3lib")


def main() -> int:
    out = lib.OUT / "patched"
    out.mkdir(parents=True, exist_ok=True)
    for name in lib.PATCHED:
        ref = lib.VEVAL / f"{name}_ref.sv"
        text = re.sub(r"\bStates'\(", "(", ref.read_text(encoding="utf-8"))
        text = text.replace("States state, next;", "logic [3:0] state, next;")
        (out / ref.name).write_text(text, encoding="utf-8")
    print("patched", len(lib.PATCHED))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
