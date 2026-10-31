# Loki fuzzy graphlet signatures (plan, 2026-10-31)

Branch exp/graphlets-fuzzy, on top of loki #70 (831eba53, experiments/graphlets). Plan written before the runs.

Plain English first: graphlet signatures are a check for "close, not exact". The question is how a
signature suggests that a structure exists. So we look at what the signature of each real thing (counter,
shift register, state machine ...) looks like in the library, then compare signatures more loosely than
#70 did (a distribution distance instead of totals; a classifier that learns the shape of each class),
and test a looser reading of directed signatures, because direction is fundamental in circuits. No result
is claimed yet; no run of the new methods was made before this plan.

## Peter's words (2026-10-31, dictated)

"So graphlets are a signature used to check if close, not exact. So the question is how signatures suggest
that a structure exists. So using that is a classifying method can we look at what the graph with signature
is for the real things we're trying to capture and make a fuzzier signature comparison. Also it's not
expected that the dag one is more specific, but I would use it and then think about what fuzziness is to
detect structures in that way because directionality is fundamental in circuits." and "Why not also do the
loki stuff too".

## Hypothesis (Peter's)

A classifier that learns what the signatures of the real structures look like, with a fuzzier comparison,
detects structures that exact-ish signature matching misses. Directed signatures are kept (direction is
fundamental); the right notion of fuzziness for them is part of the question. Purpose: Loki L2/L3
coarse-grain detection (hub L Q2.2, L Q3.1). Measures: per pattern x cell precision and recall on TEST
(CAD-style counts and geomean-free per-pattern rows first, then the label).

## Fixed rule

Same WORKING rule as GL: precision >= 0.80 and recall >= 0.80 on TEST, 90% bootstrap lower bounds. Same
TUNE / TEST split of designs (experiments/l3-detector/results/split_single.csv, composites.csv). Everything
fitted (classifiers, thresholds, calibration layers, tolerance level, per-pattern hybrid choice) is fitted
on TUNE only; TEST is scored once per method. Fuzzy-level choice is reported for every level, and the
"best level" is the one with the best TUNE F1, not the best TEST value.

## Method

Data: the #70 bounded-cone partitions (partitions.py with GLET_BOUNDED=1), rerun with the full signature
kept per partition (orbit totals and GDD, both modes), because #70 stored only the match scores. Library:
the existing signatures of 3500 netlists x 2 modes (work/glet-out/sig), reused, not rebuilt.

1. What a real thing looks like: per pattern x cell x mode, over all widths, mean and variance of the
   normalised orbit totals (total / sum of totals), the orbits that separate it from glue and from the
   other patterns (standardised difference), and how the top orbits scale with width (slope of log total
   against log width). Table in results/, plain English in the report.
2. Fuzzy comparisons (fit on TUNE only):
   (a) histogram distance: per-orbit distribution of per-node counts (the GDD; marginals, not joint node
       profiles) compared by the 1-D earth-mover (Wasserstein-1) distance on log(1+count), averaged over
       orbits; nearest library entry per pattern; a multinomial logistic layer on the 7 pattern distances
       gives probabilities.
   (b) learned classifiers: multinomial logistic regression and a random forest. Features: normalised
       orbit totals, per-orbit quantiles (median, 90th percentile, maximum of log(1+count) over nodes),
       log node count, flip-flop count of the state group (the M3 width), cell one-hot. Training rows:
       TUNE single-design partitions (label = design family, as #69/#70) plus the library netlists
       (label = pattern; the library is the only source of lfsr and timer examples). TUNE threshold and
       calibration use out-of-fold probabilities (group k-fold by design) so they are not scored on
       training rows.
   (c) direction-tolerant directed signature. Orbit graph A over the 129 directed orbits: orbit o is
       adjacent to o' when o' is obtained from o by reversing the direction of exactly one edge of its
       graphlet (the node position follows the isomorphism); built from the catalogue
       (glet_count --directed --catalogue and docs/user/graphlets.md). Tolerance knob alpha:
       f = v + alpha * A v (v = normalised orbit totals); alpha 0 is the exact directed signature and
       alpha 1 mixes each orbit fully with its one-flip neighbours. Hard end of the scale: "undirected
       collapse" = sum of directed orbits that share an underlying undirected orbit (2 to 4 nodes). Levels
       run: alpha in {0, 0.25, 0.5, 1}, collapse. The same classifiers run on each level. The knob is
       reported at every level; the winner is chosen on TUNE.
   Undirected (73 orbits), directed (129) and directed-fuzzy all run.
3. Evaluation on TEST: 243 TEST singles and 82 TEST composites (81 or 79 per cell), per pattern x cell
   precision/recall, composite parts and wires, against #70's signature (nearest entry + naive Bayes,
   rerun from its stored scores), the rule, and hybrid (rule OR signature). Plus a per-pattern hybrid
   choice fit on TUNE (per pattern: rule, signature, rule OR signature, picked by TUNE F1 on singles plus
   TUNE composite parts). Reliability table of the best classifier's probabilities on TEST partition x
   pattern pairs.
4. Results dated, register rows, paper paragraph, PDF rebuild, PR with CI, no merge.

## Agent defaults (calls the brief left open; Peter may overrule)

- Per-node profile = the GDD marginal per orbit (what the pass returns without --per-node); the joint
  per-node vectors are not rerun for 7000 library jobs. Quantile features come from the GDD.
- Partition label for training = design family; glue has no partition (no state group) and stays a
  design-level decision exactly as in #69/#70.
- Probability layer for the histogram method: logistic on the 7 distances. Acceptance threshold fit on
  TUNE maximising F1 of design-level found / not found (as #69).
- Count-known (flip-flop count of the group) is a feature of the classifiers; the nearest-entry methods
  run with the count known and over all widths.
- Wires use the #70 rule (two accepted kind fsm/counter/shift groups linked by a net, direct or comb).
- Directed orbit ids are Odin III's own numbering; the flip relation is computed from the catalogue
  arcs, not from Sarajlic labels.
