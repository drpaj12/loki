# Q-L4: where does structure recovery fail, read in directed graphlet signature terms (plan, 2026-11-01)

Branch feat/ql4-misses on loki main da13bc2 (after #68 to #71). Written before any run of this experiment.
Reuses experiments/graphlets (#68 to #70) and experiments/graphlets-fuzzy (#71) code by import; nothing is
forked and no second graphlet counter exists (signatures come from the Odin III `graphlets` pass, release
build ~/odin3-ws/odin3/build/rel-main, read only).

## Peter's words

Q-L4 (2026-10-30): "Why are high-level things not recoverable - where are the gaps (probably particular
structures now) so why can't they be reverse engineered is our next step (noting the LLM agent approach is
only useful if the decoding process gets complex)."
Peter 2026-11-01: "for a directed graph let signature how close is a failed detection into terms of its
signature. That's the way forward. Basically, is it what I'm comparing over the partition do I have the write
block and how do I check with my pattern block."
Controller reading, stated for Peter to correct: "write block" = right block. So two questions per failed
detection: (1) is the block the matcher compared the right block (partition question)? (2) does the right
block, cut out by the answer key, look like its pattern in directed signature terms (pattern question)?

Purpose: Loki reverse engineering of structural netlists (recovery of constructs). RQ: the L-series, Q-L4
(register row QL4a to QL4c). Measure: recovery (recall, precision) per construct kind, here split into
the reasons for the misses.

## Hypothesis (Peter's, as read by the controller)

Most failed detections are near misses: the true block is close to its pattern in directed signature
distance, so the gap is the partition or the threshold, not missing structure. Verdict rule below.

## Units, detectors, answer key

Constructs (answer key):
- Singles: the 243 TEST single-family designs of the L3 v0 benchmark (families fsm, counter, shift, regfile,
  register; glue is excluded because it is found by the absence of a state group), 5 cells. The true block is
  the whole design (every cell of the netlist): the answer key says the whole design is one construct.
