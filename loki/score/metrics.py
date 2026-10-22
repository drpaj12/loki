"""Metrics of a run against L0 ground truth, aggregation and ablation (L1 spec 12.2 to 12.5)."""

from __future__ import annotations

import json
import math
from collections import Counter
from collections.abc import Container, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from loki.schemas import SCHEMA
from loki.score.gt import (
    COMPARE,
    SCORED_TYPES,
    GtBus,
    GtInstance,
    NetMap,
    load_gt,
    load_netmap,
)
from loki.score.match import greedy_from_pairs, pairs_above

NA = "n/a"
AP_THRESHOLDS = tuple(round(0.1 * i, 1) for i in range(1, 10))
MATCH_J = 0.5
LIVE = ("open", "confirmed", "committed")
ROLE_CLASSES = ("control", "datapath")
CLASSES = ("fsm", "count", "lfsr")


def _r(x: float) -> float:
    return round(x, 6)


@dataclass(frozen=True)
class Pred:
    """One L1 hypothesis with cells named as in L0 (the ``.cname`` labels)."""

    id: str
    kind: str
    cells: frozenset[str]
    p: float
    status: str
    detector: str = ""
    op: str = ""
    features: Mapping[str, str] = field(default_factory=dict)

    @property
    def committed(self) -> bool:
        return self.status == "committed"

    def counted(self, p_min: float) -> bool:
        """Spec 12.2: committed, or live with ``p_comp >= p_min``."""
        return self.committed or (self.status in LIVE and self.p >= p_min)

    def types(self) -> frozenset[str]:
        """The L0 types this hypothesis is scored against (a comparator: its own operation)."""
        scored = SCORED_TYPES.get(self.kind, frozenset())
        if self.kind == "comparator" and f"${self.op}" in COMPARE:
            return frozenset({f"${self.op}"})
        return scored


@dataclass(frozen=True)
class PredBus:
    """An L1 bus: ``members`` are the L0 nodes driving the slice outputs in slice order, ``alt``
    the same with port pseudo-nodes where a slice net is a port net."""

    id: str
    p: float
    status: str
    order_source: str
    members: tuple[str, ...]
    alt: tuple[str, ...] = ()

    def counted(self, p_min: float) -> bool:
        return self.status == "committed" or (self.status in LIVE and self.p >= p_min)


# -- constructs -------------------------------------------------------------------------------
def _construct_pairs(
    preds: Sequence[Pred], gts: Sequence[GtInstance]
) -> list[tuple[str, str, float]]:
    groups: dict[frozenset[str], list[Pred]] = {}
    for p in preds:
        groups.setdefault(p.types(), []).append(p)
    out: list[tuple[str, str, float]] = []
    for types, group in groups.items():
        sub = [(g.gid, g.footprint) for g in gts if g.type in types]
        out += pairs_above([(p.id, p.cells) for p in group], sub, MATCH_J)
    return out


def construct_matches(
    preds: Sequence[Pred], gts: Sequence[GtInstance]
) -> list[tuple[str, str, float]]:
    """One-to-one matches of spec 12.2 between ``preds`` (of one kind) and ``gts``."""
    return greedy_from_pairs(_construct_pairs(preds, gts))


def ap_from_curve(curve: Sequence[Sequence[float]], n_gt: int) -> float | str:
    """Average precision over the operating points ``[t, counted, matched]``: the precision at
    each threshold weighted by the recall it adds, from the highest threshold down."""
    if n_gt == 0:
        return NA
    total, best = 0.0, 0.0
    for _t, counted, matched in sorted(curve, key=lambda c: -c[0]):
        if counted <= 0:
            continue
        rec = matched / n_gt
        if rec > best:
            total += (rec - best) * (matched / counted)
            best = rec
    return _r(total)


def _f1(prec: float | str, rec: float | str) -> float:
    if isinstance(prec, str) or isinstance(rec, str) or prec + rec == 0:
        return 0.0
    return 2 * prec * rec / (prec + rec)


