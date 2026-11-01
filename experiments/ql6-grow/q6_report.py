"""Tables, plot and verdicts of Q-L6: ``python -B q6_report.py`` (after q6_grow.py)."""

from __future__ import annotations

import math
import statistics
from collections import Counter, defaultdict
from collections.abc import Callable
from typing import Any

import q6_eval as ev
from q6_env import KINDS, RES, l3dlib


def write(name: str, rows: list[dict[str, Any]]) -> None:
    if rows:
        l3dlib.write_csv(RES / name, list(rows[0]), rows)


def by_design(rows: list[dict[str, Any]]) -> dict[str, list[Any]]:
    out: dict[str, list[Any]] = defaultdict(list)
    for r in rows:
        out[r["design"]].append(r)
    return out


def label_better(pt: float, lo: float, hi: float) -> str:
    """CAD convention: positive geomean with CI touching 1 is INCONCLUSIVE."""
    if lo > 1.0:
        return "BETTER"
    if hi < 1.0:
        return "WORSE"
    return "INCONCLUSIVE"


def right_block_tables(cons: list[dict[str, Any]], verdict: list[dict[str, Any]]
                       ) -> list[dict[str, Any]]:
    sc = [r for r in cons if r["scored"]]
    out = []
    scopes: list[tuple[str, list[dict[str, Any]]]] = [("all", sc)]
    scopes += [(f"cell {c}", [r for r in sc if r["cell"] == c]) for c in l3dlib.CELLS]
    scopes += [(f"kind {k}", [r for r in sc if r["kind"] == k]) for k in KINDS if k != "glue"]
    scopes += [("D70 misses", [r for r in sc if not r["d70_hit"]])]
    for name, rows in scopes:
        n = len(rows)
        if not n:
            continue
        g, d = sum(r["right"] for r in rows), sum(r["d70_right"] for r in rows)
        out.append({"scope": name, "constructs": n, "seeded": sum(r["seeded"] for r in rows),
                    "grow_right": g, "grow_share": round(g / n, 3), "d70_right": d,
                    "d70_share": round(d / n, 3), "grow_not_d70": sum(
                        1 for r in rows if r["right"] and not r["d70_right"]),
                    "d70_not_grow": sum(1 for r in rows if r["d70_right"] and not r["right"])})
    units: dict[tuple[str, str, str], list[int]] = defaultdict(lambda: [0, 0])
    for r in sc:
        u = units[(r["set"], r["design"], r["cell"])]
        u[0] += r["right"]
        u[1] += r["d70_right"]
    per: list[dict[str, Any]] = [{"design": k[1], "g": v[0], "d": v[1]}
                                 for k, v in units.items()]
    wl = Counter("W" if r["g"] > r["d"] else "L" if r["g"] < r["d"] else "T" for r in per)

    def geomean(rows: list[Any]) -> float:
        return math.exp(statistics.fmean(math.log((r["g"] + 1) / (r["d"] + 1)) for r in rows))

    pt, lo, hi = ev.boot_ci(by_design(per), geomean)
    verdict.append({"id": "QL6a", "question": "right block per unit vs D70, geomean (g+1)/(d+1)",
                    "value": round(pt, 3), "ci90_lo": round(lo, 3), "ci90_hi": round(hi, 3),
                    "counts": f"W{wl['W']}/L{wl['L']}/T{wl['T']} of {len(per)} units",
                    "label": label_better(pt, lo, hi)})
    return out


