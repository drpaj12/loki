"""Provenance chain completeness of the Q-L13 flow runs (no model call).

Per design (``$QL13_OUT/<name>/out/prov``, read by ``loki.prov_steps``): the flow status, the
checks (equiv-check, LVS), the extracted cells by class, (a) the name-free join share, (b) the full
chain share, and the failure catalogue. Definitions: ``EXPERIMENT.md``. Writes ``results/flow.csv``,
``results/chain.csv``, ``results/catalogue.csv``, ``results/weakest.csv``.
Usage: ``python3 -B ql13_chain.py``.
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
import sys
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import ql13_env as env

sys.path.insert(0, str(env.REPO))
from loki.prov_steps import ProvError, ProvObject, ProvRun, read_run, resolve  # noqa: E402

FILLER_RE = re.compile(r"__(tap|fill|decap|diode)")
STAGE_ORDER = ("extracted", "gds", "routed", "placed", "gates", "ir", "hdl")
CLASSES = ("logic", "tap", "fill", "cts_buffer", "repair_buffer", "hold_buffer", "tie",
           "other_physical", "unjoined")
INSERTED = ("cts_buffer", "repair_buffer", "hold_buffer", "tie", "other_physical")


@dataclass
class Chain:
    """The chain of one extracted cell: stages reached in order, weakest link, HDL spans, the
    last link kind and the break (None when the chain is complete)."""

    cls: str
    stages: list[str] = field(default_factory=list)
    weakest: str = ""
    spans: list[str] = field(default_factory=list)
    last_kind: str = ""
    own_span: str = ""  # first source span of the gates object on the path ("line.col-line.col")
    broken_at: str = ""
    cause: str = ""

    @property
    def complete(self) -> bool:
        return not self.broken_at


def cell_class(run: ProvRun, obj: ProvObject) -> str:
    """Class of an extracted cell: from the origin of the gds object it joins to (the golden)."""
    if FILLER_RE.search(obj.type):
        return "tap" if "__tap" in obj.type else "fill"
    gds = [run.objects[x.to] for x in obj.links if x.to in run.objects
           and run.objects[x.to].stage == "gds"]
    if not gds:
        return "unjoined"
    origin = _walk_to_end(run, obj)[0][-1].origin  # the label at the end of the chain
    if origin == "hdl":
        return "logic"
    kind = origin.split(":", 1)[1] if ":" in origin else origin
    return kind if kind in CLASSES else "other_physical"


def label_mismatch(run: ProvRun, obj: ProvObject) -> bool:
    """The gds-stage origin label differs from the label at the end of the chain."""
    gds = [run.objects[x.to] for x in obj.links if x.to in run.objects
           and run.objects[x.to].stage == "gds"]
    return bool(gds) and gds[0].origin != _walk_to_end(run, obj)[0][-1].origin


def full_chain(run: ProvRun, obj: ProvObject, cls: str) -> Chain:
    """Walk extracted -> gds -> routed -> placed -> gates -> ir -> hdl. ``resolve`` stops at ``ir``;
    the last hop follows the ``fine`` links of the ir cell to the hdl objects."""
    ch = Chain(cls)
    if cls == "unjoined":
        ch.stages, ch.broken_at, ch.cause = ["extracted"], "extracted", "no location_match link"
        return ch
    res = resolve(run, obj)
    ch.stages = [o.stage for o in res.path]
    ch.weakest = res.weakest
    path = list(res.path)
    if not res.reached_hdl:
        last = _walk_to_end(run, obj)
        ch.stages = [o.stage for o in last[0]]
        ch.broken_at = last[0][-1].stage
        ch.last_kind = last[0][-1].origin  # a physical origin label, or "unknown"
        end = last[0][-1]
        ch.cause = (f"origin {end.origin}: no hdl parent" if end.origin != "hdl"
                    else f"{end.stage} object has no link to an earlier stage")
        return ch
    own = next((o for o in path if o.stage == "gates"), None)
    ch.own_span = own.src[0].span if own is not None and own.src else ""
    ch.last_kind = next((lk.kind for lk in path[-2].links if lk.to == path[-1].id), "") \
        if len(path) > 1 else ""
    top = path[-1]
    spans = [f"{s.file}:{s.span}" for s in top.src]
    if top.stage == "ir":
        hdl = [run.objects[lk.to] for lk in top.links if run.objects[lk.to].stage == "hdl"]
        if hdl:
            ch.stages.append("hdl")
            spans = [f"{s.file}:{s.span}" for o in hdl for s in o.src] or spans
            ch.last_kind = "fine"
        else:
            ch.broken_at, ch.cause = "ir", "ir cell has no hdl link"
    ch.spans = sorted(set(spans))
    if not ch.spans and not ch.broken_at:
        ch.broken_at, ch.cause = ch.stages[-1], "no source span"
    missing = [s for s in STAGE_ORDER if s not in ch.stages]
    if missing and not ch.broken_at:
        ch.broken_at, ch.cause = missing[0], f"stage {missing[0]} not on the path"
    return ch


def _walk_to_end(run: ProvRun, obj: ProvObject) -> tuple[list[ProvObject]]:
    """Follow the strongest link of each object until one has none (its origin says why)."""
    path = [obj]
    seen = {obj.id}
    while path[-1].links:
        nxt = [run.objects[x.to] for x in path[-1].links if x.to not in seen]
        if not nxt:
            break
        path.append(nxt[0])
        seen.add(nxt[0].id)
    return (path,)


def census_sums(run: ProvRun) -> dict[str, int]:
    out = Counter[str]()
    for step in ("place", "route"):
        try:
            hdr = run.step(step).header
        except KeyError:
            continue
        for c in (hdr.get("census") or {}).get("steps", []):
            for k in ("resized", "removed", "renamed"):
                out[k] += int(c.get(k, 0))
    return dict(out)


def design_rows(name: str, root: Path) -> dict[str, Any]:
    """flow.csv row, from status.json and the prov directory."""
    st = json.loads((root / "status.json").read_text(encoding="utf-8"))
    steps: dict[str, str] = st["steps"]
    row: dict[str, Any] = {"design": name, "clock": st["clock"], "exit": st["exit"],
                           "seconds": st["seconds"], "failed_step": "", "error": "",
                           "equiv": "", "lvs": "", "schema_check": "", "disk_kb": _du(root)}
    for s, msg in steps.items():
        if msg.startswith("FAILED"):
            row["failed_step"], row["error"] = s, msg[len("FAILED"):].strip()[:160]
    eq = root / "out" / "equiv.txt"
    if row["failed_step"] == "equiv" and eq.is_file():
        # the flow refused the step message (a home path in it); the tool's own last line says why
        lines = [x for x in eq.read_text(encoding="utf-8").splitlines() if "notice:" not in x]
        row["error"] = "equiv-check: " + re.sub(r"\S*/out/", "", lines[-1].split(": ", 1)[-1])[:140]
    orlog = root / "out" / "openroad.log"
    if row["failed_step"] == "place" and orlog.is_file():
        errs = [x.strip() for x in orlog.read_text(encoding="utf-8", errors="replace").splitlines()
                if re.match(r"\[ERROR |Error:", x)]
        row["error"] = "openroad: " + (errs[0] if errs else "rc 1")[:140]
    for s in ("equiv", "lvs"):
        hp = list((root / "out" / "prov").glob(f"*-{s}.json"))
        if hp:
            row[s] = json.loads(hp[0].read_text(encoding="utf-8"))["check"]["result"]
    return row


def _du(path: Path) -> int:
    p = subprocess.run(["du", "-sk", str(path)], capture_output=True, text=True, check=False)
    return int(p.stdout.split()[0]) if p.stdout else 0


def partial_prov(prov: Path, dst: Path) -> Path | None:
    """A run that stopped after ``extract`` (an LVS mismatch) has step files and no index. Copy
    them to ``dst`` with an index built from the headers and the sha256 of the copied files, so the
    reader can open it. Descriptive use only: the run is not a finished flow. None when the run has
    no ``extract`` objects."""
    heads = sorted(prov.glob("[0-9][0-9]-*.json"))
    if not (prov / "09-extract.objects.jsonl").is_file() or not heads:
        return None
    dst.mkdir(parents=True, exist_ok=True)
    steps: list[dict[str, Any]] = []
    hashes = {}
    for h in heads:
        hdr = json.loads(h.read_text(encoding="utf-8"))
        shutil.copyfile(h, dst / h.name)
        obj = hdr.get("objects_file")
        entry: dict[str, Any] = {
            "id": hdr["step"], "stage": hdr["stage"], "file": h.name, "objects": obj,
            "sha256": hashlib.sha256(h.read_bytes()).hexdigest(),
            "count": hdr["counts"]["objects"], "needs": hdr.get("needs", []),
            "tool": hdr["tool"]}
        if obj:
            shutil.copyfile(prov / obj, dst / obj)
            entry["objects_sha256"] = hashlib.sha256((prov / obj).read_bytes()).hexdigest()
        steps.append(entry)
        hashes[h.name] = entry["sha256"]
    first = json.loads(heads[0].read_text(encoding="utf-8"))
    index = {"schema": 1, "kind": "odin3-prov-index", "flow": "silicon-sky130",
             "design": first.get("design", ""), "top": first.get("top", ""), "steps": steps,
             "tools": [], "inputs": [], "partial": True}
    (dst / "index.json").write_text(json.dumps(index), encoding="utf-8")
    return dst


def schema_check(prov: Path) -> str:
    p = subprocess.run(["python3", "-B", str(env.ODIN / "tools" / "silicon" / "schema_check.py"),
                        str(prov)], capture_output=True, text=True, check=False)
    return "ok" if p.returncode == 0 else (p.stdout + p.stderr).strip().splitlines()[-1][:120]


def analyse(run: ProvRun) -> tuple[dict[str, Any], list[dict[str, Any]], Counter[str]]:
    """(counts row, catalogue rows, weakest-link counts) of one run."""
    classes = Counter[str]()
    joined = 0
    nonfill = 0
    full = 0
    denom_b = 0
    cat: list[dict[str, Any]] = []
    mismatches = 0
    weakest = Counter[str]()
    insert_kinds: dict[str, Counter[str]] = {}
    for obj in run.stage_objects("extracted"):
        cls = cell_class(run, obj)
        classes[cls] += 1
        mismatches += label_mismatch(run, obj)
        if cls in ("tap", "fill"):
            continue
        nonfill += 1
        has_join = any(x.kind == "location_match" and x.to in run.objects for x in obj.links)
        joined += has_join
        ch = full_chain(run, obj, cls)
        if cls in INSERTED:
            insert_kinds.setdefault(cls, Counter())[ch.last_kind or "none"] += 1
            continue
        denom_b += 1
        if ch.complete:
            full += 1
            weakest[ch.weakest] += 1
        else:
            cat.append({"cell": obj.id, "master": obj.type, "class": cls,
                        "broken_at": ch.broken_at, "link_kind": ch.last_kind, "cause": ch.cause})
    gates = run.stage_objects("gates")
    odin_names = {g.name for g in gates} | {str(g.attrs.get("odin_name", "")) for g in gates}
    name_leaks = sum(1 for o in run.stage_objects("extracted") if o.name in odin_names)
    sums = census_sums(run)
    row = {"extracted": sum(classes.values()), **{f"n_{c}": classes[c] for c in CLASSES},
           "nonfiller": nonfill, "joined": joined, "a_share": _share(joined, nonfill),
           "logic_denominator": denom_b, "full_chain": full, "b_share": _share(full, denom_b),
           "odin_cells": len(gates), "resized": sums.get("resized", 0),
           "removed": sums.get("removed", 0), "renamed": sums.get("renamed", 0),
           "gds_label_mismatch": mismatches, "extracted_odin_names": name_leaks,
           "inserted_link_kinds": json.dumps({k: dict(v) for k, v in sorted(insert_kinds.items())},
                                             sort_keys=True)}
    return row, cat, weakest


def _share(n: int, d: int) -> str:
    return f"{n / d:.4f}" if d else ""


def main() -> int:
    flow_rows: list[dict[str, Any]] = []
    chain_rows: list[dict[str, Any]] = []
    cat_rows: list[dict[str, Any]] = []
    weak_rows: list[dict[str, Any]] = []
    for d in env.designs():
        name = d["name"]
        root = env.RUN / name
        if not (root / "status.json").is_file():
            continue
        row = design_rows(name, root)
        prov = root / "out" / "prov"
        partial = False
        if not (prov / "index.json").is_file():
            got = partial_prov(prov, root / "prov-partial")
            if got is not None:
                prov, partial = got, True
        if (prov / "index.json").is_file():
            row["schema_check"] = "partial run (no index)" if partial else schema_check(prov)
            try:
                run = read_run(prov)
            except ProvError as err:
                row["schema_check"] += f" | read: {err}"[:120]
            else:
                c_row, cat, weak = analyse(run)
                chain_rows.append({"design": name, "lvs": row["lvs"] or "none",
                                   "partial": int(partial), **c_row})
                cat_rows += [{"design": name, **x} for x in cat]
                weak_rows += [{"design": name, "weakest": k, "cells": v}
                              for k, v in sorted(weak.items())]
        flow_rows.append(row)
    env.write_csv(env.RES / "flow.csv", ["design", "clock", "exit", "seconds", "failed_step",
                                         "error", "equiv", "lvs", "schema_check", "disk_kb"],
                  flow_rows)
    if chain_rows:
        env.write_csv(env.RES / "chain.csv", list(chain_rows[0]), chain_rows)
    env.write_csv(env.RES / "catalogue.csv", ["design", "cell", "master", "class", "broken_at",
                                              "link_kind", "cause"], cat_rows)
    env.write_csv(env.RES / "weakest.csv", ["design", "weakest", "cells"], weak_rows)
    print(f"designs {len(flow_rows)}  with prov {len(chain_rows)}  catalogue {len(cat_rows)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
