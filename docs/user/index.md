# Loki III

Loki III reverse-engineers structural netlists (LUT, hard-block and gate-level) back to
hierarchical, word-level Verilog. It is part of the Yggdrasil III suite and depends on the `odin3`
Python package; it never changes the Odin III core. There is no LLM step: the method is Bayesian
hypotheses over Odin III's provenance IR, with graph analysis later.

The work is split in three levels.

| Level | What | Command |
|---|---|---|
| L0 | Ground-truth dataset builder: Odin III provenance is the answer key | `loki bench`, `loki assemble` |
| L1 | Bayesian hypothesis flow (detectors, provers, commit with `raise`/`submod`) | `loki re` |
| L2 | Analysis plugins (graph and clustering methods) | `loki analyze` |

This manual covers installing Loki III, building the L0 dataset, the files in that dataset, what L1
and L2 do, and the L0 results on the Odin III micro designs. The paper and the experiments that
measure all three levels are in the repository: the
[paper](https://github.com/drpaj12/loki/tree/main/docs/paper),
[renamed-instance experiment](https://github.com/drpaj12/loki/blob/main/experiments/rename-l2/EXPERIMENT.md) and
[f3 recovery experiment](https://github.com/drpaj12/loki/blob/main/experiments/f3-recovery/EXPERIMENT.md).
The other Yggdrasil III manuals are linked in the sidebar: the
[hub](https://drpaj12.github.io/YggdrasilIII/), [Odin III](https://drpaj12.github.io/odin3/) and
[Wyrd III](https://drpaj12.github.io/wyrd/). The Norns III uses Loki III's L2 clusters as
placement seeds: <https://github.com/drpaj12/nornsIII>.

## Features

Status: works (a `loki` command or module with tests), experiment (script under `experiments/`, not a
command), dismissed (measured, did not help). The full table with links is in the
[README](https://github.com/drpaj12/loki#features).

- Works: L0 dataset with the Odin III provenance answer key and three floors ([dataset](dataset.md), [formats](formats.md)); the
  naming-neutral key (names only in `key.json`); L1 Bayesian flow `loki re` with calibration ([hypotheses](hypotheses.md));
  the ReverseProvenance record and its document for a language model ([llm](llm.md)); L2 export, structural features,
  clustering, ORCA graphlets and the GNN baseline `loki analyze`; the loss audit `loki audit`; the HAL and DANA comparison;
  the L3 pattern census and v0 detector.
- Experiment: the Gate-Breaker LLM replication harness (arms A netlist, B netlist and hints, C interface only; follow-up arms
  A2, B1', B2, W); L3 anchor-grow-join blocks and the M2 kind guess; graphlet signature matching; the state-machine encoding
  study.
- Dismissed or inconclusive: the word-first detector ([wordfirst](wordfirst.md)), the Bayes-factor stop rule, the split step,
  clustering as the designer's hierarchy, Loki's hints to a model that already has the netlist.

```{toctree}
:maxdepth: 2

install
dataset
formats
hypotheses
wordfirst
llm
results
```