def construct_curves(
    preds: Sequence[Pred], gts: Sequence[GtInstance]
) -> dict[str, list[list[float]]]:
    """Per kind with predictions or ground truth: ``[t, counted, matched]`` at each AP threshold."""
    out: dict[str, list[list[float]]] = {}
    for kind, types in sorted(SCORED_TYPES.items()):
        kp = [p for p in preds if p.kind == kind]
        kg = [g for g in gts if g.type in types]
        if not kp and not kg:
            continue
        rows: list[list[float]] = []
        for t in AP_THRESHOLDS:
            sel = [p for p in kp if p.counted(t)]
            rows.append([t, float(len(sel)), float(len(construct_matches(sel, kg)))])
        out[kind] = rows
    return out


def construct_scores(
    preds: Sequence[Pred], gts: Sequence[GtInstance], score_p: float
) -> dict[str, dict[str, float | str]]:
    """Per kind: precision, recall, f1, ap (``"n/a"`` for a kind without ground truth) and the
    counts ``counted``, ``matched``, ``gt`` they come from."""
    out: dict[str, dict[str, float | str]] = {}
    curves = construct_curves(preds, gts)
    for kind, curve in curves.items():
        types = SCORED_TYPES[kind]
        kg = [g for g in gts if g.type in types]
        sel = [p for p in preds if p.kind == kind and p.counted(score_p)]
        matched = len(construct_matches(sel, kg))
        row: dict[str, float | str] = {
            "counted": len(sel), "matched": matched, "gt": len(kg),
        }
        if not kg:
            row.update(precision=NA, recall=NA, f1=NA, ap=NA)
        else:
            prec: float | str = matched / len(sel) if sel else NA
            rec = matched / len(kg)
            row.update(
                precision=prec if isinstance(prec, str) else _r(prec), recall=_r(rec),
                f1=_r(_f1(prec, rec)), ap=ap_from_curve(curve, len(kg)),
            )
        out[kind] = row
    return out


def label_preds(preds: Sequence[Pred], gts: Sequence[GtInstance]) -> dict[str, bool]:
    """True per prediction id when some ground truth of its scored types has Jaccard >= 0.5.

    Used for calibration and reliability, where a candidate is judged on its own (not one-to-one,
    so a duplicate of a true construct is true as well)."""
    hit = {pid for pid, _, _ in _construct_pairs([p for p in preds if p.types()], gts)}
    return {p.id: p.id in hit for p in preds}


def reliability_points(
    preds: Sequence[Pred], gts: Sequence[GtInstance]
) -> dict[str, list[list[float]]]:
    """Per scored kind: ``[p_comp, 1 or 0]`` of every live hypothesis (label: ``label_preds``)."""
    live = [p for p in preds if p.status in LIVE and p.kind in SCORED_TYPES]
    labels = label_preds(live, gts)
    out: dict[str, list[list[float]]] = {}
    for p in live:
        out.setdefault(p.kind, []).append([_r(p.p), 1.0 if labels[p.id] else 0.0])
    return out


def reliability(points: Sequence[tuple[float, bool]], bins: int = 10) -> dict[str, object]:
    """Reliability curve over equal-width bins of ``p`` (non-empty bins only) and the expected
    calibration error ``ece = sum_b n_b / N * |mean_p_b - rate_b|``."""
    cells: dict[int, list[tuple[float, bool]]] = {}
    for p, label in points:
        cells.setdefault(min(int(p * bins), bins - 1), []).append((p, label))
    out: list[dict[str, object]] = []
    ece = 0.0
    for b in sorted(cells):
        rows = cells[b]
        mean_p = sum(p for p, _ in rows) / len(rows)
        rate = sum(1 for _, y in rows if y) / len(rows)
        ece += len(rows) / len(points) * abs(mean_p - rate)
        out.append({"lo": _r(b / bins), "hi": _r((b + 1) / bins), "mean_p": _r(mean_p),
                    "rate": _r(rate), "n": len(rows)})
    return {"bins": out, "ece": _r(ece) if points else NA}


# -- buses and roles --------------------------------------------------------------------------
def _bus_pairs(
    preds: Sequence[PredBus], gts: Sequence[GtBus]
) -> list[tuple[str, str, float, bool]]:
    """Candidate (bus, gt, Jaccard, use-alt) with the better of the two member views."""
    g_sets = [(g.gid, g.members) for g in gts]
    best: dict[tuple[str, str], tuple[float, bool]] = {}
    for alt in (False, True):
        views = [(p.id, frozenset(p.alt if alt else p.members)) for p in preds]
        if alt:
            views = [(pid, m) for (pid, m), p in zip(views, preds, strict=True) if p.alt]
        for pid, gid, j in pairs_above(views, g_sets, MATCH_J):
            if (pid, gid) not in best or j > best[(pid, gid)][0]:
                best[(pid, gid)] = (j, alt)
    return [(pid, gid, j, alt) for (pid, gid), (j, alt) in best.items()]


