# Q-L8a: a growth order that respects structure (plan, 2026-11-02)

Branch feat/ql8a-order on loki main (after #74 Q-L7 and #75 Q-L8c). Written before any TEST run of this experiment
(no run of any kind had been made when this file was committed; only the code and committed results of #73, #74 and
#75 were read). Reuses experiments/ql6-grow and experiments/ql7-stop by import (anchors, Grower, likelihood
`model.json`, truth, BlockPath/UnitData, scoring, bootstrap and label helpers); nothing of them is forked or changed.
Another lane runs Q-L8c (ql8c-kind, merged); Q-L8b (ql8b-anchors) follows in its own dir and PR.

## Peter's words (2026-11-02)

"Try all them" (the three next-step pointers after #74). Purpose: Loki reverse engineering of structural netlists
(recovery of constructs). Measure: right-block share (a block is right for a construct when coverage >= 0.8 and
Jaccard >= 0.5, as #72 to #74) per target and set.

## Question and hypothesis

One question: does a growth order that respects structure give a right prefix for constructs where #74's order gives
none, and does it lift k6/hardmap and composite parts above D70. Anchors, likelihood (`model.json`), caps (300 cells
per block, units of at most 400 cells) and the stop (grow to the path end; rule d of #74 as a check) are unchanged.

Hypothesis (controller): a structural order recovers a share of the 449 constructs with no right prefix on any block
in #74, and lifts k6 (0.968 against D70) and composite parts (1.058, CI touching 1) to BETTER than D70.

Plain English first: #74 grows each block one cell at a time, always adding the neighbour whose addition makes the
block look most like a known construct under the weak likelihood. For 449 constructs no block ever passes through the
right shape; the order wandered. Here the order is chosen by wiring instead of by the weak guess: the weak guess only
breaks ties. We try three wiring rules, pick one on designs that are not in the test set, then run it once on the
test designs.

## Candidate orders (fixed now)

All three change only which frontier cell a block takes next; the block still takes exactly one cell per round, cells
owned by another block are never taken, nets read by 16 or more cells are not crossed (#73). Let b be the block, c a
frontier cell, d(c) the #73 log Bayes factor of adding c (the E74 key). Ties after all keys: lower cell index.

- E74 (reference): key = d(c) (highest first). The #74 order.
- OA "attach": key = (number of distinct non-global nets that c shares with block cells, d(c)). Grow where the block is
  most strongly tied (connection count, the attraction of netlist clustering).
- OB "loop": the frontier also contains sibling cells (cells that read a non-global net that a block cell reads; the
  frontier of E74 holds only drivers of block inputs and readers of block outputs). key = (tier, attach, d(c)) with tier
  2 = c drives a net read by the block and reads a net driven by the block (it closes a feedback path through the block),
  1 = sibling sharing a select / enable / clock-enable style net (a non-global net read by c and by at least two block
  cells), 0 = the rest.
- OC "cone": key = (tier, d(c)) with tier 1 = c drives a net read by the block (an input cone: for k6 / hard-map, a LUT is
  expanded through its input cone), 0 = c only reads a net driven by the block.

No parameters are tuned. The order is chosen on VALIDATION among OA, OB, OC (and E74 as reference) by right share
at the path end (END), overall; tie goes to the order listed first. A second reported choice, "per-target best", takes the
best order per target (gate, k4, k6/hardmap) on VALIDATION; the cell type of a netlist is known, so this is
allowed, and it counts as one extra comparison (stated in the register row). The verdicts use the single headline order.

## Split (by design, fixed now)

Same as #74: TUNE designs of the odd MD5 half; TRAIN = `(md5 // 2) % 2 == 0`, VALIDATION = rest (97 and 82 designs).
The even half trained the #73 likelihood and is not used. TRAIN is used to look at behaviour and to check
cost, VALIDATION chooses the order, TEST (the #73 units of at most 400 cells that D70 scored, 1141 constructs in #74) is
grown and scored once, after the order is chosen and committed.

## Evaluation (TEST once)

Constructs and key as #74. For every order: END right share overall, per target (gate = O-gate + Y-gate, k4 = O-lut +
Y-lut, k6/hardmap = O-hard), per set (single / comp), per kind; ORACLE (any prefix of any block right); recall and
precision of the argmax claim at END as in #74. Per unit (design x cell): right constructs of the order against D70
and against E74-END (the #74 order with grow-to-end, from #74's committed TEST paths): W/L/T and the geomean of
(g+1)/(d+1) with a 90 percent bootstrap over designs (1000 resamples, seed 1). BETTER (lower bound above 1), WORSE (upper
below 1), else INCONCLUSIVE; a positive geomean with a CI touching 1 is INCONCLUSIVE, not DISMISSED; WORSE maps to
DISMISSED. Stop rule d is run as a check (same chosen.json and clf.pkl of #74).

Remaining no-prefix constructs (ORDER class: touched but no prefix of any block right), split by failure class, each
construct once, first match: BLOATED (some block covers at least 0.8 of the construct at some prefix, but Jaccard
stays below 0.5: the block swallows neighbours first), SPLIT (no block reaches coverage 0.8, but the union of the
blocks that touch it at their path end does: the construct is cut across blocks), UNDERREACH (the union does not reach
0.8 either: growth stops, by exhaustion or cap, before the construct is covered). NOSEED is as in #74. These are
also given for E74 for comparison.

## Verdict rules (fixed now)

QL8a-a: headline order against D70 (all, and per target and set), geomean label. QL8a-b: headline order against E74-END,
same. QL8a-c (the hypothesis): SUPPORTED when the headline order is BETTER than D70 on both k6/hardmap and comp and
recovers at least 10 percent of the constructs that E74 had in class ORDER; CONTRADICTED when it is not BETTER than
E74-END on any of all / k6 / comp and recovers none of those; else INCONCLUSIVE (partial). QL8a-d: the count of
recovered formerly-ORDER constructs and the failure classes of the rest: MEASUREMENT.

## Limits, stated before the run

Units above 400 cells and blocks above 300 cells are not scored; single-design units make END the ceiling for 55
percent of the constructs (#74); three orders and one per-target choice are four comparisons, the headline carries the
verdict; the order uses only the cell graph and the #73 evidence, not the answer key; one deterministic run.
