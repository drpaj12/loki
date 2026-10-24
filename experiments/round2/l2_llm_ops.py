"""RQ-L2/L7: operator multiset of the Gate-Breaker LLM samples, by elaborating them with Odin III.

Each functionally correct sample (VerilogEval testbench success, round 1) is read with
``read_verilog --nolatches --vtr-compat`` and put through the same front as the L0 key
(``loki.odin.FRONT``); its word cells give the operator multiset, scored against the key of the
reference with ``opf1.score``. Run under the heavy lock (it loads Odin III).

Usage: l2_llm_ops.py   -> ``<data>/l2/llm_ops.json`` and ``l2_llm_ops.csv``
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

import odin3 as mod
import opf1
import r2lib

from loki.odin import FRONT
from loki.snapshot import take_snapshot

GB = r2lib.GB / "data"
OUT = r2lib.DATA / "l2" / "llm_ops.json"


def elaborate(path: Path) -> Counter[opf1.OpKey]:
    o = mod.default()
    o.load_abc()
    design = mod.Design(o)
    try:
        with o.capture_log():
            design.run_script(f'read_verilog --nolatches --vtr-compat "{path}"; {FRONT}')
        snap = take_snapshot(design)
    finally:
        design.close()
    out: Counter[opf1.OpKey] = Counter()
    for w in snap.words:
        op = opf1.word_op(w.type, w.params)
        if op is not None:
            out[op] += 1
    return out


def main() -> int:
    validations = json.loads((GB / "validations" / "validations.json").read_text("utf-8"))
    rows: list[dict[str, Any]] = []
    errors = 0
    for v in validations:
        if v.get("category") != "success":
            continue
        stem = str(v["design"]).removesuffix("_ref")
        design = f"ve_{stem}"
        key_path = r2lib.VEVAL / design / "f3" / "words.json"
        if not key_path.is_file():
            continue
        key = opf1.key_ops(opf1.load(key_path))
        try:
            got = elaborate(Path(v["rtl"]))
        except Exception as err:
            errors += 1
            rows.append({"design": design, "k": v["k"], "error": f"{type(err).__name__}"})
            continue
        rows.append({"design": design, "k": v["k"], **opf1.score(key, got)})
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(rows, sort_keys=True, indent=1) + "\n", encoding="utf-8")
    print(f"samples {len(rows)} elaboration errors {errors}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
