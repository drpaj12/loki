"""Check that the renamed dataset is a naming-only rewrite of the assembled L0 dataset.

For every renamed netlist: inverse-map every token through ``rename-map.json`` and compare the
token sequence with the original-named netlist (a structure-preserving bijection), check that the
``.blackbox`` library blocks are byte-identical, and check that no numbered identifier (``n<k>``)
survives outside the library section.  The renamed dataset must hold netlists only: no labels,
graph, words or key files.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

IDENT = re.compile(r"n\d+\Z")


def inverse(rename_map: Path, design: str) -> dict[str, str]:
    entry = json.loads(rename_map.read_text(encoding="utf-8"))["designs"][design]
    out: dict[str, str] = {}
    for kind in ("cells", "nets", "modules"):
        for old, new in entry[kind].items():
            out[new] = old
    return out


def library_lines(lines: list[str]) -> list[str]:
    """The lines of every library block (``.model`` through ``.end`` with ``.blackbox``), in order.

    The ``.blackbox`` marker sits after the model header, so the block starts at its ``.model``.
    """
    out: list[str] = []
    current: str | None = None
    start = 0
    inside = False
    for i, raw in enumerate(lines):
        s = raw.strip()
        if s.startswith(".model"):
            current = s.split()[1]
            start = i
            inside = False
        elif s.startswith(".blackbox"):
            inside = True
        elif s.startswith(".end") and current is not None:
            if inside:
                out.extend(lines[start:i + 1])
            current = None
    return out


def inverse_token(token: str, inv: dict[str, str]) -> str:
    """A BLIF token with its identifier inverted; ``pin=net`` keeps the pin name."""
    if token in inv:
        return inv[token]
    if "=" in token:
        pin, value = token.split("=", 1)
        if value in inv:
            return f"{pin}={inv[value]}"
    return token


def check_design(base: Path, renamed: Path, inv: dict[str, str]) -> list[str]:
    errors: list[str] = []
    base_lines = base.read_text(encoding="utf-8").splitlines()
    ren_lines = renamed.read_text(encoding="utf-8").splitlines()
    base_toks = "\n".join(base_lines).split()
    ren_toks = "\n".join(ren_lines).split()
    mapped = [inverse_token(t, inv) for t in ren_toks]
    if mapped != base_toks:
        for i, (a, b) in enumerate(zip(mapped, base_toks, strict=False)):
            if a != b:
                errors.append(f"token {i}: {a!r} != {b!r}")
                break
        else:
            errors.append(f"token count {len(mapped)} != {len(base_toks)}")
    # every token that was renamed must be in the map, and the map must be injective
    if len(set(inv)) != len(inv):
        errors.append("rename map is not injective")
    for t in ren_toks:
        if t in inv:
            continue
        value = t.split("=", 1)[1] if "=" in t else t
        if IDENT.match(value):
            errors.append(f"numbered identifier survives outside the map: {t}")
            break
    if library_lines(base_lines) != library_lines(ren_lines):
        errors.append(".blackbox library blocks differ")
    return errors


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", required=True, type=Path)
    ap.add_argument("--renamed", required=True, type=Path)
    ap.add_argument("--out", type=Path)
    args = ap.parse_args()
    manifest = json.loads((args.dataset / "manifest.json").read_text(encoding="utf-8"))
    renamed_manifest = json.loads((args.renamed / "manifest.json").read_text(encoding="utf-8"))
    renamed_dirs = {d["design"]: d["floors"] for d in renamed_manifest["designs"]}
    rename_map = args.renamed / "rename-map.json"
    extra = sorted(p.name for p in args.renamed.iterdir()
                   if p.name not in ("manifest.json", "rename-map.json")
                   and not p.is_dir())
    checked = 0
    bad: dict[str, list[str]] = {}
    for d in sorted(manifest["designs"], key=lambda x: x["design"]):
        design = d["design"]
        inv = inverse(rename_map, design)
        for floor, info in sorted(d["floors"].items()):
            if info["status"] != "ok":
                continue
            sub = renamed_dirs[design][floor]["dir"]
            base = args.dataset / design / floor / "netlist.blif"
            renamed = args.renamed / design / sub / "netlist.blif"
            if not renamed.is_file():
                bad[f"{design}/{floor}"] = ["renamed netlist missing"]
                continue
            errors = check_design(base, renamed, inv)
            checked += 1
            if errors:
                bad[f"{design}/{floor}"] = errors[:3]
    stats = json.loads(rename_map.read_text(encoding="utf-8"))["stats"]
    summary = {"netlists_checked": checked, "failures": bad, "extra_top_level_files": extra,
               "rename_stats": stats}
    text = json.dumps(summary, sort_keys=True, indent=1) + "\n"
    if args.out:
        args.out.write_text(text, encoding="utf-8")
    print(f"checked {checked} netlists, {len(bad)} failures, "
          f"extra top-level files {extra}, identifiers {stats['identifiers']}")
    for key, errors in list(bad.items())[:10]:
        print(" ", key, errors[0])
    return 0 if not bad and not extra else 1


if __name__ == "__main__":
    raise SystemExit(main())