def pr_tables(cons: list[dict[str, Any]], claims: list[dict[str, Any]]
              ) -> list[dict[str, Any]]:
    out = []
    for cellname in (*l3dlib.CELLS, "all"):
        for k in (*[x for x in KINDS if x != "glue"], "all"):
            for thr in (0.0, 0.5):
                cl = [c for c in claims if c["scored"] and c["size"] >= 4 and c["argmax"] != "glue"
                      and c["pmax"] >= thr and (cellname == "all" or c["cell"] == cellname)
                      and (k == "all" or c["argmax"] == k)]
                tp = sum(1 for c in cl if c["right_for"] == c["argmax"])
                cs = [r for r in cons if r["scored"]
                      and (cellname == "all" or r["cell"] == cellname)
                      and (k == "all" or r["kind"] == k)]
                hit = sum(1 for r in cs if r["right"] and r["argmax"] == r["kind"]
                          and r["pmax"] >= thr)
                top3 = sum(1 for r in cs if r["right"] and r["in_top3"])
                if not cs and not cl:
                    continue
                out.append({"cell": cellname, "kind": k, "min_pmax": thr, "claims": len(cl),
                            "tp": tp, "fp": len(cl) - tp,
                            "precision": round(tp / len(cl), 3) if cl else "",
                            "constructs": len(cs), "recalled": hit,
                            "recall": round(hit / len(cs), 3) if cs else "",
                            "right_block": sum(r["right"] for r in cs), "right_top3": top3})
    return out


def reliability(claims: list[dict[str, Any]], steps: list[dict[str, Any]]
                ) -> tuple[list[dict[str, Any]], dict[str, float]]:
    out = []
    ece: dict[str, float] = {}
    for scope, rows in (("final blocks", [(c["pmax"], c["argmax"] == c["label"])
                                          for c in claims if c["scored"] and c["label"]]),
                        ("all steps", [(s["pmax"], s["argmax"] == s["label"])
                                       for s in steps if s["label"]])):
        n = len(rows)
        tot = 0.0
        for b in range(10):
            sel = [(p, ok) for p, ok in rows if min(int(p * 10), 9) == b]
            if not sel:
                continue
            mp = statistics.fmean(p for p, _ in sel)
            ob = statistics.fmean(1.0 if ok else 0.0 for _, ok in sel)
            tot += len(sel) / n * abs(mp - ob)
            out.append({"scope": scope, "bin": f"{b / 10:.1f}-{(b + 1) / 10:.1f}", "n": len(sel),
                        "mean_pmax": round(mp, 3), "observed": round(ob, 3)})
        ece[scope] = tot
    return out, ece


def mean_of(rows: list[dict[str, Any]], pred: Callable[[dict[str, Any]], bool]) -> float:
    return statistics.fmean(1.0 if pred(r) else 0.0 for r in rows) if rows else math.nan


def sign_label(lo: float, hi: float, pos: str, neg: str) -> str:
    return pos if lo > 0 else (neg if hi < 0 else "INCONCLUSIVE")


