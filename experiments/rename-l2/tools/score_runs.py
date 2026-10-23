"""Resolve renamed runs back to the original L0 names and score them against the original GT.

The Wyrd project nests each run as ``runs/<design>__<floor>/<arch>/<hash>/<step>/re/``; every
``overlay.json`` found under ``--runs`` is one run.  Its overlay and report names are translated
through the inverse rename map (identity for the base variant), ``loki.score.metrics.score_run``
scores it against the original-named floor, the translated ``score.json`` is written next to the
run, and a per-detector precision/recall/F1 is computed with Loki's own greedy matcher.
Aggregates use Loki's ``aggregate`` so the numbers are the runbook's numbers plus ECE.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import shutil

from loki.score.gt import SCORED_TYPES, load_gt
from loki.score.match import match_greedy
from loki.score.metrics import aggregate, load_preds, score_run

TRANSLATED = pathlib.Path("/tmp/claude-1000/rn2-translated")
DETECTOR_KINDS = {
    "arith": ("adder", "subtractor", "adder_cin", "comparator", "eq_const"),
    "ff_pattern": ("ff_en", "ff_srst", "register"),
    "fsm": ("fsm",),
    "hard": ("hard_add", "hard_mul", "hard_mem"),
    "mux": ("mux_bit", "mux_tree", "mux"),
    "seqfn": ("counter",),
}


def inverse_map(rename_map: pathlib.Path, design: str) -> dict[str, str]:
    entry = json.loads(rename_map.read_text(encoding="utf-8"))["designs"][design]
    out: dict[str, str] = {}
    for kind in ("cells", "nets", "modules"):
        out.update({new: old for old, new in entry[kind].items()})
    return out


def translate(obj: object, inv: dict[str, str]) -> object:
    if isinstance(obj, dict):
        return {inv.get(k, k) if isinstance(k, str) else k: translate(v, inv)
                for k, v in obj.items()}
    if isinstance(obj, list):
        return [translate(v, inv) for v in obj]
    if isinstance(obj, str):
        return inv.get(obj, obj)
    return obj


def detector_scores(run_dir: pathlib.Path, floor_dir: pathlib.Path) -> dict[str, object]:
    overlay = json.loads((run_dir / "overlay.json").read_text(encoding="utf-8"))
    preds = load_preds(overlay)
    instances, _, _, _ = load_gt(floor_dir)
    out: dict[str, dict[str, float | int | str]] = {}
    pairs = {(det, kind) for det, kinds in DETECTOR_KINDS.items() for kind in kinds
             if kind in SCORED_TYPES}
    pairs |= {(p.detector, p.kind) for p in preds if p.kind in SCORED_TYPES}
    for det, kind in sorted(pairs):
        sel = [p for p in preds if p.detector == det and p.kind == kind and p.counted(0.5)]
        types = SCORED_TYPES[kind]
        kg = [g for g in instances if g.type in types]
        pred_t = [(p.id, p.cells) for p in sel]
        gt_t = [(g.gid, g.footprint) for g in kg]
        matched = len(match_greedy(pred_t, gt_t, 0.5))
        prec = matched / len(sel) if sel else "n/a"
        rec = matched / len(kg) if kg else "n/a"
        f1 = ("n/a" if not isinstance(prec, float) or not isinstance(rec, float)
              else (0.0 if prec + rec == 0 else round(2 * prec * rec / (prec + rec), 6)))
        out[f"{det}/{kind}"] = {"pred": len(sel), "gt": len(kg), "matched": matched,
                               "precision": prec, "recall": rec, "f1": f1}
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--variant", required=True)
    ap.add_argument("--runs", required=True, type=pathlib.Path)
    ap.add_argument("--dataset", required=True, type=pathlib.Path)
    ap.add_argument("--out", required=True, type=pathlib.Path)
    ap.add_argument("--rename-map", type=pathlib.Path)
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    scores = []
    per_detector: dict[str, dict[str, object]] = {}
    seen = 0
    for overlay in sorted(args.runs.rglob("overlay.json")):
        run_dir = overlay.parent
        rel = run_dir.relative_to(args.runs)
        name = rel.parts[0]
        design, floor = name.rsplit("__", 1)
        floor_dir = args.dataset / design / floor
        inv = inverse_map(args.rename_map, design) if args.rename_map else {}
        flat = "__".join(rel.parts)
        tdir = TRANSLATED / args.variant / flat
        if tdir.exists():
            shutil.rmtree(tdir)
        tdir.mkdir(parents=True)
        for item in ("overlay.json", "report.json"):
            obj = json.loads((run_dir / item).read_text(encoding="utf-8"))
            (tdir / item).write_text(
                json.dumps(translate(obj, inv), sort_keys=True) + "\n", encoding="utf-8")
        score = score_run(tdir, floor_dir, 0.5)
        (run_dir / "score.json").write_text(
            json.dumps(score, sort_keys=True, indent=1) + "\n", encoding="utf-8")
        scores.append(score)
        per_detector[f"{design}__{floor}"] = detector_scores(tdir, floor_dir)
        seen += 1
    obj, md = aggregate(scores)
    (args.out / "scores.json").write_text(json.dumps(obj, sort_keys=True, indent=1) + "\n",
                                          encoding="utf-8")
    (args.out / "scores.md").write_text(md, encoding="utf-8")
    (args.out / "detector-per-design.json").write_text(
        json.dumps(per_detector, sort_keys=True, indent=1) + "\n", encoding="utf-8")
    agg: dict[str, dict[str, float | int]] = {}
    for run in per_detector.values():
        for key, row in run.items():
            a = agg.setdefault(key, {"pred": 0, "gt": 0, "matched": 0})
            a["pred"] += int(row["pred"])
            a["gt"] += int(row["gt"])
            a["matched"] += int(row["matched"])
    for a in agg.values():
        prec = a["matched"] / a["pred"] if a["pred"] else None
        rec = a["matched"] / a["gt"] if a["gt"] else None
        a["precision"] = round(prec, 6) if prec is not None else "n/a"
        a["recall"] = round(rec, 6) if rec is not None else "n/a"
        a["f1"] = ("n/a" if prec is None or rec is None
                   else round(0.0 if prec + rec == 0 else 2 * prec * rec / (prec + rec), 6))
    (args.out / "detector-aggregate.json").write_text(
        json.dumps(agg, sort_keys=True, indent=1) + "\n", encoding="utf-8")
    print(f"{args.variant}: scored {seen} runs into {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
