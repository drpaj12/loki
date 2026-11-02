"""Score every rule on one split and write the tables: ``python -B q7_eval.py [SPLIT]``.

TEST only after tuning is committed (EXPERIMENT.md). SPLIT = TEST (default) writes results/*.csv.
VALIDATION is accepted for a dry run into $QL7_OUT/dry (no repository files).
"""

from __future__ import annotations

import json
import math
import pickle
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import numpy as np
import q7_env as env
import q7_feat as ft
import q7_rules as rules
import q7_score as sc

ev = env.mod("q6_eval")
rp = env.mod("q6_report")
RULES = ("a", "b", "c", "d", "END")
TARGETS = {"gate": ("O-gate", "Y-gate"), "k4": ("O-lut", "Y-lut"), "k6/hardmap": ("O-hard",)}
KINDS5 = ("fsm", "counter", "shift", "regfile", "register")
Key = tuple[str, str, str, int, str]


def ref_rows() -> dict[Key, dict[str, str]]:
    """E73 and D70 flags per construct, from the committed #73 construct records."""
    p = Path(__file__).resolve().parent.parent / "ql6-grow" / "results" / "construct_records.csv"
    return {(r["set"], r["design"], r["cell"], int(r["part"]), r["kind"]): r
            for r in env.l3dlib.read_csv(p) if r["scored"] == "1" and r["d70_known"] == "1"}


class ZeroRefs:
    """Dry runs on TRAIN or VALIDATION have no D70 and no #73 result: both count as zero."""

    def get(self, key: Any, default: Any = None) -> dict[str, str]:
        return {"right": "0", "d70_right": "0"}


def key_of(r: dict[str, Any]) -> Key:
    return (r["set"], r["design"], r["cell"], r["part"], r["kind"])


def merge_refs(rows: list[dict[str, Any]], refs: Any) -> list[dict[str, Any]]:
    out = []
    for r in rows:
        ref = refs.get(key_of(r))
        if ref is not None:
            out.append({**r, "e73": int(ref["right"]), "d70": int(ref["d70_right"])})
    return out


def per_unit(rows: list[dict[str, Any]], a: str, b: str) -> list[dict[str, Any]]:
    units: dict[tuple[str, str, str], list[int]] = defaultdict(lambda: [0, 0])
    for r in rows:
        u = units[(r["set"], r["design"], r["cell"])]
        u[0] += r[a]
        u[1] += r[b]
    return [{"design": k[1], "g": v[0], "d": v[1]} for k, v in units.items()]


def geomean(rows: list[Any]) -> float:
    return math.exp(statistics.fmean(math.log((r["g"] + 1) / (r["d"] + 1)) for r in rows))


def compare(rows: list[dict[str, Any]], a: str, b: str) -> dict[str, Any]:
    per = per_unit(rows, a, b)
    wl = Counter("W" if r["g"] > r["d"] else "L" if r["g"] < r["d"] else "T" for r in per)
    pt, lo, hi = ev.boot_ci(rp.by_design(per), geomean)
    return {"geomean": round(pt, 3), "ci90_lo": round(lo, 3), "ci90_hi": round(hi, 3),
            "W": wl["W"], "L": wl["L"], "T": wl["T"], "units": len(per),
            "label": rp.label_better(pt, lo, hi)}


def gap_closed(rows: list[dict[str, Any]]) -> float:
    if not rows:
        return math.nan
    n = len(rows)
    r, e, o = (sum(x[k] for x in rows) / n for k in ("right", "e73", "oracle"))
    return math.nan if o == e else (r - e) / (o - e)


def run_rules(units: list[ft.UnitData], cfg: dict[str, Any], clf: Any
              ) -> dict[str, tuple[list[dict[str, Any]], list[dict[str, Any]]]]:
    pk = rules.pickers(cfg, clf)
    return {n: sc.score(units, [[pk[n](bp) for bp in u.blocks] for u in units])
            for n in RULES}


