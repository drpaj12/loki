"""Summarise the f3 L1 scores of the base and renamed variants.

Reads ``<runs>/<variant>/<design>__f3/re/score.json``, aggregates per-kind counted/matched/gt
with the L1 runbook's P/R/F1 rules (a kind with no counted prediction has no F1 and is left out
of the macro average), the bus detector totals, the control/datapath role totals, and the
sha256 digest of each variant's score.json bytes for the naming-neutrality check.

Usage: analyze_f3.py RUNS_ROOT OUT_JSON
"""

from __future__ import annotations

import hashlib
import json
import sys
from collections import defaultdict
from pathlib import Path

from loki.score.metrics import reliability


def load(runs: Path) -> dict[str, dict[str, object]]:
    out: dict[str, dict[str, object]] = {}
    for path in sorted(runs.glob("*__f3/re/score.json")):
        out[path.parent.parent.name] = json.loads(path.read_text(encoding="utf-8"))
    return out


def digest(runs: Path) -> str:
    h = hashlib.sha256()
    for path in sorted(runs.glob("*__f3/re/score.json")):
        h.update(path.parent.parent.name.encode())
        h.update(path.read_bytes())
    return h.hexdigest()


def _f1(prec: float | None, rec: float | None) -> float | None:
    if prec is None or rec is None:
        return None
    return 0.0 if prec + rec == 0 else round(2 * prec * rec / (prec + rec), 6)


def summarise(scores: dict[str, dict[str, object]]) -> dict[str, object]:
    kinds: dict[str, dict[str, int]] = defaultdict(lambda: {"counted": 0, "matched": 0, "gt": 0})
    bus = {"counted": 0, "matched": 0, "gt": 0}
    roles: dict[str, dict[str, int]] = {r: {"pred": 0, "tp": 0, "gt": 0}
                                        for r in ("control", "datapath")}
    points: list[tuple[float, bool]] = []
    equiv: dict[str, int] = defaultdict(int)
    per_design = {}
    for design, score in sorted(scores.items()):
        constructs = score["constructs"]
        assert isinstance(constructs, dict)
        for kind, data in sorted(constructs.items()):
            assert isinstance(data, dict)
            for key in ("counted", "matched", "gt"):
                kinds[kind][key] += int(data[key])
        for key in bus:
            bus[key] += int(score["bus"][key])
        for role in roles:
            row = score["roles"][role]
            for key in roles[role]:
                roles[role][key] += int(row[key])
        for plist in score["points"].values():
            for p, y in plist:
                points.append((float(p), bool(y)))
        equiv[str(score["final_equiv"]["status"])] += 1
        per_design[design] = {
            "counted": sum(int(v["counted"]) for v in constructs.values()),
            "matched": sum(int(v["matched"]) for v in constructs.values()),
            "gt": sum(int(v["gt"]) for v in constructs.values()),
            "bus_counted": int(score["bus"]["counted"]),
            "bus_matched": int(score["bus"]["matched"]),
            "datapath_f1": score["roles"]["datapath"]["f1"],
            "control_f1": score["roles"]["control"]["f1"],
        }
    table = {}
    f1s = []
    for kind, row in sorted(kinds.items()):
        prec = round(row["matched"] / row["counted"], 6) if row["counted"] else None
        rec = round(row["matched"] / row["gt"], 6) if row["gt"] else None
        f1 = _f1(prec, rec)
        table[kind] = {**row, "precision": prec, "recall": rec, "f1": f1}
        if f1 is not None and row["gt"]:
            f1s.append(f1)
    bus_prec = round(bus["matched"] / bus["counted"], 6) if bus["counted"] else None
    bus_rec = round(bus["matched"] / bus["gt"], 6) if bus["gt"] else None
    role_out = {}
    for role, row in roles.items():
        prec = round(row["tp"] / row["pred"], 6) if row["pred"] else None
        rec = round(row["tp"] / row["gt"], 6) if row["gt"] else None
        role_out[role] = {**row, "precision": prec, "recall": rec, "f1": _f1(prec, rec)}
    return {
        "runs": len(scores),
        "kinds": table,
        "macro_f1": round(sum(f1s) / len(f1s), 6) if f1s else 0.0,
        "counted": sum(v["counted"] for v in kinds.values()),
        "matched": sum(v["matched"] for v in kinds.values()),
        "gt": sum(v["gt"] for v in kinds.values()),
        "bus": {**bus, "precision": bus_prec, "recall": bus_rec, "f1": _f1(bus_prec, bus_rec)},
        "roles": role_out,
        "ece": reliability(points)["ece"],
        "final_equiv": dict(sorted(equiv.items())),
        "per_design": per_design,
    }


def main() -> int:
    root, out_path = Path(sys.argv[1]), Path(sys.argv[2])
    result: dict[str, object] = {"variants": {}, "digests": {}}
    for variant in ("base", "renamed"):
        runs = root / variant
        scores = load(runs)
        result["variants"][variant] = summarise(scores)
        result["digests"][variant] = digest(runs)
    base, renamed = result["digests"]["base"], result["digests"]["renamed"]
    result["neutral"] = base == renamed
    out_path.write_text(json.dumps(result, sort_keys=True, indent=1) + "\n", encoding="utf-8")
    for variant in ("base", "renamed"):
        data = result["variants"][variant]
        print(f"== {variant}: runs={data['runs']} macro-F1 {data['macro_f1']} "
              f"counted {data['counted']} matched {data['matched']} gt {data['gt']} "
              f"ece {round(data['ece'], 4)}")
        print("bus", data["bus"])
        print("roles", data["roles"])
        for kind, row in data["kinds"].items():
            if row["counted"] or row["gt"]:
                print(f"  {kind:12s} c={row['counted']:4d} m={row['matched']:3d} "
                      f"gt={row['gt']:4d} P={row['precision']} R={row['recall']} "
                      f"F1={row['f1']}")
    print("digests", {k: v[:12] for k, v in result["digests"].items()},
          "neutral", result["neutral"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
