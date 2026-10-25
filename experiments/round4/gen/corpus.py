"""Deterministic corpus generation: parameter sampling by region, unique text, Wyrd project.

Usage: ``python -m gen.corpus OUT_DIR [--pilot]`` (from ``experiments/round4``). Writes
``OUT_DIR/designs/<id>/{<id>.v,design.json}``, ``OUT_DIR/wyrd.toml`` (same layout as
``loki bench init``, k6 architecture, floors f1, f2, f3) and ``OUT_DIR/corpus.csv`` (design,
family, split, seed, params). ``--pilot`` writes the dry-run designs (ids ``r4p_``, a separate seed
space, two designs per family and split) used only to check that the templates build.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import random
from pathlib import Path
from typing import Any

from gen.regions import FAMILIES, N_IID, N_OOD, N_TRAIN, REGIONS, Region
from gen.templates import GENERATORS

ARCH = "k6_frac_N10_frac_chain_mem32K_40nm"
FLOORS = '[{ use = "loki-dataset", floors = ["f1", "f2", "f3"] }]'
SPLITS = (("train", N_TRAIN), ("iid", N_IID), ("ood", N_OOD))


def _seed(tag: str, family: str, attempt: int) -> int:
    h = hashlib.sha256(f"{tag}:{family}:{attempt}".encode()).hexdigest()
    return int(h[:8], 16)


def draw(region: Region, ood: bool, rnd: random.Random) -> tuple[dict[str, Any], int]:
    """One parameter dict; ``ood`` forces at least one test-only value. Second value: number of
    parameters that took a test-only value."""
    flippable = [k for k, (_, test) in sorted(region.items()) if test]
    flip: set[str] = set()
    if ood:
        flip.add(rnd.choice(flippable))
        flip |= {k for k in flippable if rnd.random() < 0.25}
    params: dict[str, Any] = {}
    for k, (train, test) in sorted(region.items()):
        params[k] = rnd.choice(test) if k in flip else rnd.choice(train)
    return params, len(flip)


def family_designs(family: str, tag: str, per_split: dict[str, int]) -> list[dict[str, Any]]:
    """The designs of one family in order train, iid, ood; unique Verilog text."""
    region = REGIONS[family]
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    attempt = 0
    for split, quota in SPLITS:
        want = per_split[split]
        got = 0
        misses = 0
        while got < want and misses < 4000:
            attempt += 1
            seed = _seed(tag, family, attempt)
            rnd = random.Random(seed)
            params, n_test = draw(region, split == "ood", rnd)
            text = GENERATORS[family](params, rnd)
            digest = hashlib.sha256(text.encode()).hexdigest()
            if digest in seen:
                misses += 1
                continue
            seen.add(digest)
            out.append({"family": family, "split": split, "seed": seed, "params": params,
                        "n_test_params": n_test, "text": text, "sha256": digest})
            got += 1
        del quota
    return out


def twin_styles(family: str) -> list[str]:
    train, test = REGIONS[family]["style"]
    styles = list(train) + list(test)
    return [x for x in styles if x != "casez"] if family == "mux" else styles


def twin_designs(family: str, tag: str, n_base: int) -> list[dict[str, Any]]:
    """``n_base`` train-region parameter sets, each in every style (same seed and parameters)."""
    region = REGIONS[family]
    out: list[dict[str, Any]] = []
    for base in range(n_base):
        seed = _seed(tag, family, base + 1)
        rnd = random.Random(seed)
        params, _ = draw(region, False, rnd)
        if family == "mux":
            params["kind"] = "sel"
        if family == "shifter":
            params["amount"] = "barrel"
        for style in twin_styles(family):
            p = dict(params, style=style)
            text = GENERATORS[family](p, random.Random(seed))
            out.append({"family": family, "split": f"base{base:02d}", "seed": seed,
                        "params": p, "n_test_params": int(style in REGIONS[family]["style"][1]),
                        "text": text, "sha256": hashlib.sha256(text.encode()).hexdigest(),
                        "style": style})
    return out


def write_corpus(out: Path, prefix: str, tag: str, per_split: dict[str, int],
                 twins: int = 0) -> int:
    rows: list[dict[str, Any]] = []
    ids: list[str] = []
    for family in FAMILIES:
        ds = twin_designs(family, tag, twins) if twins else family_designs(family, tag, per_split)
        for k, d in enumerate(ds):
            did = f"{prefix}_{family}_{k:03d}"
            ddir = out / "designs" / did
            ddir.mkdir(parents=True, exist_ok=True)
            (ddir / f"{did}.v").write_text(d["text"], encoding="utf-8")
            spec = {"schema": 1, "design": did, "benchmark": "micro", "top": None,
                    "files": [{"path": f"{did}.v", "sha256": d["sha256"]}],
                    "source": {"url": "synthetic:round4", "commit": tag, "license": "MIT"}}
            (ddir / "design.json").write_text(
                json.dumps(spec, sort_keys=True, indent=2) + "\n", encoding="utf-8")
            ids.append(did)
            rows.append({"design": did, "family": family, "split": d["split"],
                         "seed": d["seed"], "n_test_params": d["n_test_params"],
                         "params": json.dumps(d["params"], sort_keys=True)})
    lines = ['[project]', 'name = "loki-l0"', ""]
    for did in ids:
        lines += ["[[design]]", f'name = "{did}"', f'files = ["designs/{did}/{did}.v"]', ""]
    lines += ["[recipe.l0]", f"steps = {FLOORS}", "", "[sweep]", 'recipe = ["l0"]',
              "design = [" + ", ".join(f'"{i}"' for i in ids) + "]", f'arch = ["{ARCH}"]', ""]
    (out / "wyrd.toml").write_text("\n".join(lines), encoding="utf-8")
    with (out / "corpus.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, ["design", "family", "split", "seed", "n_test_params", "params"],
                           lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    return len(ids)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("out", type=Path)
    ap.add_argument("--pilot", action="store_true")
    ap.add_argument("--twins", type=int, default=0, help="twin set with this many bases per family")
    args = ap.parse_args()
    if args.twins:
        n = write_corpus(args.out, "r4t", "r4twin", {}, twins=args.twins)
    elif args.pilot:
        n = write_corpus(args.out, "r4p", "r4pilot", {"train": 2, "iid": 1, "ood": 2})
    else:
        n = write_corpus(args.out, "r4", "r4", {"train": N_TRAIN, "iid": N_IID, "ood": N_OOD})
    print(f"{n} designs -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
