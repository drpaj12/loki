"""RQ-L11: the feedback register -> decoder -> select/enable chain in the ground truth, and how
many of its elements the detectors propose. Definitions: ``EXPERIMENT.md`` (round 3).
Writes ``l11_gt.csv`` and ``l11_detect.csv``.
"""

from __future__ import annotations

import json
from collections import defaultdict, deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import r3lib

from loki.score.gt import STORAGE, GtInstance, derive_instances
from loki.score.match import jaccard
from loki.score.metrics import Pred

LOGIC = frozenset({"$not", "$and", "$or", "$xor", "$xnor", "$logic_not", "$logic_and",
                   "$logic_or", "$reduce_and", "$reduce_or", "$reduce_bool"})
FB_DEPTH = 6
SINK_DEPTH = 2
EN_PORTS = ("EN", "SRST")


@dataclass
class Chains:
    fb: set[int]
    fb_fsm: set[int]
    dec: dict[int, set[int]]            # decoder -> feedback registers it reads
    sinks: dict[int, set[int]]          # sink -> decoders (on feedback registers) reaching it
    any_sinks: dict[int, set[int]]      # sink -> any constant-compare decoders reaching it
    mux_s: set[int]                     # muxes with an S edge
    en_words: set[int]                  # storage words with an EN or SRST edge
    sink_kind: dict[int, str]


def analyse(words: dict[str, Any]) -> Chains:
    by_id = {int(w["id"]): w for w in words["words"]}
    typ = {i: str(w["type"]) for i, w in by_id.items()}
    out: dict[int, list[tuple[int, str, str]]] = defaultdict(list)
    for e in words["edges"]:
        out[int(e["src"])].append((int(e["dst"]), str(e["src_port"]), str(e["dst_port"])))
    storage = {i for i, t in typ.items() if t in STORAGE}
    fb = {s for s in storage if _is_feedback(s, out, typ)}
    fb_fsm = {s for s in fb if by_id[s].get("fsm")}
    const_cmp = {i for i, t in typ.items()
                 if t in ("$eq", "$ne") and by_id[i].get("const_ports")}
    dec: dict[int, set[int]] = defaultdict(set)
    for s in fb:
        for dst, sp, _dp in out[s]:
            if sp == "Q" and dst in const_cmp:
                dec[dst].add(s)
    sinks: dict[int, set[int]] = defaultdict(set)
    kinds: dict[int, str] = {}
    for d in dec:
        for x, kind in _reach_sinks(d, out, typ):
            sinks[x].add(d)
            kinds[x] = kind
    any_sinks: dict[int, set[int]] = defaultdict(set)
    for d in const_cmp:
        for x, kind in _reach_sinks(d, out, typ):
            any_sinks[x].add(d)
            kinds[x] = kind
    mux_s = {dst for edges in out.values() for dst, _sp, dp in edges
             if dp == "S" and typ[dst] in ("$mux", "$pmux")}
    en_words = {dst for edges in out.values() for dst, _sp, dp in edges
                if dp in EN_PORTS and dst in storage}
    return Chains(fb, fb_fsm, dict(dec), dict(sinks), dict(any_sinks), mux_s, en_words, kinds)


def _is_feedback(s: int, out: dict[int, list[tuple[int, str, str]]], typ: dict[int, str]) -> bool:
    seen = {s}
    work: deque[tuple[int, int]] = deque()
    for dst, sp, dp in out[s]:
        if sp == "Q":
            if dst == s and dp == "D":
                return True
            work.append((dst, 1))
    while work:
        w, depth = work.popleft()
        if w in seen or typ[w] in STORAGE or depth > FB_DEPTH:
            continue
        seen.add(w)
        for dst, _sp, dp in out[w]:
            if dst == s and dp == "D":
                return True
            work.append((dst, depth + 1))
    return False


def _reach_sinks(d: int, out: dict[int, list[tuple[int, str, str]]],
                 typ: dict[int, str]) -> list[tuple[int, str]]:
    found: dict[int, str] = {}
    work: deque[tuple[int, int]] = deque([(d, 0)])
    seen = {d}
    while work:
        w, mid = work.popleft()
        for dst, _sp, dp in out[w]:
            if dp == "S" and typ[dst] in ("$mux", "$pmux"):
                found[dst] = "mux_s"
            elif dp in EN_PORTS and typ[dst] in STORAGE:
                found[dst] = "enable"
            elif typ[dst] in LOGIC and mid < SINK_DEPTH and dst not in seen:
                seen.add(dst)
                work.append((dst, mid + 1))
    return sorted(found.items())


