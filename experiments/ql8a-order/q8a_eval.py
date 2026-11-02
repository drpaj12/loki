"""Score the orders on one split and write the tables: ``python -B q8a_eval.py [SPLIT]``.

TEST only after the order is chosen and committed (EXPERIMENT.md). SPLIT = TEST (default) writes
results/*.csv. VALIDATION is a dry run into $QL8A_OUT/dry (no D70 and no #73 column).
"""

from __future__ import annotations

import json
import pickle
import sys
from collections import Counter
from pathlib import Path
from typing import Any

import q8a_env as env
import q8a_feat as feat

q7e = env.mod("q7_eval")
q7r = env.mod("q7_rules")
q7s = env.mod("q7_score")
ev = env.mod("q6_eval")
rp = env.mod("q6_report")
KEYS = ("set", "design", "cell", "part", "kind")
SUBCLASSES = ("NOSEED", "BLOATED", "SPLIT", "UNDERREACH", "TOOSMALL", "TOOBIG", "MERGED", "BETWEEN")


def order_subclass(u: Any, j: int) -> str:
    """Why no prefix of any block is right (class ORDER of q7_score), EXPERIMENT.md."""
    if any((bp.coverage[j] >= 0.8).any() for bp in u.blocks):
        return "BLOATED"
    total = sum(float(bp.inter[j, -1]) for bp in u.blocks)
    return "SPLIT" if total >= 0.8 * u.blocks[0].ntrue[j] else "UNDERREACH"


def score_order(units: list[Any], head_d: Any) -> dict[str, list[dict[str, Any]]]:
    """END rows (with subclass) and rule-d rows of one order."""
    end = q7s.score(units, [[bp.n - 1 for bp in u.blocks] for u in units])
    rows = end[0]
    k = 0
    for u in units:
        for j in range(len(u.cons)):
            r = rows[k]
            r["sub"] = order_subclass(u, j) if r["cls"] == "ORDER" else r["cls"]
            k += 1
    out = {"END": rows, "claims": end[1]}
    if head_d is not None:
        out["d"] = q7s.score(units, [[head_d(bp) for bp in u.blocks] for u in units])[0]
    return out


def per_target(res: dict[str, dict[str, list[dict[str, Any]]]], pick: dict[str, str],
               what: str = "END") -> list[dict[str, Any]]:
    """Rows of the per-target best order: each construct from the order chosen for its target."""
    tgt = {c: t for t, cs in env.TARGETS.items() for c in cs}
    idx = {o: {tuple(r[k] for k in KEYS): r for r in res[o][what]} for o in pick.values()}
    base = res["E74"]["END"]
    return [idx[pick[tgt[r["cell"]]]][tuple(r[k] for k in KEYS)] for r in base]


