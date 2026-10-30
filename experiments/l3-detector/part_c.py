"""Part C: composite detection on the built composites. ``python -B part_c.py tune|eval``.

tune: wire depth in {2,4,6,8} on TUNE composites (wiring F1, pooled over the five cells), writes
``wire_depth`` into loki/l3/catalogue/tuning.json. eval: TEST (and TUNE) tables.
Matching is at kind level (families fsm, counter, shift); see EXPERIMENT.md.
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from typing import Any

import l3dlib as lib
import part_a as pa

from loki.l3 import catalogue
from loki.l3.composite import Composite, Part, Wire, composites_of, parts_of, wires_of
from loki.l3.detect import Detector
from loki.l3.netlist import Netlist

GRID_D = (2, 4, 6, 8)


def load(split: str) -> list[dict[str, Any]]:
    rows = []
    for r in lib.read_csv(lib.RES / "composites.csv"):
        if r["split"] != split:
            continue
        truth = json.loads((lib.OUT / "composites" / r["name"] / "truth.json").read_text(
            encoding="utf-8"))
        for cell in lib.CELLS:
            ij = lib.intent_path(lib.OUT, cell, r["name"])
            nl = lib.netlist_path(lib.OUT, cell, r["name"])
            if ij.is_file() and nl.is_file():
                rows.append({"name": r["name"], "cell": cell, "truth": truth,
                             "claims": lib.load_claims(ij), "net": Netlist.read(nl)})
    return rows


def detect(det: Detector, row: dict[str, Any], depth: int
           ) -> tuple[list[Part], list[Wire], list[Composite]]:
    res = det.run(row["claims"], lib.TARGET[row["cell"]], row["net"])
    parts = parts_of(res)
    wires = wires_of(parts, row["net"], depth)
    return parts, wires, composites_of(parts, wires)


def score(row: dict[str, Any], parts: list[Part], wires: list[Wire]) -> dict[str, Any]:
    tparts = row["truth"]["parts"]
    tw = row["truth"]["wires"]
    truth_f: Counter[str] = Counter(f for p in tparts for f in p["families"])
    det_f: Counter[str] = Counter(p.family for p in parts)
    matched = sum(min(truth_f[k], det_f[k]) for k in truth_f)
    pairs = {(parts[w.src].family, parts[w.dst].family) for w in wires}
    hit = [any((a, b) in pairs for a in tparts[w["from"]]["families"]
               for b in tparts[w["to"]]["families"]) for w in tw]
    tpairs = {(a, b) for w in tw for a in tparts[w["from"]]["families"]
              for b in tparts[w["to"]]["families"]}
    good = sum(1 for w in wires if (parts[w.src].family, parts[w.dst].family) in tpairs)
    via = Counter(w["via"] for w in tw)
    via_hit = Counter(w["via"] for w, h in zip(tw, hit, strict=True) if h)
    n_t = sum(truth_f.values())
    return {"truth_parts": n_t, "det_parts": len(parts), "parts_matched": matched,
            "truth_wires": len(tw), "wires_hit": sum(hit), "det_wires": len(wires),
            "det_wires_good": good, "via_direct": via["direct"], "via_comb": via["comb"],
            "hit_direct": via_hit["direct"], "hit_comb": via_hit["comb"],
            "exact": int(matched == n_t == len(parts) and all(hit) and good == len(wires)),
            "miss": ("part" if matched < n_t else "wiring" if not all(hit) else "")}


def ratio(a: int, b: int) -> float:
    return round(a / b, 3) if b else 1.0


def tune() -> int:
    rows = load("TUNE")
    cfg = catalogue.load_tuning()
    det = Detector(catalogue.load(), cfg)
    res = []
    for d in GRID_D:
        tp = fp = fn = 0
        for r in rows:
            parts, wires, _ = detect(det, r, d)
            s = score(r, parts, wires)
            tp += s["wires_hit"]
            fn += s["truth_wires"] - s["wires_hit"]
            fp += s["det_wires"] - s["det_wires_good"]
        res.append((2 * tp / (2 * tp + fp + fn) if tp + fp + fn else 0.0, -GRID_D.index(d), d))
    cfg["wire_depth"] = max(res)[2]
    pa.TUNING.write_text(json.dumps(cfg, sort_keys=True, indent=1) + "\n", encoding="utf-8")
    print("wire_depth", cfg["wire_depth"], [(d, round(f, 3)) for f, _, d in res])
    return 0


def evaluate() -> int:
    cfg = catalogue.load_tuning()
    depth = int(cfg["wire_depth"])
    det = Detector(catalogue.load(), cfg)
    out, per = [], []
    for split in ("TEST", "TUNE"):
        rows = load(split)
        for cell in lib.CELLS:
            tot: Counter[str] = Counter()
            exact_pairs = []
            names = set()
            for r in (x for x in rows if x["cell"] == cell):
                parts, wires, _ = detect(det, r, depth)
                s = score(r, parts, wires)
                tot.update({k: v for k, v in s.items() if isinstance(v, int)})
                tot[f"miss_{s['miss']}"] += 1
                names.add(r["name"])
                pw = (s["wires_hit"], s["det_wires_good"], s["truth_wires"], s["det_wires"])
                exact_pairs.append((pw[0], pw[3] - pw[1], pw[2] - pw[0]))
                if split == "TEST":
                    per.append({"name": r["name"], "cell": cell, **s})
            if not names:
                continue
            lo_p, lo_r = lib.bootstrap(exact_pairs)
            wr = ratio(tot["wires_hit"], tot["truth_wires"])
            out.append({
                "split": split, "cell": cell, "composites": len(names),
                "part_recall": ratio(tot["parts_matched"], tot["truth_parts"]),
                "part_precision": ratio(tot["parts_matched"], tot["det_parts"]),
                "wire_recall": wr, "wire_recall_lo": round(lo_r, 3),
                "wire_precision": ratio(tot["det_wires_good"], tot["det_wires"]),
                "wire_precision_lo": round(lo_p, 3),
                "recall_direct": ratio(tot["hit_direct"], tot["via_direct"]),
                "recall_comb": ratio(tot["hit_comb"], tot["via_comb"]),
                "truth_wires": tot["truth_wires"], "wires_hit": tot["wires_hit"],
                "det_wires": tot["det_wires"], "det_wires_good": tot["det_wires_good"],
                "exact": tot["exact"], "exact_rate": ratio(tot["exact"], len(names)),
                "miss_part": tot["miss_part"], "miss_wiring": tot["miss_wiring"],
                "label": "WORKING" if wr >= 0.70 and lo_r >= 0.70 else (
                    "INCONCLUSIVE" if wr >= 0.70 else "NOT WORKING")})
    cols = ["split", "cell", "composites", "part_recall", "part_precision", "wire_recall",
            "wire_recall_lo", "wire_precision", "wire_precision_lo", "recall_direct",
            "recall_comb", "truth_wires", "wires_hit", "det_wires", "det_wires_good", "exact",
            "exact_rate", "miss_part", "miss_wiring", "label"]
    lib.write_csv(lib.RES / "partC_table.csv", cols, out)
    lib.write_csv(lib.RES / "partC_composite.csv", ["name", "cell", "truth_parts", "det_parts",
                  "parts_matched", "truth_wires", "wires_hit", "det_wires", "det_wires_good",
                  "via_direct", "via_comb", "hit_direct", "hit_comb", "exact", "miss"], per)
    print(len(out), "table rows; wire_depth", depth)
    return 0


if __name__ == "__main__":
    raise SystemExit({"tune": tune, "eval": evaluate}[sys.argv[1]]())
