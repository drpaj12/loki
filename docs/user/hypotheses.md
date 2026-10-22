# L1 and L2 (planned)

L1 and L2 are specified; this page says what the specifications promise. The L1 code is in an open
pull request and is not described here until it is on `main`.

## L1: Bayesian hypotheses

L1 reverse-engineers one anonymous netlist from any L0 floor into hierarchical, word-level Verilog.
Detectors propose hypotheses (for example, "these 9 LUTs are a 4-bit adder"). Each hypothesis carries
log-odds that priors from L0 statistics, structural evidence and proofs update. Confirmed pieces are
committed with Odin III's `raise` and `submod`, which moves the design up one level. The next round
detects on the new level until a fixed point. L0's labels score the result.

Spec: [L1 design](https://github.com/drpaj12/loki/blob/main/docs/specs/2026-10-21-l1-hypotheses-design.md),
plan: [L1 plan](https://github.com/drpaj12/loki/blob/main/docs/plans/2026-10-21-l1-hypotheses-plan.md).

## L2: analysis plugins

L2 turns a netlist graph into exports for other tools, partitions of the netlist, graphlet
signatures per node, and a baseline graph neural network that predicts L0's labels. Each analysis is
a plugin that reads only L0 files.

Spec: [L2 design](https://github.com/drpaj12/loki/blob/main/docs/specs/2026-10-21-l2-analysis-design.md),
plan: [L2 plan](https://github.com/drpaj12/loki/blob/main/docs/plans/2026-10-21-l2-analysis-plan.md).

## Netlists that L0 did not make

A fourth spec covers turning a BLIF netlist without Verilog source or provenance into the files of
one L0 floor directory, so that L1 and L2 can analyse it:
[from-BLIF design](https://github.com/drpaj12/loki/blob/main/docs/specs/2026-10-21-from-blif-design.md).
