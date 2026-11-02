# Q-L7: a better stop rule for anchor-and-grow (plan, 2026-11-02)

Branch feat/ql7-stop on loki main f3b7948 (after #73, Q-L6). Written before any TEST run of this experiment
(no run of any kind had been made when this file was committed; only the code of #73 and its committed
results were read). Reuses experiments/ql6-grow by import (anchors, grower, likelihood model, truth, the
bootstrap and label helpers); nothing of it is forked or changed.

## Peter's words (2026-11-01)

"I'll decide most of this tomorrow build a better stop on loki". Purpose: Loki reverse engineering of
structural netlists (recovery of constructs); follow-up to #73. Measure: right-block share (a block is right for
a construct when coverage >= 0.8 and Jaccard >= 0.5, as #72 and #73) and recall and precision per kind.

## Question and hypothesis

One question: which stop rule recovers the right block when blocks grow from anchors. The growth order, the
anchors, the likelihoods (the #73 model, `model.json`, unchanged) and the benchmark stay as in #73.

Hypothesis (controller; Peter may restate): a stop rule that does not depend on the weak per-step likelihood
closes most of the gap between #73's stop (0.049 right) and the answer-key ceiling (0.556), and beats D70 (0.385).

Plain English first: #73 grew blocks well but stopped them early, because it stopped when the odds wobbled.
Here every block is grown all the way (until nothing is left to add, or 300 cells) and the whole growth path is
recorded. Then a stop rule looks at the finished path and picks the size to cut at. We test four ways of picking:
(a) the size at which the guess "known construct, not glue" is best after a penalty for size; (b) the size where
the block is most cleanly separated from the rest of the netlist (few wires cross its border); (c) a classifier
trained on other designs to say "this is the right size"; (d) the better two of these combined. The answer key is
used only to train (c) and to choose settings on designs that are not in the test set, and to score.

## Paths (the only growth)

Same grower as #73's post hoc variant (`QL6_NOSTOP=1`, q6_grow.py): all anchors grow at once, one cell per
round per block, always the frontier cell of highest evidence (the #73 order), no Bayes factor stop, no
lookahead. A path ends when the block has no free frontier cell (frontier exhausted; a cell owned by another
block, anchor cells included, is never taken, which is the contact stop) or at the size cap of 300 cells.
Size cap: 300 cells per block, and units (design x cell) of at most 400 cells, exactly as #73's variant. Constructs
larger than 300 cells cannot be right, and units above 400 cells are not scored (about 100 of 1453 TEST units);
this keeps the ceiling 0.556 comparable. Nothing is regrown for TEST: the TEST paths are those of #73's variant
(`$QL6_OUT/blocks_nostop`, read only); a test regrows three small TEST units and checks they are identical
(determinism). TRAIN and VALIDATION paths are grown with the same code (q7_paths.py) on TUNE designs.

## Split (by design, fixed now)

#73 halves TUNE by the parity of the MD5 of the design name: even = likelihood training, odd = temperature
calibration. The growth order of an even design is in-sample for the likelihood, so no even design is used here.
The odd half (the calibration half, 179 designs of which none trained the likelihood) is split again:
TRAIN = (int(md5, 16) // 2) % 2 == 0, VALIDATION = the rest. TEST designs are touched only for the final scoring
(run once, after everything below is fixed and committed). All fitted or tuned numbers come from TRAIN; VALIDATION
chooses (i) the headline rule and (ii) the operator of rule d. Unit and construct counts are in the results.

## Per-prefix features and the key

For every block and every prefix (step 0 = the anchor, then each added cell in path order): size s; the #73
posterior over the six kinds (from the recorded trajectory); p_ng = largest non-glue posterior; log odds
L = ln p_ng - ln P(glue); ev = #73's log odds of known construct against glue (NO_EVIDENCE when no edges);
conductance phi = cut / volume, where cut = number of nets with at least one pin inside and at least one pin
outside the block and volume = number of (cell, net) incidences of the block cells; nets read by 16 or more
cells are global and ignored in both (as the grower cuts them, #73); frontier fan-in = distinct cells outside the
block that drive a net read inside, fan-out = distinct cells outside that read a net driven inside; flip-flop
share. A prefix with no edges has no signature (posterior = prior, ev = NO_EVIDENCE) and is never chosen by a rule
unless every prefix of the block is such. Key: a prefix is right for a construct under the #72 rule; "right" for
training label (c) = right for any answer-key construct of its unit.

## Candidate stop rules (fixed now)

A rule picks exactly one prefix per block. A construct is recovered when some block's chosen prefix is right
for it (the #73 criterion: the best Jaccard block is used there; the two coincide because blocks are disjoint
up to the cut).

a. MAP prefix. score_a(k) = L_k - lambda * ln(s_k). The prefix of highest score. This is the posterior odds of the
   best kind against glue with an MDL-style size term (lambda times the log of the size; lambda = 1 is the
   one-parameter-per-log-size cost of a BIC with one free size). lambda in {-1, -0.5, 0, 0.5, 1, 2, 4},
   chosen on TRAIN by right share. Negative lambda is a size reward, not a penalty; it is in the grid because
   #73's variant with lambda = 0 (ev rather than L) picked small prefixes (0.080 right). Ties go to the smaller prefix.
b. Cut quality. The first prefix k (any k >= 0) with phi_k strictly lower than phi_(k-1) (or k = 0) and phi_k <=
   phi_j for every j in k+1 .. k+W with W = max(L0, ceil(0.25 * s_k)) (the lookahead skips noise minima; the window
   is cut at the path end). L0 in {2, 4, 8, 16}, chosen on TRAIN. If no prefix qualifies: the prefix of lowest phi
   (the smaller on ties).
c. Learned stop. sklearn HistGradientBoostingClassifier(max_depth=3, max_iter=100, learning_rate=0.1,
   random_state=0) on the features of one prefix: log2 s, p_ng, P(glue), entropy, ev (clipped at -50), L,
   delta p_ng and delta ev against the previous prefix, phi, delta phi against the previous prefix, phi minus the
   lowest phi so far, p_ng minus the highest p_ng so far, fan-in, fan-out, flip-flop share. Label: right for any
   construct. Trained on every prefix of every TRAIN block. The prefix of highest predicted probability is chosen
   (the smaller on ties). No threshold.
d. One combination of the best two of a, b, c by VALIDATION right share: the operator is the one of {smaller,
   larger, geometric middle} (the prefix whose size is nearest the geometric mean of the two chosen sizes) with the
   highest VALIDATION right share. The headline rule for the verdicts is the rule of highest VALIDATION right
   share among a, b, c, d (ties: a before b before c before d). All four are reported on TEST; four rules are four
   comparisons, which the register row says.

Reference rows (not candidates): E73 = the #73 grower's final blocks (results of the committed #73 run, per
construct `right` in ql6-grow/results/construct_records.csv); END = the end of the path (frontier exhausted or
cap); ORACLE = the best prefix of any block by the key (a ceiling, 0.556 in #73).

## Evaluation (TEST once; TRAIN and VALIDATION tables are given for the fitted choices)

Constructs: the answer-key constructs with provenance of the TEST units of at most 400 cells that D70 also scored
(the #72 records), non-glue, as #73's variant (1141 there).
1. Right-block share per rule against D70, E73 and ORACLE: overall, per target (gate = O-gate + Y-gate, k4 =
   O-lut + Y-lut, k6/hardmap = O-hard), per kind. Per unit (design x cell): right constructs of the rule against D70,
   W/L/T and the geomean of (g+1)/(d+1) with a 90 percent bootstrap over designs (1000 resamples, seed 1, as #73).
   Same against E73. CAD labels: BETTER (CI lower bound above 1), WORSE (upper below 1), else INCONCLUSIVE; positive
   geomean with a CI touching 1 is INCONCLUSIVE, not DISMISSED; WORSE with the upper bound below 1 maps to
   DISMISSED as in #73.
2. Gap closed = (share_rule - share_E73) / (share_ORACLE - share_E73), all on the same construct set, 90 percent
   bootstrap over designs.
3. Recall and precision per kind at the argmax: a claim is a chosen prefix of at least 4 cells whose argmax over the
   six kinds (from the trajectory) is not glue; TP when the chosen prefix is right for a construct of the claimed
   kind; recall = constructs of the kind recovered with that kind claimed; precision = TP / claims of the kind.
4. Block size distribution: chosen size and the best-Jaccard block's size over the true size (quartiles) per rule.
5. Failure classes (each non-recovered construct gets exactly one, first match): NOSEED (no block touches the true
   block); ORDER (blocks touch it but no prefix of any block is right: the growth order fails); TOOSMALL (a right
   prefix exists, the chosen prefix of that block is smaller than every right prefix); TOOBIG (larger than every right
   prefix; sub-class MERGED if the chosen prefix also covers at least half of another construct of the unit);
   BETWEEN (a right prefix exists, chosen size lies between right sizes, i.e. wrong because the path is not
   monotone); NOTCHOSEN (the right prefix exists only on a block that is not the one with the best Jaccard; not
   reached with disjoint blocks, counted to be sure).

## Verdict rules (fixed now)

QL7a: the headline rule recovers more constructs than D70: BETTER / WORSE / INCONCLUSIVE by the geomean rule above.
QL7b: the headline rule closes most of the gap (hypothesis): SUPPORTED when the bootstrap lower bound of the gap
closed is above 0.5, CONTRADICTED when the upper bound is below 0.5, else INCONCLUSIVE.
QL7c: each rule against E73 (geomean per unit), measurement label as QL7a. QL7d (failure classes, sizes): MEASUREMENT.
QL7e (added, see Deviations): the headline rule against END (grow to the path end), geomean per unit, all / single / comp,
labelled BETTER / WORSE / INCONCLUSIVE; a stop rule is only useful if it beats "never stop".

## Limits, stated before the run

Units above 400 cells and blocks above 300 cells are not scored; the path uses the weak #73 posterior for the
order and for features; the oracle and the key-trained classifier use the key (c is trained on other designs, never
on its own); 90-odd designs train (c) and the combination; one deterministic run, seed 0 for the classifier;
Y-cell composite parts have no key and are not scored; the priors do not match the TEST mix (#73).

## Fitting and choosing (TRAIN and VALIDATION only; written before the TEST run)

Split sizes (checked): 179 odd-half designs, 97 TRAIN and 82 VALIDATION; 703 units of at most 400 cells (383
TRAIN, 320 VALIDATION); 415 and 328 non-glue constructs; 524 and 440 blocks. Right share (`results/tuning.csv`,
`results/tuning_by_set.csv`):

| rule | TRAIN | VALIDATION | VALIDATION single / comp |
|---|---|---|---|
| a (lambda = -8, grid edge) | 0.371 | 0.393 | 0.571 / 0.272 |
| b (L0 = 16, grid edge) | 0.402 | 0.442 | 0.617 / 0.323 |
| c (classifier) | 0.484 | 0.509 | 0.669 / 0.400 |
| d (larger of c and b) | 0.487 | 0.512 | 0.669 / 0.405 |
| END (grow to the end of the path) | 0.496 | 0.512 | 0.669 / 0.405 |
| ORACLE | 0.530 | 0.521 | 0.669 / 0.421 |

Chosen: lambda = -8, L0 = 16, pair c + b, operator larger, headline rule d (`results/chosen.json`). Reading before
the TEST run: on a single-design unit the true block is the whole design, so growing to the end is already
the ceiling there (0.669); on composite parts END is 0.405 against an oracle of 0.421 on VALIDATION (0.394 against 0.453 on
TRAIN). So the room for a stop rule above "never stop" is small on this benchmark, and rule a only improves as lambda
falls to the grid edge (it tends to END), rule b as L0 grows (also toward END). Rule d is within one prefix of END
on VALIDATION. The TEST verdicts below are fixed accordingly (QL7e).

## Results, 2026-11-02 (plain English first)

Plain English: letting every block grow to the end of its path and then choosing where to cut did what the
hypothesis asked for: the right block is found for 0.528 of the constructs (headline rule d), against 0.053 for the
#73 stop, 0.385 for the D70 cones and 0.556 for the answer-key ceiling, so about 94 percent of the gap between the #73 stop
and the ceiling is closed. But the result is almost entirely "do not stop": growing to the end of the path (END) is right
for the same 0.528, and none of the three stop rules we built (size-penalised posterior, lowest conductance, learned
classifier) beats it; rules a, b and c are each worse than END, and rule d, the combination chosen on VALIDATION, is END
within one prefix. The reason is the benchmark: for a single-design unit the true block is the whole design, so the end of the
path is already the ceiling (0.597 of 635 single constructs); only the composite parts (506 constructs) leave room, and
there END is 0.441 and the ceiling 0.504. Where the headline rule does beat D70 it is on gate netlists (geomean 1.348)
and single designs; on composite parts (1.058, CI 0.991 to 1.125) and on the k6 hard-map target (0.968) the difference to D70 is
inconclusive. The remaining failures are the growth order (449 of 1141 constructs have no right prefix on any block) and
anchors that never touch the true block (58), not the stop.

CAD-style counts first (TEST only; `results/*.csv`; 1141 constructs of the TEST units of at most 400 cells that D70 and
#73 also scored; the ceiling 0.556 and D70 0.385 equal the #73 post hoc numbers on the same constructs).

Right-block share (`results/right_block.csv`, `results/right_block.svg`):

| scope | constructs | E73 | D70 | a | b | c | d (headline) | END | ORACLE |
|---|---|---|---|---|---|---|---|---|---|
| all | 1141 | 0.053 | 0.385 | 0.422 | 0.462 | 0.514 | 0.528 | 0.528 | 0.556 |
| gate (O + Y) | 351 | 0.000 | 0.242 | 0.368 | 0.387 | 0.564 | 0.581 | 0.587 | 0.595 |
| k4 (O + Y) | 460 | 0.057 | 0.439 | 0.483 | 0.550 | 0.554 | 0.557 | 0.552 | 0.598 |
| k6 / hardmap | 330 | 0.106 | 0.461 | 0.394 | 0.418 | 0.406 | 0.430 | 0.430 | 0.455 |
| single | 635 | 0.043 | 0.356 | 0.450 | 0.507 | 0.581 | 0.594 | 0.597 | 0.597 |
| comp | 506 | 0.067 | 0.421 | 0.385 | 0.405 | 0.431 | 0.445 | 0.441 | 0.504 |

Per kind (all cells): fsm d 0.438 against D70 0.392 (ceiling 0.459); counter 0.483 against 0.342 (0.512); shift 0.569
against 0.525 (0.649); regfile 0.795 against 0.477 (0.795); register 0.589 against 0.310 (0.595).

Per design x cell unit against D70 (`results/unit_cmp.csv`; geomean of (g+1)/(d+1), 90 percent bootstrap over designs,
857 units): headline d 1.146 (1.105 to 1.190), W296 / L130 / T431, BETTER (QL7a). By target: gate 1.348 (1.298 to 1.404) BETTER;
k4 1.122 (1.066 to 1.179) BETTER; k6 / hardmap 0.968 (0.919 to 1.020) INCONCLUSIVE; by set: single 1.179 (1.129 to 1.234)
BETTER; comp 1.058 (0.991 to 1.125) INCONCLUSIVE. The other rules against D70: a 1.045 (1.008 to 1.084), b 1.080
(1.041 to 1.118), c 1.134 (1.092 to 1.177), all BETTER overall. Against the #73 grower every rule is far better
(QL7c: d 1.521, 1.477 to 1.569, W506 / L3 / T348). Gap closed from E73 to ORACLE for d: 0.944 (0.927 to 0.961), SUPPORTED
(QL7b).

Against growing to the path end (QL7e, added before the TEST run): a 0.912 (0.898 to 0.927) WORSE; b 0.943 (0.932 to 0.952)
WORSE; c 0.990 (0.984 to 0.996) WORSE; d 1.000 (0.997 to 1.004), W5 / L5 / T847, INCONCLUSIVE (comp only: 1.008, 0.997 to 1.022,
W5 / L3 / T214). Rule d differs from END on a handful of units and has the same 602 right constructs.

Recall and precision per kind (`results/pr_by_kind.csv`; claim = chosen prefix of 4 cells or more whose argmax is not glue;
the #73 posterior is the weak part): headline d all kinds 792 claims, 213 true positives, precision 0.269, recall 0.185 (211
of 1141 constructs recovered with the right kind claimed); END precision 0.277, recall 0.182; c precision 0.264, recall 0.186;
b 0.227 and 0.174; a 0.188 and 0.162. By kind for d (precision / recall): fsm 0.286 / 0.249, counter 0.265 / 0.129, shift
0.251 / 0.233, regfile 0.714 / 0.114 (7 claims), register 0.247 / 0.141. Recovering the block is much easier than naming
its kind with this posterior.

Block sizes (`results/sizes.csv`, chosen size of the best-Jaccard block): true median 29 cells (quartiles 13 and 65); d median
27 (10 and 66), END 27 (11 and 68), c 25, b 22, a 24. Over the true size: median 0.914 for d (0.965 for the blocks that are right); in the constructs that fail,
the ratio median is 0.63 and the upper quartile above 2 (blocks that are too big or merged) for c, d and END; b is smaller (0.525,
upper quartile 0.766).

Failure classes of the non-recovered constructs (`results/failure_classes.csv`, all cells; rule a / b / c / d / END):
NOSEED 58 for every rule; ORDER 449 for every rule (the growth order never reaches the right block); TOOSMALL 125 / 93 / 22 / 5 / 0;
TOOBIG 6 / 0 / 0 / 0 / 5; MERGED (also covers half of a neighbouring construct) 21 / 14 / 25 / 27 / 27; BETWEEN 1 / 0 / 0 / 0 / 0.
Rule a and rule b mostly stop too small (their lowest score or lowest conductance sits early on the path); rules c and d have
almost no too-small cases and are left with the merged neighbours, which END has as well.

Verdicts. QL7a (headline rule recovers more than D70): BETTER, as specified; with the caveat that composite parts
(1.058) and k6 / hardmap (0.968) are inconclusive. QL7b (closes most of the gap from #73 to the ceiling): SUPPORTED (0.944, 0.927 to 0.961).
QL7c (each rule against #73): MEASUREMENT, all BETTER. QL7d (sizes, failure classes): MEASUREMENT. QL7e (rule against growing to
the end): a, b, c WORSE, d INCONCLUSIVE. The hypothesis is true as worded and the useful part of it is "grow to the end", not
the stop rule.

Next step suggested, not run: the remaining loss is the growth order (449 constructs with no right prefix on any block) and the
anchor seed (58), so work on the order (a likelihood trained on more than six kinds, a different order than the weak per-step
evidence) and on separating merged neighbours in the composites, where END is 0.441 against 0.504.

Limits, stated not hidden. Units above 400 cells and blocks above 300 cells are not scored; the single-design units make END the
ceiling for 55 percent of the constructs; the classifier is trained on 97 designs (415 constructs) and
its features are mostly the weak #73 posterior and conductance; TEST was run once; four rules and four comparisons with
D70 (the headline carries the verdict); precision of the kind guess is low (0.27) because the #73 likelihood is weak; Y-cell
composite parts have no key and are not scored.

## Deviations from the plan (all before the TEST run)

(1) The lambda grid was extended from {-1 ... 4} to {-8, -4, -2, -1, ..., 4} after the first TRAIN and VALIDATION
tuning (best lambda was the grid edge -1, right share rising as lambda fell); -8 is still the best and still the
edge: the optimum of rule a is "no size cost", i.e. the limit END. (2) A split of the scores by set (single design
against composite part) and the comparison with END (verdict QL7e: headline rule against growing to the path end,
all / single / comp, same geomean rule) were added after TRAIN and VALIDATION showed END close to ORACLE. No TEST
number had been seen. (3) The failure class NOTCHOSEN is dropped: with the any-block criterion it cannot occur.
(4) The VALIDATION dry run of q7_eval.py has no D70 or #73 column (both counted as zero); those rows are meaningless
there and are not used. (5) Unit and construct counts were added above; the plan fixed none.