def bus_scores(
    preds: Sequence[PredBus], gts: Sequence[GtBus], score_p: float
) -> dict[str, object]:
    """Bus precision, recall and bit-order accuracy per ``order_source`` (spec 12.3)."""
    sel = [p for p in preds if p.counted(score_p)]
    pairs = _bus_pairs(sel, gts)
    alt_of = {(pid, gid): alt for pid, gid, _, alt in pairs}
    matches = greedy_from_pairs([(pid, gid, j) for pid, gid, j, _ in pairs])
    by_id = {p.id: p for p in sel}
    by_gid = {g.gid: g for g in gts}
    shared: Counter[str] = Counter()
    exact: Counter[str] = Counter()
    rev: Counter[str] = Counter()
    for pid, gid, _ in matches:
        p, g = by_id[pid], by_gid[gid]
        rep = p.alt if alt_of[(pid, gid)] else p.members
        bits = dict(g.bits)
        pos = [(i, bits[n]) for i, n in enumerate(rep) if n in bits]
        fwd = sum(1 for i, b in pos if i == b)
        bwd = sum(1 for i, b in pos if len(rep) - 1 - i == b)
        shared[p.order_source] += len(pos)
        exact[p.order_source] += fwd
        rev[p.order_source] += max(fwd, bwd)
    out: dict[str, object] = {"counted": len(sel), "matched": len(matches), "gt": len(gts)}
    if not gts:
        out.update(precision=NA, recall=NA, f1=NA)
    else:
        prec: float | str = len(matches) / len(sel) if sel else NA
        rec = len(matches) / len(gts)
        out.update(precision=prec if isinstance(prec, str) else _r(prec), recall=_r(rec),
                   f1=_r(_f1(prec, rec)))
    out["order_n"] = dict(sorted(shared.items()))
    out["order_exact_n"] = dict(sorted(exact.items()))
    out["order_reversal_n"] = dict(sorted(rev.items()))
    out["order_exact"] = {s: _r(exact[s] / n) for s, n in sorted(shared.items()) if n}
    out["order_up_to_reversal"] = {s: _r(rev[s] / n) for s, n in sorted(shared.items()) if n}
    return out


def role_scores(
    pred_roles: Mapping[str, str], gt_roles: Mapping[str, str], cells: Container[str]
) -> dict[str, object]:
    """Precision, recall and F1 of ``control`` and ``datapath`` over the logic cells whose L0
    role is one of the two; ``mixed`` predictions are listed by L0 role (spec 12.3)."""
    ev = [n for n in sorted(gt_roles) if n in cells and gt_roles[n] in ROLE_CLASSES]
    out: dict[str, object] = {}
    for role in ROLE_CLASSES:
        gt_n = sum(1 for n in ev if gt_roles[n] == role)
        pred_n = sum(1 for n in ev if pred_roles.get(n) == role)
        tp = sum(1 for n in ev if gt_roles[n] == role and pred_roles.get(n) == role)
        prec: float | str = tp / pred_n if pred_n else NA
        rec: float | str = tp / gt_n if gt_n else NA
        out[role] = {
            "precision": prec if isinstance(prec, str) else _r(prec),
            "recall": rec if isinstance(rec, str) else _r(rec),
            "f1": _r(_f1(prec, rec)) if gt_n else NA, "tp": tp, "pred": pred_n, "gt": gt_n,
        }
    out["mixed"] = {r: sum(1 for n in ev if gt_roles[n] == r and pred_roles.get(n) == "mixed")
                    for r in ROLE_CLASSES}
    return out


