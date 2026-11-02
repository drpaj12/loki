"""Score the TEST run (HEAD and ablations against BASE, D70 and #76 classes), write the tables.

``python -B q9_eval.py [STAGE SPLIT]`` reads $QL9_OUT/res_<STAGE>_<SPLIT>.pkl (default test TEST).
TEST only after the choice is committed (EXPERIMENT.md). Any other split is a dry run into
$QL9_OUT/dry.
"""

from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np
import q9_env as env
import q9_tune as tune

q7e = env.mod("q7_eval")
q8bev = env.mod("q8b_eval")
KEYS = ("set", "design", "cell", "part", "kind")
NAMES = ("HEAD", "BF73", "BFM2", "CTRL", "SPLIT", "JS")


def e74_classes() -> dict[Any, str]:
    p = env.q6env.EXP / "ql8a-order" / "results" / "construct_records.csv"
    return {(r["set"], r["design"], r["cell"], int(r["part"]), r["kind"]): r["E74_sub"]
            for r in env.l3dlib.read_csv(p)}


def joined(res: list[dict[str, Any]], refs: Any, c74: dict[Any, str]) -> list[dict[str, Any]]:
    """One row per scored construct: BASE and every config's right flag, D70, #76 class."""
    out = []
    for u in res:
        names = [n for n in NAMES if n in u["cfg"]]
        for i, b in enumerate(u["cfg"]["BASE"]["rows"]):
            ref = refs.get(q7e.key_of(b))
            if ref is None:
                continue
            row = {**b, "base": b["right"], "base_cls": b["cls"], "d70": int(ref["d70_right"]),
                   "e73": int(ref["right"]), "c74": c74.get(q7e.key_of(b), "")}
            for n in names:
                row[n.lower()] = u["cfg"][n]["rows"][i]["right"]
                row[n.lower() + "_cls"] = u["cfg"][n]["rows"][i]["cls"]
            out.append(row)
    return out


def share(rows: list[dict[str, Any]], key: str) -> float:
    return round(sum(r[key] for r in rows) / len(rows), 3) if rows else float("nan")