def gt_row(ds: str, floor: str, designs: list[str], rs_root: Path) -> list[object]:
    t: dict[str, int] = defaultdict(int)
    for d in designs:
        words = json.loads((rs_root / d / floor / "words.json").read_text("utf-8"))
        c = analyse(words)
        n_ch = sum(len(c.dec[dd]) for decs in c.sinks.values() for dd in decs)
        t["designs"] += 1
        t["designs_with_fb"] += 1 if c.fb else 0
        t["designs_with_chain"] += 1 if c.sinks else 0
        t["fb"] += len(c.fb)
        t["fb_fsm"] += len(c.fb_fsm)
        t["decoders"] += len(c.dec)
        t["sinks"] += len(c.sinks)
        t["chains"] += n_ch
        t["mux_s"] += len(c.mux_s)
        t["mux_s_chain"] += sum(1 for x in c.sinks if x in c.mux_s)
        t["mux_s_any"] += sum(1 for x in c.any_sinks if x in c.mux_s)
        t["en_words"] += len(c.en_words)
        t["en_chain"] += sum(1 for x in c.sinks if x in c.en_words)
        t["en_any"] += sum(1 for x in c.any_sinks if x in c.en_words)
    keys = ["designs", "designs_with_fb", "designs_with_chain", "fb", "fb_fsm", "decoders",
            "sinks", "chains", "mux_s", "mux_s_chain", "mux_s_any", "en_words", "en_chain",
            "en_any"]
    return [ds, floor, *(t[k] for k in keys)]


def element_gid(gts: dict[str, GtInstance], wid: int, as_register: bool) -> GtInstance | None:
    if as_register and f"r{wid}" in gts:
        return gts[f"r{wid}"]
    return gts.get(f"w{wid}")


def proposed(g: GtInstance, preds: list[Pred],
             by_cell: dict[str, list[int]]) -> tuple[int, int, int]:
    """(proposed, kind-correct, committed) as 0/1 for the best-overlapping counted candidates."""
    near = {i for c in g.footprint for i in by_cell.get(c, ())}
    prop = kc = com = 0
    for i in sorted(near):
        p = preds[i]
        if jaccard(p.cells, g.footprint) >= 0.5:
            prop = 1
            kc |= 1 if g.type in p.types() else 0
            com |= 1 if p.committed else 0
    return prop, kc, com


def detect_rows(name: str, rs: r3lib.RunSet) -> list[list[object]]:
    acc: dict[str, list[int]] = defaultdict(lambda: [0, 0, 0, 0])
    chains = complete = complete_kc = 0
    fsm_gt = fsm_hit = 0
    for d in r3lib.run_designs(rs):
        words = r3lib.read_words(rs, d)
        c = analyse(words)
        gts = {g.gid: g for g in derive_instances(words)}
        preds = r3lib.counted_preds(rs, d)
        by_cell: dict[str, list[int]] = defaultdict(list)
        for i, p in enumerate(preds):
            for cell in p.cells:
                by_cell[cell].append(i)
        for g in gts.values():
            if g.type == "fsm":
                fsm_gt += 1
                fsm_hit += 1 if any(p.kind == "fsm" and jaccard(p.cells, g.footprint) >= 0.5
                                    for p in preds) else 0
        roles: dict[str, set[int]] = {"fb_register": c.fb, "decoder": set(c.dec),
                                      "sink": set(c.sinks)}
        res: dict[tuple[str, int], tuple[int, int, int]] = {}
        for role, ids in roles.items():
            for wid in sorted(ids):
                el_g = element_gid(gts, wid, role == "fb_register")
                if el_g is None:
                    continue
                res[(role, wid)] = proposed(el_g, preds, by_cell)
                row = acc[role]
                row[0] += 1
                row[1] += res[(role, wid)][0]
                row[2] += res[(role, wid)][1]
                row[3] += res[(role, wid)][2]
        for x, decs in sorted(c.sinks.items()):
            for dd in sorted(decs):
                for s in sorted(c.dec[dd]):
                    el = [res.get(("fb_register", s)), res.get(("decoder", dd)),
                          res.get(("sink", x))]
                    if None in el:
                        continue
                    chains += 1
                    complete += 1 if all(e and e[0] for e in el) else 0
                    complete_kc += 1 if all(e and e[1] for e in el) else 0
    out: list[list[object]] = [[name, role, *acc[role]] for role in roles_order()]
    out.append([name, "chain", chains, complete, complete_kc, 0])
    out.append([name, "fsm_instance", fsm_gt, fsm_hit, 0, 0])
    return out


def roles_order() -> tuple[str, ...]:
    return ("fb_register", "decoder", "sink")


def main() -> int:
    gt_out = [gt_row("micro", f, r3lib.designs_of(r3lib.MICRO, f), r3lib.MICRO)
              for f in ("f2", "f3", "f1-k6")]
    gt_out += [gt_row("veval", f, r3lib.designs_of(r3lib.VEVAL, f), r3lib.VEVAL)
               for f in ("f2", "f3")]
    r3lib.write_csv(r3lib.HERE / "l11_gt.csv",
                    ["dataset", "floor", "designs", "designs_with_fb", "designs_with_chain",
                     "fb_registers", "fb_fsm_flagged", "decoders", "sinks", "chains", "muxes_s",
                     "muxes_s_chain", "muxes_s_any_decoder", "enabled_words", "enabled_chain",
                     "enabled_any_decoder"], gt_out)
    det: list[list[object]] = []
    for name, rs in r3lib.SETS.items():
        if r3lib.run_designs(rs):
            det += detect_rows(name, rs)
            print("done", name, flush=True)
    r3lib.write_csv(r3lib.HERE / "l11_detect.csv",
                    ["set", "element", "n", "proposed_j05", "kind_correct", "committed"], det)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
