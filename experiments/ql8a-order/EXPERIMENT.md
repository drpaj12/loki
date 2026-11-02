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

## Choice on VALIDATION (written before the TEST run)

The three orders were grown on the 320 VALIDATION units (82 designs, 328 constructs; `results/tuning_VALIDATION.csv`,
`results/chosen.json`). END right share (all): E74 0.512, OA 0.534, OB 0.521, OC 0.534; OA and OC tie, OA is listed
first. Headline order: OA. By target the best are gate OB (0.619 against OA 0.536), k4 OA (0.569, tied with OC),
k6/hardmap OA (0.485 against E74 0.426). Single-design units: OB 0.699, others 0.669 (the sibling frontier of OB
reaches more of a single design). Composite parts: OA and OC 0.441, E74 0.405, OB 0.400. The per-target best row (gate
OB, k4 OA, k6 OA) is therefore the OA+OB mix; TEST is grown for OA and OB only (OC is not needed for the verdicts).
TRAIN was not grown: no number is tuned, so TRAIN has no role (deviation 1).

## Deviations from the plan (all before the TEST run)

(1) TRAIN is not used (nothing is fitted; the choice among three fixed orders is made on VALIDATION alone).
(2) TEST is grown for the headline OA and the per-target order OB only.

## Results, 2026-11-02 (plain English first)

Plain English: none of the three structural orders helps in a way that matters. The headline order OA (grow where the
block is most strongly tied to the cells it already has) recovers the right block for 0.526 of the 1141 constructs,
against 0.528 for the #74 order grown to the end and 0.385 for the D70 cones. Of the 449 constructs that had no right
prefix on any block in #74, OA gives a right prefix to 12 at the path end (2.7 percent; 20 have a right prefix somewhere on
the path), and it loses 14 of the 602 that #74 had right. K6/hardmap (0.965 against D70) and composite parts (1.044 against
D70) stay inconclusive, exactly where #74 was. The sibling frontier of OB does help where the whole design is the block
(single designs 0.625 against 0.597) and on gate netlists (0.624 against 0.587, geomean 1.034 against the #74 order), but
costs composite parts (0.393 against 0.441, WORSE) and k6/hardmap (0.388 against 0.430, WORSE). Picking the order per target
on VALIDATION (gate OB, k4 and k6/hardmap OA) gives 0.542, a small and real gain over the #74 order (geomean 1.013, 1.006 to
1.021, W31 / L13 / T813) that is not the headline. What is left is not the order of single cells: 251 constructs are split
across several blocks, 103 are never fully reached, 95 are swallowed in a block that grows past them.

