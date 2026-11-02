# Q-L8b: anchors for the constructs no block touches (plan, 2026-11-02)

Branch feat/ql8b-anchors on loki main 83b2bc5 (after #74 Q-L7 and #75 Q-L8c; Q-L8a is PR #76 and independent of this
branch). Written before any TEST run of the new anchors (the only TEST-side reads before this file was committed are the
descriptive census below, which uses #74's committed TEST features and the answer key, and no grown block of the new
anchors). Reuses experiments/ql6-grow and experiments/ql7-stop by import (anchors, grower, likelihood `model.json`,
truth, BlockPath/UnitData, scoring, bootstrap and label helpers); nothing of them is forked or changed.

## Peter's words (2026-11-02)

"Try all them" (the three next-step pointers after #74). Purpose: Loki reverse engineering of structural netlists
(recovery of constructs). Measure: right-block share (a block is right for a construct when coverage >= 0.8 and
Jaccard >= 0.5, as #72 to #74) and, for the anchors themselves, the share of anchor blocks that touch or are right
for a construct (anchor precision).

## Question and hypothesis

One question: can anchor classes that cover the constructs no #74 anchor reaches make them touched and right, without
adding false blocks elsewhere. Order, likelihood, caps and stop (grow to the path end, END) are those of #74.

Hypothesis (controller): extra anchor classes (FF banks sharing control, open feedback loops, constants) make a share of
the 58 untouched constructs touched and right, and cost no right construct elsewhere.

Plain English first: #74's anchors look for flip-flops that form a closed loop, a chain, a staircase of dependencies or
a bank that only reads itself, and for hard cells. 58 of the 1141 TEST constructs are never touched by any block. We first
describe them, then add anchor classes for what they are, then run the same growth again and count.

## The 58 (descriptive census, TEST, from #74's committed features and the answer key; `results/describe_*.csv`)

58 constructs (of 1141, TEST units of at most 400 cells that D70 scored) have no block touching any of their cells. By
reason (first match of the anchor tests of `q6_net.anchors`):

- 39 have no flip-flop and no hard cell, so no anchor class can apply. 37 of them are the constant cells of the netlist:
  every netlist has two or three constant cells (const 0 / const 1, mostly with no reader or the shared tie-off net) and
  the provenance labels give them to a part (15 fsm of 2 cells, 5 fsm of 1 cell, 13 shift of 3 cells, 3 shift of 1 cell,
  1 counter of 1 cell, in 9 units of 2 constant cells and 27 of 3). The Odin III label of these cells is the constant
  type and the part's HDL line; which pass dropped the part's own logic is not in `labels.csv` (it has the cell type and
  the HDL span only), so L15 cannot name the pass here; this is stated as an open question, not guessed. Two more (fsm,
  6 cells, Y-gate and Y-lut, one design) are combinational netlists with no flip-flop.
- 19 have flip-flops that read two or more other flip-flops (not a closed loop, not a chain): 14 are the 64-flip-flop
  variable shifter of problem 115 (a load / enable / 4-way amount mux; the most-reading flip-flop reads 5, 6 or 14 other
  flip-flops and the cones hold 4 or 5 global nets per flip-flop: load, enable, amount), and 5 are finite-state machines of 4
  to 6 flip-flops in composites (their flip-flops read 3 to 14 other flip-flops; the 4-flip-flop ones have no global net in
  their cones). None of these flip-flops is in an anchor.

By target: O-lut 25, O-hard 18, O-gate 13, Y-gate 1, Y-lut 1; by kind: shift 30, fsm 27, counter 1; by size: 37 of 1 to 3
cells, 21 of 4 to 300, none above.

## Anchor classes added (fixed now)

Applied after the #74 anchors; a new anchor never takes a cell that an old anchor holds. `q8b_anchors.py`.

- bank: among the flip-flops in no old anchor, those whose next-state cone contains at least one global net (read by 16 or
  more cells, the cut of #73) are grouped by the exact set of global nets in their cone; a group of 8 or more flip-flops is
  one anchor (flip-flops sharing one control, as enable / load / select). Grows normally.
- loop: among the flip-flops in no old and no bank anchor, the strongly connected components of size 2 or more of the
  flip-flop dependency graph (a flip-flop depends on the flip-flops in its next-state cone) are anchors (an open feedback loop:
  the #74 fsm anchor needs the loop to be closed, no dependence from outside). Grows normally.
- const: all constant cells of the netlist (no input, not a flip-flop, not a hard cell) are one anchor. It does not grow
  (a constant anchor is complete at its cells; growing it to the path end would swallow the netlist around the tie-offs).

Not covered, stated now: the two combinational fsm netlists (no flip-flop at all), and wide-mux select decoders and constant-compare
detectors named in the brief: the 58 hold no case of either in the form of a stand-alone construct (all 39 constructs without
a flip-flop are constant cells or a six-cell combinational netlist), so they are not built (a deviation from the brief's
examples, with the census above as the reason).

## Split and procedure (fixed now)

Splits as #74: TUNE odd half, TRAIN = `(md5 // 2) % 2 == 0`, VALIDATION = rest; the even half is not used. The new anchors are
grown on the VALIDATION units (and the thresholds are fixed, not tuned). VALIDATION decides which classes stay in the headline
set: a class is dropped when its net effect on VALIDATION right constructs (constructs right with it and not before, minus
constructs right before and not now, counted per class by switching it on alone) is negative; the headline set is the
remaining classes. TEST (the units of at most 400 cells, 1350) is grown once with the headline set and scored once, after
that choice is committed. The #74 paths of the same units are the baseline OLD (VALIDATION: `$QL7_OUT/paths`, TEST:
`blocks_nostop`, read only). A test checks that the new anchor set with no new class equals the old on a small netlist.

## Evaluation (TEST once)

Constructs and key as #74 (1141 constructs, 857 units that D70 scored). For OLD and NEW (END right share): overall, per target
(gate, k4, k6/hardmap), per set (single, comp), per kind; ORACLE; recall and precision of the kind claim at END. Per unit
(design x cell): right constructs of NEW against D70 and against OLD, W/L/T and the geomean of (g+1)/(d+1), 90 percent bootstrap
over designs (1000 resamples, seed 1); BETTER, WORSE or INCONCLUSIVE by the CI; positive geomean with a CI touching 1 is INCONCLUSIVE.

The 58: for NEW, how many are touched (some block shares a cell with the construct) and how many right (END), by reason of the
census. Because the 37 constant constructs are cells of the netlist that the provenance gives to a part, they are reported
as their own group and not mixed into the structural ones.

Anchor precision: for every anchor block (old classes and each new class): number of blocks, share that touch a construct at
the anchor (some anchor cell is in an answer-key construct of the unit), share right for some construct at END. False blocks
elsewhere: the new-class blocks of units that had no untouched construct (count and share of the units), and the constructs right
in OLD but not in NEW (lost), with their cause (a new block took cells of the old block).

## Verdict rules (fixed now)

QL8b-a (the hypothesis, covering): SUPPORTED when at least 10 of the 58 become right, CONTRADICTED when none is touched, else
INCONCLUSIVE; reported for all 58 and for the 21 structural ones separately. QL8b-b (cost): NEW against OLD per unit,
geomean label as above; the hypothesis wants it not WORSE (the lower bound of the structural classes alone is reported). QL8b-c
(anchor precision): MEASUREMENT.

## Limits, stated before the run

Units above 400 cells and blocks above 300 cells are not scored; 37 of the 58 are the constant cells the provenance gives to a part,
an artefact of how parts are cut out rather than structure; the census is of TEST constructs (descriptive, no number is fitted); the
bank threshold (8 flip-flops) and the exact-control-set grouping are fixed, not tuned; one deterministic run.
