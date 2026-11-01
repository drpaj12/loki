"""Odin III pass that first lost the source units of absent and structure-miss constructs:
``python -B passes.py [JOBS]`` after ql4_run.py and report.py.

Uses the L15 loss audit (loki.audit, round 6) on the O-lut (f2) flow: snapshots after proc, fsm,
opt, flatten, opt -full, wreduce, lower, abc --lut 6, then the first pass at which each source unit
stops being a separable unit. For a construct the units are those of its source (the whole design
for a single, the part's module lines for a composite part), restricted to state units (hardware
kind fsm or register). The construct's pass is the one that first lost most of those units. Only the
O-lut cell is covered (the other floors run other pass lists). Output: results/pass_loss.csv (per
construct) and results/pass_loss_summary.csv.
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "l3-census"))
import blocks as bl  # noqa: E402
import l3dlib  # noqa: E402
import l3lib  # noqa: E402
import report as rp  # noqa: E402
import tsig  # noqa: E402

CLASSES = ("absent", "structure miss")
l3lib.OUT = l3dlib.CENSUS  # importing live pointed L3_OUT at the graphlet output
l3lib.R4 = l3dlib.CENSUS / "r4corpus"
ARCH = (l3dlib.WS / "external" / "vtr-verilog-to-routing" / "vtr_flow" / "arch" / "timing"
        / "k6_frac_N10_frac_chain_mem32K_40nm.xml")
STATE_HW = ("fsm", "register")
CELL = "O-lut"


def run_one(job: tuple[str, str, str, str, str]) -> dict[str, Any]:
    """Audit one design: (set, design, src path, top, scratch dir) -> the audit units."""
    from loki.audit.report import audit_design
    from loki.audit.snap import run_snapshots

    kind, design, src, top, scratch = job
    out = Path(scratch) / design
    try:
        run_snapshots([Path(src)], ARCH, out, top=top or None, detect=False)
        res = audit_design(out, design, "stmt")
    except Exception as exc:  # recorded, not hidden
        return {"design": design, "error": str(exc)[:100], "units": []}
    return {"design": design, "units": res["units"], "passes": res["passes"]}


def line_of(span: str) -> int:
    head = span.split("-")[0].split(".")[0]
    return int(head) if head.isdigit() else 0


def tally(units: list[dict[str, Any]], lines: tuple[int, int] | None) -> Counter[str]:
    c: Counter[str] = Counter()
    for u in units:
        if u["hw"] not in STATE_HW:
            continue
        if lines is not None and not lines[0] <= line_of(u["span"]) <= lines[1]:
            continue
        c[u["loss"]["pass"] if u["status"] == "lost" and "loss" in u else "kept"] += 1
    return c


def main(argv: list[str]) -> int:
    n = int(argv[0]) if argv else 4
    recs = [r for r in rp.read_records() if r["detector"] in ("D70", "D71c")
            and r["class"] in CLASSES and r["cell"] == CELL]
    manifest = {r["design"]: r for r in l3lib.manifest()}
    scratch = tsig.OUT / "snap"
    targets: dict[str, tuple[str, str, str, str, str]] = {}
    for r in recs:
        d = r["design"]
        if r["set"] == "single":
            m = manifest[d]
            targets[d] = ("single", d, m.get("osrc", m["src"]), m["top"], str(scratch))
        else:
            sv = l3dlib.OUT / "composites" / d / f"{d}.sv"
            targets[d] = ("comp", d, str(sv), d, str(scratch))
    with ProcessPoolExecutor(n) as pool:
        audits = {a["design"]: a for a in pool.map(run_one, list(targets.values()))}
    rows = []
    seen: set[tuple[str, str, str, int]] = set()
    for r in recs:
        key = (r["class"], r["set"], r["design"], r["part"])
        if key in seen:
            continue
        seen.add(key)
        a = audits[r["design"]]
        lines = None
        if r["set"] == "comp":
            truth = json.loads((l3dlib.OUT / "composites" / r["design"] / "truth.json").read_text(
                encoding="utf-8"))
            rng = bl.module_ranges(l3dlib.OUT / "composites" / r["design"] / f"{r['design']}.sv",
                                   {p["idx"]: p["problem"] for p in truth["parts"]})
            lines = rng.get(int(r["part"]))
        c = tally(a["units"], lines)
        lost = {k: v for k, v in c.items() if k != "kept"}
        dom = max(lost, key=lambda k: lost[k]) if lost else ("kept" if c else "no state unit")
        rows.append({"class": r["class"], "family": r["family"], "set": r["set"],
                     "design": r["design"], "part": r["part"], "state_units": sum(c.values()),
                     "kept": c.get("kept", 0), "dominant_loss_pass": dom,
                     "passes": ";".join(f"{k}={v}" for k, v in sorted(c.items())),
                     "audit_error": a.get("error", "")})
    rp.write("pass_loss.csv", rows)
    agg = Counter((r["class"], r["family"], r["dominant_loss_pass"]) for r in rows)
    rp.write("pass_loss_summary.csv", [{"class": k[0], "family": k[1], "dominant_loss_pass": k[2],
                                        "constructs": v} for k, v in sorted(agg.items())])
    print(len(rows), "constructs;", len(targets), "designs;",
          sum(1 for a in audits.values() if a.get("error")), "audit errors")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
