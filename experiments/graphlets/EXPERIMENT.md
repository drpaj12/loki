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

## Part 1 results (2026-10-31, plain English first)

We built the library of known circuits and the place to keep their signatures. The signatures
themselves are not computed yet: the Odin III `graphlets` pass is not on odin3 main (no PR for
feat/graphlets found on 2026-10-31), and Loki does not write it. No matching result is claimed.

Counts (CAD-style first):
- 700 RTL instances (counter 128, regfile 128, register 96, glue 96, fsm 93, shift 64, timer 64,
  lfsr 31) x 5 cells = 3500 builds: 3500 ok, 0 failed (~0.2 s per build; Odin and Yosys).
- LFSR taps checked by simulation for full period 2^w - 1 at every width 2..16 (unit test);
  17..22 were checked in a one-off run; 23..32 and the live taps for 33, 48, 64 are the published
  table values, period not simulated.
- Live path (generate, synthesise in a cell, register with provenance `live`): counter up/updown,
  shift serial, lfsr, register enrst, timer enable, regfile depth 8, fsm binary/onehot/gray, glue mux2
  at widths 33, 48 and 64 in all 5 cells: 165 of 165 built ok. Signature step returns "pending" until the pass
  exists (tested with a fake signer in test_graphlets.py).
- Database: `$GLET_OUT/graphlet_library.sqlite` (work/glet-out, not committed), schema in `db.py`:
  Mimir `records` columns and identity (spec section 2) holding one orbit count per row (metric
  `graphlet_orbit_count`, bin = orbit id, arm = mode undirected / directed / directed_typed,
  arch = cell, level gate or lut, source `loki-graphlet-pre` or `loki-graphlet-live`), plus a Loki-side
  `entries` table (pattern, variant, width, depth, cell, provenance, rtl and netlist sha256, build
  status, Odin III commit, Yosys version, generator hash) and `meta`. Why records and not a new table:
  the tidy table already carries every field of the brief except pattern, variant and width, which sit
  in `design` (`glet/<pattern>_<variant>[_dD]_wNNN`) and the entries table; provenance sits in `source`.
  Needs recorded for the controller (Mimir not changed): registry entry for `graphlet_orbit_count`
  with measurer `graphlet`; decide whether pattern, variant, width become first-class columns; whether
  per-node orbit profiles (method 2b) need a second metric. 3665 entries registered (3500 precomputed,
  165 live).

Width inference (library netlists, true width by construction; `width_infer.py`, results/width_infer.csv;
3185 of 3500 netlists analysed when this was written, the biggest register files were still running).
Exact-match rate of the state-register width, M1 widest word claim (counter, register, lfsr, shift_reg,
ff_en), M2 widest bus, M3 count of distinct flip-flop output nets (regfile M3 against depth x width):
counter 0.45 / 0.77 / 0.92; shift 0.60 / 0.97 / 0.97; lfsr 0.93 / 1.00 / 0.93; register 0.45 / 0.79 /
0.59; timer 0.23 / 0.41 / 0.86; regfile 0.73 / 0.59 / 0.78; fsm 0.07 / 0.34 / 0.36 (state bits; the tools
recode states, so the FSM state count is not read from flip-flop count); glue has no state, M2 0.56.
Reading: no single method is right; M3 for counter/timer, M2 for shift/lfsr/register. The honest rule
for matching: use the width of the candidate state-register group (M3) when a pattern hypothesis is
tested, and fall back to the nearest-size methods when widths disagree. Caveat: this is on isolated
library circuits, not on partitions of composites; Part 2 must redo it per partition.

## Next step (resume here)

1. Check `gh pr list -R drpaj12/odin3 --head feat/graphlets --state all` and
   `git -C ~/odin3-ws/odin3 fetch origin`; when the `graphlets` pass is on odin3 main, read its
   interface (modes, output format) and implement `live.odin_signer`.
2. Compute signatures for all 3500 library netlists (modes the pass offers) into the database; export CSV.
3. Finish `re` on the remaining library netlists (large register files), rerun `width_infer.py`.
4. Items 2 to 5 of the brief: size handling comparison, TUNE-only calibration file, matching on the L3
   v0 TEST benchmarks, report with reliability plot, paper paragraph, PR, wait CI, do not merge.

