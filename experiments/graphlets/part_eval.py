"""Calibrate on TUNE singles, evaluate partitions on TEST singles and TEST composites.

``python -B part_eval.py`` (after partitions.py). Decision per partition: highest naive-Bayes
posterior over library patterns (glue excluded: it has no flip-flops) if >= threshold; threshold
fit on TUNE to maximise F1 of the design-level found / not-found decisions (so that rejecting can
pay). Design-level: found(p) if a partition is predicted p; glue if the design has no state group.
Composites: kind-level part matching as in l3-detector/part_c.py (fsm, counter, shift families).
"""

from __future__ import annotations

import json
import os
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "l3-detector"))
import l3dlib  # noqa: E402
import live  # noqa: E402
import match_eval as me  # noqa: E402

RES = HERE / "results"
PREFIX = os.environ.get("PART_PREFIX", "part")
SCORES = os.environ.get("PART_SCORES", "part_scores.jsonl")
ENT = tuple(e for e in l3dlib.ENTRIES if e != "glue")
FAMILY = {"fsm": "fsm", "counter": "counter", "timer": "counter", "shift": "shift",
          "lfsr": "shift"}
FAMS = ("fsm", "counter", "shift")


def read_rows() -> list[dict[str, Any]]:
    p = live.OUT / "match" / SCORES
    return [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines()]


def posts(cal: me.Calib, row: dict[str, Any], tag: str) -> dict[str, float]:
    return {p: (cal.post(row[tag][p][0], row[tag][p][1]) if p in row[tag] else 0.0)
            for p in ENT}


def accepted(cal: me.Calib, row: dict[str, Any], tag: str, thr: float) -> str:
    if tag not in row:
        return ""
    ps = posts(cal, row, tag)
    p = max(ENT, key=lambda e: ps[e])
    return p if ps[p] >= thr else ""


def design_found(parts: list[dict[str, Any]], cal: me.Calib, tag: str, thr: float, n_groups: int
                 ) -> set[str]:
    f = {accepted(cal, r, tag, thr) for r in parts} - {""}
    if n_groups == 0:
        f.add("glue")
    return f


