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

## Choice on VALIDATION (written before the TEST run)

Each class alone on the 320 VALIDATION units (82 designs, 328 constructs; `results/ablation_VALIDATION.csv`,
`results/chosen.json`); 168 constructs are right at the path end with the #74 anchors. Gained = right now and not before, lost = the
reverse; anchor blocks of the class: all / touching a construct at the anchor / right at the path end.

| class | right | gained | lost | net | blocks | touch | right at end |
|---|---|---|---|---|---|---|---|
| bank | 172 | 5 | 1 | +4 | 13 | 13 | 12 |
| loop | 179 | 30 | 19 | +11 | 71 | 71 | 42 |
| const | 178 | 10 | 0 | +10 | 290 | 201 | 6 |

Every class has a non-negative net effect, so the headline set is bank + loop + const. The loop class pays for its gain: 19
constructs right before are lost (a new loop block took cells that an old block needed); that cost is reported on TEST. The
const anchor touches a construct in 201 of 290 units (the constant cells are given to a part in most units) but is right
for only 6 blocks; its 10 gains are the constant-only constructs.

## Deviations from the plan (all before the TEST run)

(1) The class ablation grew only the units that get a new anchor of the class (the others keep their #74 paths, which is the
same result, and saves the regrowth); (2) TRAIN is not used (nothing is fitted).

## Results, 2026-11-02 (plain English first)

Plain English: the new anchors reach what they were built for and cost a lot elsewhere. All 58 constructs that no block touched
are now touched, and 47 of them are right: 19 of the 21 structural ones (the 64-flip-flop shifter and the small state machines,
found by the bank and loop classes) and 28 of the 37 constant ones (the constant cells the provenance gives to a part). But
89 constructs that were right before are lost (115 are gained in total, 47 of them from the 58), because a new block takes cells
the old block needed: the constant anchor takes tie-off cells that sit inside 61 of the lost constructs (and inside hard-cell
blocks: hard blocks right at the end fall from 16 to 3), and bank and loop blocks split single designs whose whole netlist is the
construct (single designs 0.539 against 0.597, WORSE). Net: the right-block share rises from 0.528 to 0.550 (D70 0.385), gained on
composite parts (0.565 against 0.441, now BETTER than D70) and on k6/hardmap (0.491 against 0.430), lost on gate netlists (0.538
against 0.587) and single designs. The per-unit comparison against the old anchors is a tie (geomean 1.001).

