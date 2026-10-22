"""A hand-written L0 floor and L1 run directory for the scoring tests."""

import json
from pathlib import Path
from typing import Any


def write_floor_and_run(tmp: Path) -> tuple[Path, Path, dict[str, Any]]:
    """Return ``(floor_dir, run_dir, report)``: one adder word over n2, n3 found and committed."""
    rows = [("n1", "lut", "top", "", -1, "datapath"), ("n2", "lut", "top/u", "", -1, "control"),
            ("n3", "lut", "top/u", "", -1, "datapath")]
    csv = "node_id,kind,module_path,bus_name,bit_index,role\n" + "".join(
        f"{n},{k},{p},{b},{i},{r}\n" for n, k, p, b, i, r in rows)
    graph = {"nodes": [{"id": n, "kind": "lut"} for n, *_ in rows],
             "edges": [{"src": "n1", "dst": "n2", "net": "n10", "pin": "I0"}]}
    words = {"words": [{"id": 1, "type": "$add", "params": {}, "fsm": False, "role": "x",
                        "const_ports": [], "footprint": ["n2", "n3"]}], "edges": []}
    overlay = {"hypotheses": [
        {"id": "h1", "kind": "adder", "detector": "arith", "cells": ["n2", "n3"],
         "features": {}, "p_comp": 0.95, "log_odds": 3.0, "status": "committed",
         "claim": {"op": "add"}, "nets": {}, "params": {}},
        {"id": "h2", "kind": "role", "detector": "role", "cells": ["n2"], "features": {},
         "p_comp": 0.9, "log_odds": 2.0, "status": "open", "claim": None, "nets": {},
         "params": {}},
    ]}
    report = {"pieces": [{"cells": ["n2", "n3"]}], "features": {"transfers": 0},
              "rounds": [{"engines": {"cone_check": 1}, "proved": {"equivalent": 1}}],
              "counts": {"committed": 1}, "final_equiv": {"status": "equivalent"},
              "timeouts": 0}
    floor = tmp / "d" / "f2"
    floor.mkdir(parents=True)
    (floor / "labels.csv").write_text(csv, encoding="utf-8")
    (floor / "graph.json").write_text(json.dumps(graph), encoding="utf-8")
    (floor / "words.json").write_text(json.dumps(words), encoding="utf-8")
    run = tmp / "run"
    run.mkdir()
    (run / "overlay.json").write_text(json.dumps(overlay), encoding="utf-8")
    (run / "report.json").write_text(json.dumps(report), encoding="utf-8")
    return floor, run, report
