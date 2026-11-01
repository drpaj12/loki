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
