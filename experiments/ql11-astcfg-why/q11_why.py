"""Part B analysis of Q-L11: where structure recovery is lost, and the size test (no model call).

Reads results/construct_loss.csv (q11_struct.py) and the committed results of Q-L4, Q-L8c, Q-L9 and
Q-L10. Writes results/: taxonomy_kind_endpoint.csv, loss_stage.csv, size_test.csv, mixing_desc.csv.
Bootstrap: seed 20261103, 2000 resamples, designs resampled (a design's constructs stay together).
Usage: python -B q11_why.py
"""

from __future__ import annotations

import csv
import random
from collections import Counter, defaultdict
from functools import partial
from pathlib import Path
from typing import Any

import q11_env as env

KINDS = ("fsm", "counter", "shift", "regfile", "register")
ENDPOINTS = ("gate", "k4", "k6")
PARTLY = ("SPLIT", "BLOATED", "UNDERREACH")


def read(p: Path) -> list[dict[str, str]]:
    with p.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def write(name: str, rows: list[dict[str, Any]]) -> None:
    keys: list[str] = []
    for r in rows:
        keys += [k for k in r if k not in keys]
    with (env.RES / name).open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, keys, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


def status(r: dict[str, str]) -> str:
    if r["right"] == "1":
        return "recovered"
    return "missed" if r["cls"] == "NOSEED" else "partly"


