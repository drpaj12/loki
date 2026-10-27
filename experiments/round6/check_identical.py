"""Check: the snapshot writes do not change the design. Re-run the f2 flow of each MI design with
no ``--prov-ast`` and no intermediate write and compare ``write_blif --vtr --name-style hash``
byte for byte with ``b8.blif`` of the snapshot run (written with ``--prov-map refs``).

Run as one heavy-run batch: ``python check_identical.py MI``. Writes ``l15_check_identical.csv``."""

from __future__ import annotations

import sys
from pathlib import Path

from r6lib import ARCH, DATA, HERE, design_set, read_csv, write_csv

from loki.odin import odin_module, read_flags, register_slang


def plain_blif(files: list[Path], out: Path) -> str:
    mod = odin_module()
    o = mod.default()
    o.load_abc()
    if any(f.suffix == ".sv" for f in files):
        register_slang(o)
    design = mod.Design(o)
    paths = " ".join(f'"{f}"' for f in files)
    design.run_script(f'read_arch "{ARCH}"; read_verilog {read_flags(files)} {paths}')
    design.run_script("proc; fsm; opt; flatten; opt -full; wreduce; lower; abc --lut 6")
    design.run_script(f'write_blif --vtr --name-style hash "{out}"')
    return out.read_text(encoding="utf-8")


def main(name: str) -> int:
    ok = {r["design"] for r in read_csv(DATA / "snap" / name / "status.csv") if r["status"] == "ok"}
    tmp = DATA / "check"
    tmp.mkdir(exist_ok=True)
    rows = []
    for design, files, _top in design_set(name):
        if design not in ok:
            continue
        ref = (DATA / "snap" / name / design / "b8.blif").read_text(encoding="utf-8")
        got = plain_blif(files, tmp / f"{design}.blif")
        rows.append([name, design, int(ref == got)])
    write_csv(HERE / f"l15_check_identical_{name}.csv", ["set", "design", "identical"], rows)
    print(name, len(rows), sum(r[2] for r in rows), "identical")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