def main() -> int:
    rows = read_rows()
    fam = me.truth_family()
    split = {r["design"]: r["split"] for r in l3dlib.read_csv(l3dlib.RES / "split_single.csv")}
    by: dict[tuple[str, str, str, str], list[dict[str, Any]]] = defaultdict(list)
    ng: dict[tuple[str, str], int] = {}
    errors = 0
    for r in rows:
        ng[(r["design"], r["cell"])] = r.get("n_groups", 0)
        if r["mode"] == "none":
            continue
        if r.get("error"):
            errors += 1
            continue
        by[(r["set"], r["design"], r["cell"], r["mode"])].append(r)
    singles = sorted({(d, c) for (s, d, c, m) in by if s == "single"} |
                     {(r["design"], r["cell"]) for r in rows if r["set"] == "single"
                      and r["mode"] == "none"})
    pred: dict[tuple[str, str, str, str], set[str]] = {}
    thr_rows = []
    cals: dict[tuple[str, str], tuple[me.Calib, float]] = {}
    rel: list[dict[str, Any]] = []
    for mode in ("undirected", "directed"):
        for tag in ("all", "ff"):
            cal = me.Calib()
            tune = [(d, c) for d, c in singles if split[d] == "TUNE"]
            for d, c in tune:
                for r in by.get(("single", d, c, mode), []):
                    for p in ENT:
                        if p in r[tag]:
                            cal.add(r[tag][p][0], r[tag][p][1], p == fam[d])
            (RES / f"{PREFIX}_calibration_{mode}_{tag}.json").write_text(
                json.dumps(cal.file(mode), sort_keys=True), encoding="utf-8")

            def f1(thr: float, cal: me.Calib = cal, tune: list[tuple[str, str]] = tune,
                   mode: str = mode, tag: str = tag) -> float:
                tp = fp = fn = 0
                for d, c in tune:
                    f = design_found(by.get(("single", d, c, mode), []), cal, tag, thr,
                                     ng[(d, c)])
                    for p in l3dlib.ENTRIES:
                        t, x = int(fam[d] == p), int(p in f)
                        tp += t & x
                        fp += (1 - t) & x
                        fn += t & (1 - x)
                return 2 * tp / (2 * tp + fp + fn) if tp + fp + fn else 0.0

            grid = [x / 100 for x in range(5, 100, 5)]
            thr = max(grid, key=lambda t: (round(f1(t), 6), t))
            cals[(mode, tag)] = (cal, thr)
            thr_rows.append({"mode": mode, "restrict": tag, "threshold": thr,
                             "tune_F1": round(f1(thr), 3), "tune_F1_at_0.05": round(f1(0.05), 3),
                             "pairs": sum(cal.prior.values()), "same_pairs": cal.prior["same"]})
            for d, c in singles:
                pred[(mode, tag, d, c)] = design_found(by.get(("single", d, c, mode), []), cal,
                                                       tag, thr, ng[(d, c)])
                if split[d] == "TEST":
                    for r in by.get(("single", d, c, mode), []):
                        for p, pv in posts(cal, r, tag).items():
                            if p in r[tag]:
                                b = min(9, int(pv * 10))
                                rel.append({"mode": mode, "restrict": tag, "bin": b,
                                            "same": int(p == fam[d])})
    l3dlib.write_csv(RES / f"{PREFIX}_threshold.csv", list(thr_rows[0]), thr_rows)
    agg: dict[tuple[str, str, int], list[int]] = defaultdict(lambda: [0, 0])
    for x in rel:
        a = agg[(x["mode"], x["restrict"], x["bin"])]
        a[0] += 1
        a[1] += x["same"]
    l3dlib.write_csv(RES / f"{PREFIX}_reliability.csv",
                     ["mode", "restrict", "posterior_bin", "pairs", "observed_same"],
                     [{"mode": k[0], "restrict": k[1],
                       "posterior_bin": f"{k[2] / 10:.1f}-{(k[2] + 1) / 10:.1f}",
                       "pairs": v[0], "observed_same": round(v[1] / v[0], 3)}
                      for k, v in sorted(agg.items())])
    rule: dict[tuple[str, str], dict[str, int]] = {}
    for r in l3dlib.read_csv(l3dlib.RES / "partA_design.csv"):
        rule[(r["design"], r["cell"])] = {e: int(r[f"found_{e}"]) for e in l3dlib.ENTRIES}
    test = [(d, c) for d, c in singles if split[d] == "TEST" and (d, c) in rule]
    per: dict[tuple[str, str, str], dict[str, tuple[int, int, int]]] = defaultdict(dict)
    variants = ["rule"] + [f"{m}/{t}" for m in ("undirected", "directed") for t in ("all", "ff")] \
        + ["hybrid-undirected/ff", "hybrid-directed/ff"]
    for v in variants:
        for p in l3dlib.ENTRIES:
            for d, c in test:
                t = int(fam[d] == p)
                if v == "rule":
                    x = rule[(d, c)][p]
                elif v.startswith("hybrid"):
                    m, tg = v.split("-")[1].split("/")
                    x = int(rule[(d, c)][p] or p in pred[(m, tg, d, c)])
                else:
                    m, tg = v.split("/")
                    x = int(p in pred[(m, tg, d, c)])
                per[(v, p, c)][d] = (t & x, (1 - t) & x, t & (1 - x))
    tab = []
    for (v, p, c), dd in sorted(per.items()):
        cnt = list(dd.values())
        tp, fp, fn = (sum(x[i] for x in cnt) for i in range(3))
        pr, rc = me.prf(cnt)
        lp, lr = l3dlib.bootstrap(cnt)
        tab.append({"variant": v, "pattern": p, "cell": c, "designs": len(cnt), "TP": tp, "FP": fp,
                    "FN": fn, "precision": round(pr, 3), "precision_lo": round(lp, 3),
                    "recall": round(rc, 3), "recall_lo": round(lr, 3),
                    "label": l3dlib.label(pr, rc, lp, lr, tp + fn)})
    l3dlib.write_csv(RES / f"{PREFIX}_table.csv", list(tab[0]), tab)
    tests = []
    rng = random.Random(7)
    for p in l3dlib.ENTRIES:
        for c in live.CELLS:
            a, b = per.get(("undirected/ff", p, c)), per.get(("directed/ff", p, c))
            if not a or not b:
                continue
            ds = sorted(a)
            npos = sum(a[d][0] + a[d][2] for d in ds)
            if npos < 5:
                continue
            diffs = []
            for _ in range(2000):
                s = [ds[rng.randrange(len(ds))] for _ in ds]
                pa_, ra_ = me.prf([a[d] for d in s])
                pb_, rb_ = me.prf([b[d] for d in s])
                diffs.append((pb_ - pa_) if rb_ >= ra_ else -1.0)
            pa0, ra0 = me.prf([a[d] for d in ds])
            pb0, rb0 = me.prf([b[d] for d in ds])
            tests.append({"pattern": p, "cell": c, "n_pos": npos, "prec_und": round(pa0, 3),
                          "prec_dir": round(pb0, 3), "rec_und": round(ra0, 3),
                          "rec_dir": round(rb0, 3), "p": sum(x <= 0 for x in diffs) / len(diffs)})
    tests.sort(key=lambda t: t["p"])
    run = 0.0
    for i, t in enumerate(tests):
        run = max(run, min(1.0, t["p"] * (len(tests) - i)))
        t["p_holm"] = round(run, 4)
        t["directed_more_precise"] = int(t["p_holm"] < 0.05 and t["prec_dir"] > t["prec_und"])
    if tests:
        l3dlib.write_csv(RES / f"{PREFIX}_directed_vs_undirected.csv", list(tests[0]), tests)
    comp_eval(by, cals)
    print(len(tab), "single rows;", len(tests), "directed tests;", errors, "partition errors")
    return 0


