"""Part B: build composite benchmarks by wiring VerilogEval references: ``python -B compose.py``.

Writes OUT/composites/<name>/<name>.v + truth.json and results/composites.csv (name, split, parts,
wires). Deterministic (seed 20261030). Naming: Q + 3-digit problem numbers joined by underscores.
"""

from __future__ import annotations

import itertools
import json
import random
import re
from typing import Any

import l3dlib as lib
import part_a as pa

SEED = 20261030
KINDS = ("fsm", "counter", "timer", "shift", "lfsr", "regfile")
FAMILY = {"fsm": "fsm", "counter": "counter", "timer": "counter", "shift": "shift",
          "lfsr": "shift"}
SIZES = ((2, 60), (3, 30), (4, 10))  # (parts, composites per 100)
PER_SIDE = 100
RESET = re.compile(r"reset|rst", re.I)
VEVAL = lib.WS / "external" / "verilog-eval" / "dataset_spec-to-rtl"


def parse_ports(src: str) -> list[dict[str, Any]]:
    """ANSI port list of module RefModule: name, dir, width."""
    m = re.search(r"module\s+RefModule\s*\((.*?)\)\s*;", re.sub(r"//[^\n]*", "", src), re.S)
    if m is None:
        raise ValueError("no RefModule header")
    ports: list[dict[str, Any]] = []
    direction, width = "input", 1
    for item in re.split(r",(?![^\[]*\])", m.group(1)):
        t = item.split()
        if not t:
            continue
        if t[0] in ("input", "output", "inout"):
            direction = t[0]
            width = 1
        rng = re.search(r"\[\s*(\d+)\s*:\s*(\d+)\s*\]", item)
        if rng:
            width = abs(int(rng.group(1)) - int(rng.group(2))) + 1
        elif t[0] in ("input", "output"):
            width = 1
        ports.append({"name": re.sub(r"\[.*", "", t[-1]), "dir": direction, "width": width})
    return ports


def pool() -> dict[str, dict[str, Any]]:
    """Usable parts: problem id -> {design, split, kinds, ports, src}."""
    lab, skip = pa.labels(), pa.excluded()
    split = {r["design"]: r["split"] for r in lib.read_csv(lib.RES / "split_single.csv")}
    man = {r["design"] for r in lib.read_csv(lib.CENSUS_RES / "manual_labels.csv")}
    out: dict[str, dict[str, Any]] = {}
    for d, r in sorted(lab.items()):
        if not d.startswith("ve_") or r["status"] != "ok" or d in man:
            continue
        kinds = [k for k in KINDS if r[k] not in ("", "0")]
        src = (VEVAL / (d[3:] + "_ref.sv")).read_text(encoding="utf-8")
        if not kinds or len(re.findall(r"^\s*module\b", src, re.M)) != 1:
            continue
        if not all(lib.intent_path(lib.CENSUS, c, d).is_file() and (d, c) not in skip
                   for c in lib.CELLS):
            continue
        try:
            ports = parse_ports(src)
        except ValueError:
            continue
        if not any(p["name"] == "clk" and p["dir"] == "input" for p in ports):
            continue
        num = d[3:].split("_")[0][4:]
        out[num] = {"design": d, "split": split[d], "kinds": kinds, "ports": ports, "src": src}
    return out


def free_inputs(part: dict[str, Any], used: set[str]) -> list[dict[str, Any]]:
    return [p for p in part["ports"] if p["dir"] == "input" and p["name"] != "clk"
            and not RESET.search(p["name"]) and p["name"] not in used]


def pick_wire(rng: random.Random, a: int, b: int, parts: list[dict[str, Any]],
              used: list[set[str]], kind: str) -> list[dict[str, Any]] | None:
    """One wire a -> b of type control/data (handshake = two calls); None when no free port."""
    ins = free_inputs(parts[b], used[b])
    ins = [p for p in ins if (p["width"] == 1) == (kind == "control")]
    outs = [p for p in parts[a]["ports"] if p["dir"] == "output"]
    if not ins or not outs:
        return None
    dst, src = rng.choice(ins), rng.choice(outs)
    used[b].add(dst["name"])
    return [{"from": a, "to": b, "type": kind, "src": src["name"], "dst": dst["name"],
             "src_w": src["width"], "dst_w": dst["width"],
             "bit": rng.randrange(src["width"]) if kind == "control" else 0}]


