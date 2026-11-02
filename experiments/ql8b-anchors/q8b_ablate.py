"""Per-class effect on VALIDATION and the choice of the headline set: ``python -B q8b_ablate.py``.

For each class alone: constructs right at the path end with it and not in #74 (gained), the reverse
(lost), the net, and the anchor precision of its blocks. Writes results/ablation_VALIDATION.csv and
results/chosen.json (the classes with a non-negative net effect; ties keep the class).
"""

from __future__ import annotations

import json
import sys
from typing import Any

import q8b_anchors as qa
import q8b_env as env
import q8b_feat as feat

q7s = env.mod("q7_score")


def end_rows(var: str, split: str) -> tuple[list[Any], list[dict[str, Any]]]:
    units = feat.load(var, split)
    return units, list(q7s.score(units, [[bp.n - 1 for bp in u.blocks] for u in units])[0])


def precision(units: list[Any], kind: str) -> dict[str, int]:
    """Blocks of an anchor kind: all, touching a construct at the anchor, right at the path end."""
    n = t = r = 0
    for u in units:
        for bp in u.blocks:
            if bp.anchor_kind != kind:
                continue
            n += 1
            t += int(bp.inter[:, 0].sum() > 0) if bp.inter.shape[0] else 0
            r += int(bp.right[:, -1].any()) if bp.inter.shape[0] else 0
    return {"blocks": n, "touch_at_anchor": t, "right_at_end": r}


def main(argv: list[str]) -> int:
    split = argv[0] if argv else "VALIDATION"
    _, old = end_rows("OLD", split)
    rows, keep = [], []
    for cls in qa.CLASSES:
        units, new = end_rows(cls, split)
        gained = sum(1 for a, b in zip(old, new, strict=True) if b["right"] and not a["right"])
        lost = sum(1 for a, b in zip(old, new, strict=True) if a["right"] and not b["right"])
        rows.append({"split": split, "class": cls, "constructs": len(old),
                     "old_right": sum(r["right"] for r in old),
                     "new_right": sum(r["right"] for r in new), "gained": gained, "lost": lost,
                     "net": gained - lost, **precision(units, cls)})
        if gained - lost >= 0:
            keep.append(cls)
    env.l3dlib.write_csv(env.RES / f"ablation_{split}.csv", list(rows[0]), rows)
    cfg = {"classes": keep, "variant": "+".join(keep)}
    (env.RES / "chosen.json").write_text(json.dumps(cfg, sort_keys=True) + "\n", encoding="utf-8")
    for r in rows:
        print(r)
    print(cfg)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
