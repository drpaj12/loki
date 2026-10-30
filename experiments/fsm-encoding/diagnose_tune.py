"""Q-L3 diagnosis on the TUNE designs only (even design suffix): features of every FSM claim
candidate (``loki.intent.seq`` before the memory rule), one CSV row per candidate.

``diagnose_tune.py ARM FLOOR OUT.csv``. TEST designs (odd suffix) are refused.
"""

from __future__ import annotations

import csv
import importlib
import random
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
lib: Any = importlib.import_module("fsmlib")

import loki.intent.seq as seq  # noqa: E402
from loki.intent import fsm as fsmmod  # noqa: E402
from loki.intent.lower import lower_async_ff  # noqa: E402
from loki.re.fngraph import from_design  # noqa: E402
from loki.re.normalise import load_level0  # noqa: E402


def is_tune(design: str) -> bool:
    return int(design.rsplit("_", 1)[1]) % 2 == 0


def features(graph: Any, q: tuple[int, ...], fsm: Any) -> dict[str, Any]:
    cn = fsmmod.cone_of(graph, q)
    rng = random.Random("diag")
    forced = {} if fsm.reset is None else {fsm.reset[0]: 1 - fsm.reset[1]}
    got = fsmmod._explore(cn, fsm.start, forced)
    rows, _ = got
    k = len(q)
    width = len(next(iter(rows.values())))
    hold_cv = load_cv = other_cv = 0
    for cv in range(width):
        nxt = [rows[s][cv] for s in rows]
        if all(rows[s][cv] == s for s in rows):
            hold_cv += 1
        elif len(set(nxt)) == 1:
            load_cv += 1
        else:
            other_cv += 1
    # cross-bit dependence on sampled states: bit i next changes when another state bit flips
    states = fsmmod._sample_states(k, rng)
    sr = dict(zip(states, cn.step(states, forced), strict=True))
    cross = 0
    for s in states:
        for j in range(k):
            t = s ^ (1 << j)
            if t not in sr:
                continue
            for cv in range(width):
                diff = sr[s][cv] ^ sr[t][cv]
                if diff & ~(1 << j):
                    cross += 1
    fan = max(len({rows[s][cv] for cv in range(width)}) for s in rows)
    return {
        "bits": k, "states": len(rows), "enc": fsm.encoding, "controls": len(fsm.controls),
        "cv": width, "hold_cv": hold_cv, "load_cv": load_cv, "other_cv": other_cv,
        "cross": cross, "fanout_max": fan, "full_code_space": int(len(rows) == 1 << k),
        "has_reset": int(fsm.reset is not None),
    }


def main(argv: list[str]) -> int:
    arm, floor, out = argv[0], argv[1], Path(argv[2])
    rows: list[dict[str, Any]] = []
    orig = seq.read_fsm
    for d in lib.population():
        did = d["design"]
        if not is_tune(did):
            continue
        net = lib.OUT / "build" / arm / did / floor / "netlist.blif"
        graph = from_design(load_level0(net, floor, None, None))
        graph, asyn = lower_async_ff(graph)
        cap: list[dict[str, Any]] = []

        def spy(g: Any, q: Any, seed: str = "fsm", cap: list[dict[str, Any]] = cap) -> Any:
            f = orig(g, q, seed)
            if f is not None:
                cap.append(features(g, tuple(q), f))
            return f

        seq.read_fsm = spy
        claims = seq.sequential_claims(graph, set(asyn))
        seq.read_fsm = orig
        kept = sum(1 for c in claims if c.kind == "fsm")
        for f in cap:
            rows.append({"design": did, "role": d["role"], "arm": arm, "floor": floor, **f,
                         "n_fsm_claims": kept})
    with out.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, list(rows[0]), lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    print(len(rows), "candidates")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
