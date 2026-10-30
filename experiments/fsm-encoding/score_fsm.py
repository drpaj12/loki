"""Score ``OUT/re/TAG`` against the FSM truth: ``score_fsm.py TAG [--enc]``.

Writes ``results/TAG/per_design.csv`` and ``results/TAG/summary.csv`` (this directory). ``--enc``:
the kinds ``fsm_onehot`` / ``fsm_binary`` carry an encoding call (stage 3); without it the
detector makes none (stage 1) and the encoding columns are n/a.
"""

from __future__ import annotations

import csv
import importlib
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
lib: Any = importlib.import_module("fsmlib")
LIVE = frozenset({"open", "committed", "proved", "accepted"})
FSM_KINDS = ("fsm", "fsm_onehot", "fsm_binary")
CALL = {"fsm_onehot": "one-hot", "fsm_binary": "binary", "fsm": "other"}
ECE_BINS = 10


def counted(h: dict[str, Any]) -> bool:
    return h["status"] == "committed" or (h["status"] != "rejected" and h["p_comp"] >= lib.SCORE_P)


def ff_sets(key_path: Path) -> tuple[set[str], set[str]]:
    key = json.loads(key_path.read_text(encoding="utf-8"))
    ffs, state = set(), set()
    for n, c in key["cells"].items():
        if "DFF" in c["type"]:
            ffs.add(n)
            if str(c["name"]).startswith("state."):
                state.add(n)
    return ffs, state


def jac(a: set[str], b: set[str]) -> float:
    return len(a & b) / len(a | b) if a | b else 0.0


def design_row(
    arm: str, floor: str, d: dict[str, str], tag: str, enc: bool
) -> dict[str, Any] | None:
    bdir = lib.OUT / "build" / arm / d["design"]
    ov = lib.OUT / "re" / tag / arm / floor / d["design"] / "overlay.json"
    key = bdir / floor / "key.json"
    if not ov.is_file() or not key.is_file():
        return None
    ffs, state = ff_sets(key)
    hyps = [h for h in json.loads(ov.read_text(encoding="utf-8"))["hypotheses"]
            if h["kind"] in FSM_KINDS]
    pos = d["role"] == "pos"
    t = lib.truth(d, arm, bdir) if pos else {}
    rows = []
    for h in hyps:
        j = jac({c for c in h["cells"] if c in ffs}, state) if pos else 0.0
        rows.append((h, counted(h), j >= 0.5))
    cnt = [r for r in rows if r[1]]
    hit = sorted((r for r in cnt if r[2]), key=lambda r: -r[0]["p_comp"])
    best = sorted((r for r in rows if r[2]), key=lambda r: -r[0]["p_comp"])
    out: dict[str, Any] = {
        "arm": arm, "floor": floor, "design": d["design"], "role": d["role"],
        "n_fsm_hyps": len(rows), "n_counted": len(cnt), "n_counted_match": len(hit),
        "matched": int(bool(hit)), "n_counted_fp": len(cnt) - len(hit),
        "truth_states": t.get("states", ""), "truth_enc": t.get("encoding", ""),
        "truth_extracted": t.get("extracted", ""),
        "pred_states": "", "pred_enc": "", "states_ok": "", "best_p": "",
        "prop_states": "", "prop_matched": int(bool(best)),
    }
    if hit:
        h = hit[0][0]
        out["pred_states"] = h["params"].get("states", "")
        out["pred_enc"] = CALL[h["kind"]] if enc else ""
        out["states_ok"] = int(out["pred_states"] == t["states"])
    if best:
        out["prop_states"] = best[0][0]["params"].get("states", "")
        out["best_p"] = best[0][0]["p_comp"]
    out["_labels"] = json.dumps([[h["p_comp"], int(m)] for h, _, m in rows])
    return out


def ece(points: list[list[float]]) -> float | str:
    if not points:
        return "n/a"
    tot = 0.0
    for b in range(ECE_BINS):
        sel = [(p, y) for p, y in points if min(int(p * ECE_BINS), ECE_BINS - 1) == b]
        if sel:
            tot += abs(sum(p for p, _ in sel) - sum(y for _, y in sel))
    return round(tot / len(points), 4)


def wilson(k: int, n: int) -> str:
    if n == 0:
        return "n/a"
    z = 1.96
    p = k / n
    den = 1 + z * z / n
    c = (p + z * z / (2 * n)) / den
    h = z * ((p * (1 - p) / n + z * z / (4 * n * n)) ** 0.5) / den
    return f"{k}/{n} [{max(0, c - h):.2f},{min(1, c + h):.2f}]"


def summarise(rows: list[dict[str, Any]], arm: str, floor: str, enc: bool) -> dict[str, Any]:
    pos = [r for r in rows if r["role"] == "pos"]
    neg = [r for r in rows if r["role"] == "neg"]
    cnt = sum(r["n_counted"] for r in rows)
    ok = sum(r["n_counted_match"] for r in rows)
    m = [r for r in pos if r["matched"]]
    sok = sum(r["states_ok"] for r in m)
    ratio = [r["pred_states"] / r["truth_states"] for r in m
             if r["truth_states"] and isinstance(r["pred_states"], int)]
    pts = [p for r in rows for p in json.loads(r["_labels"])]
    return {
        "arm": arm, "floor": floor, "n_pos": len(pos), "n_neg": len(neg),
        "recall": round(len(m) / len(pos), 3) if pos else "n/a",
        "proposed_any_p": round(sum(r["prop_matched"] for r in pos) / len(pos), 3)
        if pos else "n/a",
        "precision": round(ok / cnt, 3) if cnt else "n/a", "counted": cnt, "counted_true": ok,
        "neg_designs_with_fp": sum(1 for r in neg if r["n_counted"]),
        "enc_acc": wilson(sum(1 for r in m if r["pred_enc"] == r["truth_enc"]), len(m))
        if enc else "n/a",
        "states_exact": wilson(sok, len(m)),
        "states_ratio_mean": round(sum(ratio) / len(ratio), 3) if ratio else "n/a",
        "ece": ece(pts),
    }


def main(argv: list[str]) -> int:
    tag, enc = argv[0], "--enc" in argv[1:]
    odir = lib.HERE / "results" / tag
    odir.mkdir(parents=True, exist_ok=True)
    allrows: list[dict[str, Any]] = []
    summ: list[dict[str, Any]] = []
    for arm in lib.ARMS:
        for floor in lib.FLOORS:
            rows = [r for d in lib.population()
                    if (r := design_row(arm, floor, d, tag, enc)) is not None]
            allrows += rows
            if rows:
                summ.append(summarise(rows, arm, floor, enc))
    fields = [k for k in allrows[0] if k != "_labels"]
    with (odir / "per_design.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fields, lineterminator="\n", extrasaction="ignore")
        w.writeheader()
        w.writerows(allrows)
    with (odir / "summary.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, list(summ[0]), lineterminator="\n")
        w.writeheader()
        w.writerows(summ)
    for s in summ:
        print(s)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
