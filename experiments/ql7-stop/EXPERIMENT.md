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

## Limits, stated before the run

Units above 400 cells and blocks above 300 cells are not scored; the path uses the weak #73 posterior for the
order and for features; the oracle and the key-trained classifier use the key (c is trained on other designs, never
on its own); 90-odd designs train (c) and the combination; one deterministic run, seed 0 for the classifier;
Y-cell composite parts have no key and are not scored; the priors do not match the TEST mix (#73).

## Deviations from the plan

(none yet)
