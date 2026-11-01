"""The five detectors of #68 to #71 as block scorers: signature in, distances and decision out.

All use the directed signature and the flip-flop-count-known library (the configurations of the
earlier PRs, with the TUNE thresholds they report). Calibrations and models are refit from TUNE by
the
earlier code; nothing is fit on TEST.
"""

from __future__ import annotations

import json
import math
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

HERE = Path(__file__).resolve().parent
EXP = HERE.parent
for _p in (EXP / "graphlets", EXP / "graphlets-fuzzy", EXP / "l3-detector"):
    sys.path.insert(0, str(_p))
import fz_run as fz  # noqa: E402
import fzlib as fl  # noqa: E402
import l3dlib  # noqa: E402
import live  # noqa: E402
import match_eval as me  # noqa: E402
import match_run as mr  # noqa: E402
import part_eval as pe  # noqa: E402

NAN = math.nan
FAMILY = pe.FAMILY
PATS = fl.PATS


def family_patterns(fam: str, merge: bool = True) -> tuple[str, ...]:
    """Library patterns that count as family ``fam``: with ``merge`` (composite parts, as in #69 to
    #71) counter+timer and shift+lfsr; without (single designs, scored by pattern) the name."""
    if not merge:
        return (fam,)
    return tuple(p for p in (*PATS, "glue") if FAMILY.get(p, p) == fam)


@dataclass
class BlockScore:
    """One block against one detector: decision plus per-pattern distance and score."""

    accepted: str = ""
    dist: dict[str, float] = field(default_factory=dict)
    score: dict[str, float] = field(default_factory=dict)
    threshold: float = NAN

    def fam_dist(self, fam: str, merge: bool = True) -> float:
        v = [self.dist.get(p, NAN) for p in family_patterns(fam, merge)]
        v = [x for x in v if not math.isnan(x)]
        return min(v) if v else NAN

    def wrong_dist(self, fam: str, merge: bool = True) -> float:
        own = set(family_patterns(fam, merge))
        v = [d for p, d in self.dist.items() if p not in own and not math.isnan(d)]
        return min(v) if v else NAN

    def fam_score(self, fam: str, merge: bool = True) -> float:
        v = [self.score.get(p, 0.0) for p in family_patterns(fam, merge)]
        return max(v) if v else 0.0


def has_entry(cell: str, fam: str, ff: int, merge: bool = True) -> bool:
    """The all-width library holds the family at this flip-flop count in this cell."""
    pats = set(family_patterns(fam, merge))
    return any(inst.pattern in pats and eff == ff for inst, eff, _s in mr._LIB[(cell, "directed")])


def lib_best(cell: str, sig: dict[str, Any], ff: int) -> dict[str, list[Any]]:
    """Best [GDD agreement, cosine, entry] per pattern over entries with flip-flop count ``ff``."""
    q = mr.prep(sig)
    best: dict[str, list[Any]] = {}
    for inst, eff, s in mr._LIB[(cell, "directed")]:
        if eff != ff:
            continue
        g, c = mr.sim(q, s)
        cur = best.get(inst.pattern)
        if cur is None or g + c > cur[0] + cur[1]:
            best[inst.pattern] = [g, c, inst.name]
    return best


class Nearest:
    """D68, D69, D70: nearest library entry per pattern, naive Bayes posterior, TUNE threshold."""

    def __init__(self, name: str, cal: me.Calib, thr: float, ent: tuple[str, ...]) -> None:
        self.name, self.cal, self.thr, self.ent = name, cal, thr, ent

    def from_best(self, best: dict[str, list[Any]]) -> BlockScore:
        dist = {p: 1.0 - (v[0] + v[1]) / 2.0 for p, v in best.items()}
        score = {p: self.cal.post(best[p][0], best[p][1]) if p in best else 0.0 for p in self.ent}
        p = max(self.ent, key=lambda e: score[e])
        return BlockScore(p if score[p] >= self.thr else "", dist, score, self.thr)

    def from_sig(self, cell: str, sig: dict[str, Any], ff: int) -> BlockScore:
        return self.from_best(lib_best(cell, sig, ff))