# -- hierarchy --------------------------------------------------------------------------------
def _best_f(a: Sequence[frozenset[str]], b: Sequence[frozenset[str]]) -> list[float]:
    """For each set of ``a``, the best ``F = 2|a & b| / (|a| + |b|)`` over the sets of ``b``."""
    index: dict[str, list[int]] = {}
    for j, s in enumerate(b):
        for c in s:
            index.setdefault(c, []).append(j)
    out: list[float] = []
    for s in a:
        hits: Counter[int] = Counter()
        for c in s:
            hits.update(index.get(c, ()))
        out.append(max((2 * n / (len(s) + len(b[j])) for j, n in hits.items()), default=0.0))
    return out


def _weighted(sizes: Sequence[int], best: Sequence[float]) -> float | str:
    total = sum(sizes)
    return sum(s * f for s, f in zip(sizes, best, strict=True)) / total if total else NA


def gt_clusters(gt_paths: Mapping[str, str]) -> list[frozenset[str]]:
    """The non-root clusters of the ``module_path`` tree: one per path prefix of length >= 2."""
    members: dict[str, set[str]] = {}
    for node, path in gt_paths.items():
        parts = path.split("/")
        for k in range(2, len(parts) + 1):
            members.setdefault("/".join(parts[:k]), set()).add(node)
    return [frozenset(members[k]) for k in sorted(members)]


def _entropy(counts: Sequence[int]) -> float:
    n = sum(counts)
    return -sum(c / n * math.log(c / n) for c in counts if c)


def nmi(a: Mapping[str, str], b: Mapping[str, str]) -> float:
    """Normalised mutual information (arithmetic-mean normalisation) of two labelings of the same
    items; 1.0 when both are one class."""
    items = sorted(a)
    ca: Counter[str] = Counter(a[i] for i in items)
    cb: Counter[str] = Counter(b[i] for i in items)
    joint: Counter[tuple[str, str]] = Counter((a[i], b[i]) for i in items)
    n = len(items)
    ha, hb = _entropy(list(ca.values())), _entropy(list(cb.values()))
    if ha + hb == 0:
        return 1.0
    mi = sum(c / n * math.log(c * n / (ca[x] * cb[y])) for (x, y), c in joint.items())
    return 2 * mi / (ha + hb)


def _leaf(cells: Sequence[str], clusters: Sequence[frozenset[str]]) -> dict[str, str]:
    """Each cell's deepest (smallest) cluster, as a label; ``""`` when in none."""
    order = sorted(range(len(clusters)), key=lambda i: (len(clusters[i]), sorted(clusters[i])))
    out = {c: "" for c in cells}
    for i in reversed(order):
        for c in clusters[i]:
            if c in out:
                out[c] = str(i)
    return out


def hierarchy_scores(
    gt_paths: Mapping[str, str],
    l1_clusters: Sequence[frozenset[str]],
    gt_constructs: Sequence[frozenset[str]],
) -> dict[str, float | str]:
    """``HS_gt``, ``HS_l1``, ``hier_f`` and ``nmi_leaf`` of spec 12.4.

    A flat L0 hierarchy gives ``HS_gt`` and ``hier_f`` of ``"n/a"``; no L1 piece gives ``HS_l1``
    ``"n/a"`` and, over a non-flat L0 hierarchy, ``hier_f`` 0.0."""
    cgt = gt_clusters(gt_paths)
    cl1 = [c for c in l1_clusters if c]
    hs_gt: float | str = NA
    if cgt:
        hs_gt = NA if not cl1 else _weighted([len(g) for g in cgt], _best_f(cgt, cl1))
        if not cl1:
            hs_gt = 0.0
    ref = [*cgt, *[c for c in gt_constructs if c]]
    hs_l1: float | str = _weighted([len(h) for h in cl1], _best_f(cl1, ref)) if cl1 else NA
    if isinstance(hs_gt, str) or isinstance(hs_l1, str):
        hier_f: float | str = 0.0 if (cgt and not cl1) else NA
    else:
        hier_f = 2 * hs_gt * hs_l1 / (hs_gt + hs_l1) if hs_gt + hs_l1 else 0.0
    cells = sorted(gt_paths)
    leaf_gt = dict(gt_paths)
    score = nmi(leaf_gt, _leaf(cells, cl1)) if cells else NA
    out: dict[str, float | str] = {
        "HS_gt": hs_gt if isinstance(hs_gt, str) else _r(hs_gt),
        "HS_l1": hs_l1 if isinstance(hs_l1, str) else _r(hs_l1),
        "hier_f": hier_f if isinstance(hier_f, str) else _r(hier_f),
        "nmi_leaf": score if isinstance(score, str) else _r(score),
    }
    return out


