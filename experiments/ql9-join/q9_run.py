"""Apply configs to the #77 blocks of a split: ``python -B q9_run.py STAGE SPLIT [JOBS]``.

STAGE names a config list of q9_cfg (the tuning stages and the TEST run). One process per unit
runs every config of the stage on that unit, sharing the signature and evidence caches.
Results: $QL9_OUT/res_<STAGE>_<SPLIT>.pkl, a list of per-unit records. Smallest unit first, at
most 2 processes.
"""

from __future__ import annotations

import pickle
import sys
from concurrent.futures import ProcessPoolExecutor
from typing import Any

import q9_cfg as cfgs
import q9_env as env
import q9_evid as qe
import q9_net as nt
import q9_rules as rules
import q9_score as sc
import q9_units as un
from q9_rules import Config

qn = env.mod("q6_net")
qs = env.mod("q6_sig")
qt = env.mod("q6_truth")


def run_unit(args: tuple[str, str, str, str, str, bool, list[Config]]) -> dict[str, Any]:
    split, kind, design, cell, tsplit, want_kind, configs = args
    u = next(x for x in qt.units(tsplit, (cell,)) if x.set == kind and x.design == design)
    g = qn.Graph.read(u.net)
    cons = un.answer_key(u, g)
    start = un.start_blocks(split, u)
    sig = qs.SigCounter(u.net, g.b)
    need_m2 = any("EM2" in c.sources for c in configs) or want_kind
    evid = qe.Evid(g, sig, cell, qe.load_m2() if need_m2 else None)
    links = nt.Links(g)
    out: dict[str, Any] = {"key": u.key, "n_cells": g.b.n, "cfg": {}}
    for c in [None, *configs]:
        blocks, nj, ns = (start, 0, 0) if c is None else rules.apply(c, start, links, evid)
        rec: dict[str, Any] = {"rows": sc.construct_rows(u.key, blocks, cons), "joins": nj,
                               "splits": ns, "n_blocks": len(blocks)}
        if want_kind:
            rec["kind"] = sc.kind_tally(blocks, cons,
                                        [evid.post("EM2", b.cells) for b in blocks])
        out["cfg"]["BASE" if c is None else c.name] = rec
    sig.close()
    return out


def main(argv: list[str]) -> int:
    stage, split = argv[0], argv[1]
    n_jobs = min(int(argv[2]) if len(argv) > 2 else 2, 2)
    configs = cfgs.stage(stage)
    want_kind = stage.startswith("test")
    us = un.units(split)
    keys = [(split, u.set, u.design, u.cell, u.split, want_kind, configs) for u in us]
    with ProcessPoolExecutor(n_jobs) as pool:
        res = list(pool.map(run_unit, keys, chunksize=1))
    env.OUT9.mkdir(parents=True, exist_ok=True)
    with (env.OUT9 / f"res_{stage}_{split}.pkl").open("wb") as fh:
        pickle.dump(res, fh)
    print(stage, split, len(res), "units", len(configs), "configs")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
