"""Hints v2 for the llm-hints2 problems: run ``loki re --intent`` on the renamed scratch copy, name
every net by an original wire, check the sequential claims against the original netlist, then write
the hint text, the linked netlist and the wrong-content variant.

Usage: ``python -I make_hints_v2.py [--selection CSV] [--problems P ...] [--table JSON]
[--out DIR]``.
Needs ``ODIN3_ROOT`` (default ``<workspace>/odin3``) and cffi. Writes, per problem under
``DIR/<problem>/``: ``intent.json`` (names are original wires), ``verify.json``, ``hints.md``,
``netlist_linked.v``, ``hints_w.md``, ``netlist_w.v``; and ``DIR/stats.csv``. Without ``--table``
the sequential claims carry no probability (used to fit the calibration, ``calib_intent.py``).
A claim that fails its check against the original netlist is dropped and listed in ``verify.json``.
"""

from __future__ import annotations

import argparse
import csv
import importlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[1]))
hintscfg: Any = importlib.import_module("hintscfg")
make_hints: Any = importlib.import_module("make_hints")
netmap: Any = importlib.import_module("netmap")
netlink: Any = importlib.import_module("netlink")
verify_mod: Any = importlib.import_module("loki.intent.verify")
text_mod: Any = importlib.import_module("loki.intent.text")
common = hintscfg.common

CALIB = HERE.parents[1] / "calib" / "f3.json"
_PIN = re.compile(r"\.(\w+)\(\s*([^()]*?)\s*\)")
_DFF = re.compile(r"^\s*(DFFSR|DFF)\s+\S+\s*\((.*?)\);", re.M | re.S)
STATS = ["problem", "claims", "seq_claims", "verified", "failed", "unverified", "dropped",
         "buses", "bytes"]


def strings(obj: Any) -> set[str]:
    if isinstance(obj, str):
        return {obj}
    if isinstance(obj, list):
        return {s for x in obj for s in strings(x)}
    if isinstance(obj, dict):
        return {s for v in obj.values() for s in strings(v)} | {k for k in obj}
    return set()


def translate(obj: Any, mapping: dict[str, str]) -> Any:
    if isinstance(obj, str):
        return mapping.get(obj, obj)
    if isinstance(obj, list):
        return [translate(x, mapping) for x in obj]
    if isinstance(obj, dict):
        return {mapping.get(k, k): translate(v, mapping) for k, v in obj.items()}
    return obj


def d_wires(text: str) -> dict[str, str]:
    """Q wire to D wire of every flip-flop instance of the original netlist, also under the
    names that ``assign alias = q`` gives the Q wire."""
    out: dict[str, str] = {}
    for _typ, body in _DFF.findall(text):
        pins = dict(_PIN.findall(body))
        if "Q" in pins and "D" in pins:
            out[pins["Q"]] = pins["D"]
    for lhs, rhs in netmap._ASSIGN.findall(text):
        left, right = netmap.bits_of(lhs), netmap.bits_of(rhs)
        if len(left) == len(right):
            for a, b in zip(left, right, strict=True):
                if b in out and a not in out:
                    out[a] = out[b]
    return out


def internal(name: str) -> bool:
    """A Loki-internal net name (``$n12``, ``c9``) or an unnamed net (``net41``)."""
    return bool(netmap.INTERNAL.match(name) or re.match(r"^net\d+$", name))


def _unresolved(c: dict[str, Any]) -> bool:
    """True when a name that the sentence needs is still a Loki-internal net."""
    needed = strings([c["facts"], {k: v for k, v in c["nets"].items() if k != "d"}])
    return any(internal(s) for s in needed)


def prune(intent: dict[str, Any], decl: dict[str, str]) -> tuple[dict[str, Any], int]:
    """Drop claims that still name an internal net; keep only declared wires in ``wires``."""
    keep, dropped = [], 0
    for c in intent["claims"]:
        if _unresolved(c):
            dropped += 1
            continue
        c["wires"] = sorted(w for w in c["wires"] if w in decl)
        c["nets"] = {k: [n for n in v if not internal(n)] for k, v in c["nets"].items()}
        keep.append(c)
    ids = {c["id"] for c in keep}
    buses = []
    for b in intent["buses"]:
        links = [x for x in b["links"] if x["claim"] in ids]
        if links and not any(internal(n) for n in b["bits"]):
            buses.append({**b, "links": links})
    intent = {**intent, "claims": keep, "buses": buses,
              "net_roles": {n: r for n, r in intent["net_roles"].items() if n in decl}}
    return intent, dropped


