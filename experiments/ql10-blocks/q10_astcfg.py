"""AST and CFG similarity of the Q-L10 rows to the VerilogEval reference (Gate-Breaker's measures).

No model call. AST: Gate-Breaker Algorithm 2 (pyverilog, depth 3,
``gatebreaker-exp2/scripts/metrics.py``, read only, as round 2 used it). CFG: Algorithm 3 over
Odin III's elaborated AST (the probe of odin3 commit 77e975e5, extracted unchanged to
``$QL10_OUT/cfg-probe/odin3_cfg.py``, the file round 2 used). Both are imported, not copied.
Candidates, per (problem, draw):
  A          the arm A reply of the full run (archive ``loki-llm-full-run.tar.xz``, extracted to
             ``$QL10_OUT/llmfull``), the code between [BEGIN] and [DONE], top ``TopModule``
  A-flat     the same, written through the same Odin III ``flatten; write_verilog`` as D-flat
             (control)
  D / Dh     the assembled ``sample.sv`` (``TopModule`` + ``Block_<k>`` modules), top module only
  D-flat / Dh-flat   the assembled design flattened to one module by Odin III (``hierarchy; proc;
             flatten; write_verilog``, top module kept), as ``f3-recovery/tools/flatten_astcfg.py``
A value is absent when pyverilog or Odin III cannot read the file (reason in ``*_err``), or the CFG
has more than 12,000 nodes. Usage: ``python -B q10_astcfg.py`` (env.sh sourced); writes
``results/astcfg_rows.csv``. Resumable: rows already in the csv are kept.
"""

from __future__ import annotations

import csv
import importlib
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

import q10_env as env

HERE = Path(__file__).resolve().parent
RUN = env.RUN
GB = env.WS / "work" / "gatebreaker-exp2" / "scripts"
PROBE = RUN / "cfg-probe"
REFS = env.WS / "external" / "verilog-eval" / "dataset_spec-to-rtl"
FULL = RUN / "llmfull" / "run" / "responses" / "A"
ODIN3 = env.WS / "odin3" / "build" / "rel-main2" / "odin3"
SCRATCH = RUN / "astcfg-scratch"
NODE_LIMIT = 12000
FIELDS = ["problem", "tier", "quartile", "arm", "draw", "variant", "ast", "cfg", "ast_err",
          "cfg_err"]
Ent = dict[str, Any]


def load_tools() -> tuple[Any, Any]:
    for p in (GB, PROBE):
        if str(p) not in sys.path:
            sys.path.insert(0, str(p))
    os.environ.setdefault("ODIN3_LIB", str(ODIN3.parent / "libodin3.so"))
    os.environ.setdefault("ODIN3_SLANG_LIB", str(ODIN3.parent / "libodin3_slang.so"))
    return importlib.import_module("metrics"), importlib.import_module("odin3_cfg")


def clean(src: Path, name: str) -> Path:
    """A copy without ``(* ... *)`` attributes, as round 2 parses them."""
    out = SCRATCH / name
    out.write_text(re.sub(r"\(\*.*?\*\)", "", src.read_text(encoding="utf-8"), flags=re.S),
                   encoding="utf-8", newline="\n")
    return out


def flatten(src: Path, dst: Path, top: str) -> None:
    script = (f'read_verilog "{src}"; hierarchy --top {top}; proc; flatten; '
              f'write_verilog "{dst}"')
    subprocess.run([str(ODIN3), "--top", top, "-p", script], check=True, capture_output=True,
                   text=True, timeout=300)
    text = dst.read_text(encoding="utf-8")
    starts = [m.start() for m in re.finditer(r"(?m)^module\s", text)]
    if len(starts) > 1:
        cut = text[: starts[1]]
        last = cut.rfind("endmodule")
        dst.write_text(cut[: last + len("endmodule")] + "\n" if last >= 0 else cut,
                       encoding="utf-8", newline="\n")


