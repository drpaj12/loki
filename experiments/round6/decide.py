"""Numeric rules of EXPERIMENT.md applied to the l15_*.csv tables -> r6_status.csv."""

from __future__ import annotations

import sys
from collections import defaultdict

from r6lib import HERE, read_csv, write_csv

MIN_KIND = 10
MIN_PASS = 5


def rule1_2() -> list[list[object]]:
    rows = read_csv(HERE / "l15_kind_pass.csv")
    by: defaultdict[tuple[str, str, str, str], list[tuple[str, int, float]]] = defaultdict(list)
    for r in rows:
        by[(r["set"], r["level"], r["axis"], r["kind"])].append(
            (r["pass"], int(r["first_losses"]), float(r["null_expected"])))
    out: list[list[object]] = []
    for (name, level, axis, kind), items in sorted(by.items()):
        total = sum(n for _, n, _ in items)
        ntotal = sum(x for _, _, x in items)
        if total < MIN_KIND:
            out.append(["R1", name, level, axis, kind, "", total, "", "", "too few"])
        else:
            top = max(items, key=lambda t: (t[1], t[0]))
            s = top[1] / total
            s0 = top[2] / ntotal if ntotal else 0.0
            res = "spread" if s < 0.5 else ("dominant" if s - s0 >= 0.2 else "dominant-null")
            out.append(["R1", name, level, axis, kind, top[0], total, f"{s:.3f}/{s0:.3f}", "", res])
        for p, n, x in items:
            if n < MIN_PASS:
                res = "few"
            elif n >= 2 * x:
                res = "above chance"
            elif n <= 0.5 * x:
                res = "below chance"
            else:
                res = "at chance"
            out.append(["R2", name, level, axis, kind, p, n, f"{x:.3f}", "", res])
    return out


def rule3() -> list[list[object]]:
    out: list[list[object]] = []
    acc: defaultdict[tuple[str, str], list[int]] = defaultdict(lambda: [0, 0])
    for r in read_csv(HERE / "l15_explained.csv"):
        m, e = int(r["merged"]), int(r["explained"])
        acc[(r["set"], r["level"])][0] += m
        acc[(r["set"], r["level"])][1] += e
        out.append(["R3", r["set"], r["level"], "pass", "", r["pass"], m, e, "",
                    _share(m, e)])
    for (name, level), (m, e) in sorted(acc.items()):
        out.append(["R3", name, level, "all", "", "", m, e, "", _share(m, e)])
    return out


def _share(m: int, e: int) -> str:
    if m < 20:
        return "few"
    s = e / m
    tag = "D14 explains" if s >= 0.9 else "partly explained" if s >= 0.5 else "mostly unexplained"
    return f"{tag} ({s:.3f})"


def detect_pooled() -> dict[tuple[str, str, str, str], list[int]]:
    """(set, arm, kind, snapshot) to [designs, counted, matched, gt], paired designs only."""
    path = HERE / "l15_detect_design.csv"
    if not path.is_file():
        return {}
    data: defaultdict[tuple[str, str, str, str], dict[str, tuple[int, int, int]]]
    data = defaultdict(dict)
    for r in read_csv(path):
        data[(r["set"], r["arm"], r["kind"], r["snapshot"])][r["design"]] = (
            int(r["counted"]), int(r["matched"]), int(r["gt"]))
    out: dict[tuple[str, str, str, str], list[int]] = {}
    for (name, arm, kind, snap), per in data.items():
        other = data.get((name, arm, kind, "S8" if snap == "S7" else "S7"), {})
        keep = [v for d, v in per.items() if d in other]
        out[(name, arm, kind, snap)] = [len(keep), sum(v[0] for v in keep),
                                        sum(v[1] for v in keep), sum(v[2] for v in keep)]
    return out


def rule4() -> list[list[object]]:
    """Recall at S7 and S8 per set (and ALL), arm, kind, and the outcome of rule 4."""
    pooled = detect_pooled()
    for key in list(pooled):
        name, arm, kind, snap = key
        if name == "ALL":
            continue
        acc = pooled.setdefault(("ALL", arm, kind, snap), [0, 0, 0, 0])
        for i, v in enumerate(pooled[key]):
            acc[i] += v
    out: list[list[object]] = []
    for (name, arm, kind, snap), v in sorted(pooled.items()):
        if snap != "S7":
            continue
        w = pooled.get((name, arm, kind, "S8"))
        if w is None or v[3] < MIN_KIND or w[3] < MIN_KIND:
            out.append(["R4", name, "", arm, kind, "S7>S8", v[3], "", "", "too few"])
            continue
        r7, r8 = v[2] / v[3], w[2] / w[3]
        d = r8 - r7
        res = "fooled by abc" if d <= -0.2 else ("helped" if d >= 0.2 else "not fooled")
        out.append(["R4", name, "", arm, kind, "S7>S8", v[3], f"{r7:.3f}", f"{r8:.3f}", res])
    return out


def main() -> int:
    rows = rule1_2() + rule3() + rule4()
    path = HERE / "r6_status.csv"
    write_csv(path, ["rule", "set", "level", "axis", "kind", "pass", "n", "aux", "aux2", "outcome"],
              rows)
    return 0


if __name__ == "__main__":
    sys.exit(main())