CAD-style counts first (TEST only; 1141 constructs of 857 units that D70 and #73 also scored; `results/*.csv`; NEW = #74 anchors
plus bank, loop and const; OLD = #74). Right-block share at the path end (oracle in brackets):

| scope | constructs | D70 | OLD | NEW |
|---|---|---|---|---|
| all | 1141 | 0.385 | 0.528 (0.556) | 0.550 (0.559) |
| gate (O + Y) | 351 | 0.242 | 0.587 (0.595) | 0.538 (0.547) |
| k4 (O + Y) | 460 | 0.439 | 0.552 (0.598) | 0.602 (0.613) |
| k6 / hardmap | 330 | 0.461 | 0.430 (0.455) | 0.491 (0.497) |
| single | 635 | 0.356 | 0.597 | 0.539 |
| comp | 506 | 0.421 | 0.441 (0.504) | 0.565 (0.585) |

By kind (OLD to NEW): fsm 0.438 to 0.568, shift 0.559 to 0.772, counter 0.483 to 0.338, register 0.595 to 0.537, regfile 0.795 to 0.659.

The 58 (`results/untouched.csv`, `untouched_summary.csv`): touched 58 of 58 (OLD 0), right 47. Structural 21: touched 21, right 19 (all
19 with flip-flops; the two combinational six-cell fsm netlists are touched by the constant anchor and not right). Constant 37:
touched 37, right 28 (the nine that are not right are one-cell constructs: the constant block holds all two or three constant cells
of the netlist, so its Jaccard with the one cell is 1/3).

Per unit (design x cell) against D70 (`results/unit_cmp.csv`; geomean of (g+1)/(d+1), 90 percent bootstrap over designs, 857 units): NEW
all 1.148 (1.103 to 1.197), W306 / L135 / T416, BETTER; gate 1.285 BETTER; k4 1.140 BETTER; k6 / hardmap 1.007 (0.956 to 1.059)
INCONCLUSIVE; single 1.135 BETTER; comp 1.184 (1.101 to 1.273) BETTER (it was 1.058, INCONCLUSIVE, in #74). Against OLD: all 1.001
(0.980 to 1.024), W78 / L66 / T713, INCONCLUSIVE; gate 0.948 (0.919 to 0.975) WORSE; k4 1.020 (0.998 to 1.045); k6 / hardmap 1.042 (1.010 to
1.076) BETTER; single 0.960 (0.942 to 0.977) WORSE, W0 / L37; comp 1.129 (1.058 to 1.203) BETTER, W78 / L29.

Anchor precision (`results/anchor_precision.csv`; blocks of the class in the 1350 TEST units; touch = some anchor cell is in an answer-key
construct of the unit; right = right for some construct at the path end): bank 107 blocks, 107 touch, 34 right (0.32); loop 167,
167, 52 (0.31); const 1186, 807 touch (0.68), 30 right (0.03). Old classes OLD to NEW right at the end: fsm 160 to 152 of 280, register
156 to 95 of 620, memory 119 to 113 of 143, hard 16 to 3 of 305, shift 89 to 91, counter 64 to 63. False blocks elsewhere
(`results/false_blocks.csv`): in units where the old anchors left no construct untouched there are 84 bank blocks (all touch a
construct), 159 loop blocks (all touch) and 1129 const blocks (750 touch). Constructs right before and lost (`results/lost.csv`): 89;
61 of them contain constant cells that the const block now holds, 28 are lost to bank or loop blocks (by set: 44 composite counters,
19 single registers, 12 single fsm, 6 single register files).

Post hoc, after the TEST numbers above were seen (not part of the plan; `results/posthoc_bank+loop/`): without the const class, bank and loop
alone recover the same 19 structural constructs, 0 of the constants, and lose 86 (right share 0.527 against OLD 0.528; against OLD
0.984, 0.965 to 1.002; single 0.963 WORSE, gate 0.930 WORSE, comp 1.049 INCONCLUSIVE, k6 / hardmap 1.023). So the const class explains the
gain on composite parts and k6 / hardmap and part of the loss; the loss on single designs belongs to bank and loop, which cut a
design whose netlist is the whole construct into several blocks.

Verdicts (rules fixed above). QL8b-a (the untouched constructs become touched and right): SUPPORTED, 47 of 58 right (58 touched);
structural 19 of 21; constant 28 of 37. QL8b-b (cost): against D70 BETTER overall (1.148); against OLD INCONCLUSIVE overall (1.001), WORSE on gate
and single designs, BETTER on composite parts and k6 / hardmap. The second half of the hypothesis, "cost no right construct elsewhere", is
false as worded (89 constructs lost, 115 gained), and by the fixed per-unit rule it is INCONCLUSIVE overall (not WORSE) with WORSE
on two targets. QL8b-c (anchor precision): MEASUREMENT, as above.

Next step suggested, not run: make the new classes harmless where the design is one construct. A new block that would take cells of a
single-design netlist could be merged into the old block when they share a net, and a constant anchor could be dropped from a part
that holds a hard cell or another class (the tie-off cells sit inside the construct). Neither is a new anchor; both are a merging step,
the same joining problem as SPLIT in Q-L8a.

Limits, stated not hidden. Units above 400 cells and blocks above 300 cells are not scored; 37 of the 58 are the constant cells the
provenance gives to a part, an artefact of how parts are cut out and not structure; the census is of TEST constructs (descriptive; the classes
were designed after seeing it, and 14 of the 19 structural recoveries are one HDL problem (115, the 64-flip-flop shifter) seen in several
composites and cells, so they are not 19 independent cases); VALIDATION chose the class set (all three kept, each net-positive there, and the TEST net of the const
class is not); TEST ran once for the headline set; the post hoc row is exploratory; the kind guess is unchanged (#73 likelihood); Y-cell composite parts
have no key and are not scored.