def entropy_tables(steps: list[dict[str, Any]], trajs: list[dict[str, Any]], prior_top3: Any,
                   verdict: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for i, name in enumerate(ev.BIN_NAMES):
        rows = [s for s in steps if ev.bin_of(int(s["size"])) == i]
        lab = [s for s in rows if s["label"]]
        if not rows:
            continue
        acc = mean_of(lab, lambda s: s["argmax"] == s["label"])
        top3 = mean_of(lab, lambda s: s["label"] in s["top3"])
        base = mean_of(lab, lambda s: s["label"] in prior_top3)
        out.append({"size_bin": name, "steps": len(rows), "labelled": len(lab),
                    "mean_entropy_bits": round(statistics.fmean(s["entropy"] for s in rows), 3),
                    "argmax_accuracy": round(acc, 3), "top3_contains_label": round(top3, 3),
                    "prior_top3_contains_label": round(base, 3), "lift": round(top3 - base, 3)})

    def acc_of(rows: list[dict[str, Any]], b: int) -> float:
        sel = [s for s in rows if s["label"] and ev.bin_of(int(s["size"])) == b]
        return statistics.fmean(1.0 if s["argmax"] == s["label"] else 0.0 for s in sel) \
            if sel else math.nan

    pt, lo, hi = ev.boot_ci(by_design(steps), lambda r: acc_of(r, 4) - acc_of(r, 1))
    verdict.append({"id": "QL6b2", "question": "argmax accuracy: size 32+ minus size 4-7",
                    "value": round(pt, 3), "ci90_lo": round(lo, 3), "ci90_hi": round(hi, 3),
                    "counts": f"{len(steps)} steps",
                    "label": sign_label(lo, hi, "SUPPORTED", "CONTRADICTED")})

    def lift4(rows: list[dict[str, Any]]) -> float:
        sel = [s for s in rows if s["label"] and ev.bin_of(int(s["size"])) == 1]
        if not sel:
            return math.nan
        return statistics.fmean((1.0 if s["label"] in s["top3"] else 0.0)
                                - (1.0 if s["label"] in prior_top3 else 0.0) for s in sel)

    pt, lo, hi = ev.boot_ci(by_design(steps), lift4)
    verdict.append({"id": "QL6c", "question": "top-3 guess at size 4-7: lift over prior-only top-3",
                    "value": round(pt, 3), "ci90_lo": round(lo, 3), "ci90_hi": round(hi, 3),
                    "counts": f"{len(steps)} steps", "label": "USEFUL" if lo > 0 else (
                        "NOT USEFUL" if hi < 0 else "INCONCLUSIVE")})
    rho_rows = [r for r in trajs if not math.isnan(r["rho"])]
    pt, lo, hi = ev.boot_ci(by_design(rho_rows), lambda r: statistics.median(x["rho"] for x in r))
    verdict.append({"id": "QL6b", "question": "median Spearman(log2 size, entropy) per block",
                    "value": round(pt, 3), "ci90_lo": round(lo, 3), "ci90_hi": round(hi, 3),
                    "counts": f"{len(rho_rows)} blocks with >= 6 steps",
                    "label": sign_label(-hi, -lo, "SUPPORTED", "CONTRADICTED")})
    return out


def rate_verdict(cons: list[dict[str, Any]], verdict: list[dict[str, Any]]) -> None:
    miss = [r for r in cons if r["scored"] and not r["d70_hit"] and r["d70_class"] != "absent"]
    pt, lo, hi = ev.boot_ci(by_design(miss), lambda r: statistics.fmean(x["right"] for x in r))
    base = statistics.fmean(x["d70_right"] for x in miss)
    verdict.append({"id": "QL6a2", "question": "share of D70 misses whose block the grower gets "
                    f"right (D70 itself: {base:.3f})", "value": round(pt, 3),
                    "ci90_lo": round(lo, 3), "ci90_hi": round(hi, 3),
                    "counts": f"{len(miss)} misses",
                    "label": "reported"})


def confusion(cons: list[dict[str, Any]]) -> list[dict[str, Any]]:
    c: Counter[tuple[str, str]] = Counter()
    for r in cons:
        if r["scored"] and r["right"]:
            c[(r["kind"], r["argmax"])] += 1
    return [{"construct_kind": k, "argmax": a, "constructs": n} for (k, a), n in sorted(c.items())]


def failure_modes(cons: list[dict[str, Any]], claims: list[dict[str, Any]], n_comp: int,
                  mixed: Counter[tuple[str, str]], unk: list[dict[str, Any]]
                  ) -> list[dict[str, Any]]:
    sc = [r for r in cons if r["scored"]]
    out: list[dict[str, Any]] = [{"mode": "1 anchor gone",
            "measure": "constructs with a block overlapping the true block",
            "value": f"{sum(r['seeded'] for r in sc)} of {len(sc)}"}]
    seeded = [r for r in sc if r["seeded"]]
    out.append({"mode": "3 shared logic", "measure": "median cell precision of best block "
                "(seeded constructs)", "value": round(statistics.median(
                    r["cell_precision"] for r in seeded), 3) if seeded else ""})
    stopped = [r for r in seeded if r["coverage"] < 0.8]
    out.append({"mode": "4 local optima", "measure": "seeded constructs whose best block stopped "
                "with coverage < 0.8", "value": f"{len(stopped)} of {len(seeded)}"})
    out.append({"mode": "4 local optima", "measure": "lookahead steps used (blocks, total)",
                "value": f"{sum(c['looks'] for c in claims)}"})
    out.append({"mode": "6 composites", "measure": "touching block pairs with both >= 8 cells",
                "value": n_comp})
    out.append({"mode": "7 no likelihood", "measure": "unknown cohesive blocks (>= 8 cells, "
                "P(glue) < 0.25, max P < 0.5)", "value": len(unk)})
    for cell in ("O-gate", "O-lut", "O-hard"):
        tot = mixed[(cell, "all")]
        if tot:
            out.append({"mode": "5 mixed provenance",
                        "measure": f"{cell}: cells with mixed (*) label",
                        "value": f"{mixed[(cell, 'mixed (*)')]} of {tot} "
                        f"({mixed[(cell, 'mixed (*)')] / tot:.3f})"})
    return out


def reliability_svg(rows: list[dict[str, Any]]) -> None:
    w = h = 360
    m = 50
    col = {"final blocks": "#c0392b", "all steps": "#1b6ca8"}
    s = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{w + 150}" height="{h + 70}" '
         'font-family="sans-serif" font-size="11">',
         f'<rect x="{m}" y="10" width="{w - m - 10}" height="{h - m - 10}" fill="none" '
         'stroke="#444"/>']

    def px(v: float) -> float:
        return m + v * (w - m - 10)

    def py(v: float) -> float:
        return 10 + (1 - v) * (h - m - 10)

    s.append(f'<line x1="{px(0)}" y1="{py(0)}" x2="{px(1)}" y2="{py(1)}" stroke="#999" '
             'stroke-dasharray="4"/>')
    for t in (0, 0.2, 0.4, 0.6, 0.8, 1.0):
        s.append(f'<text x="{px(t) - 8}" y="{h - m + 8}">{t:.1f}</text>')
        s.append(f'<text x="{m - 28}" y="{py(t) + 4}">{t:.1f}</text>')
    s.append(f'<text x="{m + 20}" y="{h - 12}">max posterior (bin mean)</text>')
    s.append(f'<text x="4" y="{h / 2}" transform="rotate(-90 14 {h / 2})">observed correct</text>')
    for r in rows:
        rad = 2 + min(10, math.sqrt(int(r["n"])) / 8)
        s.append(f'<circle cx="{px(float(r["mean_pmax"])):.1f}" '
                 f'cy="{py(float(r["observed"])):.1f}" '
                 f'r="{rad:.1f}" fill="{col[r["scope"]]}" fill-opacity="0.7"/>')
    for i, (k, c) in enumerate(col.items()):
        s.append(f'<circle cx="{w - 10}" cy="{30 + 18 * i}" r="5" fill="{c}"/>'
                 f'<text x="{w}" y="{34 + 18 * i}">{k}</text>')
    s.append("</svg>")
    (RES / "reliability.svg").write_text("\n".join(s) + "\n", encoding="utf-8")


