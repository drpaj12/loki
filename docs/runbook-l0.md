# Loki III L0 runbook: build the micro dataset

Needs: Python 3.11+, the Odin III release library (`libodin3.so`), VTR (for the architecture files),
Wyrd installed in the same virtual environment as Loki.

## Install

    python3 -m venv .venv && .venv/bin/pip install ruff mypy cffi
    .venv/bin/pip install -e <wyrd checkout>
    .venv/bin/pip install --no-deps -e .          # registers the wyrd.steps entry point loki-dataset
    .venv/bin/wyrd config init                    # writes ~/.config/wyrd/machine.toml (set vtr_root)
    export ODIN3_ROOT=<odin3 checkout> ODIN3_LIB=$ODIN3_ROOT/build/release/libodin3.so
    export PYTHONPATH=$ODIN3_ROOT/plugins/python VTR_ROOT=<vtr checkout>

## Run

    .venv/bin/loki bench init --suite micro --odin3-root $ODIN3_ROOT --out datasets/l0
    .venv/bin/wyrd run --project datasets/l0 --jobs 3 --mem-budget 8G --progress
    .venv/bin/loki assemble --project datasets/l0 --out dataset
    .venv/bin/loki check dataset

`--suite verilog-eval` clones the pinned VerilogEval commit into `~/.cache/loki/verilog-eval`
(`--cache DIR` to change it); the download is treated as data and never executed.

Acceptance test (about one minute): `.venv/bin/python -m unittest tests.test_acceptance_micros -v`.

## Which tests run where

CI (`.github/workflows/ci.yml`) installs the Odin III v1.0.0 wheel, checks out the odin3 v1.0.0
sources for `ODIN3_ROOT`, builds ABC at the odin3 v1.0.0 submodule commit (cached) for `ODIN3_ABC`,
and pins Wyrd to commit 11ee708. There is no VTR, so `f2_arch()` falls
back to Odin III's placeholder architecture (floor F2 only records the path).

- Run in CI and locally: every pure unit test, plus the Odin III tests gated on `can_run_f2()`:
  `test_extract`, `test_snapshot`, `test_blif_vs_odin`, `test_rules_registry`, `test_odin_facts`
  (except the two hardmap probes), and `test_build` (except the F1 hard-cell test). These use the
  binding, ABC and `equiv-check` from the checkout; without ABC (`ODIN3_ABC`, `build/*/third_party/abc/abc`,
  `$VTR_ROOT/build/abc/abc` or `abc` on `PATH`) they skip. From `test_f3`: `ScriptTest` and the
  text-only `TechlibTest` tests (`test_function_subset`, `test_bad_function`, `test_seq_edges`,
  `test_bad_cell_lines`, `test_latch_edge_from_library`).
- Local only (skip in CI, need a real VTR architecture via `VTR_ROOT`, gated on
  `can_run_flow()`): `test_acceptance_micros` (all three tests), `test_build`
  `test_f1_hard_cells_and_declared_ports`, `test_odin_facts` `test_hardmap_keeps_spans` and
  `test_hard_port_names`, and the network-only `test_bench` fetch (`LOKI_NETWORK=1`).
- Local only, gated on `have_f3()`: `test_f3` `F3Test` and the cmos6 tests (`test_cmos6_covers`,
  `test_gate_names_blif`). CI's pinned Odin III v1.0.0 wheel has no `lib/cmos6.o3lib` and no
  `dfflibmap` pass, so these skip there.

## Real output, 2026-10-22 (Odin III main 158ced05, library 1.0.0, 3 jobs)

`wyrd run`: 136 runs (68 designs x 2 architectures), all `ok`, 71 s wall time.

`loki assemble`: `assembled 68 designs into dataset`. `loki check dataset`: `loki check: 0 error(s)`.

Manifest summary (`dataset/manifest.json`, 43 MB on disk):

| Floor | ok | skipped | nodes (sum over ok designs) |
|---|---|---|---|
| f1-k6 | 66 | 2 | 7848 |
| f1-earch | 66 | 2 | 7848 |
| f2 | 66 | 2 | 13513 |

Split (train/test, seed `loki-l0-2026`): 52 / 16. The two skipped designs are `micro_adder_hard_block`
and `micro_hard_adder_cin_propagation`: they instantiate the library cell `adder` with a parameter, which
Odin III's reader rejects (`odin3: ODIN3_ERR_PARSE ... too many parameter values for cell type 'adder'`).

Acceptance (`tests.test_acceptance_micros`): every built floor has `writer` and `anon` equivalence
`equivalent` (no `unproven`), label coverage over `lut` and `ff` nodes 9121 / 9121 (threshold 0.95).

## Real output, F3 (Odin III d7defba, library 1.0.0, 2026-10-22)

Odin III commit: `d7defba` (gate-mapping main). The release library and Python binding were built at
2026-10-22 09:21/09:20 EDT, 35 minutes after that commit; the checkout later moved to `94cece22`
(docs and submod changes only, no F3 path). The binding reports `read_techlib`, `dfflibmap` and
`abc --gates`, and `lib/cmos6.o3lib` is present.

`tests.test_acceptance_micros.AcceptanceF3Test.test_all_micros_f3`: 65 ok, 3 skipped, 0
non-equivalent; gate and `ff` label coverage 45673 / 45673; every floor's labels row count equals its
graph node count; `loki check` on all 68 assembled designs has 0 errors; three rebuilt designs are
byte-identical; F3 files are byte-identical for any `arch_xml` (F3 reads no architecture).

The three skips are Odin III front-end parse failures (`ODIN3_ERR_PARSE ... unresolved_module`), not
Loki defects: `micro_adder_hard_block` and `micro_hard_adder_cin_propagation` (module `adder`) and
`micro_multiply_hard_block` (module `multiply`). The third appeared between Odin III `158ced05` (the
previous L0 run) and the gate-mapping main; it is an open item for Peter.
