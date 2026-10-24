"""Bus reconstruction detail for the f3 runs: matched GT buses, their widths and bit order.

Reads each base run's overlay.json, reconstructs the counted bus predictions against the L0
bus ground truth with the score's own matcher (Jaccard 0.5, best of members/alt), and reports
per matched bus its GT width, predicted width and forward/reverse bit-order agreement.

Usage: buses_f3.py RUNS_DIR DATASET OUT_JSON
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

from loki.score.gt import load_gt, load_netmap
from loki.score.match import greedy_from_pairs, pairs_above
from loki.score.metrics import load_buses


def matched(overlay: dict[str, object], floor: Path) -> list[dict[str, object]]:
    instances, gts, roles, paths = load_gt(floor)
    nm = load_netmap(floor)
    preds = [p for p in load_buses(overlay, nm) if p.counted(0.5)]
    gsets = [(g.gid, g.members) for g in gts]
    best: dict[tuple[str, str], tuple[float, bool]] = {}
    for alt in (False, True):
        views = [(p.id, frozenset(p.alt if alt else p.members)) for p in preds]
        if alt:
            views = [(pid, m) for (pid, m), p in zip(views, preds, strict=True) if p.alt]
        for pid, gid, j in pairs_above(views, gsets, 0.5):
            if (pid, gid) not in best or j > best[(pid, gid)][0]:
                best[(pid, gid)] = (j, alt)
    matches = greedy_from_pairs([(pid, gid, j) for (pid, gid), (j, _) in best.items()])
    by_id = {p.id: p for p in preds}
    by_gid = {g.gid: g for g in gts}
    out = []
    for pid, gid, j in matches:
        p, g = by_id[pid], by_gid[gid]
        alt = best[(pid, gid)][1]
        rep = p.alt if alt else p.members
        bits = dict(g.bits)
        pos = [(i, bits[n]) for i, n in enumerate(rep) if n in bits]
        fwd = sum(1 for i, b in pos if i == b)
        bwd = sum(1 for i, b in pos if len(rep) - 1 - i == b)
        out.append({
            "gt_width": len(g.members), "pred_width": len(rep), "jaccard": round(j, 6),
            "order_source": p.order_source, "alt": alt, "shared_bits": len(pos),
            "exact": round(fwd / len(pos), 6) if pos else None,
            "up_to_reversal": round(max(fwd, bwd) / len(pos), 6) if pos else None,
        })
    return out


def main() -> int:
    runs, dataset, out_path = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
    rows = {}
    for score in sorted(runs.glob("*__f3/re/score.json")):
        design = score.parent.parent.name.removesuffix("__f3")
        overlay = json.loads((score.parent / "overlay.json").read_text(encoding="utf-8"))
        rows[design] = matched(overlay, dataset / design / "f3")
    widths = Counter(r["gt_width"] for run in rows.values() for r in run)
    summary = {
        "matched": sum(len(v) for v in rows.values()),
        "gt_widths": dict(sorted(widths.items())),
        "order_exact": round(sum(1 for run in rows.values() for r in run
                                 if r["exact"] == 1.0) / max(1, sum(len(v) for v in rows.values())),
                             6),
        "designs": rows,
    }
    out_path.write_text(json.dumps(summary, sort_keys=True, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in summary.items() if k != "designs"}, sort_keys=True))
    for design, run in rows.items():
        if run:
            print(design, [(r["gt_width"], r["pred_width"], r["order_source"], r["exact"])
                           for r in run])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