# -- one run ----------------------------------------------------------------------------------
def _read(path: Path) -> dict[str, object]:
    obj = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(obj, dict):
        raise ValueError(f"{path}: not an object")
    return obj


def _float(x: object) -> float:
    if x == "inf":
        return math.inf
    if x == "-inf":
        return -math.inf
    if isinstance(x, bool) or not isinstance(x, (int, float)):
        raise ValueError(f"not a number: {x!r}")
    return float(x)


def load_preds(overlay: Mapping[str, object]) -> list[Pred]:
    """The hypotheses of an ``overlay.json`` object as ``Pred`` values."""
    hyps = overlay.get("hypotheses", [])
    if not isinstance(hyps, list):
        raise ValueError("overlay: hypotheses is not a list")
    out: list[Pred] = []
    for h in hyps:
        claim = h.get("claim")
        op = str(claim["op"]) if isinstance(claim, dict) and "op" in claim else ""
        out.append(Pred(
            id=str(h["id"]), kind=str(h["kind"]), cells=frozenset(h["cells"]),
            p=_float(h["p_comp"]), status=str(h["status"]), detector=str(h["detector"]),
            op=op, features={str(k): str(v) for k, v in h["features"].items()},
        ))
    return out


def _slice_nets(h: Mapping[str, object]) -> list[str]:
    nets = h.get("nets", {})
    assert isinstance(nets, dict)
    keys = sorted((k for k in nets if k.startswith("slice") and k[5:].isdigit() and nets[k]),
                  key=lambda k: int(k[5:]))
    return [str(nets[k][0]) for k in keys]


def load_buses(overlay: Mapping[str, Any], nm: NetMap) -> list[PredBus]:
    """Bus hypotheses with members from the slice output nets (driver node, and port node)."""
    out: list[PredBus] = []
    for h in overlay.get("hypotheses", []):
        if h["kind"] != "bus":
            continue
        nets = [n for n in _slice_nets(h) if n in nm.driver]
        members = tuple(nm.driver[n] for n in nets)
        alt = tuple(
            next((r for r in nm.readers.get(n, ()) if nm.kinds.get(r) == "po"), nm.driver[n])
            for n in nets
        )
        params = h.get("params", {})
        out.append(PredBus(str(h["id"]), _float(h["p_comp"]), str(h["status"]),
                           str(params.get("order_source", "")), members, alt))
    return out


def predicted_roles(overlay: Mapping[str, Any]) -> dict[str, str]:
    """Role per cell from the live ``role`` hypotheses (the rule of ``commit.role_label``)."""
    out: dict[str, str] = {}
    for h in overlay.get("hypotheses", []):
        if h["kind"] != "role" or h["status"] in ("refuted", "rejected"):
            continue
        for cell in h["cells"]:
            if h["features"].get("role_prop") == "mixed":
                out[cell] = "mixed"
            else:
                out[cell] = "control" if _float(h["log_odds"]) >= 0 else "datapath"
    return out


def _engines(report: Mapping[str, object]) -> dict[str, int]:
    total: Counter[str] = Counter()
    rounds = report.get("rounds", [])
    if isinstance(rounds, list):
        for rnd in rounds:
            for k, v in rnd.get("engines", {}).items():
                total[str(k)] += int(v)
    return dict(sorted(total.items()))


def _proved(report: Mapping[str, object]) -> dict[str, int]:
    total: Counter[str] = Counter()
    rounds = report.get("rounds", [])
    if isinstance(rounds, list):
        for rnd in rounds:
            for k, v in rnd.get("proved", {}).items():
                total[str(k)] += int(v)
    return dict(sorted(total.items()))


