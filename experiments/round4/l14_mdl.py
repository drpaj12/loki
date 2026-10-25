"""RQ-L14 MDL readability: description length of references and recovered RTL.

Writes ``l14_mdl.csv`` (one row per design and variant). Variants: ``ref``; ``l0-f2``, ``l0-f3``
(L0 ``netlist.v``); ``f2-none``, ``f3-none``, ``f2-calib``, ``f3-calib`` (``design.v`` of the
round-2 runs); ``llm`` (mean over the functionally correct round-1 samples of the design).
Similarity columns come from the round-2 ``astcfg.json`` (empty when unavailable).
"""

from __future__ import annotations

import json
import os
from collections import Counter
from pathlib import Path
from typing import Any

import mdl
import r4lib

REFS = Path(os.environ.get("VERILOG_EVAL", str(r4lib.WS / "external" / "verilog-eval"))) \
    / "dataset_spec-to-rtl"
GB = Path(os.environ.get("LOKI_GB2", str(r4lib.WORK / "gatebreaker-exp2" / "data")))
RUNVARS = ("f2-none", "f3-none", "f2-calib", "f3-calib")


def main() -> int:
    refs = sorted(REFS.glob("*_ref.sv"))
    model = mdl.Model()
    own: dict[str, Counter[str]] = {}
    texts: dict[str, str] = {}
    for p in refs:
        texts[p.stem] = p.read_text(encoding="utf-8")
        own[p.stem] = model.add(texts[p.stem])
    ast = {r["design"]: r for r in json.loads(
        (r4lib.R2DATA / "l2" / "astcfg.json").read_text(encoding="utf-8"))}
    ok_llm: dict[str, list[str]] = {}
    val = json.loads((GB / "validations" / "validations.json").read_text(encoding="utf-8"))
    for v in val:
        if v["category"] == "success":
            ok_llm.setdefault(v["design"], []).append(Path(v["rtl"]).name)
    rows: list[list[Any]] = []
    for e in r4lib.manifest(r4lib.VEVAL)["designs"]:
        des = str(e["design"])
        stem = des.removeprefix("ve_") + "_ref"
        if stem not in texts:
            continue
        ref_dl = model.dl(texts[stem], own[stem])
        a = ast.get(des, {})

        def row(variant: str, dl: float, ntok: int, key: str, ctx: tuple[Any, ...] = ()) -> None:
            rows.append([ctx[0], ctx[1], variant, ntok, round(dl, 3), round(ctx[2], 3),
                         round(dl / ctx[2], 6) if ctx[2] else "", ctx[3].get(f"{key}:ast", ""),
                         ctx[3].get(f"{key}:cfg", "")])

        ctx = (des, e["split"], ref_dl, a)
        row("ref", ref_dl, len(mdl.tokens(texts[stem])), "", ctx)
        for fl in ("f2", "f3"):
            p = r4lib.VEVAL / des / fl / "netlist.v"
            if p.is_file():
                t = p.read_text(encoding="utf-8")
                row(f"l0-{fl}", model.dl(t), len(mdl.tokens(t)), f"{fl}-l0", ctx)
        for var in RUNVARS:
            fl = var.split("-")[0]
            p = r4lib.R2DATA / "l2" / "runs" / var / f"{des}__{fl}" / "re" / "design.v"
            if p.is_file():
                t = p.read_text(encoding="utf-8")
                row(var, model.dl(t), len(mdl.tokens(t)), var, ctx)
        names = ok_llm.get(stem, [])
        if names:
            dls = []
            nts = []
            for nm in names:
                t = (GB / "llm" / stem / nm).read_text(encoding="utf-8")
                dls.append(model.dl(t))
                nts.append(len(mdl.tokens(t)))
            row("llm", sum(dls) / len(dls), round(sum(nts) / len(nts)), "llm", ctx)
    r4lib.write_csv(r4lib.OUT / "l14_mdl.csv",
                    ["design", "split", "variant", "tokens", "dl", "ref_dl", "ratio", "ast",
                     "cfg"], rows)
    print(len(rows), "rows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