def check(intent: dict[str, Any], text: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Verify every sequential claim on the original netlist; drop the ones that fail."""
    sig = netmap.orig_signatures(text)
    dmap = d_wires(text)
    rows, keep = [], []
    for c in intent["claims"]:
        v = verify_mod.verify_claim(c, sig, dmap) if c["source"] == "seq" else None
        if v is not None:
            rows.append({"id": c["id"], "kind": c["kind"], "ok": v.ok, "checked": v.checked,
                         "bad": v.bad, "note": v.note})
        if v is None or v.ok is not False:
            keep.append(c)
    ids = {c["id"] for c in keep}
    buses = [{**b, "links": [x for x in b["links"] if x["claim"] in ids]} for b in intent["buses"]]
    return {**intent, "claims": keep, "buses": [b for b in buses if b["links"]]}, rows


def run_loki(scratch: Path, out: Path, odin: Path, table: Path | None) -> None:
    cmd = [sys.executable, "-B", "-m", "loki.re.main", str(scratch), "--floor", "f3",
           "--calib", str(CALIB), "--detectors", make_hints.DETECTORS, "--intent",
           "--out", str(out)]
    if table is not None:
        cmd += ["--intent-calib", str(table)]
    done = subprocess.run(cmd, env=make_hints.loki_env(odin), capture_output=True, text=True,
                          cwd=str(HERE), check=False)
    if done.returncode != 0:
        raise RuntimeError(f"loki re failed ({done.returncode}): {done.stderr.strip()[-300:]}")


def hint_text(intent: dict[str, Any]) -> str:
    return str(text_mod.render_claims(intent))


def make_one(problem: str, odin: Path, root: Path, table: Path | None) -> dict[str, Any]:
    work = root / problem
    (work / "f3").mkdir(parents=True, exist_ok=True)
    text = (common.dataset_dir() / f"{problem}_netlist.v").read_text(encoding="utf-8")
    scratch = work / "f3" / "netlist.v"
    scratch.write_text(make_hints.rename_cells(text), encoding="utf-8", newline="\n")
    run_loki(scratch, work / "out", odin, table)
    raw = json.loads((work / "out" / "intent.json").read_text(encoding="utf-8"))
    graph = netmap.loki_graph(scratch, odin)
    wanted = {s for s in strings(raw) if netmap.INTERNAL.match(s)}
    mapping, _ids = netmap.resolve(graph, text, wanted)
    decl = netmap.declared(text)
    intent, dropped = prune(translate(raw, mapping), decl)
    intent, rows = check(intent, text)
    (work / "intent.json").write_text(json.dumps(intent, sort_keys=True, indent=1) + "\n",
                                      encoding="utf-8")
    (work / "verify.json").write_text(json.dumps(rows, sort_keys=True, indent=1) + "\n",
                                      encoding="utf-8")
    block = hint_text(intent)
    wrong = netlink.wrong_content(text, intent, f"hints2-w:{problem}")
    files = {"hints.md": block, "netlist_linked.v": netlink.annotate(text, intent),
             "hints_w.md": hint_text(wrong), "netlist_w.v": netlink.annotate(text, wrong)}
    for name, body in files.items():
        (work / name).write_text(body, encoding="utf-8", newline="\n")
    seq = [c for c in intent["claims"] if c["source"] == "seq"]
    return {"problem": problem, "claims": len(intent["claims"]), "seq_claims": len(seq),
            "verified": sum(r["ok"] is True for r in rows),
            "failed": sum(r["ok"] is False for r in rows),
            "unverified": sum(r["ok"] is None for r in rows), "dropped": dropped,
            "buses": len(intent["buses"]), "bytes": len(block.encode("utf-8"))}


def read_problems(path: Path) -> list[str]:
    with path.open(encoding="utf-8", newline="") as fh:
        return [r["problem"] for r in csv.DictReader(fh)]


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--selection", type=Path, default=HERE / "selection.csv")
    ap.add_argument("--problems", nargs="+", default=None)
    ap.add_argument("--table", type=Path, default=None)
    ap.add_argument("--out", type=Path, default=hintscfg.RUN / "hints2")
    args = ap.parse_args(argv)
    odin = Path(os.environ.get("ODIN3_ROOT", str(common.workspace() / "odin3")))
    make_hints.enable_odin(odin)
    args.out.mkdir(parents=True, exist_ok=True)
    rows, fails = [], []
    for p in args.problems or read_problems(args.selection):
        try:
            rows.append(make_one(p, odin, args.out, args.table))
            print(f"{p}: {rows[-1]['claims']} claims", flush=True)
        except (RuntimeError, ValueError, KeyError) as exc:
            fails.append((p, str(exc).replace("\n", " ")[:200]))
            print(f"{p}: FAILED {exc}", flush=True)
    with (args.out / "stats.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, STATS, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    (args.out / "failures.json").write_text(json.dumps(fails, indent=1) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