def comp_eval(by: dict[tuple[str, str, str, str], list[dict[str, Any]]],
              cals: dict[tuple[str, str], tuple[me.Calib, float]]) -> None:
    import part_c as pc

    det = pc.Detector(pc.catalogue.load(), pc.catalogue.load_tuning())
    out = []
    for r in pc.load("TEST"):
        name, cell = r["name"], r["cell"]
        tf: Counter[str] = Counter(f for p in r["truth"]["parts"] for f in p["families"])
        tf = Counter({k: v for k, v in tf.items() if k in FAMS})
        res = det.run(r["claims"], l3dlib.TARGET[cell], r["net"])
        parts = pc.parts_of(res)
        rf: Counter[str] = Counter(p.family for p in parts if p.family in FAMS)
        rec = {"name": name, "cell": cell, "truth": sum(tf.values())}

        def score(df: Counter[str], tf: Counter[str] = tf) -> tuple[int, int]:
            return sum(min(tf[k], df[k]) for k in tf), sum(df.values())

        rec["rule"] = score(rf)
        for (mode, tag), (cal, thr) in cals.items():
            sf: Counter[str] = Counter()
            for part in by.get(("comp", name, cell, mode), []):
                p = accepted(cal, part, tag, thr)
                if p in FAMILY:
                    sf[FAMILY[p]] += 1
            rec[f"{mode}/{tag}"] = score(sf)
            rec[f"hybrid-{mode}/{tag}"] = score(Counter({k: max(rf[k], sf[k]) for k in FAMS}))
        wires_of_comp(rec, r, by, cals, tf)
        out.append(rec)
    wire_table(out)
    keys = ["rule"] + [k for k in out[0] if "/" in k and not k.startswith("wires:")]
    tab = []
    for cell in live.CELLS:
        sub = [o for o in out if o["cell"] == cell]
        for k in keys:
            cnt = [(o[k][0], o[k][1] - o[k][0], o["truth"] - o[k][0]) for o in sub]
            pr, rc = me.prf(cnt)
            lp, lr = l3dlib.bootstrap(cnt)
            tp, fp, fn = (sum(x[i] for x in cnt) for i in range(3))
            tab.append({"variant": k, "cell": cell, "composites": len(sub), "TP": tp, "FP": fp,
                        "FN": fn, "part_precision": round(pr, 3), "part_precision_lo": round(lp, 3),
                        "part_recall": round(rc, 3), "part_recall_lo": round(lr, 3)})
    l3dlib.write_csv(RES / f"{PREFIX}_composites.csv", list(tab[0]), tab)



