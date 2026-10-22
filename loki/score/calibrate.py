"""Calibration of the Bayesian tables from L0 train designs (L1 spec 6.3, 6.7 items 1 and 5)."""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, replace
from pathlib import Path

from loki.re import bayes
from loki.re.bayes import (
    CALIB_FOLDS,
    DEFAULTS,
    NODE_MIN_COUNT,
    SCHEMA,
    STRUCT_CAP,
    WEIGHT_GRID,
    Calib,
    family_of,
    logit,
    sigmoid,
    wl_npn_bin,
)
from loki.re.loop import ReOptions, run_re
from loki.re.overlay import Hypothesis
from loki.re.structural import StructFeatures, build_features
from loki.schemas import dump_json
from loki.score.gt import SCORED_TYPES, GtInstance, load_gt
from loki.score.metrics import Pred, label_preds, reliability

SWEEPS = 3
_EPS = 1e-12

Row = tuple[float, dict[str, float], float, bool]


def _r(x: float) -> float:
    return round(x, 6)


# -- node tables (spec 6.7 item 1) -----------------------------------------------------------
@dataclass
class NodeCounts:
    """Per kind: ``keys[key] = [pos, neg]`` over LUT cells and ``totals = [POS, NEG]``."""

    keys: dict[str, dict[str, list[int]]] = field(default_factory=dict)
    totals: dict[str, list[int]] = field(default_factory=dict)

    def merge(self, other: NodeCounts) -> None:
        for kind, table in other.keys.items():
            mine = self.keys.setdefault(kind, {})
            for key, (pos, neg) in table.items():
                cell = mine.setdefault(key, [0, 0])
                cell[0] += pos
                cell[1] += neg
        for kind, (pos, neg) in other.totals.items():
            tot = self.totals.setdefault(kind, [0, 0])
            tot[0] += pos
            tot[1] += neg


def fold_of(design: str) -> int:
    """First byte of ``sha256(design)`` mod ``CALIB_FOLDS`` (spec 6.7 item 5)."""
    return hashlib.sha256(design.encode()).digest()[0] % CALIB_FOLDS


def node_tally(
    sf: StructFeatures, gt: Sequence[GtInstance], kinds: Sequence[str]
) -> NodeCounts:
    """Per kind, count the level-0 LUT cells inside (``pos``) and outside (``neg``) the footprint
    of a ground-truth instance of the kind's scored types, under each calibration key."""
    out = NodeCounts()
    luts = sorted(c for c, i in sf.index.items() if sf.fg.kind[i] == "lut")
    for kind in sorted(set(kinds) & set(SCORED_TYPES)):
        types = SCORED_TYPES[kind]
        foot: set[str] = set()
        for g in gt:
            if g.type in types:
                foot |= g.footprint
        table = out.keys.setdefault(kind, {})
        tot = out.totals.setdefault(kind, [0, 0])
        for c in luts:
            side = 0 if sf.fg.node_ids[sf.index[c]] in foot else 1
            tot[side] += 1
            for key in sf.cell_keys(c):
                table.setdefault(key, [0, 0])[side] += 1
    return out


def node_table(counts: NodeCounts) -> dict[str, dict[str, float]]:
    """``node_llr[kind][key] = ln(((pos + 1) / (POS + B_d)) / ((neg + 1) / (NEG + B_d)))`` with
    ``B_d`` the number of keys seen at the round ``d`` of the key; keys with fewer than
    ``NODE_MIN_COUNT`` cells are dropped, and kinds left empty are absent."""
    out: dict[str, dict[str, float]] = {}
    for kind, table in sorted(counts.keys.items()):
        pos_total, neg_total = counts.totals.get(kind, [0, 0])
        seen: dict[str, int] = {}
        for key in table:
            seen[key.split(":", 1)[0]] = seen.get(key.split(":", 1)[0], 0) + 1
        rows: dict[str, float] = {}
        for key, (pos, neg) in sorted(table.items()):
            if pos + neg < NODE_MIN_COUNT:
                continue
            b = seen[key.split(":", 1)[0]]
            rows[key] = math.log(((pos + 1) / (pos_total + b)) / ((neg + 1) / (neg_total + b)))
        if rows:
            out[kind] = rows
    return out


