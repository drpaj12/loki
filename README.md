# Loki III

Reverse engineering of structural netlists (LUT, hard-block and gate-level) back to hierarchical, word-level
Verilog, with a Bayesian hypothesis flow over Odin III's provenance IR. Status: specs and plans in
`docs/specs/` and `docs/plans/` (L0 ground-truth dataset, L1 Bayesian hypotheses, L2 analysis plugins).

Loki III is part of **Yggdrasil III** (the project / world tree), the suite of Odin III
(<https://github.com/drpaj12/odin3>), Wyrd III (<https://github.com/drpaj12/wyrd>), Loki III and Midgard III (the Verilog
Town game). Loki III depends on the `odin3` Python package and never changes the Odin III core.

License: MIT.

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
