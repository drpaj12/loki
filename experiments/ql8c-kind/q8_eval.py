"""Score every model on one set and write the tables: ``python -B q8_eval.py [SET]``.

SET = TEST (default) writes results/*.csv. VAL is accepted for a dry run into $QL8C_OUT/dry. Needs
q8_tune.py (models.pkl, chosen.json) and q8_data.py SET. TEST only after tuning is committed.
"""

from __future__ import annotations

import json
import pickle
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import numpy as np
import q8_env as env
import q8_score as sc
import q8_tune as tune

rp = env.mod("q6_report")
q7e = env.mod("q7_eval")
MODELS = ("B73", "B73-T", "M1", "M2", "M3", "M4")
SETS = ("single", "comp")


def scopes(recs: list[Any]) -> list[tuple[str, list[int]]]:
    out: list[tuple[str, list[int]]] = [("all", list(range(len(recs))))]
    out += [(f"target {t}", [i for i, r in enumerate(recs) if r["cell"] in cs])
            for t, cs in env.TARGETS.items()]
    out += [(f"set {s}", [i for i, r in enumerate(recs) if r["set"] == s]) for s in SETS]
    return out


def by_design(recs: list[Any], vecs: list[np.ndarray], idx: list[int]) -> dict[str, np.ndarray]:
    out: dict[str, np.ndarray] = defaultdict(lambda: np.zeros(sc.LEN))
    for i in idx:
        out[recs[i]["design"]] += vecs[i]
    return dict(out)


def paired(a: dict[str, np.ndarray], b: dict[str, np.ndarray]) -> dict[str, np.ndarray]:
    return {d: np.concatenate([a[d], b[d]]) for d in a}


def diff_stat(fn: Any) -> Any:
    return lambda s: fn(s[:sc.LEN]) - fn(s[sc.LEN:])


def ci_row(qid: str, question: str, res: tuple[float, float, float], counts: str,
           label: str) -> dict[str, Any]:
    return {"id": qid, "question": question, "value": round(res[0], 3),
            "ci90_lo": round(res[1], 3), "ci90_hi": round(res[2], 3), "counts": counts,
            "label": label}


def unit_geomean(recs: list[Any], vg: list[np.ndarray], vd: list[np.ndarray], idx: list[int]
                 ) -> dict[str, Any]:
    per = [{"design": recs[i]["design"],
            "g": int(vg[i][sc.O_REC:sc.O_REC + sc.K].sum()),
            "d": int(vd[i][sc.O_REC:sc.O_REC + sc.K].sum())} for i in idx]
    wl = Counter("W" if r["g"] > r["d"] else "L" if r["g"] < r["d"] else "T" for r in per)
    pt, lo, hi = q7e.ev.boot_ci(rp.by_design(per), q7e.geomean)
    return {"geomean": round(pt, 3), "ci90_lo": round(lo, 3), "ci90_hi": round(hi, 3),
            "W": wl["W"], "L": wl["L"], "T": wl["T"], "units": len(per),
            "label": rp.label_better(pt, lo, hi)}


def tables(recs: list[Any], vec: dict[str, list[np.ndarray]], head: str
           ) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for name in MODELS:
        for sname, idx in scopes(recs):
            tot = np.sum([vec[name][i] for i in idx], axis=0)
            for which, true in (("grown", False), ("true", True)):
                for r in sc.kind_rows(tot, true):
                    out["per_kind.csv"].append({"model": name, "blocks": which, "scope": sname,
                                                **r})
            out["summary.csv"].append({
                "model": name, "scope": sname, "units": len(idx),
                "macro_f1_grown": round(sc.macro_f1(tot), 3),
                "macro_f1_true": round(sc.macro_f1(tot, True), 3),
                "top3_right": round(sc.top3(tot, False), 3),
                "top3_true": round(sc.top3(tot, True), 3),
                "ece_grown_all": round(sc.ece(tot, 0), 3),
                "ece_grown_right": round(sc.ece(tot, 1), 3), "ece_true": round(sc.ece(tot, 2), 3),
                "nll_grown_all": round(tot[sc.O_NLL] / tot[sc.O_NLL + 1], 3)})
            if sname == "all":
                for w, label in enumerate(sc.CAL_SETS):
                    for r in sc.reliability(tot, w):
                        out["reliability.csv"].append({"model": name, "blocks": label, **r})
    out["verdict.csv"] = verdicts(recs, vec, head)
    out["unit_cmp.csv"] = [{"model": m, "against": a, "scope": s, **unit_geomean(
        recs, vec[m], vec[a], idx)} for m in MODELS[1:]
        for a in ("B73", "B73-T") if m != a for s, idx in scopes(recs)]
    return out


