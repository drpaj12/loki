"""Run the round-5 f2 flow pass by pass and write a netlist plus v2 map after each pass."""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from loki.odin import odin_module, read_flags, register_slang

PASSES: tuple[tuple[str, str], ...] = (
    ("proc", ""), ("fsm", ""), ("opt", ""), ("flatten", ""), ("opt", "-full"),
    ("wreduce", ""), ("lower", ""), ("abc", "--lut 6"),
)
MAP_OPTS = "--name-style hash --prov-map refs"


def _q(p: Path | str) -> str:
    return f'"{p}"'


def run_snapshots(files: Sequence[Path], arch: Path, out: Path, top: str | None = None,
                  detect: bool = True) -> dict[str, Any]:
    """Write ``out/s<k>.json`` (+ ``.names``) for k = 1..8, ``s0`` when writable, and for the
    last two passes ``out/b<k>.blif`` (+ ``.names``). Returns the manifest (also written)."""
    mod = odin_module()
    o = mod.default()
    o.load_abc()
    if any(f.suffix == ".sv" for f in files):
        register_slang(o)
    out.mkdir(parents=True, exist_ok=True)
    design = mod.Design(o)
    if top:
        o.lib.odin3_pass_set_top_name(top.encode())
    try:
        paths = " ".join(_q(f) for f in files)
        design.run_script(
            f"read_arch {_q(arch)}; read_verilog {read_flags(files)} --prov-ast refs {paths}")
        written = {"s0": _try_write(design, out / "s0.json")}
        words: dict[str, Any] = {}
        for k, (name, args) in enumerate(PASSES, start=1):
            design.run_script(f"{name} {args}".strip())
            _write(design, out / f"s{k}.json")
            if name == "wreduce":
                words = _words(design)
            if detect and k >= 7:
                design.run_script(f"write_blif --vtr {MAP_OPTS} {_q(out / f'b{k}.blif')}")
    finally:
        if top:
            o.lib.odin3_pass_set_top_name(o.ffi.NULL)
    manifest = {"schema": 1, "passes": [list(p) for p in PASSES], "s0": written["s0"],
                "words": words}
    (out / "manifest.json").write_text(json.dumps(manifest, sort_keys=True), encoding="utf-8")
    return manifest


def _write(design: Any, path: Path) -> None:
    design.run_script(f"write_json {_q(path)} {MAP_OPTS}")


def _try_write(design: Any, path: Path) -> bool:
    try:
        _write(design, path)
    except Exception:
        return False
    return True


def _words(design: Any) -> dict[str, Any]:
    """Word cells at S6 (the ground-truth source), as plain data."""
    from loki.snapshot import take_snapshot

    snap = take_snapshot(design)
    return {
        "top": snap.top,
        "words": [
            {"id": w.id, "type": w.type, "name": w.name, "fsm": w.fsm,
             "params": {k: v for k, v in w.params.items() if not isinstance(v, str)},
             "in": [[p.name, list(p.nets)] for p in w.inputs],
             "out": [[p.name, list(p.nets)] for p in w.outputs]}
            for w in snap.words
        ],
    }
