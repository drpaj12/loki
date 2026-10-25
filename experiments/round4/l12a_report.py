"""RQ-L12a: corpus report and manifest split rewrite.

Writes ``corpus_report.csv`` (per family and split) and ``corpus.csv`` (copy of the generator's
table with the node count per floor), and rewrites the ``split`` fields of the assembled corpus
``manifest.json`` by the corpus split (train -> train; iid, ood -> test), keeping the original in
``manifest.hash.json``. Run it after ``loki assemble`` and ``loki check`` (the check verifies the
hash split rule, which the rewrite replaces).
"""

from __future__ import annotations

import json
import shutil
from collections import defaultdict
from typing import Any

import r4lib

FLOORS3 = ("f1-k6", "f2", "f3")


def main() -> int:
    man_path = r4lib.CORPUS / "manifest.json"
    orig = r4lib.CORPUS / "manifest.hash.json"
    if not orig.is_file():
        shutil.copyfile(man_path, orig)
    man = json.loads(orig.read_text(encoding="utf-8"))
    cs = r4lib.corpus_split()
    gen = {r["design"]: r for r in r4lib.read_csv(r4lib.DATA / "corpus-project" / "corpus.csv")}
    acc: dict[tuple[str, str], dict[str, Any]] = defaultdict(lambda: defaultdict(float))
    table: list[list[Any]] = []
    for e in man["designs"]:
        des = str(e["design"])
        fam, split = cs[des]
        e["split"] = "train" if split == "train" else "test"
        a = acc[(fam, split)]
        a["generated"] += 1
        row: list[Any] = [des, fam, split, gen[des]["seed"], gen[des]["n_test_params"],
                          gen[des]["params"]]
        for fl in FLOORS3:
            info = e["floors"].get(fl, {})
            st = info.get("status", "missing")
            a[f"ok_{fl}"] += st == "ok"
            a[f"fail_{fl}"] += st == "fail"
            a[f"equiv_{fl}"] += st == "fail" and "equivalence" in str(info.get("reason", ""))
            if st == "ok":
                meta = json.loads(
                    (r4lib.CORPUS / des / fl / "meta.json").read_text(encoding="utf-8"))["counts"]
                a[f"nodes_{fl}"] += meta["nodes"]
                a[f"cells_{fl}"] += meta["nodes"] - meta["pi"] - meta["po"] - meta["const"]
            row.append(info.get("nodes", ""))
        a["all_ok"] += all(e["floors"].get(f, {}).get("status") == "ok" for f in FLOORS3)
        table.append(row)
    man_path.write_text(json.dumps(man, sort_keys=True, indent=1) + "\n", encoding="utf-8")
    rows: list[list[Any]] = []
    for (fam, split), a in sorted(acc.items()):
        row = [fam, split, int(a["generated"]), int(a["all_ok"])]
        for fl in FLOORS3:
            n = a[f"ok_{fl}"] or 1
            row += [int(a[f"ok_{fl}"]), int(a[f"fail_{fl}"]), int(a[f"equiv_{fl}"]),
                    round(a[f"nodes_{fl}"] / n, 2), round(a[f"cells_{fl}"] / n, 2)]
        rows.append(row)
    head = ["family", "split", "generated", "all_floors_ok"]
    for fl in FLOORS3:
        head += [f"ok_{fl}", f"fail_{fl}", f"equiv_fail_{fl}", f"mean_nodes_{fl}",
                 f"mean_cells_{fl}"]
    r4lib.write_csv(r4lib.OUT / "corpus_report.csv", head, rows)
    r4lib.write_csv(r4lib.OUT / "corpus.csv",
                    ["design", "family", "split", "seed", "n_test_params", "params",
                     *[f"nodes_{f}" for f in FLOORS3]], table)
    tot = sum(r[2] for r in rows)
    print(tot, "designs;", sum(r[3] for r in rows), "ok on all floors")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