def verdicts(recs: list[Any], vec: dict[str, list[np.ndarray]], head: str) -> list[dict[str, Any]]:
    allidx = list(range(len(recs)))
    bd = {m: by_design(recs, vec[m], allidx) for m in MODELS}
    out = []
    a = unit_geomean(recs, vec[head], vec["B73"], allidx)
    lab = "DISMISSED (WORSE)" if a["label"] == "WORSE" else a["label"]
    out.append({"id": "QL8c-a", "question": f"model {head} claims more right kinds than B73 "
                "(constructs recovered with their kind, per unit geomean)", "value": a["geomean"],
                "ci90_lo": a["ci90_lo"], "ci90_hi": a["ci90_hi"],
                "counts": f"W{a['W']}/L{a['L']}/T{a['T']} of {a['units']} units", "label": lab})
    for base, qid in (("B73", "QL8c-b"), ("B73-T", "QL8c-b2")):
        r = sc.boot(paired(bd[head], bd[base]), diff_stat(sc.macro_f1))
        lab = "SUPPORTED" if r[1] > 0.10 else "CONTRADICTED" if r[2] < 0.10 else "INCONCLUSIVE"
        out.append(ci_row(qid, f"macro F1 gain of {head} over {base} on grown blocks, "
                          "hypothesis: above +0.10", r, f"{len(allidx)} units", lab))
    r = sc.boot(paired(bd[head], bd["B73-T"]), diff_stat(lambda v: sc.ece(v, 0)))
    out.append(ci_row("QL8c-c", f"ECE of {head} minus ECE of B73-T (grown, all blocks)", r,
                      "", "MEASUREMENT"))
    r = sc.boot(paired(bd[head], bd["B73-T"]), diff_stat(lambda v: sc.ece(v, 1)))
    out.append(ci_row("QL8c-c2", f"ECE of {head} minus ECE of B73-T (grown, right blocks)", r,
                      "", "MEASUREMENT"))
    r = sc.boot(paired(bd[head], bd["B73"]), diff_stat(lambda v: sc.macro_f1(v, True)))
    out.append(ci_row("QL8c-d", f"macro F1 gain of {head} over B73 on true blocks", r, "",
                      "MEASUREMENT"))
    r = sc.boot(paired(bd[head], bd["B73"]), diff_stat(lambda v: sc.top3(v, True)))
    out.append(ci_row("QL8c-d2", f"top-3 gain of {head} over B73 on true blocks", r, "",
                      "MEASUREMENT"))
    for m in MODELS[2:]:
        r = sc.boot(paired(bd[m], bd["B73"]), diff_stat(sc.macro_f1))
        out.append(ci_row(f"QL8c-m-{m}", f"macro F1 gain of {m} over B73 on grown blocks", r, "",
                          "MEASUREMENT"))
    return out


def reliability_svg(rows: list[dict[str, Any]], path: Path) -> None:
    """Top-label reliability of B73-T and the chosen model(s) on all grown blocks."""
    size, left, top = 260, 40, 20
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {size + 120} {size + 50}" '
           'font-family="sans-serif" font-size="10">',
           f'<text x="{left}" y="12">Top-label reliability, grown blocks (TEST)</text>',
           f'<line x1="{left}" y1="{top + size}" x2="{left + size}" y2="{top}" stroke="#bbb"/>',
           f'<rect x="{left}" y="{top}" width="{size}" height="{size}" fill="none" stroke="#999"/>']
    cols = {"B73": "#c0504d", "B73-T": "#e69f00", "M1": "#009e73", "M2": "#1f77b4",
            "M3": "#7f3fbf", "M4": "#000000"}
    for j, (name, col) in enumerate(cols.items()):
        pts = [(float(r["confidence"]), float(r["accuracy"])) for r in rows
               if r["model"] == name and r["blocks"] == "grown_all" and r["n"]]
        path_d = " ".join(f"{left + c * size:.1f},{top + size - a * size:.1f}" for c, a in pts)
        out.append(f'<polyline points="{path_d}" fill="none" stroke="{col}" stroke-width="1.5"/>')
        ty = top + 14 * (j + 1)
        out.append(f'<text x="{left + size + 8}" y="{ty}" fill="{col}">{name}</text>')
    out.append(f'<text x="{left}" y="{top + size + 30}">confidence</text></svg>')
    path.write_text("\n".join(out) + "\n", encoding="utf-8")


def main(argv: list[str]) -> int:
    name = argv[0] if argv else "TEST"
    chosen = json.loads((env.RES / "chosen.json").read_text(encoding="utf-8"))
    with (env.OUT8 / "models.pkl").open("rb") as fh:
        m = pickle.load(fh)
    recs = tune.load(name)
    vec = {n: [sc.unit_vector(r, tune.make_post(m["lik"][n], m["temps"][n], m["prior"]))
               for r in recs] for n in MODELS}
    tabs = tables(recs, vec, chosen["model"])
    dest = env.RES if name == "TEST" else env.OUT8 / "dry"
    dest.mkdir(parents=True, exist_ok=True)
    for fname, rows in tabs.items():
        env.l3dlib.write_csv(dest / fname, list(rows[0]), rows)
    reliability_svg(tabs["reliability.csv"], dest / "reliability.svg")
    for r in tabs["verdict.csv"]:
        print(r)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