def node_calib(table: Mapping[str, Mapping[str, float]]) -> Calib:
    return Calib("", {}, {}, "", {}, {k: dict(v) for k, v in table.items()})


def wl_bin(
    table: Mapping[str, Mapping[str, float]],
    kind: str,
    cells: frozenset[str],
    keys_of: Mapping[str, tuple[str, ...]],
) -> str | None:
    """The ``wl_npn`` bin of a hypothesis (the rule of ``_Run.node_features``); ``None`` when the
    table has no entry for ``kind`` (the loop then sets no feature either)."""
    if kind not in table:
        return None
    calib = node_calib(table)
    scores = [calib.node_score(kind, keys_of[c]) for c in sorted(cells) if c in keys_of]
    known = [s for s in scores if s is not None]
    return wl_npn_bin(sum(known) / len(known) if known else None)


# -- hypothesis tables (spec 6.3) ------------------------------------------------------------
@dataclass
class Counts:
    """``priors[<detector>/<kind>] = [n, tp]``, ``bins[<kind>/<feature>][bin] = [pos, neg]`` and
    ``totals[kind] = [POS, NEG]`` (true and false candidates of the kind)."""

    priors: dict[str, list[int]] = field(default_factory=dict)
    bins: dict[str, dict[str, list[int]]] = field(default_factory=dict)
    totals: dict[str, list[int]] = field(default_factory=dict)

    def merge(self, other: Counts) -> None:
        for key, (n, tp) in other.priors.items():
            mine = self.priors.setdefault(key, [0, 0])
            mine[0] += n
            mine[1] += tp
        for key, table in other.bins.items():
            dest = self.bins.setdefault(key, {})
            for b, (pos, neg) in table.items():
                cell = dest.setdefault(b, [0, 0])
                cell[0] += pos
                cell[1] += neg
        for kind, (pos, neg) in other.totals.items():
            tot = self.totals.setdefault(kind, [0, 0])
            tot[0] += pos
            tot[1] += neg


def tally(hyps: Sequence[Pred], gt: Sequence[GtInstance]) -> Counts:
    """Count candidates of the scored kinds, true when they match a ground truth (spec 12.2;
    ``label_preds``), per prior key, per feature bin and per kind."""
    scored = [h for h in hyps if h.kind in SCORED_TYPES]
    labels = label_preds(scored, gt)
    out = Counts()
    for h in scored:
        hit = labels[h.id]
        prior = out.priors.setdefault(f"{h.detector}/{h.kind}", [0, 0])
        prior[0] += 1
        prior[1] += 1 if hit else 0
        out.totals.setdefault(h.kind, [0, 0])[0 if hit else 1] += 1
        for feat, b in sorted(h.features.items()):
            cell = out.bins.setdefault(f"{h.kind}/{feat}", {}).setdefault(b, [0, 0])
            cell[0 if hit else 1] += 1
    return out


def to_calib(counts: Counts) -> dict[str, object]:
    """The ``priors`` and ``llr`` tables of the calibration file (Laplace forms, spec 6.3)."""
    priors: dict[str, object] = {}
    for key, (n, tp) in sorted(counts.priors.items()):
        priors[key] = {"n": n, "tp": tp, "log_odds": _r(logit((tp + 1) / (n + 2)))}
    llr: dict[str, object] = {}
    for key, table in sorted(counts.bins.items()):
        pos_total, neg_total = counts.totals[key.split("/", 1)[0]]
        b = len(table)
        llr[key] = {
            name: {
                "pos": pos, "neg": neg,
                "llr": _r(math.log(((pos + 1) / (pos_total + b)) / ((neg + 1) / (neg_total + b)))),
            }
            for name, (pos, neg) in sorted(table.items())
        }
    return {"priors": priors, "llr": llr}


# -- family weights (spec 6.7 item 5) --------------------------------------------------------
def _log_lik(rows: Sequence[Row], w: Mapping[str, float]) -> float:
    total = 0.0
    for prior, fams, child, label in rows:
        feat = sum(w.get(f, 1.0) * s for f, s in fams.items()) + child
        z = prior + max(-STRUCT_CAP, min(STRUCT_CAP, feat))
        total += -math.log1p(math.exp(-z)) if label else -math.log1p(math.exp(z))
    return total


