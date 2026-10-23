# Loki III

Reverse engineering of structural netlists (LUT, hard-block and gate-level) back to hierarchical, word-level
Verilog, with a Bayesian hypothesis flow over Odin III's provenance IR. Status: specs and plans in
`docs/specs/` and `docs/plans/` (L0 ground-truth dataset, L1 Bayesian hypotheses, L2 analysis plugins).

Loki III is part of **Yggdrasil III** (the project / world tree), the suite of Odin III
(<https://github.com/drpaj12/odin3>), Wyrd III (<https://github.com/drpaj12/wyrd>), Loki III and Midgard III (the Verilog
Town game). Loki III depends on the `odin3` Python package and never changes the Odin III core.

License: MIT.

## Documentation

The [paper](docs/paper/README.md) reports the L0/L1/L2 recovery statistics under the
Gate-Breaker metrics, with every number traced to the experiment records.

## Documentation

Start at the Yggdrasil III hub; every manual links to the others.

- [Yggdrasil III hub](https://drpaj12.github.io/YggdrasilIII/): the suite, how the pieces connect, getting started.
- [Odin III manual](https://drpaj12.github.io/odin3/).
- [Wyrd III manual](https://drpaj12.github.io/wyrd/), with
  [simulation (Bifrost III)](https://drpaj12.github.io/wyrd/simulation.html) and
  [Midgard III (Verilog Town)](https://drpaj12.github.io/wyrd/midgard.html).
- Tutorials (PDF): [command line](https://drpaj12.github.io/wyrd/wyrd-tutorial.pdf) and
  [GUI](https://drpaj12.github.io/wyrd/wyrd-gui-tutorial.pdf).
- [Loki III manual](https://drpaj12.github.io/loki/).

## Development

    python3 -m venv .venv && .venv/bin/pip install ruff mypy cffi
    .venv/bin/python -m unittest discover -s tests -t . -v
    .venv/bin/ruff check . && .venv/bin/mypy --strict loki tests

See `CLAUDE.md` for the Odin III environment variables.

## L0 dataset

    loki bench init --suite micro --odin3-root $ODIN3_ROOT --out datasets/l0
    wyrd run --project datasets/l0
    loki assemble --project datasets/l0 --out dataset
    loki check dataset

See `docs/runbook-l0.md`.

## L1: `loki re` (Bayesian hypotheses)

    loki re dataset/<design>/f2/netlist.blif --floor f2 --calib calib/f2.json --out out/<design>
    loki calibrate --dataset dataset --floor f2 --split train --out calib/f2.json
    loki re-project --dataset dataset --floors f2 --split test --calib calib --out datasets/l1 [--features none]
    wyrd run --project datasets/l1 --jobs 3 && loki score-all datasets/l1/runs --dataset dataset \
        --out datasets/l1-scores [--compare <runs made with --features none>]
    LOKI_DATASET=$PWD/dataset python -m unittest tests.test_acceptance_l1 -v      # L1 exit test

`calib/f2.json` (train split) is committed. Details in `docs/runbook-l1.md`, first numbers in
`docs/results-l1.md`.
