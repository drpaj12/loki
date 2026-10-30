"""Fit the intent calibration (``calib/intent-f3.json``) from the checks of the sequential claims.

Usage: ``python -I calib_intent.py --train DIR [--test DIR] --out calib/intent-f3.json
[--report calib_intent_report.csv]``. ``DIR`` holds one ``<problem>/verify.json`` per problem as
written by ``make_hints_v2.py`` run without a table. An outcome is one claim: ``held`` when the
claim's next-state function agreed with the original netlist on every covered vector
(``loki.intent.verify``). Claims with no model or too few covered vectors are left out.

The file fitted on ``--train`` plus ``--test`` is the one the experiment uses. The report also fits
on ``--train`` alone and scores the ``--test`` claims against it (held-out reliability): per kind
the counts, the posterior and the expected calibration error.
"""

from __future__ import annotations

import argparse
import csv
import importlib
import json
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))
calib: Any = importlib.import_module("loki.intent.calib")


def outcomes(root: Path) -> list[tuple[str, bool, str]]:
    out: list[tuple[str, bool, str]] = []
    for f in sorted(root.glob("*/verify.json")):
        for row in json.loads(f.read_text(encoding="utf-8")):
            if row["ok"] is not None:
                out.append((row["kind"], bool(row["ok"]), f.parent.name))
    return out


def report_rows(train: list[tuple[str, bool, str]],
                test: list[tuple[str, bool, str]]) -> list[dict[str, Any]]:
    full = calib.fit([(k, o) for k, o, _ in train + test], "all")
    held = calib.fit([(k, o) for k, o, _ in train], "train")
    rows = []
    for kind in sorted({k for k, _, _ in train + test}):
        tr = [o for k, o, _ in train if k == kind]
        te = [o for k, o, _ in test if k == kind]
        p_held = held.p_for(kind)
        pairs = [] if p_held is None else [(p_held, o) for o in te]
        rows.append({
            "kind": kind, "train_n": len(tr), "train_held": sum(tr), "test_n": len(te),
            "test_held": sum(te), "p_train_only": held.p_for(kind), "p_fitted": full.p_for(kind),
            "test_ece_train_fit": calib.ece(pairs)})
    return rows


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--train", type=Path, required=True)
    ap.add_argument("--test", type=Path, default=None)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--report", type=Path, default=None)
    args = ap.parse_args(argv)
    train = outcomes(args.train)
    test = outcomes(args.test) if args.test else []
    source = (f"{len(train)} claims on {len({p for _, _, p in train})} train problems"
              + (f" plus {len(test)} claims on {len({p for _, _, p in test})} test problems"
                 if test else "")
              + "; outcome = next-state function agrees with the original netlist"
              " (loki.intent.verify); Beta(1,1) posterior mean per kind")
    fitted = calib.fit([(k, o) for k, o, _ in train + test], source)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(fitted.to_json(), sort_keys=True, indent=1) + "\n",
                        encoding="utf-8")
    rows = report_rows(train, test)
    if args.report is not None:
        with args.report.open("w", encoding="utf-8", newline="") as fh:
            w = csv.DictWriter(fh, list(rows[0]), lineterminator="\n")
            w.writeheader()
            w.writerows(rows)
    for r in rows:
        print(r)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