def with_refs(rows: list[dict[str, Any]], refs: Any, e74: list[dict[str, Any]],
              drows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for r, b, d in zip(rows, e74, drows, strict=True):
        ref = refs.get(q7e.key_of(r))
        if ref is not None:
            out.append({**r, "e73": int(ref["right"]), "d70": int(ref["d70"]) if "d70" in ref
                        else int(ref["d70_right"]), "e74": b["right"], "e74_sub": b["sub"],
                        "d_right": d["right"]})
    return out


def scope_sel(rows: list[dict[str, Any]], scope: str) -> list[dict[str, Any]]:
    if scope == "all":
        return rows
    k, v = scope.split(" ", 1)
    if k == "target":
        return [r for r in rows if r["cell"] in env.TARGETS[v]]
    return [r for r in rows if r[{"set": "set", "cell": "cell", "kind": "kind"}[k]] == v]


def all_scopes() -> list[str]:
    return (["all"] + [f"target {t}" for t in env.TARGETS] + ["set single", "set comp"]
            + [f"cell {c}" for c in env.CELLS] + [f"kind {k}" for k in q7e.KINDS5])


def tables(res: dict[str, dict[str, list[dict[str, Any]]]], names: list[str], refs: Any,
           head: str, pick: dict[str, str]) -> dict[str, list[dict[str, Any]]]:
    e74 = res["E74"]["END"]
    rows = {n: with_refs(res[n]["END"], refs, e74, res[n]["d"]) for n in names}
    out: dict[str, list[dict[str, Any]]] = {}
    out["right_block.csv"] = right_block(rows, names)
    out["unit_cmp.csv"] = unit_cmp(rows, names)
    out["failure_classes.csv"] = failure_rows(rows, names)
    out["recovery.csv"] = recovery_rows(rows, names)
    out["pr_by_kind.csv"] = pr_rows(res, names)
    out["verdict.csv"] = verdicts(rows, out["unit_cmp.csv"], out["recovery.csv"], head, pick)
    out["construct_records.csv"] = [
        {**{k: r[k] for k in (*KEYS, "n_true")}, "d70": r["d70"], "e73": r["e73"],
         **{f"{n}_{f}": rows[n][i][f] for n in names for f in ("right", "oracle", "sub")}}
        for i, r in enumerate(rows[names[0]])]
    return out


def right_block(rows: dict[str, list[dict[str, Any]]], names: list[str]) -> list[dict[str, Any]]:
    out = []
    for sc_name in all_scopes():
        sel = {n: scope_sel(rows[n], sc_name) for n in names}
        if not sel[names[0]]:
            continue
        r: dict[str, Any] = {"scope": sc_name, "constructs": len(sel[names[0]]),
                             "e73_share": q7s.share([{"right": x["e73"]} for x in sel[names[0]]]),
                             "d70_share": q7s.share([{"right": x["d70"]} for x in sel[names[0]]])}
        for n in names:
            r[f"{n}_end_share"] = round(q7s.share(sel[n]), 3)
            r[f"{n}_d_share"] = round(q7s.share([{"right": x["d_right"]} for x in sel[n]]), 3)
            r[f"{n}_oracle_share"] = round(q7s.share([{"right": x["oracle"]} for x in sel[n]]), 3)
        for k in ("e73_share", "d70_share"):
            r[k] = round(r[k], 3)
        out.append(r)
    return out


def unit_cmp(rows: dict[str, list[dict[str, Any]]], names: list[str]) -> list[dict[str, Any]]:
    out = []
    for n in names:
        for sc_name in ("all", *[f"target {t}" for t in env.TARGETS], "set single", "set comp"):
            sel = scope_sel(rows[n], sc_name)
            for ref in ("d70", "e74", "e73"):
                if sel and not (n == "E74" and ref == "e74"):
                    out.append({"order": n, "scope": sc_name, "against": ref.upper(),
                                **q7e.compare(sel, "right", ref)})
    return out


def failure_rows(rows: dict[str, list[dict[str, Any]]], names: list[str]) -> list[dict[str, Any]]:
    out = []
    for n in names:
        for sc_name in ("all", *[f"target {t}" for t in env.TARGETS]):
            sel = scope_sel(rows[n], sc_name)
            c = Counter(r["sub"] for r in sel if not r["right"])
            out.append({"order": n, "scope": sc_name, "constructs": len(sel),
                        "right": sum(r["right"] for r in sel), **{k: c[k] for k in SUBCLASSES}})
    return out


def recovery_rows(rows: dict[str, list[dict[str, Any]]], names: list[str]) -> list[dict[str, Any]]:
    """What an order does with the constructs E74 got wrong (ORDER, NOSEED) and right."""
    out = []
    for n in names:
        if n == "E74":
            continue
        for sc_name in ("all", *[f"target {t}" for t in env.TARGETS]):
            sel = scope_sel(rows[n], sc_name)
            o74 = [r for r in sel if r["e74_sub"] in ("BLOATED", "SPLIT", "UNDERREACH")]
            n74 = [r for r in sel if r["e74_sub"] == "NOSEED"]
            right74 = [r for r in sel if r["e74"]]
            out.append({"order": n, "scope": sc_name, "e74_order_class": len(o74),
                        "recovered_of_e74_order": sum(r["right"] for r in o74),
                        "e74_noseed": len(n74),
                        "recovered_of_e74_noseed": sum(r["right"] for r in n74),
                        "e74_right": len(right74), "lost_of_e74_right":
                        sum(1 - r["right"] for r in right74)})
    return out


def pr_rows(res: dict[str, Any], names: list[str]) -> list[dict[str, Any]]:
    out = []
    for n in (x for x in names if x != "PT"):
        claims = res[n]["claims"]
        for k in (*q7e.KINDS5, "all"):
            cl = [c for c in claims if c["claim"] and (k == "all" or c["argmax"] == k)]
            tp = sum(c["tp"] for c in cl)
            out.append({"order": n, "kind": k, "claims": len(cl), "tp": tp,
                        "precision": round(tp / len(cl), 3) if cl else ""})
    return out


def verdicts(rows: dict[str, list[dict[str, Any]]], cmp_rows: list[dict[str, Any]],
             rec: list[dict[str, Any]], head: str, pick: dict[str, str]) -> list[dict[str, Any]]:
    def get(n: str, scope: str, against: str) -> dict[str, Any]:
        return next(x for x in cmp_rows if x["order"] == n and x["scope"] == scope
                    and x["against"] == against)

    def fmt(r: dict[str, Any], i: str, q: str, lab: str | None = None) -> dict[str, Any]:
        return {"id": i, "question": q, "value": r["geomean"], "ci90_lo": r["ci90_lo"],
                "ci90_hi": r["ci90_hi"],
                "counts": f"W{r['W']}/L{r['L']}/T{r['T']} of {r['units']} units",
                "label": lab or r["label"]}

    out = []
    for scope in ("all", "target gate", "target k4", "target k6/hardmap", "set single", "set comp"):
        r = get(head, scope, "D70")
        out.append(fmt(r, f"QL8a-a {scope}", f"order {head} against D70",
                       "DISMISSED (WORSE)" if r["label"] == "WORSE" else None))
    for scope in ("all", "target gate", "target k4", "target k6/hardmap", "set single", "set comp"):
        out.append(fmt(get(head, scope, "E74"), f"QL8a-b {scope}", f"order {head} against E74-END"))
    r = next(x for x in rec if x["order"] == head and x["scope"] == "all")
    frac = r["recovered_of_e74_order"] / r["e74_order_class"] if r["e74_order_class"] else 0.0
    k6, comp = get(head, "target k6/hardmap", "D70")["label"], get(head, "set comp", "D70")["label"]
    not_better = all(get(head, s, "E74")["label"] != "BETTER" for s in
                     ("all", "target k6/hardmap", "set comp"))
    lab = ("SUPPORTED" if k6 == "BETTER" and comp == "BETTER" and frac >= 0.10 else
           "CONTRADICTED" if not_better and r["recovered_of_e74_order"] == 0 else "INCONCLUSIVE")
    out.append({"id": "QL8a-c", "question": f"hypothesis (order {head})", "value": round(frac, 3),
                "ci90_lo": "", "ci90_hi": "",
                "counts": f"{r['recovered_of_e74_order']} of {r['e74_order_class']} "
                          f"formerly ORDER; k6 {k6}, comp {comp}", "label": lab})
    if "PT" in rows:
        out.append(fmt(get("PT", "all", "D70"), "QL8a-a PT all", f"per-target best {pick} vs D70"))
        out.append(fmt(get("PT", "all", "E74"), "QL8a-b PT all", "per-target best vs E74-END"))
    return out


def bar_svg(rows: list[dict[str, Any]], names: list[str], path: Path) -> None:
    all_row = next(r for r in rows if r["scope"] == "all")
    bars = [("E73", all_row["e73_share"]), ("D70", all_row["d70_share"]),
            *[(n, all_row[f"{n}_end_share"]) for n in names],
            ("ORACLE", max(all_row[f"{n}_oracle_share"] for n in names))]
    w, h, left, top = 520, 260, 50, 20
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" '
           'font-family="sans-serif" font-size="11">',
           f'<text x="{left}" y="14">Right-block share at the path end (TEST)</text>']
    for t in (0.0, 0.25, 0.5, 0.75, 1.0):
        y = top + (h - top - 30) * (1 - t)
        out.append(f'<line x1="{left}" x2="{w - 10}" y1="{y:.1f}" y2="{y:.1f}" stroke="#ddd"/>')
        out.append(f'<text x="{left - 6}" y="{y + 4:.1f}" text-anchor="end">{t:.2f}</text>')
    bw = (w - left - 10) / len(bars)
    for i, (name, v) in enumerate(bars):
        hh = (h - top - 30) * float(v)
        x = left + i * bw + 4
        col = "#c0504d" if name in ("D70", "E73") else "#999" if name in ("ORACLE", "E74") \
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
    head = cfg["headline"]
    pick = cfg["per_target"]
    names = ["E74", *sorted({head, *pick.values()}, key=env.ORDERS.index)]
    with (env.OUT7 / "clf.pkl").open("rb") as fh:
        clf = pickle.load(fh)
    cfg7 = json.loads((env.HERE.parent / "ql7-stop" / "results" / "chosen.json"
                       ).read_text(encoding="utf-8"))
    d_pick = q7r.pickers(cfg7, clf)["d"]
    res = {n: score_order(feat.load(n, split), d_pick) for n in names}
    if len({len(res[n]["END"]) for n in names}) != 1:
        raise SystemExit("orders differ in construct count")
    if set(pick.values()) != {head}:
        res["PT"] = {"END": per_target(res, pick), "claims": [],
                     "d": per_target(res, pick, "d")}
        names.append("PT")
    refs = q7e.ref_rows() if split == "TEST" else q7e.ZeroRefs()
    tabs = tables(res, names, refs, head, pick)
    dest = env.RES if split == "TEST" else env.OUT8 / "dry"
    dest.mkdir(parents=True, exist_ok=True)
    for name, trows in tabs.items():
        if trows:
            env.l3dlib.write_csv(dest / name, list(trows[0]), trows)
    bar_svg(tabs["right_block.csv"], names, dest / "right_block.svg")
    for r in tabs["verdict.csv"]:
        print(r)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
