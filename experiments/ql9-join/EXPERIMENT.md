# Q-L9: a rule for joining and splitting grown blocks (plan, 2026-11-02)

Branch feat/ql9-join on loki main 9608573 (after #77 Q-L8b). Written before any run of the join and split rules on any
split (the only reads before this file was committed are the code and the committed results of #73 to #77). Reuses
experiments/ql6-grow, ql7-stop, ql8b-anchors and ql8c-kind by import (graph, anchors, grower paths, the #73 likelihood
`model.json`, the #75 M2 likelihood `models.pkl`, truth, scoring helpers, bootstrap and labels); nothing of them is forked or
changed.

## Peter's words (2026-11-02)

"Let's do the recommended for all of them": the next Loki question is block joining. Purpose: Loki reverse engineering of
structural netlists (recovery of constructs). Measure: right-block share (a block is right for a construct when coverage >= 0.8
and Jaccard >= 0.5, as #72 to #77) per target and set. Loki is Bayesian only, no LLM.

## Question and hypothesis

One question: after the blocks are grown, can a join step (merge blocks) and a split step (cut a block) recover constructs that
growth alone cuts across blocks or swallows, without losing the ones it already gets right.

Hypothesis (controller): a post-growth join / split step (merge adjacent blocks whose union is more probable as one construct than
as two, split a block where a cut separates two constructs) recovers a large share of the 251 split and 95 swallowed
constructs of #76 and raises the right-block share above #77's 0.550 without losing single designs.

Plain English first: growth starts one block at every anchor and lets the blocks compete. A construct that two anchors both
reach ends up cut in two blocks (SPLIT, the biggest failure class in #76), a block that runs past its construct swallows the
neighbour (BLOATED), and a block never gets to the full construct (UNDERREACH). Here the finished blocks are the input. We look
at every pair of touching blocks and ask whether one construct explains the union better than two do (join), and at every block
and ask whether one cut explains it better as two (split). The test counts how many constructs become right, and how many that were
right stop being right.

## Input (fixed now)

The #77 blocks: anchors of #74 plus bank, loop and const (`ql8b-anchors/results/chosen.json`), grown to the end of the path
(300 cells at most, END), no stop rule. Blocks are disjoint. TRAIN and VALIDATION units get the #77 paths regrown by
`q8b_grow.py bank+loop+const` (units that get no new anchor keep the #74 paths); TEST reads the #77 paths of
`$QL8_OUT/b` and #74's `blocks_nostop`, read only. A test checks that the cell sets rebuilt here give #77's END right share on
VALIDATION (reproduction of the baseline, "BASE"). Units above 400 cells are not scored (as #74 to #77).

## Join rules (fixed now)

Two blocks are adjacent when at least one non-global net (fewer than 16 readers, the cut of #73) links a cell of one to a cell of
the other (driver to reader). A union above 300 cells is never made. Const-anchor blocks take part like any other.

Evidence of a block: ev(B) = log odds that B is a known construct against glue, in the form the grower uses (`Model.evidence`:
log sum_k w_k exp(T loglik_k) - T loglik_glue, w = the block's own posterior over the five kinds). Two evidence sources: E73 (the
#73 likelihood) and EM2 (the #75 chosen M2 Gaussian, T = 0.2; the evidence is built the same way from its kind log-likelihoods
and the census prior). A block with no edges has no signature and ev = 0.

- JBF(E): score s = ev(A u B) - ev(A) - ev(B) (the log Bayes factor of "one construct" against "two constructs", each measured
  against glue), E in {E73, EM2}. Join when s >= t. Grid t in {-8, -4, -2, -1, 0, 1, 2, 4}.
- JCOND: s = links(A,B) / min(deg A, deg B), links = non-global driver-to-reader links between the two, deg = such links at any
  cell of the block (cut conductance between blocks). Grid {0.1, 0.2, 0.3, 0.5, 0.7}.
- JCTRL: s = Jaccard of the sets of global nets (16 or more readers) read by the cells of A and of B (shared control nets;
  adjacent pairs only; both empty gives 0). Grid {0.25, 0.5, 0.75, 1.0}.

Join step: greedy; the adjacent pair of highest score is merged, the scores of the new block are recomputed, until no pair has a
score at or above t or 50 merges are done (ties by the lower block id).

## Split rule (fixed now)

SFIED(E, t): for every block of 8 or more cells that is not a const-anchor block: the undirected graph of the block (cells linked
through non-global nets); its Fiedler vector (second smallest eigenvector of the normalised Laplacian, dense, numpy); the cells
sorted by the vector; the cut of least conductance among the prefixes with 4 or more cells on each side (a disconnected block is
cut at its components first); the cut is made when ev(A) + ev(B) - ev(B u A) >= t (the log Bayes factor of "two constructs"
against "one"). Each side may be cut again in the next round. Grid t in {0, 2, 4, 8, 16}.

## Order (fixed now)

JOIN (join step only), SPLIT (split step only), JS (split round then join step), SJ (join step then split round), FIX (alternate
a join step and a split round until nothing changes, at most 3 rounds of each). In FIX and for a BF join rule the split
threshold must exceed minus the join threshold (otherwise one pair can be joined and split by the same score); other rule pairs
are protected by the cap of 3 rounds only, and the state after the cap is the result.

## Split of the data and tuning (fixed now; as #74 to #77)

TUNE odd half: TRAIN = `(md5 // 2) % 2 == 0`, VALIDATION = rest; the even half is not used. TEST = the units of at most 400 cells.

1. TRAIN: every join rule at every threshold, JOIN only; metric: constructs right after minus constructs right before (net),
   per rule the best threshold (ties: the strictest, i.e. fewest joins).
2. VALIDATION: the four join rules at their TRAIN threshold; the headline join rule = highest net on VALIDATION; if no rule has a
   net above 0 there is no join in the headline (and the result is stated as it is).
3. TRAIN: SFIED with each evidence source (E73, EM2), every threshold, SPLIT only; best net (ties: the strictest, the highest
   threshold); it stays in the headline only if its VALIDATION net is above 0 (as for the join), else there is no split.
4. VALIDATION: the five orders at the chosen thresholds; the headline order = highest net on VALIDATION (ties: JOIN, SPLIT,
   JS, SJ, FIX).
5. TEST (the 1350 units) is run once with the headline configuration, the BASE row, and the fixed ablations (JOIN only and
   SPLIT only with the chosen thresholds), after the choice is committed. No number is tuned on TEST.

## Failure classes (of the blocks before the step, per construct that is not right)

NOSEED (no block shares a cell with it), UNDERREACH (the blocks that touch it together hold under 0.8 of it), SPLIT (no block
holds 0.8 of it, the touching blocks together do), BLOATED (a block holds 0.8 of it and the Jaccard is below 0.5: swallowed). The
#76 counts (251 SPLIT, 103 UNDERREACH, 95 swallowed) are those of the E74 blocks (`ql8a-order/results/construct_records.csv`
column `e74_sub`); here the classes are also taken on the #77 blocks, and the fixed share is given for both (the #76 class of a
construct, and whether it is right after the step).

## Evaluation (TEST once)

Constructs and key as #77 (1141 constructs of 857 units that D70 scored). For BASE and the headline: right-block share overall, per
target (gate = O + Y gate, k4 = O + Y lut, k6 / hardmap), per set (single, comp), per kind; oracle share (some block ever right is
not defined after joining, so the oracle column is #77's). Per unit (design x cell): right constructs of the headline against D70
and against BASE, W/L/T and the geomean of (g+1)/(d+1), 90 percent bootstrap over designs (1000 resamples, seed 1); BETTER, WORSE
or INCONCLUSIVE by the CI; a positive geomean with a CI touching 1 is INCONCLUSIVE, not DISMISSED. Also: constructs gained and
lost against BASE (newly broken) with the cause (the class and set of the lost construct), the fixed count per failure class
(#76 and #77 definitions), joins and splits made (count per unit, per rule), and the kind F1 of the blocks after the step (the
#75 M2 posterior, claim as #74 and #75: a block of 4 cells or more whose argmax is not glue; precision over claims, recall over
constructs, macro F1 over the five kinds), BASE against headline.

## Verdict rules (fixed now)

QL9-a (the hypothesis, share): SUPPORTED when the per-unit geomean against BASE is BETTER overall and the single designs are not
WORSE; CONTRADICTED when it is WORSE overall or fewer constructs are right than before; else INCONCLUSIVE. QL9-b (coverage of the
failure classes): SUPPORTED when at least a quarter of the #76 SPLIT constructs of TEST are right after the step, CONTRADICTED
when under 5 percent, else INCONCLUSIVE; the same for the swallowed class, reported separately. QL9-c (cost): constructs lost;
MEASUREMENT. QL9-d (kind F1 after joining): MEASUREMENT.

## Limits, stated before the run

Units above 400 cells and blocks above 300 cells are not scored; the join and split are on finished blocks, so a construct whose
cells are in no block (NOSEED) cannot be fixed; the evidence of a block is a tempered likelihood trained on true blocks, and a union
of two true parts is out of its training distribution; the thresholds are tuned on 383 and 320 units; one deterministic run; Y-cell
composite parts have no key and are not scored.

## Choice on TRAIN and VALIDATION (written before the TEST run)

Sizes: TRAIN 383 units, 415 constructs (219 right before any step); VALIDATION 320 units, 328 constructs (189 right before).
Net = constructs right after and not before, minus the reverse (`results/tuning_*.csv`, `results/chosen.json`).

Step 1, join rules on TRAIN, JOIN only, best threshold of each rule: JBF(E73) at -4: gained 46, lost 17, net +29 (130 joins);
JBF(EM2) at -1: 40 / 4, net +36 (82 joins); JCOND at 0.2: 66 / 12, net +54 (145 joins); JCTRL at 0.5: 8 / 4, net +4 (22 joins).
Step 2, the four on VALIDATION: JBF(E73) +37 (gained 52, lost 15), JBF(EM2) +44 (45 / 1), JCOND +54 (62 / 8, 134 joins; 189 to 243
right), JCTRL +14 (15 / 1); JCOND at 0.2 is the headline join.
Step 3, SFIED on TRAIN, SPLIT only: every threshold of the grid loses constructs (net -120 at 0 down to -10 at 8 for E73, -3 at 16
for EM2); E73 at 16 splits 4 blocks and has net 0 on TRAIN and on VALIDATION (5 splits), so it is not above 0 and **there is no split
in the headline**. The grid is monotone: a stricter threshold would only split nothing.
Step 4, orders on VALIDATION with no active split: JOIN, JS, SJ and FIX are the same result (net +54), SPLIT alone is +0; the
headline order is JOIN (the tie rule). So the headline is **JCOND at 0.2 as one join step**.

## Deviations from the plan (all before the TEST run)

(1) With no split in the headline, the fixed TEST ablations are, besides HEAD (= JOIN with JCOND at 0.2): the other three join rules at
their TRAIN thresholds (BF73 at -4, BFM2 at -1, CTRL at 0.5, so the hypothesis's own wording, Bayes factor, is scored on TEST), SPLIT
(SFIED E73 at 16, the TRAIN-best threshold, alone) and JS (HEAD join after that split round). Their per-unit comparisons and counts are
reported; none of them is the headline and none is tuned on TEST. (2) The TEST block set of units that get no new anchor is #74's
`blocks_nostop` and the others #77's own paths, read only; TRAIN and VALIDATION #77 paths were regrown here with `q8b_grow.py` (same code).
(3) A dry run of the whole evaluation on VALIDATION (`$QL9_OUT/dry`) was made to test the scripts; it has no D70 column.

## Results, 2026-11-02 (TEST, run once; plain English first)

Plain English: joining touching blocks works and splitting does not. One join step, run after growth, raises the right-block share
from 0.550 to 0.715 (cone detector D70 0.385). It fixes 157 of the 251 constructs that growth had cut across several blocks. It
does not help the constructs swallowed by a block that grows past them (the join never recovers one), and it costs 29 constructs
that were right (a joined block takes in a neighbour). The split step, in every setting tried, cuts more true constructs than it
repairs, so the headline has none. The join rule that won is the plainest of the four: join two blocks when a fifth or more of the
link ends of the smaller block lie on links to the other. The Bayes-factor rule the hypothesis described is weaker (0.680 with the
#73 likelihood, 0.677 with the #75 Gaussian) and shared control nets are weaker still (0.617).

CAD-style counts first (TEST only; 1141 constructs of 857 units that D70 also scored; `results/*.csv`; BASE = the #77 blocks,
reproduced here to 0.550, single 0.539, composite 0.565 before any step; HEAD = BASE plus the JCOND join at 0.2). Right-block share:

| scope | constructs | D70 | BASE (#77) | HEAD |
|---|---|---|---|---|
| all | 1141 | 0.385 | 0.550 | 0.715 |
| gate (O + Y) | 351 | 0.242 | 0.538 | 0.610 |
| k4 (O + Y) | 460 | 0.439 | 0.602 | 0.754 |
| k6 / hardmap | 330 | 0.461 | 0.491 | 0.773 |
| single | 635 | 0.356 | 0.539 | 0.742 |
| comp | 506 | 0.421 | 0.565 | 0.682 |

By kind (BASE to HEAD): fsm 0.568 to 0.736, counter 0.338 to 0.750, shift 0.772 to 0.693, regfile 0.659 to 0.864, register 0.537 to
0.663. Join rules (share): JCOND 0.715 (headline), JBF(E73) 0.680, JBF(EM2) 0.677, JCTRL 0.617; SPLIT alone 0.550; JS (join, then the
TRAIN-best split) 0.713.

Per unit (design x cell; geomean of (g+1)/(d+1), 90 percent bootstrap over designs, 857 units; `results/unit_cmp.csv`). HEAD against
BASE: all 1.149 (1.123 to 1.177), W194 / L9 / T654, BETTER; gate 1.061 (1.043 to 1.083), k4 1.134 (1.099 to 1.172), k6 / hardmap 1.295
(1.252 to 1.346), single 1.151 (1.120 to 1.181) W129 / L0, comp 1.142 (1.096 to 1.190) W65 / L9, all BETTER. HEAD against D70: all 1.318
(1.276 to 1.364), W394 / L46 / T417, BETTER, and BETTER in every target and set (k6 / hardmap 1.304, composite parts 1.352). The other
rules against BASE: JBF(E73) 1.129, JBF(EM2) 1.116, JCTRL 1.055 (all BETTER); SPLIT 0.999 (0.998 to 1.000), INCONCLUSIVE.

Failure classes (`results/fixed_by_class.csv`). On the #77 blocks the 513 constructs not right are 425 SPLIT, 53 BLOATED and 35
UNDERREACH (no NOSEED, the anchors of #77 touch all). Right after HEAD: SPLIT 217 of 425 (0.511), BLOATED 0 of 53, UNDERREACH 0 of
35. On the #76 classes (the E74 blocks): SPLIT 157 of 251 right after HEAD, and 0 right before (BASE); BLOATED 42 of 95 right after and
44 right before (the anchors of #77 had already fixed them, the join recovers none and loses 2); UNDERREACH 6 of 103 (7 before);
MERGED 11 of 27 (15 before); NOSEED 46 of 58 (47 before: the #77 result). Newly broken (`results/gained_lost.csv`, `lost.csv`): 217 gained,
29 lost, net +188; all 29 lost are composite parts whose construct is now swallowed by a joined block (17 shift, 11 fsm, 1 counter), none
a single design. Steps made: 584 joins in 284 of the 1350 units; the split alone makes 2 splits in 2 units, 0 gained and 1 lost.

Kind F1 after joining (`results/kind_f1.csv`; the #75 M2 posterior, claim of a block of 4 or more cells whose argmax is not glue;
precision over claims, recall over constructs): macro F1 0.237 to 0.392; fsm 0.282 to 0.476, counter 0.132 to 0.509, shift 0.287 to 0.317,
regfile 0.296 to 0.393, register 0.188 to 0.266. These are not the #75 numbers (those are on the rule-d blocks of 1163 constructs).

Verdicts (rules fixed above; `results/verdict.csv`). QL9-a (the hypothesis, share): SUPPORTED (geomean 1.149 BETTER against BASE overall,
single designs 1.151 not WORSE). QL9-b (failure classes): SPLIT SUPPORTED (157 of 251, 62.5 percent, bar a quarter); swallowed SUPPORTED
by the fixed count (42 of 95, bar a quarter), but 44 were right before the step and the join gained none, so this label is fragile and
registered as POSSIBLY GOOD. QL9-c (cost): MEASUREMENT, 29 lost, 217 gained. QL9-d (kind F1): MEASUREMENT. The split half of the
hypothesis is not supported: no split threshold had a net above 0 on TRAIN or VALIDATION (step 3), so by the fixed rule there is no split
(registered DISMISSED).

Limits, stated not hidden. Units above 400 cells and blocks above 300 cells are not scored; the join is greedy and capped at 50
merges per unit; the headline rule and its threshold (0.2) were chosen on VALIDATION among four rules at TRAIN thresholds, and on TEST
cut conductance is first and shared control nets last, as on VALIDATION (the two Bayes-factor rules swap places); the split rule is one family (Fiedler cut with a Bayes-factor test) with
a grid of five thresholds, so "no split helps" means this one does not; the 251 / 95 / 103 counts are of the E74 blocks, the #77 blocks
have a different mix (425 / 53 / 35) and the swallowed constructs are mostly #77's own repair; the 29 lost constructs show the join has no
guard against taking in a neighbour; one deterministic run; Y-cell composite parts have no key and are not scored.

Next step suggested, not run: a guard against swallowing (the 29 lost constructs): do not join two blocks whose kind posteriors are both
confident and different. And a different cut for the split step (for example along the dependency graph of the flip-flops instead of
the Fiedler vector of the cell graph), since the Fiedler cut with a Bayes-factor test never gained.
