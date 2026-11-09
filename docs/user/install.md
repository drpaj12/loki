# Install

Needs Python 3.11 or newer, the Odin III release library (`libodin3.so`), VTR (for the architecture
files) and Wyrd III installed in the same virtual environment as Loki III.

Odin III version: the commands of this manual were checked against Odin III 1.6.0 (C ABI 7). `loki prov`
reads the provenance step files that Odin III 1.4.0 and later write; the other commands need the
provenance and API of 1.0.0 or later (the CI of this repository still pins 1.0.0). Wyrd III is
checked against 1.6.0 as well. VTR and the other tools outside the suite are listed with their versions on
the hub's [tools page](https://github.com/drpaj12/YggdrasilIII/blob/main/docs/tools.md).

```
python3 -m venv .venv && .venv/bin/pip install ruff mypy cffi
.venv/bin/pip install -e <wyrd checkout>             # git clone https://github.com/drpaj12/wyrd
.venv/bin/pip install --no-deps -e .          # registers the wyrd.steps entry point loki-dataset
.venv/bin/wyrd config init                    # writes ~/.config/wyrd/machine.toml (set vtr_root)
export ODIN3_ROOT=<odin3 checkout> ODIN3_LIB=$ODIN3_ROOT/build/release/libodin3.so
export PYTHONPATH=$ODIN3_ROOT/plugins/python VTR_ROOT=<vtr checkout>
```

`pip install --no-deps -e .` installs the `loki` command (`loki.cli:main`) and registers the Wyrd
step `loki-dataset`, which Wyrd runs once per design and architecture.

## Check the install

```
.venv/bin/python -m unittest discover -s tests -t . -v
.venv/bin/ruff check . && .venv/bin/mypy --strict loki tests
```

Tests that need a real VTR architecture (`VTR_ROOT`) skip when it is not set. See the L0 runbook
(`docs/runbook-l0.md` in the repository) for which tests run in CI and which run only locally.