def fit_weights(rows: Sequence[Row]) -> dict[str, float]:
    """Coordinate ascent over ``WEIGHT_GRID`` (three sweeps, families in name order, ties to the
    larger weight) on the Bernoulli log-likelihood of the labels under ``sigmoid(prior +
    capped(sum_f w_f s_f + child))``. ``rows`` are ``(prior, family sums, child sum, label)``."""
    families = sorted({f for _, fams, _, _ in rows for f in fams})
    w = dict.fromkeys(families, 1.0)
    for _ in range(SWEEPS):
        for fam in families:
            best_w, best = w[fam], -math.inf
            for cand in WEIGHT_GRID:
                ll = _log_lik(rows, {**w, fam: cand})
                if ll >= best - _EPS:
                    best_w, best = cand, max(best, ll)
            w[fam] = best_w
    return {f: _r(v) for f, v in w.items()}


# -- the fit over designs ---------------------------------------------------------------------
@dataclass
class DesignData:
    """One train design after ``run_re`` with ``DEFAULTS``: hypotheses, ground truth, node
    tallies, the calibration keys of its LUT cells and each hypothesis's child sum."""

    design: str
    preds: list[Pred]
    gt: list[GtInstance]
    nodes: NodeCounts
    keys: dict[str, tuple[str, ...]]
    child: dict[str, float]


def _augment(d: DesignData, table: Mapping[str, Mapping[str, float]]) -> list[Pred]:
    out: list[Pred] = []
    for p in d.preds:
        b = wl_bin(table, p.kind, p.cells, d.keys) if p.kind in SCORED_TYPES else None
        out.append(p if b is None else replace(p, features={**p.features, "wl_npn": b}))
    return out


def _rows(
    d: DesignData, preds: Sequence[Pred], tables: Mapping[str, object]
) -> list[Row]:
    priors = tables["priors"]
    llr = tables["llr"]
    assert isinstance(priors, dict) and isinstance(llr, dict)
    labels = label_preds([p for p in preds if p.kind in SCORED_TYPES], d.gt)
    rows: list[Row] = []
    for p in preds:
        if p.kind not in SCORED_TYPES:
            continue
        prior = priors.get(f"{p.detector}/{p.kind}", {}).get("log_odds", 0.0)
        fams: dict[str, float] = {}
        for feat, b in sorted(p.features.items()):
            val = llr.get(f"{p.kind}/{feat}", {}).get(b, {}).get("llr", 0.0)
            fam = family_of(feat)
            fams[fam] = fams.get(fam, 0.0) + val
        rows.append((float(prior), fams, d.child.get(p.id, 0.0), labels[p.id]))
    return rows


def _node_file(counts: NodeCounts, table: Mapping[str, Mapping[str, float]]) -> dict[str, object]:
    return {
        kind: {key: {"pos": counts.keys[kind][key][0], "neg": counts.keys[kind][key][1],
                     "llr": _r(v)} for key, v in sorted(rows.items())}
        for kind, rows in sorted(table.items())
    }


def _with_defaults(llr: dict[str, object]) -> dict[str, object]:
    """Add the default LLRs of kinds that cannot be calibrated (not scored against L0 types), so
    a calibration file does not silence them."""
    for key, bins in DEFAULTS.llr.items():
        if key.split("/", 1)[0] not in SCORED_TYPES and key not in llr:
            llr[key] = {b: {"pos": 0, "neg": 0, "llr": v} for b, v in sorted(bins.items())}
    return dict(sorted(llr.items()))