def score_run(re_dir: Path, floor_dir: Path, score_p: float) -> dict[str, object]:
    """The ``score.json`` object of one run (``re_dir``) against one L0 floor (``floor_dir``,
    ``<dataset>/<design>/<floor>``)."""
    overlay = _read(re_dir / "overlay.json")
    report = _read(re_dir / "report.json")
    instances, buses, roles, paths = load_gt(floor_dir)
    nm = load_netmap(floor_dir)
    preds = load_preds(overlay)
    logic = {n for n, k in nm.kinds.items() if k not in ("pi", "po")}
    pieces = report.get("pieces", [])
    clusters = [frozenset(p["cells"]) for p in pieces] if isinstance(pieces, list) else []
    feats = report.get("features", {})
    assert isinstance(feats, dict)
    curves = construct_curves(preds, instances)
    constructs: dict[str, object] = {
        kind: {**row, "curve": curves[kind]}
        for kind, row in construct_scores(preds, instances, score_p).items()
    }
    return {
        "schema": SCHEMA,
        "design": floor_dir.parent.name,
        "floor": floor_dir.name,
        "score_p": score_p,
        "constructs": constructs,
        "bus": bus_scores(load_buses(overlay, nm), buses, score_p),
        "roles": role_scores(predicted_roles(overlay), roles, logic),
        "hierarchy": hierarchy_scores(
            {n: p for n, p in paths.items() if n in logic},
            clusters, [g.footprint for g in instances]),
        "points": reliability_points(preds, instances),
        "engines": _engines(report),
        "proved": _proved(report),
        "transfers": feats.get("transfers", 0),
        "transfer_failures": feats.get("transfer_failures", 0),
        "final_equiv": report.get("final_equiv", {}),
    }


def wyrd_metrics(report: Mapping[str, object], score: Mapping[str, object]) -> dict[str, object]:
    """The ``metrics.json`` keys of the Wyrd step (spec 13); non-numeric values are left out.

    ``precision`` and ``recall`` pool the kinds that have ground truth and at least one counted
    hypothesis (one ground-truth word can serve several kinds, so a kind that proposed nothing is
    not pooled)."""
    rounds = report.get("rounds", [])
    proved = _proved(report)
    counts = report.get("counts", {})
    cons = score.get("constructs", {})
    assert isinstance(cons, dict) and isinstance(counts, dict) and isinstance(rounds, list)
    used = [c for c in cons.values() if c["gt"] and c["counted"]]
    counted = sum(int(c["counted"]) for c in used)
    matched = sum(int(c["matched"]) for c in used)
    gt = sum(int(c["gt"]) for c in used)
    bus = score.get("bus", {})
    hier = score.get("hierarchy", {})
    equiv = report.get("final_equiv", {})
    assert isinstance(bus, dict) and isinstance(hier, dict) and isinstance(equiv, dict)
    out: dict[str, object] = {
        "rounds": len(rounds), "committed": counts.get("committed", 0),
        "proved": proved.get("equivalent", 0), "refuted": proved.get("differs", 0),
        "timeouts": report.get("timeouts", 0),
        "final_equiv_ok": 1 if equiv.get("status") in ("equivalent", "skipped:hard") else 0,
    }
    if counted:
        out["precision"] = _r(matched / counted)
    if gt:
        out["recall"] = _r(matched / gt)
    for key, src in (("bus_recall", bus.get("recall")), ("hier_f", hier.get("hier_f"))):
        if isinstance(src, (int, float)):
            out[key] = src
    return out


# -- aggregation ------------------------------------------------------------------------------
def gate_breaker_class(design: str) -> str:
    """The Gate-Breaker class (VerilogEval ``fsm``, ``count``, ``lfsr`` problems) or ``""``."""
    for c in CLASSES:
        if design.startswith("ve_") and c in design.lower():
            return c
    return ""


