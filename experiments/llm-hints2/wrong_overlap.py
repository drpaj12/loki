"""Per-problem overlap of the tagged lines of arm W with the true linking (arm B2).

Usage: ``python -I wrong_overlap.py``. Reads ``run/hints2/<problem>/netlist_{linked,w}.v`` and
``hints.md`` / ``hints_w.md``; writes ``wrong_overlap.csv`` and prints the summary.
A tag is a (line, claim id) pair; ``tag_of_linked`` is the share of the true tags that W also puts
on the same line,
``tag_of_wrong`` the share of W's tags that are also true. ``line_*`` is the same for the set of
tagged lines (high when claims cover most of a small netlist, whatever W does). A problem with no
claim has no tags (W equals B2 there). A problem is ``excluded`` from the W tests when
``max(tag_of_linked, tag_of_wrong)`` exceeds ``LIMIT``.
"""

from __future__ import annotations

import csv
import importlib
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
hintscfg: Any = importlib.import_module("hintscfg")
netlink: Any = importlib.import_module("netlink")
LIMIT = 0.5
AIM = 0.2
COLS = ["problem", "linked_lines", "wrong_lines", "both_lines", "line_of_linked",
        "line_of_wrong", "linked_tags", "wrong_tags", "both_tags", "tag_of_linked", "tag_of_wrong",
        "hint_bytes", "hint_bytes_w", "status"]


def rows() -> list[dict[str, Any]]:
    with (HERE / "selection.csv").open(encoding="utf-8", newline="") as fh:
        probs = [r["problem"] for r in csv.DictReader(fh)]
    out = []
    for p in probs:
        d = hintscfg.RUN / "hints2" / p
        o = netlink.overlap((d / "netlist_linked.v").read_text(encoding="utf-8"),
                            (d / "netlist_w.v").read_text(encoding="utf-8"))
        worst = max(o["tag_of_linked"], o["tag_of_wrong"])
        status = ("no_claims" if o["linked_lines"] == 0 else
                  "excluded" if worst > LIMIT else "ok")
        out.append({"problem": p, **{k: (round(v, 3) if isinstance(v, float) else v)
                                     for k, v in o.items()},
                    "hint_bytes": len((d / "hints.md").read_bytes()),
                    "hint_bytes_w": len((d / "hints_w.md").read_bytes()), "status": status})
    return out


def main() -> int:
    r = rows()
    with (HERE / "wrong_overlap.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, COLS, lineterminator="\n")
        w.writeheader()
        w.writerows(r)
    live = [x for x in r if x["status"] != "no_claims"]
    mean = sum(x["tag_of_linked"] for x in live) / len(live)
    mean_w = sum(x["tag_of_wrong"] for x in live) / len(live)
    mean_l = sum(x["line_of_linked"] for x in live) / len(live)
    hb = sum(x["hint_bytes"] for x in r)
    hw = sum(x["hint_bytes_w"] for x in r)
    print(f"{len(r)} problems, {len(live)} with claims; tag overlap of_linked mean "
          f"{mean:.3f} max {max(x['tag_of_linked'] for x in live):.3f}; of_wrong mean {mean_w:.3f} "
          f"max {max(x['tag_of_wrong'] for x in live):.3f}; line overlap of_linked mean "
          f"{mean_l:.3f}; above {AIM}: "
          f"{sum(max(x['tag_of_linked'], x['tag_of_wrong']) > AIM for x in live)}; excluded "
          f"{[x['problem'] for x in r if x['status'] == 'excluded']}; hint bytes W/B2 "
          f"{hw / hb:.3f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
