"""Decisions of round 3: the numbers and statuses of H9a, H9b, H10a, H10b, with the rules of
``EXPERIMENT.md`` (Stage 0, commit recorded in the paper). Reads the CSVs; writes
``r3_status.csv``. Imported by ``paper_tables.py``.
"""

from __future__ import annotations

import csv
from pathlib import Path

HERE = Path(__file__).resolve().parent
DECISIVE = ("ff_en", "mux_bit", "eq_const", "register")
PRIMARY = ("M2N", "V2N")
CLASSES = ("same_extent", "fragment_related", "fragment_other", "straddle", "partial", "noise")
DATAPATH = ("register", "mux", "mux_tree", "adder", "subtractor", "comparator", "counter")
CONTROL = ("eq_const", "fsm")
# Thresholds, copied from EXPERIMENT.md
A_KIND, A_POOL, A_NOT_FRAG, A_NOT_NOISE = 0.50, 0.50, 0.25, 0.50
B_KIND, B_NOT_POOL = 0.50, 0.20
D_SUP, D_NOT, C_GAP_SUP, C_GAP_NOT = 0.50, 0.25, 0.20, 0.10


def read(name: str) -> list[dict[str, str]]:
    with (HERE / name).open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def share(a: float, b: float) -> float:
    return a / b if b else 0.0


def h9a(sets: tuple[str, ...] = PRIMARY) -> dict[str, object]:
    rows = [r for r in read("l9_false.csv") if r["set"] in sets]
    out: dict[str, object] = {}
    tot_false = tot_frag = tot_noise = 0
    n_ok = 0
    for k in DECISIVE:
        sel = [r for r in rows if r["kind"] == k]
        nf = sum(int(r["n_false"]) for r in sel)
        cls = {c: sum(int(r[c]) for r in sel) for c in CLASSES}
        out[f"{k}_cand"] = sum(int(r["n_cand"]) for r in sel)
        out[f"{k}_false"] = nf
        for c in CLASSES:
            out[f"{k}_{c}"] = share(cls[c], nf)
        tot_false += nf
        tot_frag += cls["fragment_related"]
        tot_noise += cls["noise"]
        n_ok += 1 if share(cls["fragment_related"], nf) >= A_KIND else 0
    out["pool_false"] = tot_false
    out["pool_frag"] = share(tot_frag, tot_false)
    out["pool_noise"] = share(tot_noise, tot_false)
    out["kinds_ok"] = n_ok
    if n_ok >= 3 and share(tot_frag, tot_false) >= A_POOL:
        out["status"] = "S"
    elif share(tot_frag, tot_false) < A_NOT_FRAG or share(tot_noise, tot_false) >= A_NOT_NOISE:
        out["status"] = "N"
    else:
        out["status"] = "I"
    return out


def h9b(sets: tuple[str, ...] = PRIMARY) -> dict[str, object]:
    rows = [r for r in read("l9_h9b.csv") if r["set"] in sets]
    out: dict[str, object] = {}
    n_ok = tot = tot_frag = 0
    for k in DECISIVE:
        sel = [r for r in rows if r["kind"] == k]
        n = sum(int(r["n_gt"]) for r in sel)
        fr = sum(int(r["n_cov_frag_ge08"]) for r in sel)
        an = sum(int(r["n_cov_any_ge08"]) for r in sel)
        out[f"{k}_n"] = n
        out[f"{k}_q"] = share(fr, n)
        out[f"{k}_qany"] = share(an, n)
        out[f"{k}_meancov"] = share(sum(float(r["sum_cov_frag"]) for r in sel), n)
        out[f"{k}_matched"] = sum(int(r["n_matched"]) for r in sel)
        n_ok += 1 if share(fr, n) >= B_KIND else 0
        tot += n
        tot_frag += fr
    out["pool_n"] = tot
    out["pool_q"] = share(tot_frag, tot)
    out["kinds_ok"] = n_ok
    if n_ok >= 3:
        out["status"] = "S"
    elif share(tot_frag, tot) < B_NOT_POOL:
        out["status"] = "N"
    else:
        out["status"] = "I"
    return out


def reach(floor: str = "f2", rule: str = "relaxed", dataset: str | None = None,
          h: int = 2) -> dict[str, object]:
    rows = [r for r in read("l10_reach.csv")
            if r["floor"] == floor and r["rule"] == rule and (dataset in (None, r["dataset"]))]
    out: dict[str, object] = {}
    for cls, kinds in (("datapath", DATAPATH), ("control", CONTROL)):
        sel = [r for r in rows if r["kind"] in kinds]
        n = sum(int(r["n_gt"]) for r in sel)
        hit = sum(int(r[f"seed_h{h}"]) for r in sel)
        out[f"{cls}_n"] = n
        out[f"{cls}_hit"] = hit
        out[f"{cls}_share"] = share(hit, n)
    for k in (*DATAPATH, *CONTROL):
        sel = [r for r in rows if r["kind"] == k]
        n = sum(int(r["n_gt"]) for r in sel)
        for hh in (1, 2, 3, 4):
            out[f"{k}_h{hh}"] = share(sum(int(r[f"seed_h{hh}"]) for r in sel), n)
        out[f"{k}_n"] = n
        out[f"{k}_never"] = share(sum(int(r["never_seed"]) for r in sel), n)
    return out


def h10() -> tuple[dict[str, object], str, str]:
    r = reach()
    d = float(str(r["datapath_share"]))
    c = float(str(r["control_share"]))
    a = "S" if d >= D_SUP else "N" if d < D_NOT else "I"
    b = "S" if c <= d - C_GAP_SUP else "N" if c > d - C_GAP_NOT else "I"
    return r, a, b


def design_macro(floor: str = "f2", rule: str = "relaxed") -> dict[str, float]:
    """Report-only: mean over designs of the per-design share reached at h <= 2, by class."""
    rows = [r for r in read("l10_design.csv") if r["floor"] == floor and r["rule"] == rule]
    out: dict[str, float] = {}
    for cls in ("datapath", "control"):
        sel = [r for r in rows if r["class"] == cls]
        vals = [int(r["seed_h2"]) / int(r["n_gt"]) for r in sel if int(r["n_gt"])]
        out[f"{cls}_designs"] = float(len(vals))
        out[f"{cls}_macro"] = sum(vals) / len(vals) if vals else 0.0
    return out


def main() -> int:
    a, b = h9a(), h9b()
    r, h10a, h10b = h10()
    rows: list[list[object]] = [
        ["H9a", a["status"], f"pooled fragment_related {float(str(a['pool_frag'])):.3f}; "
         f"kinds >= 0.5: {a['kinds_ok']}/4; pooled noise {float(str(a['pool_noise'])):.3f}"],
        ["H9b", b["status"], f"pooled q {float(str(b['pool_q'])):.3f}; kinds >= 0.5: "
         f"{b['kinds_ok']}/4"],
        ["H10a", h10a, f"datapath reached at h<=2: {float(str(r['datapath_share'])):.3f}"],
        ["H10b", h10b, f"control reached at h<=2: {float(str(r['control_share'])):.3f}"],
    ]
    with (HERE / "r3_status.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(["hypothesis", "status", "deciding_number"])
        w.writerows(rows)
    for row in rows:
        print(row)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
