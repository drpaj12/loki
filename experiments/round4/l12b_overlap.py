"""RQ-L12b word-level overlap (report only): the round-3 fragment coverage of GT words.

For every GT instance g of the kinds of ``dictlib.KDICT`` with at least two cells (E_real, f2),
the fragments are the candidates of the family of g's type that lie in g at containment >= 0.8;
g is covered when the fragments' union covers >= 0.8 of g (round-3 H9b definitions). Writes
``l12b_overlap.csv`` (arm, kind, instances, covered, share) for the dictionary variants at their
selected radius and for the detector arms N and C.
"""

from __future__ import annotations

import json
from collections import defaultdict

import l12b_dict
import r3lib
import r4lib
from dictlib import KDICT, load_fg, match, signatures

from loki.score.gt import SCORED_TYPES, GtInstance, derive_instances
from loki.score.metrics import Pred

FAMILIES: dict[str, frozenset[str]] = {
    "storage": frozenset({"$dff", "$dffe", "$adff", "$adffe", "$sdff", "$sdffe", "$sdffce",
                          "$dffsr", "$dffsre", "$aldff", "$aldffe", "$dlatch", "$adlatch",
                          "$dlatchsr", "register", "counter", "fsm"}),
    "mux": frozenset({"$mux", "$pmux", "mux_tree"}),
    "compare": frozenset({"$eq", "$ne", "$lt", "$le", "$gt", "$ge"}),
    "arith": frozenset({"$add", "$sub", "$mul", "counter"}),
}
KIND_FAMILY = {"ff_en": "storage", "ff_srst": "storage", "register": "storage",
               "counter": "storage", "fsm": "storage", "mux_bit": "mux", "mux": "mux",
               "mux_tree": "mux", "eq_const": "compare", "comparator": "compare",
               "adder": "arith", "subtractor": "arith", "adder_cin": "arith"}
FRAG = 0.8


def covered(g: GtInstance, preds: list[Pred]) -> bool:
    fams = {f for f, t in FAMILIES.items() if g.type in t}
    cover: set[str] = set()
    for p in preds:
        if KIND_FAMILY.get(p.kind) in fams and p.cells:
            if len(p.cells & g.footprint) / len(p.cells) >= FRAG:
                cover |= p.cells & g.footprint
    return len(cover) / len(g.footprint) >= FRAG


def tally(arm: str, items: list[tuple[list[Pred], list[GtInstance]]],
          acc: dict[tuple[str, str], list[int]]) -> None:
    for preds, gts in items:
        for g in gts:
            if len(g.footprint) < 2:
                continue
            for k in KDICT:
                if g.type in SCORED_TYPES[k]:
                    row = acc[(arm, k)]
                    row[0] += 1
                    row[1] += int(covered(g, preds))


def main() -> int:
    sets = r4lib.eval_sets("f2")
    real = sets["micro"] + sets["vetest"]
    acc: dict[tuple[str, str], list[int]] = defaultdict(lambda: [0, 0])
    radius = {(r["variant"]): (int(r["radius"]), bool(int(r["clock_union"])))
              for r in r4lib.read_csv(r4lib.OUT / "l12b_radius.csv")
              if r["floor"] == "f2" and r["selected"] == "1"}
    gts: dict[str, list[GtInstance]] = {}
    for ds, d in real:
        words = json.loads((ds / d / "f2" / "words.json").read_text(encoding="utf-8"))
        gts[d] = derive_instances(words)
    for var, (kmax, _cu) in l12b_dict.VARIANTS.items():
        dic = l12b_dict.mine("f2", kmax)
        r, cu = radius[var]
        items = []
        for ds, d in real:
            sg = signatures(load_fg(ds / d / "f2" / "graph.json"), kmax)
            items.append((match(sg, dic, r, cu), gts[d]))
        tally(f"dict-{var}", items, acc)
    for arm, names in (("det-N", ("M2N", "V2N")), ("det-C", ("M2C", "V2C"))):
        items = []
        for ds, d in real:
            rs = r3lib.SETS[names[0] if ds == r4lib.MICRO else names[1]]
            if (r3lib.run_dir(rs, d) / "overlay.json").is_file():
                items.append((r3lib.counted_preds(rs, d), gts[d]))
        tally(arm, items, acc)
    rows = [[arm, k, n, c, round(c / n, 6) if n else ""]
            for (arm, k), (n, c) in sorted(acc.items())]
    r4lib.write_csv(r4lib.OUT / "l12b_overlap.csv",
                    ["arm", "kind", "instances", "covered", "share"], rows)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
