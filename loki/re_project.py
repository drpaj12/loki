"""``loki re-project``: a Wyrd project that runs ``loki re`` over a dataset (L1 spec 13)."""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path

from loki.schemas import FLOORS

SEP = "__"
ARCH = "k6_frac_N10_frac_chain_mem32K_40nm"


def _q(text: str) -> str:
    return json.dumps(text)


def write_re_project(
    dataset: Path, floors: Sequence[str], split: str, calib: Path, out: Path
) -> Path:
    """Write ``out/wyrd.toml``: one design per (design, floor) of ``split`` whose floor status is
    ``ok``, named ``<id>__<floor>`` with that floor's ``netlist.blif`` as its file, and one recipe
    ``re`` that runs the ``loki-re`` step. Returns the toml path."""
    bad = [f for f in floors if f not in FLOORS]
    if bad or not floors:
        raise ValueError(f"floors must be among {FLOORS}, got {list(floors)}")
    if split not in ("train", "test"):
        raise ValueError(f"split must be train or test, got {split!r}")
    manifest = json.loads((dataset / "manifest.json").read_text(encoding="utf-8"))
    names: list[tuple[str, str]] = []
    for entry in sorted(manifest["designs"], key=lambda e: e["design"]):
        if entry["split"] != split:
            continue
        for floor in floors:
            info = entry["floors"].get(floor)
            if info is not None and info["status"] == "ok":
                names.append((f"{entry['design']}{SEP}{floor}",
                              str((dataset / entry["design"] / floor / "netlist.blif").resolve())))
    if not names:
        raise ValueError(f"no ok {split} design for floors {list(floors)} in {dataset}")
    lines = ['[project]', 'name = "loki-l1"', ""]
    for name, path in names:
        lines += ["[[design]]", f"name = {_q(name)}", f"files = [{_q(path)}]", ""]
    lines += [
        "[recipe.re]",
        f'steps = [{{ use = "loki-re", calib = {_q(str(calib.resolve()))}, '
        f'dataset = {_q(str(dataset.resolve()))} }}]',
        "",
        "[sweep]",
        'recipe = ["re"]',
        "design = [" + ", ".join(_q(n) for n, _ in names) + "]",
        f"arch = [{_q(ARCH)}]",
        "",
    ]
    out.mkdir(parents=True, exist_ok=True)
    toml = out / "wyrd.toml"
    toml.write_text("\n".join(lines), encoding="utf-8")
    return toml