def fit(
    designs: Sequence[DesignData], floor: str, dataset_sha: str, split: str
) -> dict[str, object]:
    """The calibration file object (spec 6.3) from the runs of the train designs, with the
    2-fold cross-fitting of spec 6.7 item 5.

    A hypothesis's ``wl_npn`` bin comes from the node table of the other fold, in the rows and in
    the final bin tables alike (the tables then describe the bins the test designs will see)."""
    ds = sorted(designs, key=lambda d: d.design)
    node_fold = []
    for f in range(CALIB_FOLDS):
        other_nodes = NodeCounts()
        for d in ds:
            if fold_of(d.design) != f:
                other_nodes.merge(d.nodes)
        node_fold.append(node_table(other_nodes))
    aug = {d.design: _augment(d, node_fold[fold_of(d.design)]) for d in ds}
    per = {d.design: tally(aug[d.design], d.gt) for d in ds}
    rows: list[Row] = []
    for f in range(CALIB_FOLDS):
        other = Counts()
        for d in ds:
            if fold_of(d.design) != f:
                other.merge(per[d.design])
        fold_tables = to_calib(other)
        for d in ds:
            if fold_of(d.design) == f:
                rows += _rows(d, aug[d.design], fold_tables)
    weights = fit_weights(rows)
    points: list[tuple[float, bool]] = []
    for prior, fams, child, label in rows:
        feat = sum(weights.get(f, 1.0) * s for f, s in fams.items()) + child
        points.append((sigmoid(prior + max(-STRUCT_CAP, min(STRUCT_CAP, feat))), label))
    final = Counts()
    for d in ds:
        final.merge(per[d.design])
    nodes_all = NodeCounts()
    for d in ds:
        nodes_all.merge(d.nodes)
    node_llr = node_table(nodes_all)
    tables = to_calib(final)
    llr = tables["llr"]
    assert isinstance(llr, dict)
    return {
        "schema": SCHEMA, "floor": floor, "dataset": dataset_sha, "split": split,
        "designs": [d.design for d in ds],
        "priors": tables["priors"], "llr": _with_defaults(llr),
        "node_llr": _node_file(nodes_all, node_llr), "weights": weights,
        "reliability": reliability(points),
    }


# -- running the flow -------------------------------------------------------------------------
def _child_sum(h: Hypothesis) -> float:
    pos = sum(e.llr for e in h.evidence if e.source == "child" and e.llr > 0)
    neg = sum(e.llr for e in h.evidence if e.source == "child" and e.llr <= 0)
    return min(pos, bayes.CHILD_CAP) + neg


def design_data(design: str, floor_dir: Path, opts: ReOptions) -> DesignData:
    """Run ``loki re`` with ``DEFAULTS`` on one design and collect what the fit needs."""
    res = run_re(opts)
    gt = load_gt(floor_dir)[0]
    preds: list[Pred] = []
    child: dict[str, float] = {}
    for h in res.overlay.all():
        op = h.claim.op if h.claim is not None else ""
        preds.append(Pred(
            h.id, h.kind, frozenset(res.graph.label(c) for c in h.cells), h.p_comp, h.status,
            h.detector, op, dict(h.features)))
        child[h.id] = _child_sum(h)
    sf = build_features(res.graph)
    keys = {
        res.graph.label(c): sf.cell_keys(c)
        for c, i in sf.index.items() if sf.fg.kind[i] == "lut"
    }
    return DesignData(design, preds, gt, node_tally(sf, gt, sorted(SCORED_TYPES)), keys, child)


def calibrate(
    dataset: Path, floor: str, split: str, odin3_root: Path | None, seed: int
) -> dict[str, object]:
    """Run the flow with ``DEFAULTS`` on every ``ok`` design of ``split`` for ``floor`` and fit the
    calibration file object (spec 6.3). Only designs of the requested split run."""
    manifest_path = dataset / "manifest.json"
    raw = manifest_path.read_bytes()
    manifest = json.loads(raw)
    sha = hashlib.sha256(raw).hexdigest()
    data: list[DesignData] = []
    for entry in sorted(manifest["designs"], key=lambda e: e["design"]):
        info = entry["floors"].get(floor)
        if entry["split"] != split or info is None or info["status"] != "ok":
            continue
        floor_dir = dataset / entry["design"] / floor
        opts = ReOptions(
            netlist=floor_dir / "netlist.blif", floor=floor, odin3_root=odin3_root, techlib=None,
            calib=None, seed=seed, max_rounds=bayes.MAX_ROUNDS, timeout=30, time_budget=3600,
            detectors=None, commit=True, keep_levels=None, features="all",
        )
        data.append(design_data(entry["design"], floor_dir, opts))
    return fit(data, floor, sha, split)


def write_calib(obj: Mapping[str, object], path: Path) -> None:
    """Write the calibration file (deterministic)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dump_json(obj), encoding="utf-8")
