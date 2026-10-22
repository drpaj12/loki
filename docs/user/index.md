# Loki III

Loki III reverse-engineers structural netlists (LUT, hard-block and gate-level) back to
hierarchical, word-level Verilog. It is part of the Yggdrasil III suite and depends on the `odin3`
Python package; it never changes the Odin III core. There is no LLM step: the method is Bayesian
hypotheses over Odin III's provenance IR, with graph analysis later.

The work is split in three levels. Only L0 is on `main` today.

| Level | What | Status |
|---|---|---|
| L0 | Ground-truth dataset builder: Odin III provenance is the answer key | on `main` |
| L1 | Bayesian hypothesis flow (detectors, provers, commit with `raise`/`submod`) | specified; code in an open pull request |
| L2 | Analysis plugins (graph and clustering methods) | specified |

This manual is short because the tool is young. It covers installing Loki III, building the L0
dataset, the files in that dataset, what L1 and L2 will do, and the L0 results on the Odin III micro
designs. The other Yggdrasil III manuals are linked in the sidebar: the
[hub](https://drpaj12.github.io/YggdrasilIII/), [Odin III](https://drpaj12.github.io/odin3/) and
[Wyrd III](https://drpaj12.github.io/wyrd/).

```{toctree}
:maxdepth: 2

install
dataset
formats
hypotheses
results
```