def wires_for(rng: random.Random, parts: list[dict[str, Any]]) -> list[dict[str, Any]] | None:
    used: list[set[str]] = [set() for _ in parts]
    wires: list[dict[str, Any]] = []
    for i in range(1, len(parts)):
        j = rng.randrange(i)
        kind = rng.choice(("control", "data", "handshake"))
        for try_kind in dict.fromkeys([kind, "control", "data"]):
            a, b = (i, j) if rng.random() < 0.5 else (j, i)
            kk = "control" if try_kind == "handshake" else try_kind
            w = pick_wire(rng, a, b, parts, used, kk)
            if w is None:
                continue
            if try_kind == "handshake":
                back = pick_wire(rng, b, a, parts, used, "control")
                if back is None:
                    continue
                w += back
            for x in w:
                x["via"] = rng.choice(("direct", "comb"))
                x["type"] = "handshake" if try_kind == "handshake" else x["type"]
            wires += w
            break
        else:
            return None
    return wires


def render(name: str, nums: list[str], parts: list[dict[str, Any]],
           wires: list[dict[str, Any]]) -> str:
    head = []
    body: list[str] = []
    glue: list[str] = []
    into: dict[tuple[int, str], str] = {}
    for m, w in enumerate(wires):
        wn = f"w{m}"
        body.append(f"wire [{w['dst_w'] - 1}:0] {wn};")
        sw, dw = w["src_w"], w["dst_w"]
        src = f"p{w['from']}_{w['src']}"
        expr = f"{src}[{w['bit']}]" if w["type"] != "data" and sw > 1 else src
        ew = 1 if (w["type"] != "data" and sw > 1) else sw
        if ew < dw:
            expr = f"{{{{{dw - ew}{{1'b0}}}}, {expr}}}"
        elif ew > dw:
            expr = f"{src}[{dw - 1}:0]"
        if w["via"] == "comb":
            head.append(f"input g{m}")
            expr = f"({expr}) & {{{dw}{{g{m}}}}}"
        glue.append(f"assign {wn} = {expr};")
        into[(w["to"], w["dst"])] = wn
    insts = []
    for k, (num, part) in enumerate(zip(nums, parts, strict=True)):
        conns = []
        for p in part["ports"]:
            rng_ = f"[{p['width'] - 1}:0] " if p["width"] > 1 else ""
            if p["name"] == "clk":
                conns.append(".clk(clk)")
            elif p["dir"] == "input" and (k, p["name"]) in into:
                conns.append(f".{p['name']}({into[(k, p['name'])]})")
            else:
                top = f"p{k}_{p['name']}"
                head.append(f"{p['dir']} {rng_}{top}")
                conns.append(f".{p['name']}({top})")
        insts.append(f"P{num} u{k} ({', '.join(conns)});")
    mods = [re.sub(r"module\s+RefModule\b", f"module P{n}", p["src"])
            for n, p in zip(nums, parts, strict=True)]
    top = f"module {name} (input clk, {', '.join(head)});\n" + "\n".join(
        [*body, *glue, *insts]) + "\nendmodule\n"
    return "\n".join(mods) + "\n" + top


def build_side(rng: random.Random, side: str, nums: list[str], items: dict[str, Any]
               ) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: set[tuple[str, ...]] = set()
    for size, pct in SIZES:
        want = PER_SIDE * pct // 100
        combos = list(itertools.combinations(nums, size))
        rng.shuffle(combos)
        got = 0
        for combo in combos:
            if got >= want:
                break
            if combo in seen:
                continue
            order = list(combo)
            rng.shuffle(order)  # the part order decides wire direction, the name stays sorted
            parts = [items[n] for n in order]
            wires = wires_for(rng, parts)
            if wires is None:
                continue
            seen.add(combo)
            name = "Q" + "_".join(sorted(combo))
            out.append({"name": name, "split": side, "nums": order, "wires": wires,
                        "verilog": render(name, order, parts, wires)})
            got += 1
    return out


def main() -> int:
    rng = random.Random(SEED)
    items = pool()
    rows = []
    for side in ("TUNE", "TEST"):
        nums = sorted(n for n, p in items.items() if p["split"] == side)
        for c in build_side(rng, side, nums, items):
            d = lib.OUT / "composites" / c["name"]
            d.mkdir(parents=True, exist_ok=True)
            (d / f"{c['name']}.sv").write_text(c["verilog"], encoding="utf-8")
            truth = {"name": c["name"], "split": side, "wires": c["wires"], "parts": [
                {"idx": k, "problem": n, "design": items[n]["design"],
                 "families": sorted({FAMILY[x] for x in items[n]["kinds"] if x in FAMILY})}
                for k, n in enumerate(c["nums"])]}
            (d / "truth.json").write_text(json.dumps(truth, sort_keys=True, indent=1) + "\n",
                                          encoding="utf-8")
            rows.append({"name": c["name"], "split": side, "parts": len(c["nums"]),
                         "wires": len(c["wires"])})
    lib.write_csv(lib.RES / "composites.csv", ["name", "split", "parts", "wires"], rows)
    print(len(items), "parts;", len(rows), "composites")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
