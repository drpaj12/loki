"""Stage 1/3 builds: Odin III synthesis of the population in one arm, both floors.

Usage: ``python -I build_arms.py ARM`` (env as in docs/runbook-l0.md; run from outside the repo).
Writes ``OUT/build/ARM/<design>/{f3,f2}`` (netlist.blif, key.json, ...) and ``fsm.log``.
Resumes: a design whose floors are all decided is skipped.
"""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
lib: Any = importlib.import_module("fsmlib")
od: Any = importlib.import_module("loki.odin")
bd: Any = importlib.import_module("loki.build")

_STASH: dict[str, list[str]] = {}


def open_front_logged(floor: str, files: Any, top: Any, arch_xml: Any, cmos6: Any) -> Any:
    """loki.odin.open_front with the fsm log lines kept (same steps, same errors)."""
    mod = od.odin_module()
    o = mod.default()
    o.load_abc()
    reader = od.read_script(floor, files, arch_xml, cmos6)
    design = mod.Design(o)
    with o.capture_log() as records:
        try:
            design.run_script(reader)
            instances = od.take_instances(design)
            design.run_script(od.FRONT)
        except mod.Odin3Error as err:
            raise od.OdinSkip(od.error_reason(err, records, o.lib)) from err
    _STASH[floor] = [r.message for r in records if "fsm" in r.message]
    return design, instances


def main(arm: str) -> int:
    od.FRONT = lib.ARMS[arm]
    bd.open_front = open_front_logged
    base = lib.OUT / "build" / arm
    status: dict[str, dict[str, str]] = {}
    for d in lib.population():
        did = d["design"]
        ddir = base / did
        done = ddir / "done.json"
        if done.is_file():
            continue
        ddir.mkdir(parents=True, exist_ok=True)
        res: dict[str, str] = {}
        for floor in lib.FLOORS:
            arch = None if floor == "f3" else lib.ARCH
            r = bd.build_floor(did, [lib.src_path(did)], None, floor, arch, base, lib.ODIN)
            res[floor] = r.status if not r.reason else f"{r.status}: {r.reason}"
            if floor == "f3":
                (ddir / "fsm.log").write_text("\n".join(_STASH.get(floor, [])) + "\n", encoding="utf-8")
        done.write_text(json.dumps(res, sort_keys=True), encoding="utf-8")
        status[did] = res
    print(arm, "built", len(status))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1]))