class Scorer:
    def __init__(self) -> None:
        self.m, self.cfg = load_tools()
        self.binding = self.cfg.load_binding()
        self.cfg.ensure_sanitizer_preload(self.binding)
        self.refs: dict[str, tuple[Any, Any, str, str]] = {}

    def reference(self, problem: str) -> tuple[Any, Any, str, str]:
        if problem not in self.refs:
            path = REFS / f"{problem}_ref.sv"
            mod, cfg, e1, e2 = None, None, "", ""
            try:
                mod = self.m.parse_module(str(clean(path, f"ref_{problem}.sv")))
            except Exception as err:
                e1 = f"{type(err).__name__}: {str(err)[:80]}"
            try:
                cfg = self.cfg_of(path, "RefModule")
            except Exception as err:
                e2 = f"{type(err).__name__}: {str(err)[:80]}"
            self.refs[problem] = (mod, cfg, e1, e2)
        return self.refs[problem]

    def cfg_of(self, path: Path, top: str) -> Any:
        design = self.cfg.read_design(self.binding, path)
        try:
            return self.cfg.design_cfg(design, top)
        finally:
            design.close()

    def score(self, problem: str, cand: Path, top: str) -> dict[str, Any]:
        ref_mod, ref_cfg, e1, e2 = self.reference(problem)
        out: dict[str, Any] = {"ast": "", "cfg": "", "ast_err": e1, "cfg_err": e2}
        if ref_mod is not None:
            try:
                gen = self.m.parse_module(str(clean(cand, f"cand_{problem}.sv")), top)
                out["ast"] = round(float(self.m.ast_similarity(ref_mod, gen, depth=3)), 6)
            except Exception as err:
                out["ast_err"] = f"{type(err).__name__}: {str(err)[:80]}"
        if ref_cfg is not None:
            try:
                g = self.cfg_of(cand, top)
                if max(len(g), len(ref_cfg)) > NODE_LIMIT:
                    raise ValueError(f"skipped: CFG over {NODE_LIMIT} nodes")
                out["cfg"] = round(float(self.cfg.cfg_similarity(ref_cfg, g)), 6)
            except Exception as err:
                out["cfg_err"] = f"{type(err).__name__}: {str(err)[:80]}"
        return out


def a_code(problem: str, draw: int) -> str | None:
    f = FULL / str(draw) / f"{problem}.txt"
    if not f.is_file():
        return None
    code, ok = env.mod("collect").extract_rtl(f.read_text(encoding="utf-8", errors="replace"))
    return code if ok else None


def work_items(designs: dict[str, Ent], rows: list[dict[str, str]]) -> list[tuple[Ent, str, int]]:
    out: list[tuple[Ent, str, int]] = []
    seen_a: set[tuple[str, int]] = set()
    for r in rows:
        d = designs[r["problem"]]
        if r["outcome"] not in ("pass", "runtime") or d["tier"] == "ext":
            continue
        out.append((d, r["arm"], int(r["draw"])))
        if (d["problem"], int(r["draw"])) not in seen_a:
            seen_a.add((d["problem"], int(r["draw"])))
            out.append((d, "A", int(r["draw"])))
    return out


def main() -> int:
    import json
    SCRATCH.mkdir(parents=True, exist_ok=True)
    os.chdir(SCRATCH)  # pyverilog writes parser tables to the working directory
    designs = {d["problem"]: d for d in json.loads((HERE / "designs.json").read_text("utf-8"))}
    res = list(csv.DictReader((HERE / "results" / "results.csv").open(encoding="utf-8")))
    outp = HERE / "results" / "astcfg_rows.csv"
    done: list[dict[str, str]] = []
    if outp.is_file():
        done = list(csv.DictReader(outp.open(encoding="utf-8")))
    have = {(r["problem"], r["arm"], r["draw"], r["variant"]) for r in done}
    sc = Scorer()
    for d, arm, draw in work_items(designs, res):
        p = d["problem"]
        variants: list[tuple[str, Path | None]] = []
        if arm == "A":
            code = a_code(p, draw)
            src = None
            if code is not None:
                src = SCRATCH / f"A_{p}_{draw}.sv"
                src.write_text(code, encoding="utf-8", newline="\n")
            variants = [("raw", src), ("flat", src)]
        else:
            src = RUN / "work" / p / f"top-{arm}-{draw}" / "sample.sv"
            variants = [("asm", src), ("flat", src)]
        for var, path in variants:
            if (p, arm, str(draw), var) in have:
                continue
            row: dict[str, Any] = {"problem": p, "tier": d["tier"], "quartile": d["quartile"],
                                   "arm": arm, "draw": draw, "variant": var, "ast": "", "cfg": "",
                                   "ast_err": "", "cfg_err": ""}
            if path is None or not path.is_file():
                row["ast_err"] = row["cfg_err"] = "no code"
            else:
                use = path
                if var == "flat":
                    use = SCRATCH / f"flat_{arm}_{p}_{draw}.v"
                    try:
                        flatten(path, use, "TopModule")
                    except Exception as err:
                        use = None  # type: ignore[assignment]
                        row["ast_err"] = row["cfg_err"] = f"flatten {type(err).__name__}"
                if use is not None:
                    row.update(sc.score(p, use, "TopModule"))
            done.append({k: str(row[k]) for k in FIELDS})
            with outp.open("w", encoding="utf-8", newline="") as fh:
                w = csv.DictWriter(fh, FIELDS, lineterminator="\n")
                w.writeheader()
                w.writerows(done)
        print(p, arm, draw, flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