def main() -> int:
    r = ev.evaluate()
    verdict: list[dict[str, Any]] = []
    write("construct_records.csv", r["cons"])
    write("right_block.csv", right_block_tables(r["cons"], verdict))
    rate_verdict(r["cons"], verdict)
    write("pr_by_kind.csv", pr_tables(r["cons"], r["claims"]))
    rel, ece = reliability(r["claims"], r["steps"])
    write("reliability.csv", rel)
    reliability_svg(rel)
    tab = entropy_tables(r["steps"], r["trajs"], r["prior_top3"], verdict)
    write("entropy_size.csv", tab)
    verdict.append({"id": "QL6d", "question": "expected calibration error of the max posterior",
                    "value": round(ece.get("final blocks", math.nan), 3), "ci90_lo": "",
                    "ci90_hi": "", "counts": f"all steps ECE {ece.get('all steps', math.nan):.3f}",
                    "label": "measurement"})
    write("confusion.csv", confusion(r["cons"]))
    write("failure_modes.csv", failure_modes(r["cons"], r["claims"], len(r["comp"]), r["mixed"],
                                             r["unk"]))
    write("mixed_provenance.csv", [{"cell": c, "category": k, "cells": n}
                                   for (c, k), n in sorted(r["mixed"].items())])
    write("unknown_cohesive.csv", r["unk"])
    write("composites.csv", r["comp"])
    write("verdict.csv", verdict)
    for v in verdict:
        print(v)
    print(r["n_units"], "units;", len(r["cons"]), "constructs;", len(r["claims"]), "blocks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