## Blocker found 2026-10-31 (fixed by odin3 #305, 20ffe2b3) (Odin III pass, for the controller)

The `graphlets` pass of odin3 0a44260b drops every cell whose type has a `const_value` hook:
`node_eligible` in `src/passes/graphlets/gl_net.c` returns `def->const_value == NULL`, and `$sop`
(a BLIF `.names`) and `$lut` both have that hook (`src/ir/cells/sop.c`, `lut.c`). Effect, checked:
`.model t; .inputs a b; .outputs y; .names a b y; 11 1` reads as 3 nodes and 0 edges (`$port_in` x2,
`$port_out`; the AND is missing). For the library netlists O-gate/O-lut/Y-gate/Y-lut every logic
gate/LUT is missing (counter_up_w008 O-gate: 18 nodes, 0 edges instead of ~30 nodes); only
flip-flops, ports and hard blocks survive (O-hard 25 edges). Signatures from the pass would therefore
describe flip-flops and ports only. Fix wanted in Odin III (not done by Loki): exclude a node only when
it is an actual constant (its output net has `odin3_net_const_value != ODIN3_CONST_NONE`), not by
cell type; add a unit test with a 2-input `.names`. Also noted: the pass has no typed mode, so the
directed + typed variant is not available; the global-net rule is Odin's (clock pin or >= 16 readers).
No signatures were computed (they would be wrong). Resume at "Next step" item 1 once fixed; the
signer is then `Design.read_blif(netlist, techlibs=[lib/vtr.o3lib]).graphlets(exclude_global=True,
directed=...)`, groups[0] orbit_totals and gdd, stored through `db.put_signature`.

## Results, 2026-10-31 (Odin III graphlets pass at 20ffe2b3; plain English first)

Plain English: describing a whole small design by its graphlet signature is not enough to say what
kind of circuit it is. It cannot beat the rule detector of L3 v0 on counters, state machines or glue,
and it does not reach the 0.80 bar for any pattern. Directed graphlets helped in one case of 25. Where a
library circuit of the right kind exists at another width, the nearest-size match finds the kind about
four times in five. The partition question (cones around state registers, the 82 composites) is not
answered: it is the next step.

CAD-style counts first.
- Library: 700 instances x 5 cells = 3500 netlists, signatures in 2 modes (undirected size 5 with 73
  orbits, directed with 129 orbits) = 7000 pass runs, 0 failures; stored in the database (`sigs.py`).
  Global-signal rule is Odin III's (net reaches a clock pin or has >= 16 readers), simpler than Loki's
  `signals.py`. Typed mode: the pass has none, so directed + typed was not run.
- Python similarity (`simil.py`: GDD agreement, cosine of log(1+totals)) equals `odin3.graphlet_compare`
  to 5 decimals on 6 pairs (undirected and directed).
- Live path at 33/48/64: 165 of 165 built and signed (both modes).
- L3 v0 single designs with exactly one pattern label: 243 TEST (counter 14, fsm 41, glue 99, regfile 12,
  register 74, shift 3; no lfsr or timer single exists), 253 TUNE. Signature jobs: 5 failures, all
  Yosys netlists of one design (`ve_Prob021_mux256to1v`, work cap 3e8 sets), excluded from the
  comparison for every variant.
- Calibration (TUNE only): per mode and library-restriction a binned likelihood file in pass format
  (`results/calibration_<mode>_<restriction>.json`), prior from TUNE pairs (best entry of each of 8
  patterns per design: 1 same, 7 different); threshold fit on TUNE accuracy (0.05 in all four, so the
  posterior never rejected: TUNE accuracy 0.33 undirected / 0.37 directed over all widths, 0.43 / 0.44 with
  the flip-flop count known). Reliability on TEST (`results/match_reliability.csv`): the posterior is
  ordered but poorly calibrated (undirected, count known: posterior 0.0-0.1 observed 0.09, 0.2-0.3
  observed 0.27, 0.8-0.9 observed 0.73; no pairs in the other bins).