def right_block(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for name in q8bev.scopes():
        sel = q8bev.scope_sel([{**r, "cell": r["cell"]} for r in rows], name)
        if sel:
            out.append({"scope": name, "constructs": len(sel), "d70_share": share(sel, "d70"),
                        "base_share": share(sel, "base"), **{
                            f"{n.lower()}_share": share(sel, n.lower()) for n in NAMES}})
    return out


def unit_cmp(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for name in ("all", *[f"target {t}" for t in env.TARGETS], "set single", "set comp"):
        sel = q8bev.scope_sel(rows, name)
        for n in NAMES:
            for ref in ("d70", "base"):
                out.append({"scope": name, "config": n, "against": ref.upper(),
                            **q7e.compare(sel, n.lower(), ref)})
    return out


def fixed_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Per failure class (#77 blocks, and the #76 class of the E74 blocks): how many go right."""
    out = []
    for how, key in (("#77 class", "base_cls"), ("#76 class (E74)", "c74")):
        for cls in sorted({r[key] for r in rows if not r["base"] or key == "c74"} - {""}):
            sel = [r for r in rows if r[key] == cls and (key == "c74" or not r["base"])]
            out.append({"classes": how, "class": cls, "constructs": len(sel),
                        "base_right": sum(r["base"] for r in sel),
                        **{f"{n.lower()}_right": sum(r[n.lower()] for r in sel) for n in NAMES},
                        "base_share": share(sel, "base"),
                        **{f"{n.lower()}_share": share(sel, n.lower()) for n in NAMES}})
    return out


def gained_lost(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for n in NAMES:
        g = [r for r in rows if r[n.lower()] and not r["base"]]
        lo = [r for r in rows if r["base"] and not r[n.lower()]]
        out.append({"config": n, "gained": len(g), "lost": len(lo), "net": len(g) - len(lo),
                    "lost_single": sum(r["set"] == "single" for r in lo),
                    "lost_comp": sum(r["set"] == "comp" for r in lo),
                    "lost_by_class": ";".join(f"{k}:{v}" for k, v in sorted(
                        Counter(r[n.lower() + "_cls"] for r in lo).items()))})
    return out


def lost_list(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [{**{k: r[k] for k in KEYS}, "n_true": r["n_true"], "head_class": r["head_cls"]}
            for r in rows if r["base"] and not r["head"]]


def step_rows(res: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for n in NAMES:
        if n not in res[0]["cfg"]:
            continue
        j = [u["cfg"][n]["joins"] for u in res]
        s = [u["cfg"][n]["splits"] for u in res]
        out.append({"config": n, "units": len(res), "joins": sum(j), "units_with_join":
                    sum(x > 0 for x in j), "splits": sum(s), "units_with_split":
                    sum(x > 0 for x in s)})
    return out


def kind_f1(res: list[dict[str, Any]], which: str) -> list[dict[str, Any]]:
    k5 = env.KINDS5
    claims: Counter[str] = Counter()
    tp: Counter[str] = Counter()
    rec: Counter[str] = Counter()
    cons: Counter[str] = Counter()
    for u in res:
        t = u["cfg"][which]["kind"]
        for k in k5:
            claims[k] += t["claims"][k]
            tp[k] += t["tp"][k]
        cons.update(k for _p, k in t["cons"])
        rec.update(k for _p, k in t["got"])
    out, f1s = [], []
    for k in k5:
        p = tp[k] / claims[k] if claims[k] else 0.0
        r = rec[k] / cons[k] if cons[k] else 0.0
        f1 = 2 * p * r / (p + r) if p + r else 0.0
        f1s.append(f1)
        out.append({"config": which, "kind": k, "claims": claims[k], "tp": tp[k],
                    "precision": round(p, 3), "constructs": cons[k], "recalled": rec[k],
                    "recall": round(r, 3), "f1": round(f1, 3)})
    out.append({"config": which, "kind": "macro", "f1": round(float(np.mean(f1s)), 3)})
    return out


def label(c: dict[str, Any]) -> str:
    return str(c["label"])


def verdicts(rows: list[dict[str, Any]], cmp_rows: list[dict[str, Any]],
             gl: list[dict[str, Any]]) -> list[dict[str, Any]]:
    def get(scope: str, against: str) -> dict[str, Any]:
        return next(r for r in cmp_rows if r["scope"] == scope and r["config"] == "HEAD"
                    and r["against"] == against)

    allb, single = get("all", "BASE"), get("set single", "BASE")
    net = next(r for r in gl if r["config"] == "HEAD")["net"]
    lab_a = ("SUPPORTED" if label(allb) == "BETTER" and label(single) != "WORSE"
             else "CONTRADICTED" if label(allb) == "WORSE" or net <= 0 else "INCONCLUSIVE")
    out = [{"id": "QL9-a", "question": "headline against BASE (per-unit geomean)",
            "value": allb["geomean"], "ci90_lo": allb["ci90_lo"], "ci90_hi": allb["ci90_hi"],
            "counts": f"W{allb['W']}/L{allb['L']}/T{allb['T']}; single {single['geomean']} "
                      f"{label(single)}; net {net}", "label": lab_a}]
    for cls, qid in (("SPLIT", "QL9-b split"), ("BLOATED", "QL9-b swallowed")):
        sel = [r for r in rows if r["c74"] == ("SPLIT" if cls == "SPLIT" else "BLOATED")]
        right = sum(r["head"] for r in sel)
        sh = right / len(sel) if sel else 0.0
        out.append({"id": qid, "question": f"#76 {cls} constructs right after the step",
                    "value": round(sh, 3), "ci90_lo": "", "ci90_hi": "",
                    "counts": f"{right} of {len(sel)} ({sum(r['base'] for r in sel)} right "
                              "already before the step)",
                    "label": "SUPPORTED" if sh >= 0.25 else "CONTRADICTED" if sh < 0.05
                    else "INCONCLUSIVE"})
    h = next(r for r in gl if r["config"] == "HEAD")
    out.append({"id": "QL9-c", "question": "cost: constructs lost", "value": h["lost"],
                "ci90_lo": "", "ci90_hi": "", "counts": f"gained {h['gained']}",
                "label": "MEASUREMENT"})
    return out


def bar_svg(rows: list[dict[str, Any]], path: Path) -> None:
    allr = next(r for r in rows if r["scope"] == "all")
    bars = [("D70", allr["d70_share"]), ("BASE", allr["base_share"]),
            *[(n, allr[f"{n.lower()}_share"]) for n in NAMES]]
    w, h, left, top = 460, 240, 50, 20
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
        col = "#c0504d" if name == "D70" else "#999" if name == "BASE" else "#1f77b4"
        out.append(f'<rect x="{x:.1f}" y="{h - 30 - hh:.1f}" width="{bw - 8:.1f}" '
                   f'height="{hh:.1f}" fill="{col}"/>')
        out.append(f'<text x="{x + (bw - 8) / 2:.1f}" y="{h - 30 - hh - 3:.1f}" '
                   f'text-anchor="middle">{float(v):.3f}</text>')
        out.append(f'<text x="{x + (bw - 8) / 2:.1f}" y="{h - 14}" '
                   f'text-anchor="middle">{name}</text>')
    out.append("</svg>")
    path.write_text("\n".join(out) + "\n", encoding="utf-8")


def main(argv: list[str]) -> int:
    stage, split = (argv[0], argv[1]) if len(argv) > 1 else ("test", "TEST")
    res = tune.load(stage, split)
    refs = q7e.ref_rows() if split == "TEST" else q7e.ZeroRefs()
    rows = joined(res, refs, e74_classes())
    cmp_rows, gl = unit_cmp(rows), gained_lost(rows)
    tabs: dict[str, list[dict[str, Any]]] = {
        "right_block.csv": right_block(rows), "unit_cmp.csv": cmp_rows,
        "fixed_by_class.csv": fixed_rows(rows), "gained_lost.csv": gl,
        "lost.csv": lost_list(rows), "steps.csv": step_rows(res),
        "kind_f1.csv": kind_f1(res, "BASE") + kind_f1(res, "HEAD"),
        "verdict.csv": verdicts(rows, cmp_rows, gl)}
    dest = env.RES if split == "TEST" else env.OUT9 / "dry"
    dest.mkdir(parents=True, exist_ok=True)
    for name, trows in tabs.items():
        if trows:
            env.l3dlib.write_csv(Path(dest / name), list(trows[0]), trows)
    bar_svg(tabs["right_block.csv"], dest / "right_block.svg")
    for r in tabs["verdict.csv"]:
        print(r)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