def taxonomy(rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    out = []
    for kind in (*KINDS, "all"):
        for ep in (*ENDPOINTS, "all"):
            sel = [r for r in rows if kind in ("all", r["kind"]) and ep in ("all", r["endpoint"])]
            c = Counter(status(r) for r in sel)
            cls = Counter(r["cls"] for r in sel if r["right"] != "1")
            n = len(sel)
            out.append({"kind": kind, "endpoint": ep, "constructs": n,
                        "recovered": c["recovered"], "partly": c["partly"], "missed": c["missed"],
                        "recovered_share": round(c["recovered"] / n, 3) if n else "",
                        **{k: cls[k] for k in ("SPLIT", "BLOATED", "UNDERREACH", "NOSEED")}})
    return out


def boot_diff(rows: list[dict[str, str]], flag: Any) -> tuple[float, float, float]:
    """Right share of flagged minus unflagged constructs, design-clustered bootstrap 95 CI."""
    by: dict[str, list[dict[str, str]]] = defaultdict(list)
    for r in rows:
        by[f"{r['set']}/{r['design']}/{r['cell']}"].append(r)
    keys = sorted(by)

    def diff(ks: list[str]) -> float:
        a = [int(r["right"]) for k in ks for r in by[k] if flag(r)]
        b = [int(r["right"]) for k in ks for r in by[k] if not flag(r)]
        if not a or not b:
            return float("nan")
        return sum(a) / len(a) - sum(b) / len(b)

    point = diff(keys)
    rng = random.Random(env.SEED)
    vals = sorted(v for v in (diff([rng.choice(keys) for _ in keys]) for _ in range(env.BOOT))
                  if v == v)
    return point, vals[int(0.025 * len(vals))], vals[int(0.975 * len(vals)) - 1]


def label(lo: float, hi: float) -> str:
    return "SUPPORTED" if hi < 0 else ("DISMISSED" if lo > 0 else "INCONCLUSIVE")


def is_large(med: int, r: dict[str, str]) -> bool:
    return int(r["n_true"]) > med


def size_test(rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    out = []
    for ep in (*ENDPOINTS, "all"):
        sel = [r for r in rows if ep in ("all", r["endpoint"])]
        sizes = sorted(int(r["n_true"]) for r in sel)
        med = sizes[len(sizes) // 2]
        big = [r for r in sel if int(r["n_true"]) > med]
        small = [r for r in sel if int(r["n_true"]) <= med]
        d, lo, hi = boot_diff(sel, partial(is_large, med))
        out.append({"endpoint": ep, "constructs": len(sel), "median_cells": med,
                    "small_n": len(small), "small_right": round(
                        sum(int(r["right"]) for r in small) / max(1, len(small)), 3),
                    "large_n": len(big), "large_right": round(
                        sum(int(r["right"]) for r in big) / max(1, len(big)), 3),
                    "large_minus_small": round(d, 3), "ci_lo": round(lo, 3), "ci_hi": round(hi, 3),
                    "split_share_of_large_misses": round(
                        sum(r["cls"] == "SPLIT" for r in big)
                        / max(1, sum(r["right"] != "1" for r in big)), 3),
                    "split_share_of_small_misses": round(
                        sum(r["cls"] == "SPLIT" for r in small)
                        / max(1, sum(r["right"] != "1" for r in small)), 3),
                    "label": label(lo, hi)})
    return out


def share(rows: list[dict[str, str]]) -> float:
    return round(sum(int(r["right"]) for r in rows) / max(1, len(rows)), 3)


def mixing(rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    out = []
    for ep in (*ENDPOINTS, "all"):
        sel = [r for r in rows if ep in ("all", r["endpoint"]) and r["star"] != ""]

        def flag(r: dict[str, str]) -> bool:
            return float(r["star"]) > 0

        mixed = [r for r in sel if flag(r)]
        plain = [r for r in sel if not flag(r)]
        d, lo, hi = boot_diff(sel, flag) if mixed and plain else (float("nan"),) * 3
        out.append({"endpoint": ep, "labelled_constructs": len(sel), "with_mixed_cell": len(mixed),
                    "share_with_mixed_cell": round(len(mixed) / max(1, len(sel)), 3),
                    "right_mixed": share(mixed), "right_plain": share(plain),
                    "mixed_minus_plain": round(d, 3), "ci_lo": round(lo, 3), "ci_hi": round(hi, 3),
                    "label": "descriptive"})
    return out


def stage(name: str, source: str, measure: str) -> dict[str, Any]:
    return {"stage": name, "source": source, "measure": measure}


def stages() -> list[dict[str, Any]]:
    e = env.EXP / "ql4-misses" / "results"
    q6, q9, q10 = (env.EXP / x / "results" for x in ("ql6-grow", "ql9-join", "ql10-blocks"))
    out: list[dict[str, Any]] = []
    pl: Counter[tuple[str, str]] = Counter()
    for r in read(e / "pass_loss_summary.csv"):
        pl[(r["class"], r["dominant_loss_pass"])] += int(r["constructs"])
    out.append(stage("(i) synthesis lost the structure", "Q-L4 pass_loss (O-lut flow)",
                     "; ".join(f"{c} lost first in {p}: {n}" for (c, p), n in sorted(pl.items()))))
    mp = {(r["cell"], r["category"]): int(r["cells"]) for r in read(q6 / "mixed_provenance.csv")}
    for c in ("O-gate", "O-lut", "O-hard"):
        mixed, total = mp[(c, "mixed (*)")], mp[(c, "all")]
        out.append(stage("(i) provenance mixing across design parts", "Q-L6 mixed_provenance",
                         f"{c}: {mixed} of {total} cells have a mixed label"))
    for r in read(q9 / "fixed_by_class.csv"):
        if r["classes"].startswith(("#77", "#76")):
            out.append(stage("(ii) partition cut the structure wrongly",
                             f"Q-L9 fixed_by_class {r['classes']}",
                             f"{r['class']}: {r['constructs']} constructs, right after join and "
                             f"split {r['head_right']} ({r['head_share']})"))
    for r in read(q9 / "kind_f1.csv"):
        if r["config"] == "HEAD":
            out.append(stage("(iii) wrong kind label", "Q-L9 kind_f1 HEAD (M2 kind posterior)",
                             f"{r['kind']}: precision {r['precision'] or '-'}, recall "
                             f"{r['recall'] or '-'}, F1 {r['f1']}"))
    for r in read(q10 / "key_recovery.csv"):
        if r["arm"] == "D" and int(r["key_total"]):
            out.append(stage("(iv) LLM decode of a right block wrong", "Q-L10 key_recovery",
                             f"{r['tier']}: {r['key_right']} of {r['key_total']} key constructs in "
                             f"a right block, {r['key_right_ok']} also decoded ok"))
    checks = [r for r in read(q10 / "blocks.csv") if r["check"]]
    ck = Counter((r["arm"], r["check"]) for r in checks)
    for arm in ("D", "Dh"):
        n = sum(v for (a, _), v in ck.items() if a == arm)
        detail = ", ".join(f"{k} {v}" for (a, k), v in sorted(ck.items()) if a == arm)
        out.append(stage("(iv) LLM decode of a right block wrong",
                         "Q-L10 blocks.csv (all tiers, rows with a block check)",
                         f"arm {arm}: {n} checked block replies; {detail}"))
    for r in read(q10 / "ext_diagnostic.csv"):
        if r["arm"] == "D":
            out.append(stage("(v) assembly", "Q-L10 ext_diagnostic",
                             f"{r['problem']}: {r['original']}, {r['n_failed']} failed block(s); "
                             f"with them replaced by their own cells: "
                             f"{r['after_replacing_failed_with_own_cells']}"))
    return out


def main() -> int:
    rows = read(env.RES / "construct_loss.csv")
    write("taxonomy_kind_endpoint.csv", taxonomy(rows))
    write("size_test.csv", size_test(rows))
    write("mixing_desc.csv", mixing(rows))
    write("loss_stage.csv", stages())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
