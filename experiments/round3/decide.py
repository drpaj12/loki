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


def h9a_without_top() -> dict[str, object]:
    """Report-only sensitivity: H9a pooled shares with the design that holds the most false
    candidates of the four kinds in P left out."""
    rows = [r for r in read("l9_false_design.csv") if r["set"] in PRIMARY]
    per: dict[str, int] = {}
    for r in rows:
        per[r["design"]] = per.get(r["design"], 0) + int(r["n_false"])
    top = sorted(per.items(), key=lambda kv: (-kv[1], kv[0]))[0][0]
    keep = [r for r in rows if r["design"] != top]
    nf = sum(int(r["n_false"]) for r in keep)
    out: dict[str, object] = {"design": top, "false": nf}
    for c in CLASSES:
        out[c] = share(sum(int(r[c]) for r in keep), nf)
    for k in DECISIVE:
        sel = [r for r in keep if r["kind"] == k]
        out[f"{k}_frag"] = share(sum(int(r["fragment_related"]) for r in sel),
                                 sum(int(r["n_false"]) for r in sel))
    return out


def h9a_without_kind(drop: str = "ff_en", drop_top: bool = False) -> dict[str, object]:
    """Exploratory (2026-10-24 addition, non-deciding): pooled H9a shares over the decisive kinds
    except ``drop``, optionally also without the design that holds most false candidates."""
    if drop_top:
        top = str(h9a_without_top()["design"])
        rows = [r for r in read("l9_false_design.csv")
                if r["set"] in PRIMARY and r["design"] != top]
    else:
        rows = [r for r in read("l9_false.csv") if r["set"] in PRIMARY]
    kinds = [k for k in DECISIVE if k != drop]
    out: dict[str, object] = {"kinds": len(kinds)}
    nf = fr = ok = 0
    for k in kinds:
        sel = [r for r in rows if r["kind"] == k]
        a = sum(int(r["n_false"]) for r in sel)
        b = sum(int(r["fragment_related"]) for r in sel)
        nf, fr = nf + a, fr + b
        ok += 1 if share(b, a) >= A_KIND else 0
    out.update({"false": nf, "frag": share(fr, nf), "kinds_ok": ok})
    return out


def expl_false() -> dict[str, object]:
    """Exploratory: noise' (cells only in plain-gate GT words) and distinct-cell shares, in P."""
    rows = [r for r in read("l9_exploratory_false.csv") if r["set"] in PRIMARY]
    out: dict[str, object] = {}
    t_f = t_n = t_cf = t_cr = 0
    for k in DECISIVE:
        sel = [r for r in rows if r["kind"] == k]
        nf = sum(int(r["n_false"]) for r in sel)
        npr = sum(int(r["noise_prime_plain_gates"]) for r in sel)
        cf = sum(int(r["distinct_cells_false"]) for r in sel)
        cr = sum(int(r["distinct_cells_fragment_related"]) for r in sel)
        out.update({f"{k}_noise_prime": share(npr, nf), f"{k}_noise_prime_n": npr,
                    f"{k}_cells": cf, f"{k}_cell_frag": share(cr, cf)})
        t_f, t_n, t_cf, t_cr = t_f + nf, t_n + npr, t_cf + cf, t_cr + cr
    out.update({"pool_noise_prime": share(t_n, t_f), "pool_noise_prime_n": t_n,
                "pool_cells": t_cf, "pool_cell_frag": share(t_cr, t_cf)})
    return out


def expl_h9b() -> dict[str, object]:
    """Exploratory: H9b share over the GT words touched by at least one candidate."""
    rows = [r for r in read("l9_exploratory_h9b.csv") if r["set"] in PRIMARY]
    out: dict[str, object] = {}
    tt = tf = 0
    for k in DECISIVE:
        sel = [r for r in rows if r["kind"] == k]
        nt = sum(int(r["n_touched"]) for r in sel)
        nq = sum(int(r["n_cov_frag_ge08"]) for r in sel)
        out.update({f"{k}_touched": nt, f"{k}_qtouched": share(nq, nt)})
        tt, tf = tt + nt, tf + nq
    out.update({"pool_touched": tt, "pool_qtouched": share(tf, tt)})
    return out


def expl_l10(variant: str, floor: str = "f2", rule: str = "relaxed") -> dict[str, float]:
    """Exploratory: datapath share reached at h <= 2 under a recount ``variant``."""
    rows = [r for r in read("l10_exploratory.csv")
            if r["floor"] == floor and r["rule"] == rule and r["variant"] == variant]
    out: dict[str, float] = {}
    for cl in ("datapath", "control"):
        sel = [r for r in rows if r["class"] == cl]
        n = sum(int(r["n_gt"]) for r in sel)
        out[f"{cl}_n"] = float(n)
        out[f"{cl}_share"] = share(sum(int(r["seed_h2"]) for r in sel), n)
    return out


def expl_l10_count(variant: str, floor: str = "f2", rule: str = "relaxed") -> int:
    return sum(int(r["count"]) for r in read("l10_exploratory.csv")
               if r["floor"] == floor and r["rule"] == rule and r["variant"] == variant)


def write_exploratory() -> list[list[object]]:
    """``r3_exploratory.csv``: every exploratory, non-deciding number of the 2026-10-24
    additions to ``EXPERIMENT.md``."""
    rows: list[list[object]] = []

    def add(name: str, value: object) -> None:
        rows.append([f"exploratory_{name}", value if isinstance(value, int)
                     else f"{float(str(value)):.6f}"])

    for tag, d in (("no_ffen", h9a_without_kind()),
                   ("no_ffen_no_top", h9a_without_kind(drop_top=True))):
        add(f"h9a_{tag}_false", d["false"])
        add(f"h9a_{tag}_fragment_related", d["frag"])
        add(f"h9a_{tag}_kinds_ge05_of_3", d["kinds_ok"])
    for k, v in expl_false().items():
        add(f"h9a_{k}", v)
    for k, v in expl_h9b().items():
        add(f"h9b_{k}", v)
    for var in ("deciding", "no_relconst", "dedup_footprint", "no_relconst_dedup"):
        x = expl_l10(var)
        for cl in ("datapath", "control"):
            add(f"h10_{var}_{cl}_n", int(x[f"{cl}_n"]))
            add(f"h10_{var}_{cl}_share", x[f"{cl}_share"])
    add("h10_relconst_count_f2", expl_l10_count("relconst_count"))
    add("h10_subsumed_count_f2", expl_l10_count("subsumed_count"))
    add("h10_footprint_io_cells_f2", expl_l10_count("footprint_io_cells"))
    with (HERE / "r3_exploratory.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(["metric", "value"])
        w.writerows(rows)
    return rows


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
    write_exploratory()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