def wires_of_comp(rec: dict[str, Any], r: dict[str, Any],
                  by: dict[tuple[str, str, str, str], list[dict[str, Any]]],
                  cals: dict[tuple[str, str], tuple[me.Calib, float]], tf: Counter[str]) -> None:
    """Part-to-part links of the signature partitions scored against truth.json wires."""
    tparts, tw = r["truth"]["parts"], r["truth"]["wires"]
    tpairs = {(a, b) for w in tw for a in tparts[w["from"]]["families"]
              for b in tparts[w["to"]]["families"]}
    for (mode, tag), (cal, thr) in cals.items():
        rows = by.get(("comp", rec["name"], rec["cell"], mode), [])
        fam_of = {}
        for row in rows:
            p = accepted(cal, row, tag, thr)
            if p in FAMILY:
                fam_of[row["gi"]] = FAMILY[p]
        det = {(a, row["gi"]): "direct" if k == 0 else "comb"
               for row in rows if row["gi"] in fam_of
               for a, k in row.get("links", []) if a in fam_of}
        pairs = {(fam_of[a], fam_of[b]) for a, b in det}
        hit = [any((a, b) in pairs for a in tparts[w["from"]]["families"]
                   for b in tparts[w["to"]]["families"]) for w in tw]
        good = sum(1 for a, b in det if (fam_of[a], fam_of[b]) in tpairs)
        found = set(fam_of.values())
        both = [all(f in found for f in tparts[w["from"]]["families"] + tparts[w["to"]]["families"])
                for w in tw]
        rec[f"wires:{mode}/{tag}"] = {
            "truth": len(tw), "hit": sum(hit), "det": len(det), "good": good,
            "cond_n": sum(both), "cond_hit": sum(1 for b, h in zip(both, hit, strict=True)
                                                if b and h),
            "direct": sum(1 for w in tw if w["via"] == "direct"),
            "direct_hit": sum(1 for w, h in zip(tw, hit, strict=True)
                              if h and w["via"] == "direct"),
            "comb": sum(1 for w in tw if w["via"] != "direct"),
            "comb_hit": sum(1 for w, h in zip(tw, hit, strict=True)
                            if h and w["via"] != "direct")}


def wire_table(out: list[dict[str, Any]]) -> None:
    rule = {(x["name"], x["cell"]): x for x in l3dlib.read_csv(l3dlib.RES / "partC_composite.csv")}
    keys = [k for k in out[0] if k.startswith("wires:")]
    tab = []
    for cell in live.CELLS:
        sub = [o for o in out if o["cell"] == cell]
        rr = [rule[(o["name"], cell)] for o in sub if (o["name"], cell) in rule]
        variants: dict[str, list[dict[str, int]]] = {"rule": [
            {"truth": int(x["truth_wires"]), "hit": int(x["wires_hit"]), "det": int(x["det_wires"]),
             "good": int(x["det_wires_good"]), "cond_n": 0, "cond_hit": 0,
             "direct": int(x["via_direct"]), "direct_hit": int(x["hit_direct"]),
             "comb": int(x["via_comb"]), "comb_hit": int(x["hit_comb"])} for x in rr]}
        for k in keys:
            variants[k[6:]] = [o[k] for o in sub]
        for v, items in variants.items():
            t = sum(i["truth"] for i in items)
            h = sum(i["hit"] for i in items)
            d = sum(i["det"] for i in items)
            g = sum(i["good"] for i in items)
            _, lr = l3dlib.bootstrap([(i["hit"], 0, i["truth"] - i["hit"]) for i in items])
            lp, _ = l3dlib.bootstrap([(i["good"], i["det"] - i["good"], 0) for i in items])
            cn = sum(i["cond_n"] for i in items)
            tab.append({"variant": v, "cell": cell, "composites": len(items), "truth_wires": t,
                        "wires_hit": h, "wire_recall": round(h / t, 3) if t else 1.0,
                        "wire_recall_lo": round(lr, 3), "det_wires": d, "det_good": g,
                        "wire_precision": round(g / d, 3) if d else 1.0,
                        "wire_precision_lo": round(lp, 3),
                        "recall_given_ends": (round(sum(i["cond_hit"] for i in items) / cn, 3)
                                              if cn else ""),
                        "recall_direct": round(sum(i["direct_hit"] for i in items) /
                                               max(1, sum(i["direct"] for i in items)), 3),
                        "recall_comb": round(sum(i["comb_hit"] for i in items) /
                                             max(1, sum(i["comb"] for i in items)), 3)})
    l3dlib.write_csv(RES / f"{PREFIX}_wires.csv", list(tab[0]), tab)


if __name__ == "__main__":
    raise SystemExit(main())
