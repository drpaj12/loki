"""Score the v2 FSM claims (``OUT/re/v2/*/*/*/intent.json``) against the FSM truth, compare with
stage 1 (``OUT/re/stage1``, rescored here with the stage 1 rule) and test the one-hot hypothesis.

``score_v2.py [TAG]``: writes ``results/TAG/per_design.csv``, ``summary.csv``, ``paired.csv``
(recall, v2 minus stage 1, per cell) and ``onehot_vs_binary.csv``. Default TAG ``v2``.
"""

from __future__ import annotations

import csv
import importlib
import json
import random
import sys
from pathlib import Path
from typing import Any

import networkx as nx

sys.path.insert(0, str(Path(__file__).resolve().parent))
lib: Any = importlib.import_module("fsmlib")
s1: Any = importlib.import_module("score_fsm")
BOOT, SEED = 10000, 20261030


def state_nets(key_path: Path) -> set[str]:
    key = json.loads(key_path.read_text(encoding="utf-8"))
    return {n for n, v in key["nets"].items() if any(x.startswith("state[") for x in v["names"])}


def truth_graph(design: str) -> nx.DiGraph:
    g = lib.hdl_graph(lib.src_path(design).read_text(encoding="utf-8"))
    seen, work = {0}, [0]
    while work:
        s = work.pop()
        for t in g.get(s, ()):
            if t not in seen:
                seen.add(t)
                work.append(t)
    d = nx.DiGraph()
    d.add_nodes_from(seen)
    d.add_edges_from((s, t) for s in seen for t in g.get(s, ()))
    return d


def claim_graph(f: dict[str, Any]) -> nx.DiGraph:
    d = nx.DiGraph()
    d.add_nodes_from(f["states"])
    d.add_edges_from((t["src"], t["dst"]) for t in f["transitions"])
    return d


def rooted_iso(a: nx.DiGraph, a0: int, b: nx.DiGraph, b0: int) -> bool:
    for g, r in ((a, a0), (b, b0)):
        nx.set_node_attributes(g, {n: n == r for n in g}, "root")
    return bool(nx.is_isomorphic(a, b, node_match=lambda x, y: x["root"] == y["root"]))


def v2_row(arm: str, floor: str, d: dict[str, str]) -> dict[str, Any] | None:
    bdir = lib.OUT / "build" / arm / d["design"]
    ip = lib.OUT / "re" / "v2" / arm / floor / d["design"] / "intent.json"
    key = bdir / floor / "key.json"
    if not ip.is_file() or not key.is_file():
        return None
    state = state_nets(key)
    pos = d["role"] == "pos"
    claims = [c for c in json.loads(ip.read_text(encoding="utf-8"))["claims"]
              if c["kind"] == "fsm" and c["source"] == "seq"]
    t = lib.truth(d, arm, bdir) if pos else {}
    rows = []
    for c in claims:
        q = set(c["facts"]["q"])
        j = len(q & state) / len(q | state) if pos and (q | state) else 0.0
        ok = c["status"] != "rejected" and (c["p"] is None or c["p"] >= lib.SCORE_P)
        rows.append((c, ok, j >= 0.5))
    cnt = [r for r in rows if r[1]]
    hit = sorted((r for r in cnt if r[2]), key=lambda r: -(r[0]["p"] or 0))
    out: dict[str, Any] = {
        "arm": arm, "floor": floor, "design": d["design"], "role": d["role"],
        "n_claims": len(rows), "n_counted": len(cnt), "n_counted_match": len(hit),
        "matched": int(bool(hit)), "truth_states": t.get("states", ""),
        "truth_trans": t.get("transitions", ""), "truth_enc": t.get("encoding", ""),
        "pred_states": "", "pred_enc": "", "pred_trans": "", "states_ok": "", "enc_ok": "",
        "trans_iso": "", "trans_count_ok": "", "match_any_p": int(any(r[2] for r in rows)),
    }
    if hit:
        f = hit[0][0]["facts"]
        enc = f.get("encoding", "other")
        enc = enc if enc in ("one-hot", "binary") else "other"
        out.update(
            pred_states=len(f["states"]), pred_enc=enc, pred_trans=len(f["transitions"]),
            states_ok=int(len(f["states"]) == t["states"]), enc_ok=int(enc == t["encoding"]),
            trans_count_ok=int(len(f["transitions"]) == t["transitions"]),
            trans_iso=int(rooted_iso(claim_graph(f), f["start"], truth_graph(d["design"]), 0)))
    return out


def stage1_matched(arm: str, floor: str, d: dict[str, str]) -> int | None:
    r = s1.design_row(arm, floor, d, "stage1", False)
    return None if r is None else int(r["matched"])


def boot(diffs: list[int]) -> tuple[float, float, float, float]:
    """mean, 95 % CI low, high, two-sided p (bootstrap of the mean around zero)."""
    rnd = random.Random(SEED)
    n = len(diffs)
    means = sorted(sum(diffs[rnd.randrange(n)] for _ in range(n)) / n for _ in range(BOOT))
    m = sum(diffs) / n
    lo, hi = means[int(0.025 * BOOT)], means[int(0.975 * BOOT) - 1]
    below = sum(1 for x in means if x <= 0) / BOOT
    above = sum(1 for x in means if x >= 0) / BOOT
    return m, lo, hi, min(1.0, 2 * min(below, above))