def tables(res: dict[str, tuple[list[dict[str, Any]], list[dict[str, Any]]]],
           refs: Any, head: str) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = defaultdict(list)
    merged = {n: merge_refs(res[n][0], refs) for n in RULES}
    base = merged[head]
    scopes: list[tuple[str, list[int]]] = [("all", list(range(len(base))))]
    scopes += [(f"target {t}", [i for i, r in enumerate(base) if r["cell"] in cs])
               for t, cs in TARGETS.items()]
    scopes += [(f"cell {c}", [i for i, r in enumerate(base) if r["cell"] == c]) for c in env.CELLS]
    scopes += [(f"kind {k}", [i for i, r in enumerate(base) if r["kind"] == k]) for k in KINDS5]
    for name, idx in scopes:
        if not idx:
            continue
        row: dict[str, Any] = {"scope": name, "constructs": len(idx)}
        for n in RULES:
            row[f"{n}_right"] = sum(merged[n][i]["right"] for i in idx)
            row[f"{n}_share"] = round(row[f"{n}_right"] / len(idx), 3)
        row["e73_share"] = round(sum(base[i]["e73"] for i in idx) / len(idx), 3)
        row["d70_share"] = round(sum(base[i]["d70"] for i in idx) / len(idx), 3)
        row["oracle_share"] = round(sum(base[i]["oracle"] for i in idx) / len(idx), 3)
        out["right_block.csv"].append(row)
    out["unit_cmp.csv"] = unit_comparisons(merged)
    out["pr_by_kind.csv"] = pr_rows(res, merged)
    out["sizes.csv"] = size_rows(merged)
    out["failure_classes.csv"] = class_rows(merged)
    out["verdict.csv"] = verdicts(merged, head, out["unit_cmp.csv"])
    out["construct_records.csv"] = [
        {"set": r["set"], "design": r["design"], "cell": r["cell"], "part": r["part"],
         "kind": r["kind"], "n_true": r["n_true"], "d70": r["d70"], "e73": r["e73"],
         "oracle": r["oracle"], **{f"{n}_{f}": merged[n][i][f] for n in RULES
                                   for f in ("right", "best_size", "cls")}}
        for i, r in enumerate(merged[head])]
    return out


