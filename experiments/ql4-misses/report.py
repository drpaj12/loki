"""Tables, validation and the plot from results/records.csv: ``python -B report.py``."""

from __future__ import annotations

import csv
import math
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import classify as cl  # noqa: E402

RES = HERE / "results"
DETS = ("D68", "D69", "D70", "D71h", "D71c")
FAMS = ("fsm", "counter", "shift", "regfile", "register")
CLASSIFIED = ("missing pattern (width)", "partition miss", "threshold miss", "structure miss")
NEAR = ("missing pattern (width)", "partition miss", "threshold miss")


def read_records() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with (RES / "records.csv").open(encoding="utf-8", newline="") as fh:
        for r in csv.DictReader(fh):
            for k in ("jaccard", "coverage", "b_dist", "b_wrong", "t_dist", "t_wrong", "b_score",
                      "t_score", "threshold", "q90"):
                r[k] = float(r[k]) if r[k] not in ("", "nan") else math.nan
            r["hit"] = int(r["hit"])
            rows.append(r)
    return rows


def write(name: str, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    with (RES / name).open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, list(rows[0]), lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


def counts(recs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Per detector x family: constructs, hits, misses by class (CAD-style counts first)."""
    out = []
    for det in DETS:
        for fam in (*FAMS, "all"):
            sub = [r for r in recs if r["detector"] == det and (fam == "all" or r["family"] == fam)]
            if not sub:
                continue
            miss = [r for r in sub if not r["hit"]]
            c = Counter(r["class"] for r in miss)
            row: dict[str, Any] = {"detector": det, "family": fam, "constructs": len(sub),
                                   "hits": len(sub) - len(miss), "misses": len(miss)}
            for k in (*cl.CLASSES, "unclassified (no provenance)", "unclassified (no signature)"):
                row[k] = c.get(k, 0)
            cls = sum(c.get(k, 0) for k in CLASSIFIED)
            near = sum(c.get(k, 0) for k in NEAR)
            row["classified"] = cls
            row["near_share"] = round(near / cls, 3) if cls else ""
            out.append(row)
    return out


def by_cell(recs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for det in DETS:
        for cell in sorted({r["cell"] for r in recs}):
            miss = [r for r in recs if r["detector"] == det and r["cell"] == cell and not r["hit"]]
            c = Counter(r["class"] for r in miss)
            tot = sum(1 for r in recs if r["detector"] == det and r["cell"] == cell)
            out.append({"detector": det, "cell": cell, "constructs": tot, "misses": len(miss),
                        **{k: c.get(k, 0) for k in (*cl.CLASSES, "unclassified (no provenance)",
                                                   "unclassified (no signature)")}})
    return out


def quant(v: list[float]) -> dict[str, Any]:
    xs = [x for x in v if not math.isnan(x)]
    if not xs:
        return {"n": 0, "p10": "", "p50": "", "p90": ""}
    return {"n": len(xs), **{f"p{int(q * 100)}": round(cl.percentile(xs, q), 4)
                             for q in (0.1, 0.5, 0.9)}}


def distances(recs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Distance distributions: hits (b), all misses (b), near misses (right block, true block t)."""
    out = []
    for det in DETS:
        for fam in FAMS:
            sub = [r for r in recs if r["detector"] == det and r["family"] == fam]
            hits = [r["b_dist"] for r in sub if r["hit"]]
            right = [r for r in sub if not r["hit"] and r["class"] in ("threshold miss",
                                                                      "structure miss")]
            miss_b = [r["b_dist"] for r in sub if not r["hit"]]
            for name, v in (("hit: compared block", hits), ("miss: compared block", miss_b),
                            ("miss, right block: true block",
                             [r["t_dist"] for r in right]),
                            ("miss, all with signature: true block",
                             [r["t_dist"] for r in sub if not r["hit"]])):
                out.append({"detector": det, "family": fam, "what": name, **quant(v)})
    return out


def boot_share(items: list[tuple[str, str]], n: int = 2000) -> tuple[float, float, float]:
    """Share of near classes among classified misses; 90% bootstrap over designs."""
    by: dict[str, list[str]] = defaultdict(list)
    for d, c in items:
        by[d].append(c)
    ds = sorted(by)
    rng = random.Random(3)

    def share(sel: list[str]) -> float:
        cs = [c for d in sel for c in by[d]]
        return sum(c in NEAR for c in cs) / len(cs) if cs else math.nan

    pt = share(ds)
    xs = sorted(s for s in (share([ds[rng.randrange(len(ds))] for _ in ds]) for _ in range(n))
                if not math.isnan(s))
    if not xs:
        return pt, math.nan, math.nan
    return pt, xs[int(0.05 * len(xs))], xs[int(0.95 * len(xs))]


def verdict(recs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for det in ("D70", "D71c"):
        items = [(r["design"], r["class"]) for r in recs
                 if r["detector"] == det and not r["hit"] and r["class"] in CLASSIFIED]
        pt, lo, hi = boot_share(items)
        struct = 1 - pt if items else math.nan
        label = "INCONCLUSIVE"
        if items and pt >= 0.6 and lo > 0.5:
            label = "NEAR-MISS HYPOTHESIS SUPPORTED"
        elif items and (1 - hi) > 0.5:
            label = "NEAR-MISS HYPOTHESIS CONTRADICTED"
        out.append({"detector": det, "classified_misses": len(items),
                    "near_share": round(pt, 3), "near_lo90": round(lo, 3),
                    "near_hi90": round(hi, 3),
                    "structure_share": round(struct, 3), "label": label})
    return out


def plot(recs: list[dict[str, Any]]) -> None:
    """Strip plot per detector: hits' compared-block distance and misses' true-block distance."""
    pan = ("D70", "D71c")
    fams = ("fsm", "counter", "shift", "regfile", "register")
    w, h, m = 330, 300, 50
    s = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{2 * w + 40}" height="{h + 90}" '
         'font-family="sans-serif" font-size="10">']
    rng = random.Random(5)
    cols = {"hit": "#1b6ca8", "right": "#e6a09a", "struct": "#c0392b"}
    for pi, det in enumerate(pan):
        x0 = 20 + pi * (w + 10)
        sub = [r for r in recs if r["detector"] == det]
        vals = [v for r in sub for v in (r["b_dist"], r["t_dist"]) if not math.isnan(v)]
        top = max(vals) if vals else 1.0
        s.append(f'<text x="{x0 + m}" y="14" font-size="12">{det}: distance to the pattern</text>')
        s.append(f'<rect x="{x0 + m}" y="20" width="{w - m - 10}" height="{h - m - 10}" '
                 'fill="none" stroke="#444"/>')
        for fi, fam in enumerate(fams):
            cx = x0 + m + (fi + 0.5) * (w - m - 10) / len(fams)
            s.append(f'<text x="{cx - 14}" y="{h - m + 14}">{fam}</text>')
            for r in (x for x in sub if x["family"] == fam):
                if r["hit"]:
                    v, c, dx = r["b_dist"], cols["hit"], -9
                elif r["class"] == "structure miss":
                    v, c, dx = r["t_dist"], cols["struct"], 9
                elif r["class"] == "threshold miss":
                    v, c, dx = r["t_dist"], cols["right"], 9
                else:
                    continue
                if math.isnan(v):
                    continue
                y = 20 + (1 - v / top) * (h - m - 10)
                s.append(f'<circle cx="{cx + dx + rng.uniform(-6, 6):.1f}" cy="{y:.1f}" r="1.6" '
                         f'fill="{c}" fill-opacity="0.5"/>')
        s.append(f'<text x="{x0 + 8}" y="26">{top:.2f}</text><text x="{x0 + 8}" '
                 f'y="{h - m + 8}">0</text>')
    ly = h + 30
    for i, (k, lab) in enumerate((("hit", "hit: compared block"),
                                  ("right", "threshold miss: true block"),
                                  ("struct", "structure miss: true block"))):
        s.append(f'<circle cx="{40 + i * 200}" cy="{ly}" r="4" fill="{cols[k]}"/>'
                 f'<text x="{50 + i * 200}" y="{ly + 4}">{lab}</text>')
    s.append("</svg>")
    (RES / "distances.svg").write_text("\n".join(s) + "\n", encoding="utf-8")


def validation(recs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Singles TP and FN per family, pooled over cells, against the tables of #68 to #71."""
    exp = HERE.parent
    src = {"D68": (exp / "graphlets/results/match_table.csv", "directed/ff"),
           "D69": (exp / "graphlets/results/part_table.csv", "directed/ff"),
           "D70": (exp / "graphlets/results/cone_table.csv", "directed/ff"),
           "D71h": (exp / "graphlets-fuzzy/results/fz_table.csv", "nn-emd:dir:ff"),
           "D71c": (exp / "graphlets-fuzzy/results/fz_table.csv", "clf-rf:dir")}
    out = []
    for det, (path, variant) in src.items():
        with path.open(encoding="utf-8", newline="") as fh:
            tab = [r for r in csv.DictReader(fh) if r["variant"] == variant]
        for fam in FAMS:
            sub = [r for r in recs if r["detector"] == det and r["set"] == "single"
                   and r["family"] == fam]
            if not sub:
                continue
            tp = sum(r["hit"] for r in sub)
            ptp = sum(int(r["TP"]) for r in tab if r["pattern"] == fam)
            pfn = sum(int(r["FN"]) for r in tab if r["pattern"] == fam)
            out.append({"detector": det, "family": fam, "constructs": len(sub), "hits": tp,
                        "published_TP": ptp, "misses": len(sub) - tp, "published_FN": pfn,
                        "match": int(tp == ptp)})
    return out


def main() -> int:
    recs = read_records()
    write("validation.csv", validation(recs))
    write("miss_classes.csv", counts(recs))
    write("miss_classes_cell.csv", by_cell(recs))
    write("distances.csv", distances(recs))
    write("verdict.csv", verdict(recs))
    plot(recs)
    for r in counts(recs):
        if r["family"] == "all":
            print(r)
    for r in verdict(recs):
        print(r)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