def holm(ps: list[float]) -> list[float]:
    order = sorted(range(len(ps)), key=lambda i: ps[i])
    adj, run = [0.0] * len(ps), 0.0
    for k, i in enumerate(order):
        run = max(run, min(1.0, (len(ps) - k) * ps[i]))
        adj[i] = run
    return adj


def summary(rows: list[dict[str, Any]], arm: str, floor: str) -> dict[str, Any]:
    pos = [r for r in rows if r["role"] == "pos"]
    neg = [r for r in rows if r["role"] == "neg"]
    cnt = sum(r["n_counted"] for r in rows)
    ok = sum(r["n_counted_match"] for r in rows)
    m = [r for r in pos if r["matched"]]
    n = len(pos)
    return {
        "arm": arm, "floor": floor, "n_pos": n, "n_neg": len(neg),
        "recall": round(len(m) / n, 3),
        "proposed_any_p": round(sum(r["match_any_p"] for r in pos) / n, 3),
        "precision": round(ok / cnt, 3) if cnt else "n/a", "counted": cnt, "counted_true": ok,
        "neg_designs_with_fp": sum(1 for r in neg if r["n_counted"]),
        "design_precision": round(len(m) / sum(1 for r in rows if r["n_counted"]), 3),
        "claims_on_regfile_negs": sum(r["n_counted"] for r in neg if "_regfile_" in r["design"]),
        "precision_excl_regfile": round(ok / (cnt - sum(
            r["n_counted"] for r in neg if "_regfile_" in r["design"])), 3),
        "enc_acc": s1.wilson(sum(r["enc_ok"] for r in m), len(m)),
        "states_exact": s1.wilson(sum(r["states_ok"] for r in m), len(m)),
        "trans_exact_iso": s1.wilson(sum(r["trans_iso"] for r in m), len(m)),
        "trans_count_ok": s1.wilson(sum(r["trans_count_ok"] for r in m), len(m)),
        "trans_exact_iso_of_all_pos": round(sum(r["trans_iso"] for r in m) / n, 3),
    }


def write(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, list(rows[0]), lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


def main(argv: list[str]) -> int:
    tag = argv[0] if argv else "v2"
    odir = lib.HERE / "results" / tag
    odir.mkdir(parents=True, exist_ok=True)
    pop = lib.population()
    allrows: list[dict[str, Any]] = []
    summ: list[dict[str, Any]] = []
    paired: list[dict[str, Any]] = []
    rec: dict[tuple[str, str], dict[str, int]] = {}
    prec_old = {(r["arm"], r["floor"]): r["precision"]
                for r in csv.DictReader((lib.HERE / "results/stage1/summary.csv").open())}
    for arm in lib.ARMS:
        for floor in lib.FLOORS:
            rows = [r for d in pop if (r := v2_row(arm, floor, d)) is not None]
            allrows += rows
            s = summary(rows, arm, floor)
            summ.append(s)
            new = {r["design"]: r["matched"] for r in rows if r["role"] == "pos"}
            rec[(arm, floor)] = new
            old = {d["design"]: stage1_matched(arm, floor, d) for d in pop if d["role"] == "pos"}
            ds = [new[k] - o for k in new if (o := old.get(k)) is not None]
            m, lo, hi, p = boot(ds)
            s1r = sum(o for k in new if (o := old.get(k)) is not None) / len(ds)
            paired.append({
                "arm": arm, "floor": floor, "n": len(ds), "stage1_recall": round(s1r, 3),
                "v2_recall": s["recall"],
                "diff": round(m, 3), "ci_lo": round(lo, 3), "ci_hi": round(hi, 3), "p": round(p, 4),
                "precision_stage1": prec_old[(arm, floor)], "precision_v2": s["precision"]})
    for r, h in zip(paired, holm([float(x["p"]) for x in paired]), strict=True):
        r["holm_p"] = round(h, 4)
        ps, pv = float(r["precision_stage1"]), r["precision_v2"]
        guard = pv != "n/a" and float(pv) >= ps - 0.05
        r["verdict"] = ("V2 BETTER" if r["holm_p"] < 0.05 and r["ci_lo"] > 0 and guard else
                        "V2 WORSE" if r["holm_p"] < 0.05 and r["ci_hi"] < 0 else
                        "NO DETECTABLE EFFECT" if not (r["holm_p"] < 0.05 and r["ci_lo"] > 0)
                        else "PRECISION GUARD FAILED")
    ob: list[dict[str, Any]] = []
    for floor in (*lib.FLOORS, "pooled"):
        fl = lib.FLOORS if floor == "pooled" else (floor,)
        ds = [rec[("onehot", f)][k] - rec[("binary", f)][k] for f in fl for k in rec[("onehot", f)]
              if k in rec[("binary", f)]]
        m, lo, hi, p = boot(ds)
        ob.append({"floor": floor, "n": len(ds), "diff_onehot_minus_binary": round(m, 3),
                   "ci_lo": round(lo, 3), "ci_hi": round(hi, 3), "p": round(p, 4),
                   "verdict": "SUPPORTED" if lo >= -0.10 and hi <= 0.10 else "NOT SUPPORTED"})
    write(odir / "per_design.csv", allrows)
    write(odir / "summary.csv", summ)
    write(odir / "paired.csv", paired)
    write(odir / "onehot_vs_binary.csv", ob)
    for t in (summ, paired, ob):
        for r in t:
            print(r)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
