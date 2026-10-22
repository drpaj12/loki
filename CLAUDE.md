# loki

Loki III L0: Wyrd III step plugin that turns Verilog designs into labelled, anonymised netlist datasets
with Odin III provenance as the answer key. Part of Yggdrasil III. Later: L1 Bayesian hypotheses, L2 analysis.

Spec: `docs/specs/2026-10-21-l0-dataset-design.md`. Plan: `docs/plans/2026-10-21-l0-dataset-plan.md`.

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
