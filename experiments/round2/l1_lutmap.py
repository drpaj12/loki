"""RQ-L1: re-map the f3 gate netlists to LUT6 with Odin III and record which gates each LUT covers.

Script per design (the f2 floor's mapping step, applied to the f3 netlist instead of the
elaborated RTL): ``read_blif <f3 netlist.blif>; abc --lut 6; write_blif <out>``. The LUT netlist
gets ``.cname L<k>`` lines (Odin III drops cnames in ``abc``) and is written under
``<out>/<design>/f2/netlist.blif`` so ``loki re --floor f2`` accepts it. ``cover.json`` maps each
LUT to the f3 gate cnames of its cone.

Usage: l1_lutmap.py DATASET OUT [design ...]   (designs default to all with an f3 floor)
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

import blifmap
import odin3 as mod

SCRIPT = "read_blif {src}; abc --lut 6; write_blif {dst}"


def designs_with_f3(dataset: Path) -> list[str]:
    manifest = json.loads((dataset / "manifest.json").read_text(encoding="utf-8"))
    return sorted(str(e["design"]) for e in manifest["designs"]
                  if e["floors"].get("f3", {}).get("status") == "ok")


def remap(src: Path, dst: Path) -> dict[str, object]:
    o = mod.default()
    o.load_abc()
    design = mod.Design(o)
    with tempfile.TemporaryDirectory(prefix="le2-lut-") as tmp:
        raw = Path(tmp) / "lut.blif"
        try:
            design.run_script(SCRIPT.format(src=f'"{src}"', dst=f'"{raw}"'))
        finally:
            design.close()
        text = blifmap.add_cnames(raw.read_text(encoding="utf-8"))
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(text, encoding="utf-8")
    gate = blifmap.read(src)
    lut = blifmap.parse_blif(text)
    cover, netmap, unmatched = blifmap.cover_map(gate, lut)
    return {
        "gate_cells": len(gate.names), "luts": len(lut.names), "unmatched": unmatched,
        "covered_gates": len({g for s in cover.values() for g in s}),
        "cover": {k: sorted(v) for k, v in sorted(cover.items())},
        "netmap": dict(sorted(netmap.items())),
    }


def main() -> int:
    dataset, out = Path(sys.argv[1]), Path(sys.argv[2])
    names = sys.argv[3:] or designs_with_f3(dataset)
    for name in names:
        src = dataset / name / "f3" / "netlist.blif"
        dst = out / name / "f2" / "netlist.blif"
        info = remap(src, dst)
        (out / name / "cover.json").write_text(
            json.dumps(info, sort_keys=True, indent=1) + "\n", encoding="utf-8")
        print(name, {k: v for k, v in info.items() if k not in ("cover", "netmap")}, flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
