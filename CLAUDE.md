# loki

Loki III L0: Wyrd III step plugin that turns Verilog designs into labelled, anonymised netlist datasets
with Odin III provenance as the answer key. Part of Yggdrasil III. Later: L1 Bayesian hypotheses, L2 analysis.

Spec: `docs/specs/2026-10-21-l0-dataset-design.md`. Plan: `docs/plans/2026-10-21-l0-dataset-plan.md`.
L1 (`loki re`): spec `docs/specs/2026-10-21-l1-hypotheses-design.md`, plan `docs/plans/2026-10-21-l1-hypotheses-plan.md`.
L2 (`loki analyze`): spec `docs/specs/2026-10-21-l2-analysis-design.md`, plan `docs/plans/2026-10-21-l2-analysis-plan.md`.
The base install stays `odin3` only; numpy, scipy, scikit-learn and networkx are the `analysis` extra,
torch and torch_geometric (`torch_geometric`) the `gnn` extra, and `dev` unions both. Install them with
`.venv/bin/pip install --no-deps -e .` plus the extras' libraries (odin3 is not on PyPI); tests that
need one skip through `tests.helpers.skip_without` instead of failing.

## Setup

    python3 -m venv .venv && .venv/bin/pip install ruff mypy cffi
    .venv/bin/pip install -e <wyrd checkout>        # dev dependency, for the step tests
    # Odin III for local runs:
    export ODIN3_ROOT=<odin3 checkout> ODIN3_LIB=$ODIN3_ROOT/build/release/libodin3.so
    export PYTHONPATH=$ODIN3_ROOT/plugins/python

## Build, test, lint

    .venv/bin/python -m unittest discover -s tests -t . -v
    .venv/bin/ruff check .
    .venv/bin/mypy --strict loki tests

Dataset flow (details in `docs/runbook-l0.md`):

    .venv/bin/loki bench init --suite micro --odin3-root $ODIN3_ROOT --out datasets/l0
    .venv/bin/wyrd run --project datasets/l0 --jobs 3 --mem-budget 8G
    .venv/bin/loki assemble --project datasets/l0 --out dataset
    .venv/bin/loki check dataset

L1 commands (details in `docs/runbook-l1.md`; sweeps and `LOKI_SCALE=1` run through `$ODIN3_ROOT/tools/heavy-run`):

    .venv/bin/loki re <netlist.blif> --floor f2 --calib calib/f2.json --out out/x [--features none]
    .venv/bin/loki calibrate --dataset dataset --floor f2 --split train --out calib/f2.json
    .venv/bin/loki re-project --dataset dataset --floors f2 --split test --calib calib --out datasets/l1
    .venv/bin/loki score-all datasets/l1/runs --dataset dataset --out datasets/l1-scores
    LOKI_DATASET=$PWD/dataset .venv/bin/python -m unittest tests.test_acceptance_l1 -v

Refit `calib/f2.json` after any detector or commit-rule change.

## Rules

- Python 3.11+, no 3.12-only syntax. Runtime dependency: the `odin3` wheel only, imported through
  `importlib.import_module` in `loki/odin.py`. Never edit the Odin III repo; a missing Odin III API is
  an open question, not a workaround.
- ruff and `mypy --strict` clean. No `# noqa`, `# type: ignore` or similar suppressions without Peter's approval.
  Line length 100. Small functions. Tests are `unittest` under `tests/`; Odin III tests use
  `skipUnless(odin_available())`.
- Never commit to `main`. Branch, PR, squash merge on green CI. Commit and push after each green step.
- Outputs are deterministic: sorted keys, `\n` line ends, UTF-8, `schema` = 1.
- Original names exist only in `key.json`. Names in outputs are `n<k>` from one shared counter.
- Labels are an answer key, not a claim: never fill a label by guessing; an unmatched cell stays `unknown`.
