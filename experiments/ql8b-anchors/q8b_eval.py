"""Score the new anchors on one split and write the tables: ``python -B q8b_eval.py [SPLIT]``.

TEST only after the class set is chosen and committed (EXPERIMENT.md). SPLIT = TEST (default) writes
results/*.csv; VALIDATION is a dry run into $QL8B_OUT/dry (no D70 column).
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

import q8b_describe as qd
import q8b_env as env
import q8b_feat as feat

q7e = env.mod("q7_eval")
q7s = env.mod("q7_score")
NEW_KINDS = ("bank", "loop", "const")
KEYS = ("set", "design", "cell", "part", "kind")


def end_rows(units: list[Any]) -> list[dict[str, Any]]:
    rows = list(q7s.score(units, [[bp.n - 1 for bp in u.blocks] for u in units])[0])
    k = 0
    for u in units:
        for j in range(len(u.cons)):
            touch = [bp.anchor_kind for bp in u.blocks if bp.inter[j, -1] > 0]
            rows[k]["touched"] = int(bool(touch))
            rows[k]["touch_kinds"] = "+".join(sorted(set(touch)))
            rows[k]["new_touch"] = int(any(t in NEW_KINDS for t in touch))
            k += 1
    return rows


def joined(old: list[dict[str, Any]], new: list[dict[str, Any]], refs: Any) -> list[dict[str, Any]]:
    out = []
    for a, b in zip(old, new, strict=True):
        ref = refs.get(q7e.key_of(b))
        if ref is None:
            continue
        d70 = int(ref["d70_right"])
        out.append({**b, "e73": int(ref["right"]), "d70": d70, "old": a["right"],
                    "old_oracle": a["oracle"], "old_touched": a["touched"]})
    return out


def scope_sel(rows: list[dict[str, Any]], scope: str) -> list[dict[str, Any]]:
    if scope == "all":
        return rows
    k, v = scope.split(" ", 1)
    if k == "target":
        return [r for r in rows if r["cell"] in env.TARGETS[v]]
    return [r for r in rows if r[k] == v]


def scopes() -> list[str]:
    return (["all"] + [f"target {t}" for t in env.TARGETS] + ["set single", "set comp"]
            + [f"cell {c}" for c in env.CELLS] + [f"kind {k}" for k in env.KINDS5])


def share(rows: list[dict[str, Any]], key: str) -> float:
    return round(sum(r[key] for r in rows) / len(rows), 3) if rows else float("nan")


def right_block(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for name in scopes():
        sel = scope_sel(rows, name)
        if sel:
            out.append({"scope": name, "constructs": len(sel), "e73_share": share(sel, "e73"),
                        "d70_share": share(sel, "d70"), "old_end_share": share(sel, "old"),
                        "old_oracle_share": share(sel, "old_oracle"),
                        "new_end_share": share(sel, "right"),
                        "new_oracle_share": share(sel, "oracle"),
                        "old_touched_share": share(sel, "old_touched"),
                        "new_touched_share": share(sel, "touched")})
    return out


def unit_cmp(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for name in ("all", *[f"target {t}" for t in env.TARGETS], "set single", "set comp"):
        sel = scope_sel(rows, name)
        for ref in ("d70", "old", "e73"):
            if sel:
                out.append({"scope": name, "against": ref.upper(),
                            **q7e.compare(sel, "right", ref)})
    return out


def census(rows: list[dict[str, Any]], desc: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The old NOSEED constructs: what the new anchors do with each (EXPERIMENT.md 'The 58')."""
    info = {(r["set"], r["design"], r["cell"], int(r["part"]), r["kind"]): r for r in desc}
    out = []
    for r in rows:
        d = info.get(q7e.key_of(r))
        if d is None:
            continue
        grp = "constant" if int(d["n_const"]) == int(d["n_true"]) else "structural"
        out.append({**{k: r[k] for k in KEYS}, "n_true": r["n_true"], "group": grp,
                    "reason": d["reason"], "new_touched": r["touched"], "new_right": r["right"],
                    "touch_kinds": r["touch_kinds"], "best_jaccard": r["best_jaccard"],
                    "best_size": r["best_size"]})
    return out


