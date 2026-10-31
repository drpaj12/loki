"""Partition-level signatures and library matching: ``python -B partitions.py [JOBS]``.

A partition is a state group of the L1 claims (flip-flop output nets of counter, register,
shift_reg, lfsr, fsm and ff_* claims, merged when their output sets overlap) grown to the union
of the fan-in
cones of its output nets (write_dot's ``cone(NET)``, which crosses flip-flops). The pass counts the
induced subgraph (``--cells``, halo 0, Odin III global-signal rule). Each partition is matched with
the library of every width (all entries, or only entries whose measured flip-flop count equals the
group's). Output: $GLET_OUT/match/part_scores.jsonl, one line per (set, design, cell, mode, group).
Sets: ``single`` (L3 v0 single-pattern designs), ``comp`` (the composites).
"""

from __future__ import annotations

import json
import os
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "l3-detector"))
import l3dlib  # noqa: E402
import live  # noqa: E402
import match_run as mr  # noqa: E402
import sigs  # noqa: E402

from loki.l3.netlist import Netlist  # noqa: E402

STATE_KINDS = ("counter", "register", "shift_reg", "lfsr", "fsm", "ff_en", "ff_srst", "ff_sen",
               "ff_arst", "ff")
MAX_WORK = 3e8
OUT = live.OUT


def state_groups(claims: list[dict[str, Any]]) -> list[list[str]]:
    """Flip-flop output net sets of the claims, merged on overlap (union-find)."""
    parent: dict[str, str] = {}

    def find(x: str) -> str:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for c in claims:
        if c["kind"] not in STATE_KINDS:
            continue
        qs = [n for k in ("q", "Q") for n in c.get("nets", {}).get(k, [])]
        for n in qs:
            parent.setdefault(n, n)
        for n in qs[1:]:
            parent[find(n)] = find(qs[0])
    groups: dict[str, list[str]] = {}
    for n in parent:
        groups.setdefault(find(n), []).append(n)
    return sorted((sorted(g) for g in groups.values()), key=lambda g: g[0])


def bounded_cone(nl: Netlist, qs: list[str], other_q: dict[str, int]
                 ) -> tuple[set[str], dict[int, int]]:
    """Nets of the cone of one state group that stops at the flip-flop outputs of other state
    groups (``other_q``: net -> group index) and at primary inputs. Returns (member nets whose
    driver node belongs to the partition, {other group: fewest combinational cells crossed from
    that group's output to this group's flip-flop inputs})."""
    producer: dict[str, int] = {}
    for i, (_ins, outs) in enumerate(nl.cells):
        for o in outs:
            producer[o] = i
    latch_d = {q: d for d, q in nl.latches}
    own = set(qs)
    seen: dict[str, int] = {}  # net -> combinational cells crossed since the flip-flop input
    links: dict[int, int] = {}
    frontier = [(q, 0) for q in qs]
    while frontier:
        net, depth = frontier.pop()
        if net in seen and seen[net] <= depth:
            continue
        if net in other_q and net not in own:
            links[other_q[net]] = min(links.get(other_q[net], depth), depth)
            continue
        seen[net] = depth
        if net in latch_d:  # an own flip-flop, or an unclaimed one (glue): walk through to its D
            frontier.append((latch_d[net], 0 if net in own else depth + 1))
            continue
        i = producer.get(net)
        if i is None:
            continue  # primary input (kept as a member: its port node)
        for n in nl.cells[i][0]:
            frontier.append((n, depth + 1))
    return set(seen), links


