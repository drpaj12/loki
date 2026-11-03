# Q-L11: AST/CFG for every LLM arm, and why higher-level structure is not recovered (plan, 2026-11-03)

Branch exp/ql11-astcfg on loki main fa542d6 (after #82, Q-L10). Plan written before any scoring or analysis run of this
lane; no model call is made at any point. A later change is a dated entry under "Amendments"; the old text stays.

## Peter's words (2026-11-03)

"have AST/CFG all the way so we can say that Loki approach with LLM agent is better than Gatebreaker alone, but for the
deeper part of the question have some understanding of or hypothesis, why we can't recover higher level structures - Note
too that these experiements are from 3 end points (k=6, k=4, and gates) three points instead of 1 for gatebreaker (so the k
ones are bigger reverse engineerings)".

Purpose: Loki reverse engineering of structural netlists. RQ: L, Q-L10 continued, Q-L4 (why structure is missed).
Measures: functional pass@1 and Gate-Breaker's two similarity measures (AST, CFG), per endpoint; right-block share per
structure kind and endpoint.

## Part A: AST and CFG for every LLM arm

1. Inventory of every experiment with model replies (arms, endpoints, problems, draws), from the committed results and
   the archived run data. Read only.
2. One scorer. The three AST/CFG wrappers (`ql10-blocks/q10_astcfg.py`, `f3-recovery/tools/astcfg.py`,
   `round2/l2_astcfg.py` with `metrics_ext.py`) are run on one shared sample and compared value by value. One is chosen and
   every arm is re-scored with it; the reasons are written in the results.
3. Paired comparison per endpoint and per arm pair against arm A (Gate-Breaker whole-netlist prompting): pass@1, AST, CFG,
   each with W/L/T and a seeded bootstrap 95 percent CI over problems (seed 20261103, 2000 resamples). Both writers: "as
   written" (raw) and flattened through the same Odin III writer on both sides (the headline, as in Q-L10).
   Labels per the CAD reporting convention: headline geomean-style gain first, then the strict label; a CI touching zero is
   INCONCLUSIVE, not DISMISSED.
4. Endpoint framing: Gate-Breaker reports one endpoint (gates); Loki runs three (gates, k4, k6). Size per endpoint (cells,
   nets, mean LUT input count, provenance constructs per cell) from the structural benchmark of Q-L4 to Q-L10.

Limit stated in advance: every LLM experiment (llm-pilot, llm-full, llm-hints2, ql10-blocks) was run on the Gate-Breaker
gate netlists only. If the replies for k4 and k6 do not exist, the paired comparison at k4 and k6 cannot be made without
new model calls; this lane makes none and gives the call count and token estimate for the controller.

## Part B: why higher-level structure is not recovered

1. Gather the existing misses (Q-L4 census, Q-L5 distances, Q-L6 to Q-L9 right-block data, Q-L10 block checks): per
   structure kind and endpoint, recovered, partly (a block touches it, none is right), missed (no block touches it).
2. Locate the loss: (i) provenance mixing (one cell carries logic of more than one HDL construct), (ii) partition cut
   wrongly (SPLIT, BLOATED, UNDERREACH, NOSEED of Q-L9), (iii) wrong kind label, (iv) wrong LLM decode of a right block,
   (v) assembly.
3. 3 to 5 ranked plain-English hypotheses, each with its measure. One question at a time: the strongest is tested with
   existing data only, with a CI.

## Amendments

### 2026-11-03 amendment 1: scope found in the inventory, and the Part B test fixed before the outcome analysis

1. Every model reply in the repository (llm-pilot, llm-full, llm-hints2, ql10-blocks) is for the Gate-Breaker gate netlists
   of VerilogEval. No reply exists for a k4 or k6 netlist. The paired Part A comparison is therefore at the gates endpoint
   only; k4 and k6 carry the structural data (Q-L4 to Q-L9, benchmark of r4 and composite designs, cell classes O-gate/Y-gate =
   gates, O-lut/Y-lut = k4, O-hard = k6 hard-block map) and no LLM number. The cost of the missing LLM arms is given in the
   results.
2. Scorer: the three wrappers were run on 16 problems spread over the reply sizes (`results/scorer_compare.csv`). Chosen:
   `ql10-blocks/q10_astcfg.py` (see results for the reason).
3. Part B primary test, fixed here before any recovery-rate analysis of construct sizes or provenance mixing was run (the
   marginals of `endpoint_size.csv` had been read: they show provenance mixing across parts is small, 4 percent of O-gate
   cells and under 1 percent of O-lut and O-hard cells, and not rising with k). The strongest hypothesis by the existing
   evidence (Q-L9: of the constructs with no right block, SPLIT is the largest class) is the size hypothesis:
   H-L11 (controller's words): a construct is recovered less often the more cells it has, because a large construct is cut
   across several blocks (SPLIT). Measure: right-block share of the answer-key constructs (Q-L9 HEAD, TEST), large against
   small, where large = more than the median number of cells of the constructs of that endpoint; difference large minus small
   with a seeded bootstrap 95 percent CI resampling designs (seed 20261103, 2000 resamples), per endpoint and all. SUPPORTED when the
   CI of the all-endpoint difference is below zero, INCONCLUSIVE when it touches zero, DISMISSED when above zero.
   The provenance-mixing hypothesis (recovery falls as the share of a construct's cells with mixed provenance rises) is
   reported as a descriptive table (share of constructs with a mixed cell, right share with and without), without a verdict.
   Mixed cell: the module path of the cell's Odin III label contains `*` (a join of cells from more than one design part).

## Results (2026-11-03)

Full tables: `results/summary.md` (written by `q11_report.py`; csv files beside it). No model call was made. Scorer: the
three wrappers agree to six decimals on 15 of 16 problems (`results/scorer_compare.csv`; the sixteenth is a pyverilog parse
failure in all three), because all call the same Gate-Breaker `metrics.py` and `odin3_cfg.py`. Chosen: `q10_astcfg.py`
(numpy kernel equal to the probe's sum, flatten step, 12,000-node limit, tested; re-scoring arm A reproduced the 492 values
of Q-L10 exactly). 1,967 compiled replies of llm-full (A, B, C) and llm-hints2 (A2, B1p, B2, W) were scored raw and flat
(`results/astcfg_all.csv`, 3,934 scores); D and D+h come from `ql10-blocks/results/astcfg_rows.csv` (same scorer). The 40-problem
pilot replies are stored without an arm key and were not re-scored (llm-full re-runs its arms).

### Inventory (`results/inventory.csv`)

Every reply is at the gates endpoint; no reply exists at k4 or k6. Arms and sizes: A, B, C 137 problems x 3 draws; A2, B1p, B2, W 64 x 3;
D 43 problems run (+4 over-cap, +5 processor modules), D+h 28 (+4, +5); pilot A/B/C 40/38/40 x 1.

### Part A: Loki with a model against Gate-Breaker alone, gates endpoint (same writer; tested minus reference; 95% CI over problems)

| comparison | pass@1 | AST | CFG |
| --- | --- | --- | --- |
| D (blocks) vs A, 43 / 36 / 41 problems | +0.008 (-0.031, +0.054) INCONCLUSIVE; draws W5 L4 T118 | -0.026 (-0.045, -0.010) WORSE; draws W16 L57 T33 | -0.028 (-0.046, -0.013) WORSE; W20 L65 T34 |
| D+h vs A, 28 / 24 / 28 | -0.024 (-0.083, +0.024) INCONCLUSIVE | -0.036 (-0.063, -0.015) WORSE | -0.040 (-0.064, -0.019) WORSE |
| B (hints v1) vs A, 137 | -0.010 (-0.037, +0.017) INCONCLUSIVE | 0.000 (-0.001, +0.001) INCONCLUSIVE | -0.005 (-0.016, +0.001) INCONCLUSIVE |
| B2 (hints v2) vs A2, 64 | +0.099 (+0.052, +0.151) BETTER; W20 L1 T171 | +0.001 (-0.000, +0.003) INCONCLUSIVE | +0.007 (+0.000, +0.019) BETTER |
| B2 vs W (wrong hints) | +0.073 (+0.026, +0.130) BETTER | +0.001 INCONCLUSIVE | +0.012 INCONCLUSIVE |
| C (no netlist) vs A | -0.329 (-0.409, -0.253) WORSE | -0.045 (-0.064, -0.030) WORSE | -0.015 (-0.028, -0.001) WORSE |

Headline, gates: the blocks arm (Loki + LLM agent) is not better than Gate-Breaker alone on pass@1 (no detectable difference) and
is lower on both of Gate-Breaker's similarity measures by about 0.03 with the interval below zero; version-2 hints are the one
Loki+LLM arm that passes more tests than the netlist alone (+0.099), with unchanged similarity. As written (not the headline), the
assembled D top module is far lower (AST -0.354, CFG -0.396) because it only instantiates blocks. Where A cannot run (4 over-cap
designs) D stands alone: 8 of 12 draws pass, flattened AST 0.748, CFG 0.874. k4 and k6: untested, no replies. Cost to close the gap
(`results/gap_cost.csv`, estimates): arm A needs 411 calls per endpoint, about 0.18 million input tokens at k4 and 0.33 million at k6
(gates 0.89 million), 51 thousand output tokens; arm D needs the block builder run on the k4 and k6 netlists first (no model call).

### Endpoint size (`results/ve_endpoint_size.csv`, 156 VerilogEval references; `results/endpoint_size.csv`, benchmark)

Cells per design 305.3 / 63.2 / 113.5 (gates / k4 / k6), inputs per logic cell 1.74 / 4.27 / 4.04, gates per cell 1.00 / 4.83 / 2.69,
construct types per labelled cell 3.70 / 3.65 / 1.79. Larger in what a cell hides, smaller in cell count. The repository calls the
f2 soft-logic LUT netlist "k4" and the f1-k6 hard-block map "k6" (both come from the six-input mapper).

### Part B: where structure is lost (Q-L9 HEAD blocks, TEST, 1,141 constructs, five state kinds; `results/taxonomy_kind_endpoint.csv`)

Recovered 816 (0.715): gates 214 of 351 (0.610), k4 347 of 460 (0.754), k6 255 of 330 (0.773). Partly (a block touches, none right) 325;
missed outright 0. Failure classes: SPLIT 180, BLOATED (swallowed) 110, UNDERREACH 35. Per kind, recovered share: fsm 0.736, counter
0.750, shift 0.693, regfile 0.864, register 0.663; shift at gates is the lowest (0.489). Stage table: `results/loss_stage.csv`.
Provenance mixing across design parts: 4.1% of O-gate cells, 0.2% O-lut, 0.3% O-hard.

Ranked hypotheses (plain English): (1) swallowing (a block grown to its end takes in neighbours, small constructs vanish; 37 of 92 and 39 of
57 misses of small constructs at k4 and k6); (2) cutting (SPLIT, 180; join repaired 157 of 251 earlier); (3) mixed provenance at gates
(0.30 vs 0.71 right, 30 constructs, descriptive); (4) synthesis erased the structure (106 of 119 audited soft-logic constructs lost units at the first opt); (5) the kind guess (macro F1 0.392; loses the name, not the cells).

Test of the pre-registered hypothesis (amendment 1): H-L11, larger constructs are recovered less often. DISMISSED: large minus small
right-block share +0.126 (+0.076, +0.177) over all endpoints; gates -0.008 (-0.116, +0.101) INCONCLUSIVE; k4 +0.292 (+0.216, +0.363); k6 +0.234 (+0.145, +0.320).
Large constructs are recovered more often, so the first one-question test of Part B fails. Mixing (descriptive, no verdict): constructs with a mixed
cell 51 of 928 labelled; right 0.451 against 0.761 without (-0.310, -0.450 to -0.167).

### Deviations and limits

1. The 1,141 constructs are those of Q-L9 (constructs D70 also scored); the answer key covers five state kinds, so adders, mux trees,
   ALUs and memories (as arrays) are not covered. 2. "Partly" is any construct a block touches without a right block. 3. The Part B
   benchmark (micro/composite designs) is not the VerilogEval set of Part A: endpoints are compared inside each, not across them.
4. Pairing uses the common draws; Q-L10 used the same pairs for D against A (35 vs 36 problems because the pilot single-block problem is included here).
5. The size test splits at each endpoint's median; sizes differ by endpoint (gates 69 cells, k4 21, k6 20).
