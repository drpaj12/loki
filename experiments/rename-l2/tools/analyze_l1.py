"""Summarise L1 runs from their score.json files: per-floor per-kind P/R/F1, macro F1, ECE,
per-design rows, and the base/renamed byte-identity check.

``score.json`` is the translated score for the renamed variant (``score_runs.py`` wrote it after
mapping the overlay back to the original names), so both variants are scored by the same rule
against the same L0 answer key.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import defaultdict
from pathlib import Path

from loki.score.metrics import reliability


def load_scores(runs: Path) -> dict[str, dict]:
    """Every ``score.json`` under the project, keyed ``<design>__<floor>`` (the run's top name)."""
    out: dict[str, dict] = {}
    for path in sorted(runs.rglob("score.json")):
        rel = path.relative_to(runs)
        out[rel.parts[0]] = json.loads(path.read_text(encoding="utf-8"))
    return out


def floor_of(run: str) -> str:
    return run.rsplit("__", 1)[1]


def summarise(runs: Path) -> dict[str, object]:
    scores = load_scores(runs)
    per_kind: dict[str, dict[str, dict[str, int]]] = defaultdict(dict)
    per_floor = defaultdict(lambda: {"counted": 0, "matched": 0, "gt": 0})
    points: list[tuple[float, bool]] = []
    points_floor: dict[str, list[tuple[float, bool]]] = defaultdict(list)
    points_kind: dict[str, list[tuple[float, bool]]] = defaultdict(list)
    per_design: dict[str, dict[str, object]] = {}
    for run, score in sorted(scores.items()):
        floor = floor_of(run)
        row = {"design": run.rsplit("__", 1)[0], "floor": floor}
        counted = matched = gt = 0
        for kind, data in sorted(score["constructs"].items()):
            row[f"{kind}_counted"] = data["counted"]
            bucket = per_kind[floor].setdefault(
                kind, {"counted": 0, "matched": 0, "gt": 0, "designs": 0})
            for key in ("counted", "matched", "gt"):
                bucket[key] += int(data[key])
            bucket["designs"] += 1
            counted += int(data["counted"])
            matched += int(data["matched"])
            gt += int(data["gt"])
            for p, y in score["points"].get(kind, []):
                points.append((float(p), bool(y)))
                points_floor[floor].append((float(p), bool(y)))
                points_kind[kind].append((float(p), bool(y)))
        pf = per_floor[floor]
        pf["counted"] += counted
        pf["matched"] += matched
        pf["gt"] += gt
        row.update({"counted": counted, "matched": matched, "gt": gt,
                    "f1_micro": round(2 * matched / (counted + gt), 6) if counted + gt else 0.0,
                    "bus_precision": score["bus"]["precision"],
                    "bus_recall": score["bus"]["recall"],
                    "final_equiv": score["final_equiv"].get("status")})
        per_design[run] = row
    tables: dict[str, dict[str, dict[str, object]]] = {}
    macro: dict[str, float] = {}
    for floor, kinds in sorted(per_kind.items()):
        table = {}
        f1s = []
        for kind, b in sorted(kinds.items()):
            prec = b["matched"] / b["counted"] if b["counted"] else None
            rec = b["matched"] / b["gt"] if b["gt"] else None
            f1 = (None if prec is None or rec is None
                  else 0.0 if prec + rec == 0 else 2 * prec * rec / (prec + rec))
            table[kind] = {"counted": b["counted"], "matched": b["matched"], "gt": b["gt"],
                           "precision": None if prec is None else round(prec, 6),
                           "recall": None if rec is None else round(rec, 6),
                           "f1": None if f1 is None else round(f1, 6)}
            if f1 is not None and b["gt"]:
                f1s.append(f1)
        tables[floor] = table
        macro[floor] = round(sum(f1s) / len(f1s), 6) if f1s else 0.0
    return {
        "runs": len(scores),
        "per_floor_totals": {f: dict(v) for f, v in sorted(per_floor.items())},
        "per_floor_kind": tables,
        "macro_f1": macro,
        "ece_overall": reliability(points)["ece"],
        "ece_by_floor": {f: reliability(v)["ece"] for f, v in sorted(points_floor.items())},
        "ece_by_kind": {k: reliability(v)["ece"] for k, v in sorted(points_kind.items())},
        "per_design": per_design,
    }


def digest(runs: Path) -> str:
    h = hashlib.sha256()
    for path in sorted(runs.rglob("score.json")):
        h.update(path.relative_to(runs).parts[0].encode())
        h.update(path.read_bytes())
    return h.hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--set", action="append", required=True, metavar="LABEL=DIR")
    ap.add_argument("--out", required=True, type=Path)
    args = ap.parse_args()
    summary: dict[str, object] = {"sets": {}, "digests": {}}
    for item in args.set:
        label, _, directory = item.partition("=")
        runs = Path(directory)
        summary["sets"][label] = summarise(runs)
        summary["digests"][label] = digest(runs)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(summary, sort_keys=True, indent=1) + "\n", encoding="utf-8")
    for label, data in summary["sets"].items():
        print(f"== {label}: runs={data['runs']} ece={round(data['ece_overall'], 4)} "
              f"macro-F1 {data['macro_f1']}")
        for floor, rows in data["per_floor_kind"].items():
            hit = {k: v for k, v in rows.items() if (v["counted"] or v["gt"])}
            print(f"  {floor}: macro-F1 {data['macro_f1'][floor]} "
                  f"counted {sum(v['counted'] for v in rows.values())} "
                  f"matched {sum(v['matched'] for v in rows.values())} "
                  f"gt {sum(v['gt'] for v in rows.values())}")
            for kind, v in hit.items():
                print(f"    {kind:12s} c={v['counted']:4d} m={v['matched']:3d} gt={v['gt']:4d} "
                      f"P={v['precision']} R={v['recall']} F1={v['f1']}")
    print("digests", {k: v[:12] for k, v in summary["digests"].items()})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