def unit_comparisons(merged: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    out = []
    for n in RULES:
        rows = [{**r, "g": r["right"]} for r in merged[n]]
        for scope, cells in (("all", None), *[(f"target {t}", cs) for t, cs in TARGETS.items()]):
            sel = [r for r in rows if cells is None or r["cell"] in cells]
            for ref in ("d70", "e73"):
                out.append({"rule": n, "scope": scope, "against": ref.upper(),
                            **compare(sel, "right", ref)})
    return out


def pr_rows(res: dict[str, tuple[list[dict[str, Any]], list[dict[str, Any]]]],
            merged: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    out = []
    for n in RULES:
        claims = res[n][1]
        for k in (*KINDS5, "all"):
            cl = [c for c in claims if c["claim"] and (k == "all" or c["argmax"] == k)]
            tp = sum(c["tp"] for c in cl)
            cs = [r for r in merged[n] if k == "all" or r["kind"] == k]
            rec = sum(r["claimed"] for r in cs)
            out.append({"rule": n, "kind": k, "claims": len(cl), "tp": tp,
                        "precision": round(tp / len(cl), 3) if cl else "",
                        "constructs": len(cs), "recalled": rec,
                        "recall": round(rec / len(cs), 3) if cs else ""})
    return out


def quart(v: list[float]) -> list[float]:
    return [round(float(x), 3) for x in np.percentile(v, [25, 50, 75])] if v else [math.nan] * 3


def size_rows(merged: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    out = []
    for n in RULES:
        rows = merged[n]
        for scope, sel in (("all", rows), ("right", [r for r in rows if r["right"]]),
                           ("not right", [r for r in rows if not r["right"]])):
            sz = quart([float(r["best_size"]) for r in sel])
            ra = quart([float(r["ratio"]) for r in sel])
            out.append({"rule": n, "scope": scope, "constructs": len(sel), "size_q1": sz[0],
                        "size_median": sz[1], "size_q3": sz[2], "ratio_q1": ra[0],
                        "ratio_median": ra[1], "ratio_q3": ra[2]})
    tru = quart([float(r["n_true"]) for r in merged[RULES[0]]])
    out.append({"rule": "TRUE", "scope": "all", "constructs": len(merged[RULES[0]]),
                "size_q1": tru[0], "size_median": tru[1], "size_q3": tru[2]})
    return out


def class_rows(merged: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    out = []
    for n in RULES:
        for scope, cells in (("all", None), *[(f"target {t}", cs) for t, cs in TARGETS.items()]):
            sel = [r for r in merged[n] if cells is None or r["cell"] in cells]
            c = Counter(r["cls"] for r in sel if not r["right"])
            out.append({"rule": n, "scope": scope, "constructs": len(sel),
                        "right": sum(r["right"] for r in sel),
                        **{k: c[k] for k in sc.CLASSES}})
    return out


def verdicts(merged: dict[str, list[dict[str, Any]]], head: str,
             cmp_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    hd = next(r for r in cmp_rows if r["rule"] == head and r["scope"] == "all"
              and r["against"] == "D70")
    lab = "DISMISSED (WORSE)" if hd["label"] == "WORSE" else hd["label"]
    out.append({"id": "QL7a", "question": f"headline rule {head} recovers more than D70",
                "value": hd["geomean"], "ci90_lo": hd["ci90_lo"], "ci90_hi": hd["ci90_hi"],
                "counts": f"W{hd['W']}/L{hd['L']}/T{hd['T']} of {hd['units']} units",
                "label": lab})
    rows = merged[head]
    by = rp.by_design(rows)
    pt, lo, hi = ev.boot_ci(by, gap_closed)
    ql7b = "SUPPORTED" if lo > 0.5 else "CONTRADICTED" if hi < 0.5 else "INCONCLUSIVE"
    out.append({"id": "QL7b", "question": f"rule {head} closes most of the gap from E73 to ORACLE",
                "value": round(pt, 3), "ci90_lo": round(lo, 3), "ci90_hi": round(hi, 3),
                "counts": f"{len(rows)} constructs", "label": ql7b})
    for n in RULES:
        r = next(x for x in cmp_rows if x["rule"] == n and x["scope"] == "all"
                 and x["against"] == "E73")
        out.append({"id": f"QL7c-{n}", "question": f"rule {n} against the #73 grower",
                    "value": r["geomean"], "ci90_lo": r["ci90_lo"], "ci90_hi": r["ci90_hi"],
                    "counts": f"W{r['W']}/L{r['L']}/T{r['T']} of {r['units']} units",
                    "label": "MEASUREMENT (" + r["label"] + ")"})
    return out


def bar_svg(rows: list[dict[str, Any]], path: Path) -> None:
    """Right-block share per rule (all constructs), with D70, E73 and the oracle."""
    all_row = next(r for r in rows if r["scope"] == "all")
    bars = [("E73", all_row["e73_share"]), *[(n, all_row[f"{n}_share"]) for n in RULES],
            ("D70", all_row["d70_share"]), ("ORACLE", all_row["oracle_share"])]
    w, h, left, top = 520, 260, 50, 20
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" '
           'font-family="sans-serif" font-size="11">',
           f'<text x="{left}" y="14">Right-block share (TEST)</text>']
    for t in (0.0, 0.25, 0.5, 0.75, 1.0):
        y = top + (h - top - 30) * (1 - t)
        out.append(f'<line x1="{left}" x2="{w - 10}" y1="{y:.1f}" y2="{y:.1f}" stroke="#ddd"/>')
        out.append(f'<text x="{left - 6}" y="{y + 4:.1f}" text-anchor="end">{t:.2f}</text>')
    bw = (w - left - 10) / len(bars)
    for i, (name, v) in enumerate(bars):
        hh = (h - top - 30) * float(v)
        x = left + i * bw + 4
        col = "#c0504d" if name in ("D70", "E73") else "#999" if name in ("ORACLE", "END") \
            else "#1f77b4"
        out.append(f'<rect x="{x:.1f}" y="{h - 30 - hh:.1f}" width="{bw - 8:.1f}" '
                   f'height="{hh:.1f}" fill="{col}"/>')
        out.append(f'<text x="{x + (bw - 8) / 2:.1f}" y="{h - 30 - hh - 3:.1f}" '
                   f'text-anchor="middle">{float(v):.3f}</text>')
        out.append(f'<text x="{x + (bw - 8) / 2:.1f}" y="{h - 14}" '
                   f'text-anchor="middle">{name}</text>')
    out.append("</svg>")
    path.write_text("\n".join(out) + "\n", encoding="utf-8")


def main(argv: list[str]) -> int:
    split = argv[0] if argv else "TEST"
    cfg = json.loads((env.RES / "chosen.json").read_text(encoding="utf-8"))
    with (env.OUT7 / "clf.pkl").open("rb") as fh:
        clf = pickle.load(fh)
    units = ft.load(split)
    res = run_rules(units, cfg, clf)
    tabs = tables(res, ref_rows() if split == "TEST" else ZeroRefs(), cfg["headline"])
    dest = env.RES if split == "TEST" else env.OUT7 / "dry"
    dest.mkdir(parents=True, exist_ok=True)
    for name, rows in tabs.items():
        if rows:
            env.l3dlib.write_csv(dest / name, list(rows[0]), rows)
    bar_svg(tabs["right_block.csv"], dest / "right_block.svg")
    for r in tabs["verdict.csv"]:
        print(r)
    for r in tabs["right_block.csv"][:4]:
        print(r)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
