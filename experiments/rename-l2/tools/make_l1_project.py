"""Write a Wyrd project that runs ``loki re`` over one dataset's floors.

Same project shape as ``loki re-project`` (one design per ``<id>__<floor>``, one ``re`` recipe
running the ``loki-re`` step), with two differences the renamed dataset needs: the floor's
directory is read from the manifest's ``dir`` field (the renamed floors are aliased), and the
score dataset can differ from the netlist dataset (a renamed netlist is scored by translation,
not by the step).  ``--odin3-root`` is passed through the step when given.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

SEP = "__"
ARCH = "k6_frac_N10_frac_chain_mem32K_40nm"


def _q(text: str) -> str:
    return json.dumps(text)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", required=True, type=Path)
    ap.add_argument("--floors", required=True)
    ap.add_argument("--split", default=None)
    ap.add_argument("--calib", default="none", help="calibration directory or 'none'")
    ap.add_argument("--score-dataset", type=Path, default=None)
    ap.add_argument("--odin3-root", default=None)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--name", default="loki-l1")
    args = ap.parse_args()
    floors = [f.strip() for f in args.floors.split(",") if f.strip()]
    score_dataset = args.score_dataset or args.dataset
    manifest = json.loads((args.dataset / "manifest.json").read_text(encoding="utf-8"))
    names: list[tuple[str, str]] = []
    for entry in sorted(manifest["designs"], key=lambda e: e["design"]):
        if args.split is not None and entry.get("split") != args.split:
            continue
        for floor in floors:
            info = entry["floors"].get(floor)
            if info is None or info.get("status") != "ok":
                continue
            sub = info.get("dir", floor)
            path = (args.dataset / entry["design"] / sub / "netlist.blif").resolve()
            names.append((f"{entry['design']}{SEP}{floor}", str(path)))
    if not names:
        raise SystemExit(f"no ok design for floors {floors} in {args.dataset}")
    step = '{ use = "loki-re"'
    if args.calib not in ("none", ""):
        step += f', calib = {_q(args.calib)}'
    step += f', dataset = {_q(str(score_dataset.resolve()))}'
    if args.odin3_root:
        step += f', odin3_root = {_q(args.odin3_root)}'
    step += " }"
    lines = ["[project]", f"name = {_q(args.name)}", ""]
    for name, path in names:
        lines += ["[[design]]", f"name = {_q(name)}", f"files = [{_q(path)}]", ""]
    lines += ["[recipe.re]", f"steps = [{step}]", "", "[sweep]",
              'recipe = ["re"]',
              "design = [" + ", ".join(_q(n) for n, _ in names) + "]",
              f"arch = [{_q(ARCH)}]", ""]
    args.out.mkdir(parents=True, exist_ok=True)
    toml = args.out / "wyrd.toml"
    toml.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {toml} ({len(names)} designs)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
