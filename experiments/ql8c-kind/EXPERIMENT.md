# Q-L8c: a stronger kind likelihood for grown blocks (plan, 2026-11-02)

Branch feat/ql8c-kind on loki main fbcaa21 (after #74, Q-L7). Written before any TEST run of this experiment
(no run of any kind had been made when this file was committed; only the code and the committed results of #73
and #74 were read). Reuses experiments/ql6-grow and experiments/ql7-stop by import (anchors, grower paths, the
#73 likelihood `model.json`, truth, the #74 headline stop rule, geometry, the bootstrap and label helpers);
nothing of them is forked or changed. Another lane runs Q-L8a/b (ql8a-order, ql8b-anchors); those dirs are not
touched.

## Peter's words (2026-11-02)

"Try all them" (the three next-step pointers after #74). The pointer for this one, from the controller: "use the
directed graphlet approach of the growth to suggest what it is or might be". Purpose: Loki reverse engineering of
structural netlists (recovery of constructs). Measure: kind recall and precision per construct kind (macro F1),
top-3 accuracy and calibration (ECE), on the grown blocks and on the answer-key true blocks. Loki is Bayesian
only: every model below gives P(features | kind), the posterior is prior times likelihood.

## Question and hypothesis

One question: given a block, how well can its kind be guessed. The blocks are #74's (headline rule d, which is
within one prefix of growing to the end of the path); anchors, order and stop are not changed.

Hypothesis (controller): a likelihood built from richer directed graphlet features of the block (orbit
histograms normalised by size, the boundary signature, flip-flop share, feedback-path counts, typed cells where
Odin III gives them) raises kind precision and recall well above #74's at the same blocks, with calibrated
posteriors. "Well above" is fixed below as +0.10 absolute in macro F1.

Plain English first: #74 finds the right block for about half of the constructs, but its guess of what the block
is (FSM, counter, shift register, register file, register) is right only about a fifth to a quarter of the time. That guess
uses one thing, the shares of the 129 directed orbit types. Here we give the guess more to look at: how many
orbit instances per cell (not only shares), how the block touches the rest of the netlist, how many of its cells
are flip-flops, how much of it loops back on itself, how deep its logic is, and what hard cells it holds. Three
different ways of turning those into a likelihood are fitted on designs not in the test set, one is chosen on
other designs, and the chosen one is scored once on the test designs against #74's likelihood. It is scored twice:
on the blocks the grower really finds (right or wrong), and on the answer-key true blocks (an upper bound: the
kind guess when the block is already right).

## Data and split (by design, fixed now)

Units, constructs and the answer key are those of #73 and #74 (q6_truth): singles are one construct (the whole
design; kinds fsm, counter, shift, regfile, register and glue), composites are parts of kind fsm, counter, shift
cut out by the Odin III provenance labels (O-cells only). Units above 400 cells are not scored, blocks above 300
cells do not exist (#74). Three disjoint design sets from #73/#74:

- FIT: the even-MD5 half of TUNE (the half that trained #73's likelihood). Samples: the prefixes of the answer-key
  blocks (breadth-first visit order from the seed, prefix sizes from the schedule of q6_train.py), as in #73, every
  kind including glue. Same data as #73 so that the only change is the features and the model.
- CAL: #74's TRAIN (odd half, `(md5 // 2) % 2 == 0`, 97 designs): the temperature of every model is fitted here on
  the grown blocks (#74 rule d). Also the #74 likelihood is re-calibrated here, as a second baseline (B73-T).
- VAL: #74's VALIDATION (82 designs): the model choice (below), on the same grown blocks.
- TEST: scored once, after everything above is fixed and committed.

Grown blocks of CAL and VAL are the #74 paths (`$QL7_OUT/paths`, read only), cut at the prefix chosen by rule d with
the committed `chosen.json` and classifier `clf.pkl`; those of TEST are #73's no-stop paths (`blocks_nostop`),
cut the same way. No path is regrown.

Label of a grown block: the set of constructs it is right for (the #72 rule: coverage >= 0.8 and Jaccard >= 0.5).
A block right for at least one construct is a "right block"; its label kind(s) are the kinds of those constructs.
A block right for none has label glue ("no known construct") for the likelihood calibration and the 6-way
scores; the claim metrics below follow #74 exactly.

## Features (fixed now; every graph statistic is computed on the block's cell set)

Orbit counts come from the Odin III graphlets pass (q6_sig.SigCounter, directed, global nets excluded; no second
counter). Per block B with n cells:

- H, 129 values: Hellinger-scaled orbit shares sqrt(o_i / sum o) (the #73 feature, kept).
- D, 129 values: log(1 + o_i / n), the orbit instances per cell.
- S, scalars (19): log2 n; flip-flop share; hard-cell share; adder share; hard cells by model count (memory,
  multiplier, adder) as shares; mean LUT inputs of the logic cells; internal edges per cell (cell-to-cell driver
  to reader links through non-global nets); boundary: conductance phi = cut / volume (as q7_feat.Geometry), fan-in
  and fan-out of the frontier per cell, distinct primary inputs read per cell; feedback: nontrivial strongly
  connected components of the internal directed graph (count, share of cells inside, largest as share of n, share
  of flip-flops inside, cycle rank = edges inside SCCs minus nodes inside plus SCC count, per cell); longest
  combinational path (log1p) in the internal graph with flip-flop outputs cut.

## Likelihood models (fixed now; all give log P(features, size | kind), per target cell with the pooled fit as a
fallback when a cell-kind has fewer than 40 samples, as #73)

- M1, naive Bayes on binned features. Every feature of D and S plus log2 n is cut into 6 quantile bins (edges from
  FIT, pooled over kinds; constant features dropped); P(bin | kind, cell) is a Laplace-smoothed (alpha = 1) count
  mixed 10:1 with the pooled cell estimate. No H (D carries the same information in a form without the sum constraint).
- M2, full-covariance Gaussian per kind on reduced features. Standard-scale H, D and S on FIT, PCA to 24
  components (FIT, pooled over kinds), per kind the mean is a ridge-regressed line in log2 n (the #73 size term),
  the residual covariance is the sample covariance shrunk 0.3 toward its diagonal plus 1e-3, further shrunk
  toward the pooled-kind diagonal with weight 200 samples as #73.
- M3, a generative mixture per kind with a size term. Same PCA, plus standardised log2 n as a 25th coordinate;
  per kind sklearn GaussianMixture(covariance_type="diag", reg_covar=1e-3, random_state=0, n_init=2) with
  min(3, n // 40) components (1 when fewer than 80 samples). The size term is the joint density of the size
  coordinate with the rest.
- B73: #74's likelihood (q6_model, `model.json`, T as fitted in #73). B73-T: the same model with its temperature
  refitted on CAL grown blocks like the new models, so the calibration is not what separates the models.

Posterior (all models): P(k | B) proportional to prior_k * exp(T * loglik_k); prior = the L3 census prior as #73
(q6_model.census_prior); a block with no edges (empty orbit vector) gets the prior. T is chosen on a grid
(0.002 .. 1, the grid of #73) by the held-out negative log posterior of the label on the CAL grown blocks.
The log-likelihoods of the 129 orbits are far from independent, so T < 1 is expected (the tempered likelihood
is still a Bayesian posterior with a flattened likelihood; this is the #73 convention, not a change).

## Evaluation (TEST once)

Block sets: GROWN = #74 rule-d blocks of the TEST units (all blocks; "right blocks" = those right for a
construct); TRUE = the answer-key blocks of the same units' non-glue constructs. Argmax over the six kinds.
Claim: a block of at least 4 cells whose argmax is not glue (as #74). TP: the claimed kind is the kind of a
construct the block is right for (GROWN) or the construct's kind (TRUE).

1. Per kind (fsm, counter, shift, regfile, register): recall and precision at the argmax, macro F1 over the five
   kinds, for B73, B73-T, the three models and the chosen one. GROWN (precision over all claims; recall over the
   constructs, a construct counts when a right block claims its kind, as #74's pr_by_kind) and TRUE (precision
   over the claims on true blocks).
2. Top-3 accuracy: label among the three most probable kinds, on right blocks (label = kind) and on TRUE.
3. Calibration: top-label reliability (10 equal-width confidence bins) and ECE, on GROWN all blocks (label glue
   when not right), GROWN right blocks, and TRUE. Plot: reliability.svg.
4. Per target (gate = O-gate + Y-gate, k4 = O-lut + Y-lut, k6/hardmap = O-hard) and single vs composite: macro F1,
   ECE.
5. Per unit (design x cell): constructs claimed with the right kind, chosen model against B73, W/L/T and the
   geomean of (g+1)/(d+1) with a 90 percent bootstrap over designs (1000 resamples, seed 1, as #74).

## Choice and verdicts (fixed now)

Choice: the model with the highest macro F1 on VAL grown blocks (precision over all claims, recall as above), ties
by the lower negative log posterior on VAL. The three models are three comparisons.

QL8c-a: chosen model against B73 on GROWN, per unit geomean (point 5): BETTER (CI lower bound above 1), WORSE (upper
below 1; DISMISSED), else INCONCLUSIVE (a positive geomean with a CI touching 1 is INCONCLUSIVE, not DISMISSED).
QL8c-b (the hypothesis): macro F1 gain of the chosen model over B73 on GROWN, 90 percent bootstrap over designs:
SUPPORTED when the lower bound exceeds +0.10, CONTRADICTED when the upper bound is below +0.10, else INCONCLUSIVE.
QL8c-c: ECE of the chosen model against B73-T (GROWN, all blocks), difference with 90 percent CI: MEASUREMENT.
QL8c-d: macro F1 and top-3 on TRUE blocks, chosen against B73: MEASUREMENT (the upper bound).

## Limits, stated before the run

The blocks are the #74 blocks (right-block share about 0.53): a kind guess on a wrong block has no right answer
except glue, and no model here is trained on wrong blocks (the fit samples are true-block prefixes), so precision
on wrong blocks is limited by that; the benchmark is the VerilogEval-derived corpus of #69 to #74 with its kind
mix and the census prior does not match the TEST mix (#73); regfile has few constructs; FIT, CAL and VAL are
small (about 9.6 thousand prefix samples, a few hundred grown blocks), so M2 and M3 fit few components per kind; one
deterministic run (seeds fixed).

## Deviations, found on CAL and VAL and fixed before any TEST run (2026-11-02)

The first fit-and-score on VAL (`results/tuning_first.csv`, the plan as written) showed a flaw of the plan, not of
the models: with the temperature fitted on all CAL grown blocks (label glue for the wrong half), every new model
sank to a flat posterior (T 0.002 to 0.05) and almost nothing was claimed (VAL macro F1 0.00 to 0.07). No model
has seen a wrong block, so the only way to lower the loss on wrong blocks is to give up on kinds. Two changes,
both decided on CAL and VAL numbers only:

1. Calibration set. T is fitted on the CAL grown blocks that are right for a construct only (label = their kinds):
   the kind guess given a right block, as #73 fitted T on true blocks. The plan's all-blocks calibration is kept
   as the first-run table and as the "ECE on all grown blocks" column, which now measures how the posterior
   behaves on wrong blocks too.
2. Wrong blocks for the glue class (model M4). M4 is M2 fitted on the FIT samples plus the grown blocks of the FIT
   designs (the same #74 paths grown on the even half by q8_grow.py, cut by rule d; units up to 400 cells), each
   with its label: the kind of the construct it is right for (one sample per kind), glue when it is right for
   none. The grown paths of the FIT designs are in-sample for the #73 likelihood that ordered them, so their
   wrong blocks are somewhat less wrong than those of unseen designs; stated, not corrected. M4 is a fourth
   comparison; the choice rule (highest VAL macro F1) is unchanged and runs over M1 to M4.

## Fitting and choosing (FIT, CAL, VAL only; written before the TEST run)

Sizes: FIT 9596 prefix samples (as #73) plus 1286 grown blocks of 769 FIT units for M4; CAL 383 units, 524 blocks,
415 constructs; VAL 320 units, 440 blocks, 328 constructs. Temperatures from the CAL right blocks. VAL
(`results/tuning.csv`; B73 reproduces #74's posterior to 5e-5):

| model | T | macro F1 grown | macro F1 true | ECE grown | ECE true | top-3 right |
|---|---|---|---|---|---|---|
| B73 (= B73-T) | 0.15 | 0.326 | 0.550 | 0.166 | 0.133 | 0.921 |
| M1 naive Bayes | 0.1 | 0.319 | 0.565 | 0.189 | 0.098 | 0.945 |
| M2 full Gaussian | 0.2 | 0.375 | 0.601 | 0.141 | 0.078 | 0.909 |
| M3 mixture | 0.1 | 0.266 | 0.478 | 0.121 | 0.081 | 0.945 |
| M4 M2 + wrong blocks | 0.2 | 0.356 | 0.508 | 0.156 | 0.169 | 0.896 |

Chosen: M2 (`results/chosen.json`). Reading before the TEST run: the VAL gain of M2 over B73 is +0.049 macro F1
(90 percent CI -0.001 to +0.075, same bootstrap), below the +0.10 of QL8c-b, so QL8c-b is expected to be
CONTRADICTED on TEST unless TEST differs from VAL; the TEST verdicts are fixed by the rules above, not by this reading.
