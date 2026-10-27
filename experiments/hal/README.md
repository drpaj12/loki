# Loki vs HAL/DANA word recovery

Pre-registration: `docs/plan/hal-compare-prereg.md`. Feasibility and sources:
`docs/plan/hal-feasibility.md`.

Credits. HAL, the Hardware Analyzer (Embedded Security Group, MIT licence,
https://github.com/emsec/hal, tag v4.5.0, commit e7fea566b51e) and its dataflow plugin, which
implements DANA: N. Albartus, M. Hoffmann, S. Temme, L. Azriel, C. Paar, "DANA: Universal Dataflow
Analysis for Gate-Level Netlist Reverse Engineering", IACR TCHES 2020(4), 309-336,
doi 10.46586/tches.v2020.i4.309-336. No HAL code is vendored here; the `.hgl` files below are our
own descriptions of the Loki floors in HAL's gate-library format (structure after HAL's
`example_library.hgl`).

Files (all standard-library Python, code in the `loki.hal` package):

| file | role |
|---|---|
| `loki/hal/blif.py` | BLIF reader (`.names .latch .subckt .cname`) |
| `loki/hal/blif2hal.py` | BLIF to HAL structural Verilog, floor f2 (LUT1..6, FF) or f3 (BUF INV NAND2 NOR2 DFF DFFSR); instance name = L0 node id |
| `loki/hal/hgl.py`, `experiments/hal/hgl/{lut6,cmos6}.hgl` | the two gate libraries (generated, a test checks the committed text) |
| `loki/hal/sim.py` | BLIF simulator, cell models and iverilog testbench for the function round trip |
| `loki/hal/dana.py` | reader of the dataflow plugin's `groups.txt` |
| `loki/hal/wordscore.py` | one word scorer for both tools (exact, Jaccard 0.5, purity, completeness, coverage) |

Build HAL (not part of this repo; MIT licence; Peter-approved adoption, built only with its own
CMake): shallow clone of tag v4.5.0 (commit e7fea566b51e), then
`cmake -G Ninja -DPL_DATAFLOW=ON -DPL_GUI=OFF -DPL_GEXF_WRITER=OFF -DPL_SOLVE_FSM=OFF
-DPL_Z3_UTILS=OFF -DPL_VHDL_PARSER=OFF -DPL_NETLIST_PREPROCESSING=OFF -DUSE_VENDORED_PYBIND11=OFF
-Dpybind11_DIR=<pip pybind11 --cmakedir>` and `ninja -j4` (needs libboost-dev and rapidjson-dev;
HAL's vendored pybind11 2.9 does not compile against Python 3.12, so a pip pybind11 2.13.6 is used;
measured here: about 7 minutes in three attempts, 320 MB, no sudo beyond the two packages).
HAL v4.5.0's `--dataflow` command line does not run (no gate types set); `dana_run.py` drives the
plugin through the Python API (`hal --python-script`, Amendment 2 B1).

Driver (`PYTHONPATH=<repo>:<repo>/experiments/round5 HAL_BIN=<hal>`; sub-commands `plan`, `lutcheck`,
`loadcheck`, `roundtrip`, `repeat`, `permute`, `run`, `summary`, `score`, `f2f3`; `python -m
loki.hal.compare` writes `docs/results-hal.md` and `docs/paper/hal-tables.tex`). `run`, `repeat`
and `permute` reuse the `status.json` of an earlier run in the same output directory; `--fresh`
ignores it. `f2f3` compares DANA's f2 and f3 partitions per design (under the original flip-flop
names) and counts `DFFSR` cells; `dana_default.py` runs DANA with no `min_group_size` call (check
of the default 8). The result files in `results/` are the outputs of these commands; the tests in
`tests/test_hal_results.py` read them.

One design by hand:

    python -m loki.hal.blif2hal --floor f2 <ds>/<design>/f2/netlist.blif design.v
    HAL_V=design.v HAL_L=experiments/hal/hgl/lut6.hgl HAL_OUT=out HAL_MIN=8 \
      hal --volatile-mode --no-log --python-script experiments/hal/dana_run.py
    python -m loki.hal.wordscore --floor-dir <ds>/<design>/f2 --dana out/groups.txt
    python -m loki.hal.wordscore --floor-dir <ds>/<design>/f2 --loki-re <run>/re

(`HAL_MIN` is DANA's `min_group_size`; the library default is 8.) Netlists with
`.subckt` hard blocks other than `DFFSR` (for example `micro_multiply_hard_block` at f2), latch
types other than `re`, and f3 covers other than BUF, INV, NAND2, NOR2 are rejected by the
converter. Tests: `tests/test_hal_convert.py` (round trip needs iverilog; the micro round trip
needs the micro dataset, `LOKI_MICRO`), `tests/test_hal_score.py`.