def census_summary(cen: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    groups = [("all", cen)] + [(g, [r for r in cen if r["group"] == g])
                               for g in ("constant", "structural")]
    groups += [(f"reason: {k}", [r for r in cen if r["reason"] == k])
               for k in sorted({r["reason"] for r in cen})]
    for name, sel in groups:
        out.append({"group": name, "constructs": len(sel),
                    "touched": sum(r["new_touched"] for r in sel),
                    "right": sum(r["new_right"] for r in sel)})
    return out


def precision(units: list[Any]) -> list[dict[str, Any]]:
    stat: dict[str, Counter[str]] = {}
    for u in units:
        for bp in u.blocks:
            c = stat.setdefault(bp.anchor_kind, Counter())
            c["blocks"] += 1
            if bp.inter.shape[0]:
                c["touch_at_anchor"] += int(bp.inter[:, 0].sum() > 0)
                c["right_at_end"] += int(bp.right[:, -1].any())
    return [{"anchor_kind": k, "blocks": c["blocks"], "touch_at_anchor": c["touch_at_anchor"],
             "touch_share": round(c["touch_at_anchor"] / c["blocks"], 3),
             "right_at_end": c["right_at_end"],
             "right_share": round(c["right_at_end"] / c["blocks"], 3)}
            for k, c in sorted(stat.items())]


def false_blocks(units: list[Any], old_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """New-class blocks in units where #74 left no construct untouched, and the constructs lost."""
    untouched_units = set()
    k = 0
    for u in units:
        for _ in u.cons:
            if not old_rows[k]["touched"]:
                untouched_units.add(u.key)
            k += 1
    out = []
    for cls in NEW_KINDS:
        n = elsewhere = touch_else = 0
        for u in units:
            for bp in u.blocks:
                if bp.anchor_kind == cls:
                    n += 1
                    if u.key not in untouched_units:
                        elsewhere += 1
                        touch_else += int(bool(bp.inter.shape[0]) and bp.inter[:, 0].sum() > 0)
        out.append({"class": cls, "blocks": n, "in_units_without_untouched": elsewhere,
                    "of_which_touch_a_construct": touch_else})
    return out


def lost_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [{**{k: r[k] for k in KEYS}, "n_true": r["n_true"], "new_block_touches": r["new_touch"],
             "touch_kinds": r["touch_kinds"]} for r in rows if r["old"] and not r["right"]]


def verdicts(cen_sum: list[dict[str, Any]], cmp_rows: list[dict[str, Any]],
             prec: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for r in cen_sum:
        if r["group"] in ("all", "structural", "constant"):
            right, touched = r["right"], r["touched"]
            lab = ("SUPPORTED" if right >= 10 else "CONTRADICTED" if touched == 0
                   else "INCONCLUSIVE")
            out.append({"id": f"QL8b-a {r['group']}", "question": "untouched constructs become "
                        "touched and right", "value": right, "ci90_lo": "", "ci90_hi": "",
                        "counts": f"{touched} touched, {right} right of {r['constructs']}",
                        "label": lab})
    for against in ("D70", "OLD"):
        c = next(x for x in cmp_rows if x["scope"] == "all" and x["against"] == against)
        out.append({"id": f"QL8b-b vs {against}", "question": f"new anchors against {against}",
                    "value": c["geomean"], "ci90_lo": c["ci90_lo"], "ci90_hi": c["ci90_hi"],
                    "counts": f"W{c['W']}/L{c['L']}/T{c['T']} of {c['units']} units",
                    "label": c["label"]})
    for p in prec:
        if p["anchor_kind"] in NEW_KINDS:
            out.append({"id": f"QL8b-c {p['anchor_kind']}", "question": "anchor precision",
                        "value": p["touch_share"], "ci90_lo": "", "ci90_hi": "",
                        "counts": f"{p['blocks']} blocks, {p['touch_at_anchor']} touch, "
                                  f"{p['right_at_end']} right at end", "label": "MEASUREMENT"})
    return out


def main(argv: list[str]) -> int:
    split = argv[0] if argv else "TEST"
    cfg = json.loads((env.RES / "chosen.json").read_text(encoding="utf-8"))
    var = cfg["variant"]
    old_u, new_u = feat.load("OLD", split), feat.load(var, split)
    old_r, new_r = end_rows(old_u), end_rows(new_u)
    refs = q7e.ref_rows() if split == "TEST" else q7e.ZeroRefs()
    rows = joined(old_r, new_r, refs)
    cen = census(rows, qd.describe()) if split == "TEST" else []
    cs = census_summary(cen) if cen else []
    prec = precision(new_u)
    tabs: dict[str, list[dict[str, Any]]] = {
        "right_block.csv": right_block(rows), "unit_cmp.csv": unit_cmp(rows),
        "untouched.csv": cen, "untouched_summary.csv": cs,
        "anchor_precision.csv": [{"set": "NEW", **r} for r in prec]
        + [{"set": "OLD", **r} for r in precision(old_u)],
        "false_blocks.csv": false_blocks(new_u, old_r), "lost.csv": lost_rows(rows)}
    tabs["verdict.csv"] = verdicts(cs, tabs["unit_cmp.csv"], prec) if cs else []
    dest = env.RES if split == "TEST" else env.OUT8 / "dry"
    dest.mkdir(parents=True, exist_ok=True)
    for name, trows in tabs.items():
        if trows:
            env.l3dlib.write_csv(Path(dest / name), list(trows[0]), trows)
    for r in tabs["verdict.csv"] or tabs["right_block.csv"][:3]:
        print(r)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