CAD-style counts first (TEST only; 1141 constructs of 857 units that D70 and #73 also scored; `results/*.csv`). Right-block
share at the path end (END), and in brackets the oracle (any prefix of any block right):

| scope | constructs | D70 | E74 (#74 order) | OA (headline) | OB | per-target mix |
|---|---|---|---|---|---|---|
| all | 1141 | 0.385 | 0.528 (0.556) | 0.526 (0.573) | 0.522 (0.578) | 0.542 (0.588) |
| gate (O + Y) | 351 | 0.242 | 0.587 (0.595) | 0.573 (0.632) | 0.624 (0.681) | 0.624 |
| k4 (O + Y) | 460 | 0.439 | 0.552 (0.598) | 0.561 (0.613) | 0.541 (0.607) | 0.561 |
| k6 / hardmap | 330 | 0.461 | 0.430 (0.455) | 0.427 (0.455) | 0.388 (0.427) | 0.427 |
| single | 635 | 0.356 | 0.597 | 0.597 | 0.625 | 0.622 |
| comp | 506 | 0.421 | 0.441 (0.504) | 0.437 (0.543) | 0.393 (0.518) | 0.441 |

Per unit (design x cell) against D70 (`results/unit_cmp.csv`; geomean of (g+1)/(d+1), 90 percent bootstrap over designs,
857 units): OA all 1.145 (1.102 to 1.188), W293 / L127 / T437, BETTER; gate 1.341 BETTER; k4 1.125 BETTER; k6 / hardmap 0.965
(0.914 to 1.016) INCONCLUSIVE; single 1.182 BETTER; comp 1.044 (0.979 to 1.111) INCONCLUSIVE. Against the #74 order grown to
the end: OA all 0.999 (0.994 to 1.004), W12 / L13 / T832, INCONCLUSIVE; gate 0.990 (0.980 to 0.998) WORSE; k4 1.006
(1.000 to 1.013); k6 / hardmap 0.999 (0.986 to 1.013); comp 0.996 (0.975 to 1.016). OB against the #74 order: gate 1.034 BETTER,
single 1.020 BETTER, k4 0.993, k6 / hardmap 0.964 (0.941 to 0.986) WORSE, comp 0.939 (0.911 to 0.968) WORSE. Per-target mix
against D70 1.161 (1.117 to 1.205) BETTER (k6 / hardmap 0.965 INCONCLUSIVE), against the #74 order 1.013 (1.006 to 1.021) BETTER
(the one extra comparison; not the headline).

Remaining constructs with no right prefix on any block (class ORDER of #74, by failure class, all targets; E74 / OA / OB):
NOSEED 58 / 58 / 58 (anchors, Q-L8b); BLOATED (some block covers 0.8 of it at some prefix, Jaccard stays below 0.5) 95 / 76 / 75;
SPLIT (no block covers 0.8, the blocks that touch it together do) 251 / 250 / 269; UNDERREACH (together they do not
reach 0.8) 103 / 103 / 80. At the path end, constructs that have a right prefix but whose END is past it: TOOBIG 5 / 9 / 12, MERGED 27 / 45 / 51.
Orders that reach more right prefixes also overshoot them more: ORACLE rises (0.556 to 0.573 and 0.578) while END does not.
SPLIT is the largest class and does not move: a construct cut across blocks is a competition between anchors, not a
question of the order inside one block. Of the 449 formerly ORDER: recovered 12 (OA), 30 (OB, 19 of them gate), 31 (per-target mix);
lost of the 602 right in #74: 14 (OA), 37 (OB), 15 (mix). Precision of the claimed kind at END: E74 0.277, OA 0.290, OB 0.254.
Stop rule d of #74 as a check: OA 0.528 (END 0.526), OB 0.530, mix 0.543; the stop does not change the picture.

Verdicts (rules fixed above). QL8a-a (headline OA against D70): BETTER overall, gate and k4 and single; INCONCLUSIVE k6 / hardmap
and comp. QL8a-b (OA against the #74 order): INCONCLUSIVE overall (0.999), gate WORSE (0.990). QL8a-c (hypothesis): INCONCLUSIVE by the fixed
rule (k6 / hardmap and comp not BETTER than D70, 12 of 449 = 2.7 percent recovered, below the 10 percent bar; not CONTRADICTED because
12 is not none); in plain words, not supported: the order changes almost nothing. QL8a-d: MEASUREMENT (the counts above).

Next step suggested, not run: the loss is SPLIT, not order. A construct that is cut across blocks needs blocks merged or
anchors joined (for example two anchors that share a feedback or enable net), so work on merging blocks at the end of the
path; and a stop that knows OB's gate gain and OA's k4 gain is a per-target choice, not a new order.

Limits, stated not hidden. Units above 400 cells and blocks above 300 cells are not scored; three orders and one per-target
mix are four comparisons (the verdicts carry OA only); the orders use only the cell graph and the #73 evidence; TRAIN was not used;
TEST ran once; rule d and its classifier come from #74 (trained on E74 paths); the per-target mix is chosen on 82 designs; Y-cell composite
parts have no key and are not scored. The precision of the kind guess stays low because the #73 likelihood is weak.