def partitions_of(netlist: Path, qgroups: list[list[str]], bounded: bool = False
                  ) -> list[dict[str, Any]]:
    """Per group: node ids (cone union), then the two signatures (both modes) of that subgraph."""
    import odin3

    out: list[dict[str, Any]] = []
    tmp = OUT / "tmp"
    tmp.mkdir(exist_ok=True)
    cells = tmp / f"cells_{os.getpid()}.txt"
    nl = Netlist.read(netlist)
    other = {q: gi for gi, g in enumerate(qgroups) for q in g}
    with odin3.Design.read_blif(netlist, techlibs=[sigs.VTR_LIB]) as d:
        mod = d.top()
        for gi, qs in enumerate(qgroups):
            rec: dict[str, Any] = {"gi": gi, "ff": len(qs)}
            try:
                idset: set[int] = set()
                if bounded:
                    nets, links = bounded_cone(nl, qs, other)
                    rec["links"] = [[g, k] for g, k in sorted(links.items())]
                    for n in nets:
                        net = mod.net(n)
                        pin = net.driver() if net is not None else None
                        if pin is not None:
                            idset.add(pin.node().id)
                # the pass takes at most 8 foci per call
                for k in range(0, 0 if bounded else len(qs), 8):
                    res = d.graphlets(exclude_global=True, per_node=True,
                                      focus=[f"cone({q})" for q in qs[k:k + 8]],
                                      max_work=int(MAX_WORK))
                    idset |= {n["id"] for g in res["groups"] for n in g["node_vectors"]}
                ids = sorted(idset)
                cells.write_text("@p\n" + "\n".join(str(i) for i in ids) + "\n", encoding="utf-8")
                for mode, directed in sigs.MODES.items():
                    r = d.graphlets(exclude_global=True, directed=directed, cells=cells,
                                    max_work=int(MAX_WORK))
                    g = r["groups"][0]
                    g["mode"] = r["mode"]
                    rec[mode] = g
            except Exception as exc:  # work cap or cone failure: recorded
                rec["error"] = str(exc)[:80]
            out.append(rec)
    return out


BOUNDED = os.environ.get("GLET_BOUNDED", "") == "1"


def one(job: tuple[str, str, str, str, str]) -> list[dict[str, Any]]:
    kind, name, cell, net, intent = job
    if not mr._LIB:
        mr.load_lib()
    claims = json.loads(Path(intent).read_text(encoding="utf-8"))["claims"]
    qgroups = state_groups(claims)
    rows: list[dict[str, Any]] = []
    for rec in partitions_of(Path(net), qgroups, BOUNDED):
        for mode in sigs.MODES:
            row: dict[str, Any] = {"set": kind, "design": name, "cell": cell, "mode": mode,
                                   "gi": rec["gi"], "ff": rec["ff"], "n_groups": len(qgroups),
                                   "links": rec.get("links", [])}
            if "error" in rec or mode not in rec:
                row["error"] = rec.get("error", "")
                rows.append(row)
                continue
            g = rec[mode]
            row["nodes"], row["edges"] = g["nodes"], g["edges"]
            q = mr.prep(g)
            for tag in ("all", "ff"):
                best: dict[str, list[Any]] = {}
                for inst, eff, s in mr._LIB[(cell, mode)]:
                    if tag == "ff" and eff != rec["ff"]:
                        continue
                    gg, cc = mr.sim(q, s)
                    cur = best.get(inst.pattern)
                    if cur is None or gg + cc > cur[0] + cur[1]:
                        best[inst.pattern] = [gg, cc, inst.name]
                row[tag] = best
            rows.append(row)
        if not qgroups:
            break
    if not qgroups:
        rows.append({"set": kind, "design": name, "cell": cell, "mode": "none", "n_groups": 0})
    return rows


def jobs() -> list[tuple[str, str, str, str, str]]:
    out = []
    lab_designs = {(j[1], j[2]) for j in mr.l3_jobs() if j[3] == "undirected"}
    for d, cell in sorted(lab_designs):
        out.append(("single", d, cell, str(l3dlib.netlist_path(l3dlib.CENSUS, cell, d)),
                    str(l3dlib.intent_path(l3dlib.CENSUS, cell, d))))
    for r in l3dlib.read_csv(l3dlib.RES / "composites.csv"):
        for cell in l3dlib.CELLS:
            net = l3dlib.netlist_path(l3dlib.OUT, cell, r["name"])
            ij = l3dlib.intent_path(l3dlib.OUT, cell, r["name"])
            if net.is_file() and ij.is_file():
                out.append(("comp", r["name"], cell, str(net), str(ij)))
    return out


def main(argv: list[str]) -> int:
    n = int(argv[0]) if argv else 10
    todo = jobs()
    with ProcessPoolExecutor(n) as pool:
        res = list(pool.map(one, todo, chunksize=2))
    p = OUT / "match" / ("part_scores_bounded.jsonl" if BOUNDED else "part_scores.jsonl")
    with p.open("w", encoding="utf-8") as fh:
        for rows in res:
            for r in rows:
                fh.write(json.dumps(r, sort_keys=True) + "\n")
    errs = sum(1 for rows in res for r in rows if r.get("error"))
    print(len(todo), "designs;", sum(len(r) for r in res), "rows;", errs, "partition errors")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
