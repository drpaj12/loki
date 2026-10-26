"""Deterministic design selection: 10 problems per Gate-Breaker quartile (seed in common.SEED).

Eligible: in the quartile file and ``*_prompt.txt`` at most 40000 bytes. Rank by SHA-256 of
``<seed>:<problem>`` ascending, take the first 10 per quartile, list by netlist line count.
A problem whose reference fails the pre-flight (score.py preflight) is replaced by the next in
rank; replacements are listed in selection.csv column ``note``.
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common  # noqa: E402  (path set above)


def read_list(path: Path) -> list[str]:
    return [ln.strip() for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]


def eligible(quartile: str) -> list[str]:
    names = read_list(common.ve_root() / "quartiles" / f"{common.QUARTILES[quartile]}_quartile.txt")
    ok = [p for p in names
          if (common.dataset_dir() / f"{p}_prompt.txt").stat().st_size <= common.MAX_PROMPT_BYTES]
    return sorted(ok, key=common.rank_key)


def lines_of(problem: str) -> int:
    text = (common.dataset_dir() / f"{problem}_netlist.v").read_text(encoding="utf-8")
    return text.count("\n")


def select(skip: frozenset[str] = frozenset()) -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []
    for q in common.QUARTILES:
        chosen = [p for p in eligible(q) if p not in skip][: common.PER_QUARTILE]
        chosen.sort(key=lambda p: (lines_of(p), p))
        rows += [(q, p) for p in chosen]
    return rows


def load_csv(path: Path, key: str) -> dict[str, dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as fh:
        return {r[key]: r for r in csv.DictReader(fh)}


def main() -> int:
    veval = common.REPO / "experiments" / "veval-l0"
    bench = load_csv(veval / "benchmark.csv", "problem")
    feats = load_csv(veval / "features.csv", "design")
    out = common.HERE / "selection.csv"
    with out.open("w", encoding="utf-8", newline="\n") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(["quartile", "problem", "netlist_lines", "prompt_bytes", "bin_quartile",
                    "fsm_gt", "dffsr"])
        for q, p in select():
            ds = common.dataset_dir()
            bq = bench[p]["quartile"] if p in bench else "-"
            fsm = feats[f"ve_{p}"]["fsm"] if f"ve_{p}" in feats else "-"
            net = (ds / f"{p}_netlist.v").read_text(encoding="utf-8")
            w.writerow([q, p, lines_of(p), (ds / f"{p}_prompt.txt").stat().st_size, bq, fsm,
                        "y" if "DFFSR" in net else ""])
    print(f"wrote {out.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