- Composite parts: the 82 TEST composites, parts with family fsm, counter or shift (as in #69 to #71; timer
  and lfsr count as counter and shift). The true block is the set of cells whose Odin III provenance label
  (`labels.csv`, `module_path`) is the part's instance `u<idx>`; a cell with a mixed (`*`) or top-level label is attributed by the source line of its first
  provenance span (the line range of the part's module `P<problem>` in the composite file); the other cells
  (ports, wiring of the top module) belong to no part. Ports are not cells. A part whose true block holds no
  flip-flop is absent from the netlist (Odin III optimised it away, class 0 below).
  Only the three Odin III cells (O-gate, O-lut, O-hard) have this provenance; the two Yosys cells (Y-gate,
  Y-lut) have no labels, so composite parts on Y cells are counted as hits or misses but not classified
  ("no provenance"). Singles on Y cells are classified (the whole design needs no labels).

Detectors (all directed signature, flip-flop count known, thresholds and calibrations exactly as in the
earlier PRs, fitted on TUNE; nothing is refit on TEST):
- D68: whole-design nearest-entry match (#68), singles only (no partition step).
- D69: unbounded state-group cones, nearest entry + naive Bayes posterior (#69).
- D70: bounded cones, same matcher (#70).
- D71h: bounded cones, histogram (earth mover) distance to the nearest entry per pattern, logistic layer,
  nn-emd:dir:ff of #71.
- D71c: bounded cones, random forest on directed signature features, clf-rf:dir of #71.
A detector's claim = a partition (cone) accepted as pattern p (posterior or probability >= the TUNE threshold);
design-level for singles (found set contains the family), part-level for composites by greedy one-to-one
assignment of the accepted partitions of family f to the true parts of family f by block overlap (Jaccard,
highest first); the number of hits per design and family equals the kind-level count min(truth, detected) of
#69 to #71. A miss = a construct with no assigned claim. Hits are recorded the same way.

## Per construct record (all misses, and all hits)

(a) block: the partition (cone) of the detector with the largest Jaccard overlap to the true block over cells
(cells = labelled netlist cells, ports excluded), and the share of the true block it covers (coverage). For
D68 the block is the whole design.
(b) distance of that compared block's directed signature to the true family's pattern, in the matcher's own
distance: D68/D69/D70: 1 - (GDD agreement + cosine of log totals) / 2 to the best library entry with the
group's flip-flop count; D71h: the mean-over-orbits W1 distance; D71c: 1 - P(family).
(c) the same distance for the TRUE block (cut out by the answer key; same pass, same library, flip-flop count
= flip-flops in the block).
(d) the decision threshold (posterior or probability) and the best wrong pattern's distance, for both the
compared block and the true block, and whether the true block would have been accepted as the family.

## Classification rule (fixed now; applied in this order to each miss)

Let Cv = coverage, J = Jaccard of the best-overlap compared block (a), D_true = (c) distance of the true family,
and q90 = the 90th percentile of the (b) distance over HITS of the same detector (pooled over cells, kind-specific
when the kind has at least 10 hits for that detector, else pooled over kinds).
0. absent: the true block holds no flip-flop (the part, or for a single the whole design, was removed or
   turned into constants before the netlist). No netlist detector can find it: neither a missing detector
   nor complex decoding. Its Odin III pass is named from provenance like class 4.
1. missing pattern: the library has no entry for the family at the block's flip-flop count (no entry for
   the true family with that count, so no distance exists). Reported as "missing pattern (width)".
2. partition miss: not (Cv >= 0.8 and J >= 0.5). The partition did not give the right block.
3. threshold miss: a right block (Cv >= 0.8, J >= 0.5) and D_true <= q90: the true block looks like the hits.
   Flag "rank" when the best wrong pattern is nearer than the family for the true block.
4. structure miss: a right block and D_true > q90: the true block itself does not look like its pattern.
   Its Odin III pass is named from provenance (below).
Missing detector = classes 1, 2, 3 (a detector with another partition, a library entry or another threshold
could succeed on the same netlist). Complex decoding = class 4 only (the signature of the structure itself
differs; the LLM path of Q-L4 applies here). The words follow Q-L4; the split is by signature, not proof that a
better detector cannot exist for class 4.
For composites on Y cells (no true block): class "unclassified (no provenance)", not counted in the rates.

Naming the Odin III pass for structure misses: the construct types of the true block cells from the labels
(`construct_type`, `construct_types`) are tabulated; for O-lut the L15 audit flow (round 6, snapshots after
proc, fsm, opt, flatten, opt -full, wreduce, lower, abc --lut 6) is run on the structure-miss designs and the
first-loss pass of the units of the true block is reported. Other cells: construct types only (stated, not
hidden).

## Hit comparison (item 4 of the brief)

The same records for hits give the distribution of (b) per kind and detector (CSV and one plot). Near-miss
distances (c) are compared with hit distances per kind.

## Verdict rule for the hypothesis (fixed now)

Classified misses are classes 1 to 4 (absent misses are counted and shown, not in the denominator,
because nothing in the netlist could be recovered). Pooled over classified misses of D70 (the bounded-cone detector, the headline of #70) and D71c, per detector:
NEAR-MISS HYPOTHESIS SUPPORTED when partition + threshold + missing-pattern misses are at least 60 percent of
classified misses, CI (bootstrap over designs, 90 percent) lower bound above 50 percent; CONTRADICTED when
structure misses are the majority with the CI lower bound above 50 percent; otherwise INCONCLUSIVE. Rates are
reported per kind, cell and detector too. Headline format: counts and shares first, then the label
(memory cad-reporting-convention).

## Agent defaults (calls left open; Peter may overrule)

- Directed and flip-flop-count-known variants for every detector (the #71 chosen configuration); other
  variants are not rerun.
- "Near" is relative to the hits of the same detector (q90), not a hand-set number.
- Library, calibrations, thresholds: reused from the earlier PRs, recomputed by the same code on TUNE.
- Not in scope: VTR rows and round 4 families (no answer-key constructs of these kinds exist in the
  graphlet experiments' benchmark; recorded, not hidden). The VerilogEval designs are the singles and the
  composite parts (Q3/Q4 families come from them).

## Results, 2026-11-01 (plain English first)

Plain English: Peter's two questions have different answers. Is the block the matcher compared the right
block? Mostly not: for the cone detectors fewer than 40 percent of the misses compared the right block,
so the partition is the largest single gap (486 of 864 classified misses of D70, 286 of 506 of D71c), and
even among the hits only 30 percent (D70) and 35 percent (D71c) compared the right block (a hit counts
as soon as the right kind is claimed anywhere in the design). Is the right block close to its pattern? It
depends on the detector and on how close is counted. By the rule fixed before the run, 80 percent of D70
misses and 79 percent of D71c misses are "near" (wrong partition, missing width entry or threshold), so
the near-miss hypothesis is SUPPORTED as fixed. But that rule calls every partition miss near without
looking at the distance of the true block. Looking at that distance (post hoc, miss_2x2.csv), the true
block is near its pattern for only 39 percent of D70 misses and 26 percent of D71c misses, and for 67 to
75 percent of D68, D69 and D71h misses. So for the best two cone detectors the other half of the story is
that the true block itself does not look like its pattern in directed signature terms: complex decoding,
in Q-L4's words, accounts for 20 percent of misses by the fixed rule and up to 61 to 74 percent by the
post hoc reading. The Odin III pass that first loses the source units of both the structure misses and
the absent constructs is `opt` (O-lut flow). The LLM path of Q-L4 is therefore worth trying on the
structure misses, and a better partitioner is worth building for the rest; neither claim is a proof.

CAD-style counts first. Constructs (answer key): 695 single-design constructs (243 TEST designs minus
glue, 5 cells, families fsm 197, counter 70, shift 15, regfile 60, register 353) and 1044 composite parts
(fsm, counter, shift; 82 TEST composites, 5 cells), 1739 in all (D68 is singles only, 695).
Reproduction check (`results/validation.csv`): hits and misses per family on the singles equal the
published TP and FN of #68 to #71 in 25 of 25 detector x family rows.

| detector | constructs | hits | misses | absent | missing pattern | partition | threshold | structure | no provenance | near share (rule) |
|---|---|---|---|---|---|---|---|---|---|---|
| D68 | 695 | 261 | 434 | 2 | 32 | 0 | 288 | 112 | 0 | 0.741 |
| D69 | 1739 | 559 | 1180 | 109 | 97 | 423 | 193 | 88 | 270 | 0.890 |
| D70 | 1739 | 485 | 1254 | 113 | 105 | 486 | 101 | 172 | 277 | 0.801 |
| D71h | 1739 | 640 | 1099 | 108 | 77 | 431 | 198 | 32 | 253 | 0.957 |
| D71c | 1739 | 891 | 848 | 109 | 93 | 286 | 22 | 105 | 233 | 0.792 |

"No provenance" = composite parts on the two Yosys cells (counted as misses, not classified). Near share
= (missing pattern + partition + threshold) / classified (the four classes after absent). Per kind and per
cell: `results/miss_classes.csv`, `results/miss_classes_cell.csv`. Examples, D70: fsm 306 misses (absent
54, partition 82, threshold 52, structure 43); counter 185 (partition 101, structure 18); shift 385
(absent 51, missing width 65, partition 55, structure 56); register 326 (partition 224, structure 48).
Structure misses of D70 sit mostly on O-lut (65) and O-hard (68), few on O-gate (20). 255 misses of D70 and of D71c had no partition at all (the claim chain found no register,
`no_partition` in records.csv).

Rule verdict (`results/verdict.csv`, 90 percent bootstrap over designs): D70 near share 0.801 (0.771 to
0.831), D71c 0.792 (0.753 to 0.830), both NEAR-MISS HYPOTHESIS SUPPORTED. Post hoc, the two questions
crossed (`results/miss_2x2.csv`, classified misses; right block = coverage >= 0.8 and Jaccard >= 0.5; true
block near = distance <= q90 of the detector's hits): D70 wrong block 542 (true block near 235, far 307),
right block 322 (near 101, far 221); D71c wrong block 335 (near 107, far 228), right block 171 (near 22,
far 149); D71h wrong block 485 (near 355), right block 253 (near 198, far 55); D69 wrong 471 (near 351),
right 330 (near 193, far 137); D68 right block by construction, 288 near, 144 far. "Near" is relative to
each detector's own hits, so the shares are not comparable across detectors without care.

Distances (`results/distances.csv`, `results/distances.svg`; hits' compared block against misses' true
block): D70, median distance of the hits 0.02 to 0.08 per kind (counter 0.054, fsm 0.076, shift 0.060,
register 0.065, regfile 0.025); the true block of a right-block miss has median 0.09 to 0.16 (fsm 0.097, counter 0.153,
shift 0.090, register 0.155), 90th percentile up to 0.28. D71c (1 - P(family)): hits median 0.10 to 0.60
(fsm 0.316, counter 0.421, register 0.185, regfile 0.103), true block of right-block misses 0.74 to 0.96. The nearest
wrong pattern was nearer than the family for the true block in 57 of D70's 101 threshold misses ("rank"
flag), 246 of 288 for D68, 106 of 198 for D71h, none of D71c's 22.

Odin III pass (provenance). Construct types of the true blocks of structure misses
(`results/structure_provenance.csv`, labels of the three Odin III cells): arithmetic ($add, $sub, $lt) and
registers with enable or reset ($sdff, $dffe, $sdffe) lead, with $eq, $mux and $not behind them. Absent
constructs have no flip-flop in the netlist: their cells are constants (`$_CONST0_`/`$_CONST1_`) for 17
fsm and 17 shift parts and for most of the 2 to 3 counter parts per Odin III cell (a counter part on
O-hard keeps a subtractor); the part was optimised away. The L15 loss audit on
the O-lut flow (`results/pass_loss.csv`, 119 constructs in 92 designs): the pass that first loses most of
the state units of the construct's source is `opt` for all 17 absent fsm parts, 17 absent shift parts, 3
absent counter parts, and for the structure misses of fsm (17), shift (37), counter (5), regfile (3) and
7 of 20 register designs; the other 13 register designs keep their state units through the whole flow
("kept": the source units are intact and the signature differs for another reason). Only O-lut is
covered; the O-gate and O-hard flows run other pass lists.

Verdicts. QL4a (fixed rule) SUPPORTED for D70 and D71c (POSSIBLY GOOD in the register). QL4b (post hoc,
true block near for most misses) is INCONCLUSIVE: 39 percent and 26 percent for D70 and D71c against 67 to
75 percent for D68, D69 and D71h. QL4c (missing detector vs complex decoding): by the fixed rule
complex decoding is class 4 only, 172 of 864 (20 percent) for D70 and 105 of 506 (21 percent) for D71c;
reading "far from the pattern" as complex gives about 61 and 74 percent.

Limits, stated not hidden. (1) The true block of a single is the whole design, so a cone around the state
group covers it only when the design is nearly all state logic; this inflates partition misses for
singles (325 of D70's 486 partition misses are singles). (2) The true block of a composite part comes from provenance
labels plus the source line of the first span for mixed cells; the other composites' cells (ports, top
wiring) are in no part. (3) Y-cell composite parts are not classified. (4) q90 of the hits sets "near";
the cut is relative to each detector. (5) D71c's distance is 1 - probability, not a graphlet distance;
D71h's distance is the earth mover distance. (6) The verdict rule sets the denominator to classified
misses; absent constructs (about 9 percent of all misses) are shown separately. (7) VTR rows and round 4
families are not separate sets: the round 4 designs are inside the singles; VTR designs are outside the
graphlet benchmark (stated in the plan).

## Deviations from the plan

(1) Class 0 (absent) and the source-line attribution were added to the rule after a first look at three
composites (parts optimised away) and before the full run; they are in the plan above. (2) The post hoc
2x2 and the distance statistics are not in the fixed rule; the verdict rule is unchanged. (3) The L15 pass
naming covers O-lut only. (4) The counter and shift families of composites merge timer and counter,
shift and LFSR as in #69 to #71; singles use the pattern name, which is what reproduces the published
counts.