class Fuzzy:
    """D71h (histogram distance + logistic layer) and D71c (random forest on directed features)."""

    def __init__(self, name: str, kind: str, thr: float) -> None:
        self.name, self.kind, self.thr = name, kind, thr
        self.lib = fl.Lib()
        self.model: Any = None
        self.cdf: dict[str, tuple[np.ndarray, np.ndarray, np.ndarray]] = {}
        for cell in fl.CELLS:
            ents = self.lib.rows[(cell, "directed")]
            self.cdf[cell] = (np.array([e["po"]["cdf"] for e in ents]),
                              np.array([e["pattern"] for e in ents]),
                              np.array([e["ff"] for e in ents]))

    def x_of(self, po: dict[str, np.ndarray], nodes: int, ff: int, cell: str,
             raw: np.ndarray | None = None) -> np.ndarray:
        if self.kind == "rf":
            return fl.feature(po, nodes, ff, cell, "dir")
        d = raw if raw is not None else self.emd(po, ff, cell)
        return fz.fill(d)

    def emd(self, po: dict[str, np.ndarray], ff: int, cell: str) -> np.ndarray:
        mat, pats, ffl = self.cdf[cell]
        return fz.emd_dists(po["cdf"], mat, pats, ff, ffl, "ff")

    def fit(self, tune: list[tuple[dict[str, np.ndarray], int, int, str, str]]) -> None:
        """tune rows: (po, nodes, ff, cell, label)."""
        xt = np.array([self.x_of(po, n, ff, c) for po, n, ff, c, _l in tune])
        yt = [t[4] for t in tune]
        if self.kind == "rf":
            xl, yl = [], []
            for cell in fl.CELLS:
                for e in self.lib.rows[(cell, "directed")]:
                    xl.append(fl.feature(e["po"], e["nodes"], max(e["ff"], 0), cell, "dir"))
                    yl.append(e["pattern"])
            xt = np.vstack([np.array(xl), xt])
            yt = [*yl, *yt]
        self.model = fz.make_model(self.kind if self.kind == "rf" else "lr")
        self.model.fit(xt, yt)

    def score(self, sig: dict[str, Any], ff: int, cell: str) -> BlockScore:
        po = fl.per_orbit(sig, fl.NORB["directed"])
        raw = self.emd(po, ff, cell) if self.kind == "emd" else None
        x = self.x_of(po, int(sig["nodes"]), ff, cell, raw)
        pr = fz.proba(self.model, x[None, :])[0]
        score = {p: float(pr[j]) for j, p in enumerate(fz.ENT)}
        if raw is not None:
            dist = {p: float(raw[j]) for j, p in enumerate(fz.ENT)}
        else:
            dist = {p: 1.0 - score[p] for p in fz.ENT}
        j = int(np.argmax(pr))
        return BlockScore(fz.ENT[j] if pr[j] >= self.thr else "", dist, score, self.thr)


def read_thr(path: Path, **where: str) -> float:
    for r in l3dlib.read_csv(path):
        if all(r[k] == v for k, v in where.items()):
            return float(r["threshold"])
    raise KeyError(where)


def calibrations(split: dict[str, str], fam: dict[str, str]) -> dict[str, Nearest]:
    """D68, D69, D70 calibrated on TUNE exactly as match_eval.py and part_eval.py do."""
    res = HERE.parent / "graphlets" / "results"
    out: dict[str, Nearest] = {}
    rows = [json.loads(x) for x in (live.OUT / "match" / "scores.jsonl").read_text(
        encoding="utf-8").splitlines()]
    cal = me.Calib()
    for r in rows:
        if r["set"] == "l3" and r["mode"] == "directed" and split[r["design"]] == "TUNE":
            for p in me.ENT:
                if p in r["ff"]:
                    cal.add(r["ff"][p][0], r["ff"][p][1], p == fam[r["design"]])
    out["D68"] = Nearest("D68", cal, read_thr(res / "match_threshold.csv", mode="directed",
                                             tag="ff"), tuple(me.ENT))
    for name, fname, thr_csv in (("D69", "part_scores.jsonl", "part_threshold.csv"),
                                 ("D70", "part_scores_bounded.jsonl", "cone_threshold.csv")):
        cal = me.Calib()
        for line in (live.OUT / "match" / fname).read_text(encoding="utf-8").splitlines():
            r = json.loads(line)
            if (r["set"] == "single" and r["mode"] == "directed" and "ff" in r
                    and split.get(r["design"]) == "TUNE" and r["design"] in fam):
                for p in pe.ENT:
                    if p in r["ff"]:
                        cal.add(r["ff"][p][0], r["ff"][p][1], p == fam[r["design"]])
        out[name] = Nearest(name, cal, read_thr(res / thr_csv, mode="directed", restrict="ff"),
                            tuple(pe.ENT))
    return out
