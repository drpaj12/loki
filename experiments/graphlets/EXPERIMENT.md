# Loki graphlet signatures and directed graphlets (plan, 2026-10-30)

Resumed 2026-10-30 (dispatch the same day). The graphlet counters live in an Odin III analysis pass
(`graphlets`, another lane); Loki consumes them. Part 1 (generators, synthesis, database, live path)
does not need the pass; the signatures and matching (Parts 2 to 5) wait for it on odin3 main.

Plain English first: we want to ask "is this chunk of netlist the same kind of circuit as that pattern?"
without exact graph matching. We build a large library of known circuits (counters, shifters, state
machines ...) at every bit width from 1 to 32, synthesise each in five tool-and-target settings, take a
graphlet signature of each, and compare the signature of an unknown partition with the library. Widths
above 32 are made on demand ("live run") and cached. No result is claimed yet; no run was made before
this plan was written.

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

## Peter's words, addendum (2026-10-30, before dispatch)

"And then look at using both in the loki matching question? Is this graph this graph? Such that the
patterns to match against might need instances that are rolled out of different sizes such that we have
the signatures of the graphlets to look against. Does that make sense?" Earlier: "This should be possible
as a subgraph input such as a cone or some partition as this tells us if the signatures have similarity
suggesting (Bayesian condideance) that they are the same". Then: "I think it might need all bit sizes
(which from other loki methods suggest we know them) - this makes the database of patterns deeper - to the
point where >32-bits might be a db live run as opposed to already in the database. Ok do it."

## Plan (written before the runs, 2026-10-30)

Hypothesis (Peter's): graphlet signatures of a partition, matched against a library of pattern instances
rolled out at every width, find patterns the L1 claim chain misses; directed graphlets make the match more
precise. Purpose: Loki L2/L3 coarse-grain detection (hub L Q2.2, L Q3.1). Measures: per pattern x cell x
mode precision and recall on TEST (CAD-style counts first, then the label). Rule (unchanged): works when
precision >= 0.80 and recall >= 0.80 on TEST, 90% bootstrap lower bounds; "directed more precise" = higher
precision at equal or better recall, paired bootstrap over designs, Holm over patterns x cells.

### Part 1: library (no Odin III pass needed)

Generators (experiments/graphlets/gen.py), one top module `top`, every width 1..32 unless stated:
- counter: up, down, updown, up+load (4 variants); width = counter bits.
- shift: serial-in shift register (sipo), parallel-load/shift (2 variants); width = length.
- lfsr: Fibonacci, taps from the Xilinx XAPP052 table (checked for full period by simulation up to 22
  bits, reported); width 2..32.
- register: plain, enable, enable + sync reset (3 variants).
- timer: load-and-count-down with done flag, with and without enable (2 variants); width = counter bits.
- regfile: depth {2,4,8,16} x width 1..32, one write port, one async read port.
- fsm: state count 2..32 x encoding {binary, one-hot, gray}; cyclic advance on input 0, reset-to-0 on
  input 1, output = last state.
- glue: combinational: bus mux2, bitwise and/or/xor mix, equality comparator (3 variants).
Cells: O-gate (f3), O-lut (f2), O-hard (f1-k6), Y-gate, Y-lut, using the l3-census build scripts
(`build_odin.py`, `build_yosys.py` through a manifest swap as in l3-detector/run_all.py). Smallest
source first. Build failures are counted and listed, not hidden.

Database (decision in the report of 2026-10-30, see "Database" below): Mimir `records` columns, one SQLite
file written by Loki, plus a Loki-side `entries` table with pattern, variant, width, depth, cell,
provenance (precomputed or live), RTL and netlist sha256. Live path (experiments/graphlets/live.py):
generate at the inferred width, synthesise in the needed cell, store the netlist and (after the pass
exists) the signature with provenance `live`; tested at 33, 48 and 64.

Width inference (item for the report): evaluate on the l3d-out composites and singles which of the L1
claim widths (word / bus / counter width) matches the true width, and how often.

### Part 2 onward (waits for the Odin III `graphlets` pass on odin3 main)

Signatures: undirected, directed, directed + typed when the pass has it. Size handling: (a) whole-partition
normalised signature (GDD agreement), (b) per-node orbit-profile distributions, (c) nearest library size;
with all widths precomputed the width comes from inference and 1..32 lookups are exact; held-out widths are
only a secondary check of what a missing entry costs. Calibration file (Bayesian likelihoods) from TUNE
pairs only. Matching: partitions = cones around state-register groups and L2 partitions, on the L3 v0
benchmarks (singles TEST and the 82 TEST composites) and rolled-out TEST sizes; posterior threshold fit on
TUNE. Report per pattern x cell x mode vs the L3 v0 rule detector and a hybrid (rule OR signature);
reliability plot; register rows; paper paragraph; PDF rebuild; PR, wait CI, do not merge.