def _sum_construct(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    counted = sum(int(r["counted"]) for r in rows)
    matched = sum(int(r["matched"]) for r in rows)
    gt = sum(int(r["gt"]) for r in rows)
    curve = [[t, 0.0, 0.0] for t in AP_THRESHOLDS]
    for r in rows:
        for acc, cur in zip(curve, r["curve"], strict=True):
            acc[1] += cur[1]
            acc[2] += cur[2]
    out: dict[str, Any] = {"counted": counted, "matched": matched, "gt": gt}
    if not gt:
        out.update(precision=NA, recall=NA, f1=NA, ap=NA)
        return out
    prec: float | str = matched / counted if counted else NA
    rec = matched / gt
    out.update(precision=prec if isinstance(prec, str) else _r(prec), recall=_r(rec),
               f1=_r(_f1(prec, rec)), ap=ap_from_curve(curve, gt))
    return out


def _micro_bus(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    counted = sum(int(r["counted"]) for r in rows)
    matched = sum(int(r["matched"]) for r in rows)
    gt = sum(int(r["gt"]) for r in rows)
    out: dict[str, Any] = {"counted": counted, "matched": matched, "gt": gt}
    out["precision"] = _r(matched / counted) if counted and gt else NA
    out["recall"] = _r(matched / gt) if gt else NA
    shared: Counter[str] = Counter()
    exact: Counter[str] = Counter()
    rev: Counter[str] = Counter()
    for r in rows:
        for src, n in r["order_n"].items():
            shared[src] += n
            exact[src] += r["order_exact_n"][src]
            rev[src] += r["order_reversal_n"][src]
    out["order_exact"] = {s: _r(exact[s] / n) for s, n in sorted(shared.items()) if n}
    out["order_up_to_reversal"] = {s: _r(rev[s] / n) for s, n in sorted(shared.items()) if n}
    return out


def _micro_roles(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for role in ROLE_CLASSES:
        tp = sum(int(r[role]["tp"]) for r in rows)
        pred = sum(int(r[role]["pred"]) for r in rows)
        gt = sum(int(r[role]["gt"]) for r in rows)
        prec: float | str = tp / pred if pred else NA
        rec: float | str = tp / gt if gt else NA
        out[role] = {
            "precision": prec if isinstance(prec, str) else _r(prec),
            "recall": rec if isinstance(rec, str) else _r(rec),
            "f1": _r(_f1(prec, rec)) if gt else NA, "tp": tp, "pred": pred, "gt": gt,
        }
    return out


def _mean_hier(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {"designs": len(rows)}
    for key in ("HS_gt", "HS_l1", "hier_f", "nmi_leaf"):
        vals = [float(r[key]) for r in rows if isinstance(r[key], (int, float))]
        out[key] = _r(sum(vals) / len(vals)) if vals else NA
    return out


def _points(rows: Sequence[Mapping[str, Any]], kind: str) -> list[tuple[float, bool]]:
    pts: list[tuple[float, bool]] = []
    for r in rows:
        for p, y in r["points"].get(kind, ()):
            pts.append((float(p), bool(y)))
    return pts


def aggregate_floor(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Micro-averaged numbers of the ``score.json`` objects of one floor."""
    kinds = sorted({k for r in rows for k in r["constructs"]})
    cons: dict[str, Any] = {}
    for kind in kinds:
        agg = _sum_construct([r["constructs"][kind] for r in rows
                              if kind in r["constructs"]])
        agg["reliability"] = reliability(_points(rows, kind))
        cons[kind] = agg
    return {
        "designs": len(rows), "constructs": cons,
        "bus": _micro_bus([r["bus"] for r in rows]),
        "roles": _micro_roles([r["roles"] for r in rows]),
        "hierarchy": _mean_hier([r["hierarchy"] for r in rows]),
    }


def _by_floor(scores: Sequence[Mapping[str, Any]]) -> dict[str, list[Mapping[str, Any]]]:
    out: dict[str, list[Mapping[str, Any]]] = {}
    for s in sorted(scores, key=lambda s: (str(s["floor"]), str(s["design"]))):
        out.setdefault(str(s["floor"]), []).append(s)
    return out


def _cell(x: object) -> str:
    return f"{x:.3f}" if isinstance(x, float) else str(x)


def _md_table(head: Sequence[str], rows: Sequence[Sequence[object]]) -> list[str]:
    lines = ["| " + " | ".join(head) + " |", "|" + "|".join("---" for _ in head) + "|"]
    lines += ["| " + " | ".join(_cell(c) for c in row) + " |" for row in rows]
    return lines


def aggregate(scores: Sequence[Mapping[str, Any]]) -> tuple[dict[str, Any], str]:
    """``scores.json`` object and ``scores.md`` text of many ``score.json`` objects (spec 12.5)."""
    floors = {fl: aggregate_floor(rows) for fl, rows in _by_floor(scores).items()}
    classes = {str(s["design"]): gate_breaker_class(str(s["design"])) for s in scores}
    obj: dict[str, Any] = {
        "schema": SCHEMA, "floors": floors,
        "gate_breaker": {d: c for d, c in sorted(classes.items()) if c},
    }
    lines = ["# Loki re scores", ""]
    rows: list[list[object]] = []
    for fl, data in sorted(floors.items()):
        cons = data["constructs"]
        assert isinstance(cons, dict)
        for kind, c in sorted(cons.items()):
            rows.append([fl, kind, c["counted"], c["gt"], c["precision"], c["recall"], c["f1"],
                         c["ap"], c["reliability"]["ece"]])
    lines += _md_table(
        ["floor", "kind", "counted", "gt", "precision", "recall", "f1", "ap", "ece"], rows)
    lines += ["", "## Buses, roles and hierarchy", ""]
    rows = []
    for fl, data in sorted(floors.items()):
        bus, hier, roles = data["bus"], data["hierarchy"], data["roles"]
        assert isinstance(bus, dict) and isinstance(hier, dict) and isinstance(roles, dict)
        rows.append([fl, data["designs"], bus["precision"], bus["recall"],
                     roles["control"]["f1"], roles["datapath"]["f1"], hier["hier_f"],
                     hier["nmi_leaf"]])
    lines += _md_table(
        ["floor", "designs", "bus precision", "bus recall", "control f1", "datapath f1",
         "hier_f", "nmi_leaf"], rows)
    gb = obj["gate_breaker"]
    assert isinstance(gb, dict)
    if gb:
        lines += ["", "## Gate-Breaker classes", ""]
        lines += _md_table(["design", "class"], sorted(gb.items()))
    return obj, "\n".join(lines).rstrip("\n") + "\n"


def _delta(a: object, b: object) -> object:
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return _r(float(a) - float(b))
    return NA


def _calls(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    eng: Counter[str] = Counter()
    for r in rows:
        eng.update({str(k): int(v) for k, v in r["engines"].items()})
    return {
        "engines": dict(sorted(eng.items())),
        "transfers": sum(int(r["transfers"]) for r in rows),
        "transfer_failures": sum(int(r["transfer_failures"]) for r in rows),
    }


def compare(
    with_scores: Sequence[Mapping[str, Any]], without_scores: Sequence[Mapping[str, Any]]
) -> tuple[dict[str, Any], str]:
    """``ablation.json`` object and ``ablation.md`` text (spec 12.5): per floor and kind
    precision, recall, F1 and AP with and without the features, and their difference."""
    a, b = _by_floor(with_scores), _by_floor(without_scores)
    floors: dict[str, Any] = {}
    rows: list[list[object]] = []
    for fl in sorted(set(a) | set(b)):
        wa, wb = aggregate_floor(a.get(fl, [])), aggregate_floor(b.get(fl, []))
        ca, cb = wa["constructs"], wb["constructs"]
        assert isinstance(ca, dict) and isinstance(cb, dict)
        kinds: dict[str, Any] = {}
        for kind in sorted(set(ca) | set(cb)):
            x, y = ca.get(kind, {}), cb.get(kind, {})
            entry: dict[str, Any] = {}
            for m in ("precision", "recall", "f1", "ap"):
                entry[m] = {"with": x.get(m, NA), "without": y.get(m, NA),
                            "delta": _delta(x.get(m), y.get(m))}
            kinds[kind] = entry
            rows.append([fl, kind] + [
                v for m in ("precision", "recall", "f1", "ap")
                for v in (x.get(m, NA), y.get(m, NA), _delta(x.get(m), y.get(m)))])
        floors[fl] = {"constructs": kinds, "with": _calls(a.get(fl, [])),
                      "without": _calls(b.get(fl, []))}
    obj: dict[str, Any] = {"schema": SCHEMA, "floors": floors}
    head = ["floor", "kind"] + [f"{m} {s}" for m in ("P", "R", "F1", "AP")
                                for s in ("with", "without", "delta")]
    lines = ["# Ablation: with and without structural features", ""]
    lines += _md_table(head, rows)
    lines += ["", "## Proof calls and transfers", ""]
    prow: list[list[object]] = []
    for fl, data in sorted(floors.items()):
        assert isinstance(data, dict)
        for side in ("with", "without"):
            c = data[side]
            prow.append([fl, side, json.dumps(c["engines"], sort_keys=True), c["transfers"],
                         c["transfer_failures"]])
    lines += _md_table(["floor", "features", "engines", "transfers", "transfer_failures"], prow)
    return obj, "\n".join(lines).rstrip("\n") + "\n"