- Per pattern x cell x variant TP/FP/FN, precision, recall, bootstrap lower bounds, label:
  `results/match_table.csv` (variants: rule, undirected/directed x all widths / flip-flop count known,
  hybrid = rule OR signature). Pooled over the five cells, TP/FP/FN: counter rule 70/0/0, undirected
  (count known) 54/176/16, directed 57/150/13; fsm rule 192/19/5, undirected 58/60/139, directed 54/37/143;
  regfile rule 6/6/54, undirected 36/116/24, directed 38/104/22, hybrid-directed 42/109/18; register rule
  287/37/66, directed 108/166/245; shift rule 10/71/5, undirected 7/108/8; glue rule 494/2/0, directed
  221/29/273. Labels (40 pattern x cell rows per variant): each signature-only variant has 0 WORKING, 25 NOT WORKING,
  15 INCONCLUSIVE (fewer than 5 positives); the rule has 14 WORKING, 8 NOT WORKING, 18 INCONCLUSIVE;
  the hybrid is WORKING only for glue (4 or 5 cells), where the rule already was.
- Directed more precise: 1 of 25 tests after Holm (fsm, Y-gate: precision 0.50 -> 0.78, recall 0.22 ->
  0.49, Holm p 0.0125); `results/match_directed_vs_undirected.csv`.
- Missing library width (held-out widths 5, 11, 19, 27; 88 instances x 5 cells x 2 modes): nearest-size
  match finds the pattern 339/440 undirected and 352/440 directed when the flip-flop count has no entry; 0.95 to
  1.00 per pattern when every other width is searched (undirected register 0.78).
- Width inference: see "Part 1 results"; to be rerun per partition.

Verdicts: GL1 (signatures find what the claim chain misses) INCONCLUSIVE, whole-design matching
NOT WORKING, partitions untested; GL2 (directed more precise) INCONCLUSIVE (1 of 25); GL3 measurement.
Register rows and the paper paragraph are in docs/paper (hypotheses.md, register.tex, loki.tex,
build/loki.pdf).

Not done (stated, not hidden): cones around state-register groups and L2 partitions; the 82 TEST
composites; rolled-out TEST sizes as partitions; the posterior reliability plot is a table, not a plot;
width inference rerun on the last 315 library netlists (large register files).

## Next step (resume here, 2026-10-31)

1. Partitions: for each single/composite, take state groups from the L1 claims (counter, register,
   shift_reg, lfsr, fsm q nets), build a cells file from the union of `cone(net)` groups (per-node ids),
   run `graphlets --cells`, match each partition against the library (width = flip-flop count of the
   group), score against composite truth (families per part) with the same TUNE calibration.
2. Rerun `width_infer.py` when `re` has finished for all 3500 netlists.
3. Reliability plot from `results/match_reliability.csv`.

## Plan for the partition round (written 2026-10-31 before the runs; branch exp/graphlets-partitions)

Controller request: the core of Peter's question. Partition = state group of the L1 claims (flip-flop
output nets of counter, register, shift_reg, lfsr, fsm and ff_* claims, merged on overlap), grown to
the union of the fan-in cones of its outputs (`cone(NET)`; the cone crosses flip-flops, so in a
composite it can include upstream parts: a known limit, reported), counted with `--cells` (halo 0,
Odin III's global rule), undirected and directed, matched with the library by the group's flip-flop
count (width known) and over all widths. Truth: L3 v0 singles (design family; glue = no state group)
and the 82 TEST composites (part families by kind, same scoring as part_c: parts matched / truth parts,
parts matched / detected parts). Comparators: the rule detector and the hybrid (rule OR signature).
Calibration fix: the earlier threshold never rejected because it was fit on top-1 accuracy, where a
rejection is always wrong on single-family designs. Now: pairs are partition x pattern on TUNE singles,
and the threshold maximises TUNE F1 of the design-level found/not-found decisions (a rejection avoids a
false alarm). The reliability table is reported as it is. L2 partitions (loki.analysis clustering) are
not run: their node ids come from Loki's graph.json, not Odin III's node ids, and a mapping would have to
be built first (recorded as a need, not done). Rule unchanged: works at precision and recall >= 0.80
(90% bootstrap lower bounds); directed more precise = paired bootstrap, Holm.
