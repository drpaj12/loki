# Loki graphlet signatures and directed graphlets (plan, 2026-10-30)

paused 2026-10-30: counters move to Odin III (Peter); Part C resumes after the Odin III pass merges.

No counter code is written in Loki. No runs were made. This file holds the plan text written so far.

## Peter's words (2026-10-30)

"Is the pattern at L3 too restrictive - these are graph reconsrtuctions, so is there a way to use
graphlett signatures to ask in a partition is the signature there - isomorphism won't work, but maybe a
graphlett signature method might suggest things?" and "Is there a way of counting directional graphlets
(an extension of the method but with directionality? ...) can we build graphlets as signatures BUT also
directional graphlets as it's own thing and use it as a coarse grain pattern detection in circuit
recomositioon)". Scope change, same day: "Again, I feel this is an Odin characteristic feature that
should be a property, much like all the Mimir characteristics". The graphlet counters (undirected
native, directed, typed) become an Odin III analysis pass. Loki only consumes them.

## Hypothesis (Peter's)

Graphlet signatures of a partition find patterns that the L1 claim chain misses, and directed graphlets
make the signature more precise. Purpose: Loki L2/L3 coarse-grain pattern detection; hub L Q2.2, L Q3.1.
Measures: per-pattern precision and recall on TEST (L3 v0 baseline: experiments/l3-detector).

## Rule (fixed now)

A signature detector "works" for a pattern on TEST when precision >= 0.80 and recall >= 0.80 (90%
bootstrap lower bounds reported). "Directed is more precise" when directed beats undirected in
precision at equal or better recall, paired bootstrap over designs, Holm over patterns x cells.

## Part C (Loki, resumes later)

Partitions: cone around each state-register group, and loki/analysis/partition.py. Signature = normalised
orbit distribution with global signals removed (signals.py). Library per pattern x cell from TUNE singles
and composites; nearest signature or small classifier fit on TUNE only. Variants: undirected, directed,
directed+typed, plus hybrid (rule OR signature). Compare with the L3 v0 rule detector on TEST, focus on
shift, timer, regfile. Benchmarks: l3d-out (5 cells), truth by construction.

## Facts gathered for the Odin III lane (verified 2026-10-30)

Crossref-verified references:
- Przulj, Bioinformatics 23(2):e177-e183, 2007, doi:10.1093/bioinformatics/btl301 (orbit definitions).
- Hocevar and Demsar, Bioinformatics 30(4):559-565, 2014, doi:10.1093/bioinformatics/btt717 (ORCA; GPL-3.0, oracle only).
- Sarajlic, Malod-Dognin, Yaveroglu, Przulj, Sci Rep 6:35098, 2016, doi:10.1038/srep35098.
- Aparicio, Ribeiro, Silva, IEEE/ACM TCBB 14(6):1302-1315, 2017, doi:10.1109/TCBB.2016.2586046
  (title confirmed; its graphlet and orbit counts NOT yet read: read the paper before stating them).

From the Sarajlic text (nature.com/articles/srep35098, read 2026-10-30): directed graphlets are induced
subgraphs without anti-parallel edges; 40 two- to four-node directed graphlets G0..G39 with 129 orbits
(0..128); an anti-parallel pair is handled by counting the graphlet once per direction separately (Fig 1c:
one G21 for one edge, one G25 for the other); counted by complete enumeration. Check any implementation
against 40 / 129.
