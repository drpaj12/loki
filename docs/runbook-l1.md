# Loki III L1 runbook: `loki re`, calibration, baseline

Needs everything of `docs/runbook-l0.md` (Odin III release library, VTR for the architecture files,
Wyrd in the same virtual environment) and an assembled L0 dataset.

## Environment

    export ODIN3_ROOT=<odin3 checkout> ODIN3_LIB=$ODIN3_ROOT/build/release/libodin3.so
    export PYTHONPATH=$ODIN3_ROOT/plugins/python VTR_ROOT=<vtr checkout>

## 1. The L0 dataset (micros and VerilogEval)

    .venv/bin/loki bench init --suite all --odin3-root $ODIN3_ROOT --out datasets/l0 --cache ~/.cache/loki/verilog-eval
    .venv/bin/wyrd run --project datasets/l0 --jobs 3 --mem-budget 8G
    .venv/bin/loki assemble --project datasets/l0 --out dataset
    .venv/bin/loki check dataset

`--suite all` needs network access (it clones the pinned VerilogEval commit; use `--suite micro`
without). `datasets/` and `dataset/` are gitignored. Every sweep below runs through
`$ODIN3_ROOT/tools/heavy-run` (needs `ODIN3_HEAVY_OK=1`; it holds the machine-wide heavy lock and a
memory-capped slice; run it only when no other lane sweeps).

## 2. One netlist

    .venv/bin/loki re dataset/<design>/f2/netlist.blif --floor f2 --calib calib/f2.json --out out/<design> \
        --score-dataset dataset --score-design <design>

Outputs in `--out`: `design.v`, `overlay.json`, `report.json`, `report.md`, `timing.json`, and
`score.json` with `--score-dataset`. `--calib none` uses the default priors; `--features none` turns
the structural features off (ablation). Exit codes: 0 done, 1 internal error or `final_equiv =
differs`, 2 usage, 3 input unreadable.

A gate-level `netlist.v` input (floor f3) is checked as the BLIF that level 0 writes out (the
netlist read back from the mapped Verilog), because `equiv-check` reads BLIF only; a faithful
rewrite gives `report.final_equiv` `equivalent` (fixed Loki issue #14).

## 3. Calibration (train split)

    ODIN3_HEAVY_OK=1 $ODIN3_ROOT/tools/heavy-run .venv/bin/loki calibrate --dataset dataset --floor f2 \
        --split train --out calib/f2.json

`calib/f2.json` is committed. Refit it whenever a detector or the commit rule changes (the priors
count proposals that match L0 constructs).

## 4. Baseline and ablation (test split)

    .venv/bin/loki re-project --dataset dataset --floors f2 --split test --calib calib --out datasets/l1
    .venv/bin/loki re-project --dataset dataset --floors f2 --split test --calib calib \
        --out datasets/l1-none --features none
    ODIN3_HEAVY_OK=1 $ODIN3_ROOT/tools/heavy-run .venv/bin/wyrd run --project datasets/l1 --jobs 3 --mem-budget 8G
    ODIN3_HEAVY_OK=1 $ODIN3_ROOT/tools/heavy-run .venv/bin/wyrd run --project datasets/l1-none --jobs 3 --mem-budget 8G
    .venv/bin/loki score-all datasets/l1/runs --dataset dataset --out datasets/l1-scores \
        --compare datasets/l1-none/runs

`datasets/l1-scores/` then holds `scores.md`, `scores.json`, `ablation.md`, `ablation.json`. The
tables of the last run are in `docs/results-l1.md`.

## 5. Acceptance (L1 exit) and scale tests

    LOKI_DATASET=$PWD/dataset .venv/bin/python -m unittest tests.test_acceptance_l1 -v      # about 135 s
    LOKI_SCALE=1 ODIN3_HEAVY_OK=1 $ODIN3_ROOT/tools/heavy-run .venv/bin/python -m unittest tests.test_features_scale -v

The acceptance test runs `loki re --calib none` twice over the micro subset (spec 15) and checks
items 1 to 7; `AcceptanceF3Test` runs the same subset from the f3 `netlist.blif` and checks exit 0
with `final_equiv` equivalent. Without `LOKI_DATASET` it skips.
