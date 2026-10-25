# Loki round 4: patterns from our own data, big designs as a pattern source, what is recoverable

Protocol written 2026-10-25, before the corpus was generated and before any round-4 number was
computed. This file is committed and pushed first (Stage 0); its commit SHA is the rule-provenance
SHA quoted in the paper. A later change to a rule is a dated entry in "Rule additions" at the end
that keeps the old rule; the paper reports the result under both rules. Post-data analyses are
dated, labelled exploratory entries and never change a status.

Compute-only: no LLM call (existing round-2 LLM outputs are rescored), no new detector code in
`loki/`. Prototype code (generator, dictionary matcher, scripts) lives in `experiments/round4/`.

## Questions

Peter (2026-10-24), verbatim: "Queue those as round 4 after round 3 finishes - we're trying to
make these better - I like the Loki ideas so yes (especially the idea of patterns from our data
(what about the bigger designs, do they provide other insights of patterns)." Framing: how do we
go from the low-level, obfuscated, information-lost netlist back to behavioural HDL?

Round 3 (loki main b15c079) found that wrong candidates sit inside real constructs but do not tile
the words (H9b 0.065), that `ff_en` candidates are correct per-bit slices and the miss is word
grouping, that `eq_const` is a detector problem, that port propagation stalls after about one hop
and that complete FSM -> decode -> control chains are rare (5/89). A word-first detector (round 5)
needs labelled data and pattern knowledge. This round builds both.

- RQ-L12a: can we generate a labelled synthetic corpus of idioms (our own data), with a
  train / test split by parameter region?
- RQ-L12b: does a signature dictionary mined from the corpus propose word constructs better than
  the round-2 detectors, on real designs, and which signatures survive from f2 to f3?
- RQ-L12c: does a GNN trained on the corpus transfer to real designs, and does transfer improve
  with corpus size?
- RQ-L13: do the larger VTR designs show repetition (instances, isomorphic subgraphs) that gives
  free word or module evidence? (Measure only, plus the three hypotheses below.)
- RQ-L14: what is recoverable in principle (identifiability of RTL style from the netlist; an MDL
  readability score)?

## Data and environment

Odin III 1.1.0 (ABI 6, `libodin3.so`, `libodin3_slang.so`), Wyrd (venv of `work/loki-f3-exp`),
Loki main b15c079 plus this branch, 12 cores, 23 GB VM. Read-only reuse: micro dataset
`work/loki-rename-exp/dataset-rebuild` (68 designs at f2 and f1-k6, 65 at f3), VerilogEval L0
dataset `work/loki-veval-exp/dataset` (150 designs; manifest split 117 train / 33 test),
round-2 runs `work/loki-exp2-data`, round-3 runs `work/loki-exp3-data`, VTR sources in
`$VTR_ROOT/vtr_flow/benchmarks/verilog` (read-only), round-1 LLM samples
`work/gatebreaker-exp2/data/llm`. New data under `work/loki-exp4-data/` (not in git).

Real evaluation set E_real = the micro designs (f2) plus the 33 VerilogEval test designs (f2);
f3 is the second floor. "Held-out" always refers to the dictionary and the GNN, both trained on the
corpus only (the real designs enter no fit).

Earlier data the rules were informed by (all known before this file): round-2 and round-3
counts (detectors propose many candidates with low precision; GT kind counts); the GT instance
counts per kind and design count of E_real, used to fix the eligible kinds of H12b (see there);
a pilot of 60 generated designs (seed tag `r4pilot`, ids `r4p_*`, two train, one iid, two ood
designs per family, not part of the corpus) that was built through the whole veval-l0 pipeline to
check the templates: 60 of 60 designs built on f1-k6, f2 and f3, all equivalence checks
`equivalent`, `loki check` 0 errors, f2 node counts 9 to 529. No matcher, detector or GNN has been
run on any generated design.

## Stage 1: corpus specification (RQ-L12a)

Generator `experiments/round4/gen/` (`regions.py` holds the parameter regions, `templates.py` the
twelve templates, `corpus.py` the sampler). Deterministic: the seed of a design is the first 32 bits
of sha256 of `tag:family:attempt`; every design records family, split, seed, parameters in
`corpus.csv`. Duplicate Verilog text is dropped (sha256), so a family may fall short of its quota;
the shortfall is reported.

Families (twelve): `mux` (2:1 to N:1, select or priority; styles ternary, if/else, case; test
styles `index`, `casez`), `counter` (up, down, load, enable; if/else, ternary), `adder` (carry
in/out, registered or not; `assign`, `always`), `subtractor`, `comparator` (eq, lt, gt; variable
or constant operand), `shifter` (constant and barrel), `fsm` (3 to 16 states, binary, one-hot,
gray, Moore, Mealy, 1 to 3 inputs, random transition table), `regfile` (2 to 16 words, 1 or 2 read
ports), `pipeline` (2 to 5 stages), `register` (enable, reset, input mux), `dpfsm` (datapath with an
FSM controller), `alu` (2 to 6 operations).

Split by parameter region (full table in `regions.py`; widths 4, 6, 8, 12, 16 are train, 5, 7, 10, 24
(32 for the shifter) are test only; test-only styles: mux `index` and `casez`, counter
`nextstate` and `updown` and async reset, adder `ripple`, subtractor `twos`, comparator `ne le ge`,
signed operands and `ternary`, shifter `asr`, `c5` and `stages`, fsm gray encoding, three inputs,
`ifelse`, 7/10/12/16 states, regfile async reset and non-power-of-two depths, pipeline 5 stages and
`vector` and async reset, register async reset and `nextstate`, dpfsm 5/6 states and `xor` and
`ifelse`, alu 5/6 operations and `ifelse`). Per family: indices 0 to 69 are **train** (every
parameter has a train value), 70 to 79 are **iid test** (train region, text not seen in train),
80 to 99 are **ood test** (at least one parameter has a test-only value). Nominal sizes: 840 train,
120 iid, 240 ood designs (1,200 corpus designs); the dataset is capped at 4 GB and the run stops
if `df -h /mnt/c` shows less than 30 GB free (110 GB at the time of writing). Estimated size from the
pilot: 0.6 GB. Build: Odin III on f1-k6, f2, f3 via the veval-l0 pipeline (Wyrd project, `wyrd run
--jobs 3 --mem-budget 8G` under the heavy lock, `loki assemble`, `loki check`). The split rule of
`loki assemble` (hash of the design name) is kept in the assembled `manifest.json` and checked by
`loki check`; afterwards the manifest `split` fields are rewritten by the corpus split (train ->
`train`, iid and ood -> `test`; original saved as `manifest.hash.json`) so `loki calibrate
--split train` and the GNN read the corpus split.

Twin set (RQ-L14): 12 base designs per family (tag `r4twin`, train region only), each rendered in
every coding style of its family with the other parameters and the seed unchanged (styles per
family: mux 5, counter 3, adder 3, subtractor 3, comparator 3, shifter 2, fsm 2, regfile 2,
pipeline 3, register 3, dpfsm 2, alu 3; 34 variants per base position, 408 designs). The shifter
twin base uses the barrel amount so that both styles apply. Twins are built (floors f1-k6, f2,
f3) in a separate dataset and enter no fit or test of RQ-L12.

Report (`corpus_report.csv`): per family and split: generated, built per floor, failed per floor,
equivalence-gate failures per floor, nodes and cells per floor.

**H12a (the corpus is usable).** P_ok = share of generated corpus designs that build on all three
floors with every equivalence check `equivalent` or skipped for black boxes. Supported: P_ok >= 0.95,
every family has at least 60 designs ok on all floors, and P_ok(ood) >= P_ok(train) - 0.05. Not
supported: P_ok < 0.80 or some family below 30 ok designs. Otherwise inconclusive. Reachability:
VerilogEval L0 lost 6 of 156 designs (Q4 casts, `initial x`, negedge); the corpus uses none of
these but the test-only async-reset styles are exactly the kind of construct that can make
`lower --async sync` non-equivalent; the pilot (2 ood designs per family) passed, so the supported arm is the expected one and the not-supported arm is the style-driven
failure.

## Stage 2: signature dictionary (RQ-L12b) and GNN scaling (RQ-L12c)

### Dictionary (prototype `experiments/round4/dictlib.py`, `l12b_dict.py`)

Graph: `graph.json` of the floor; cells = nodes of kind lut, gate, ff, hard.

Cone class of a cell c: the combinational cone (stopping at pi, const, ff outputs and hard cells,
which are leaves) of c, cut with at most 4 leaves, taking the cut with the most leaves (ties: the
cut whose canonical truth table is smallest). The function of a cell is its `lut_table` (luts) or
the function of its gate in `lib/cmos6.o3lib` (via `loki.techlib`). For an ff the cone is that of
the net driving its data input, with a flag when the ff's own output is a leaf (feedback). The
cone class is the NPN canonical form of the truth table (exhaustive over input permutations and
input and output negations, k <= 4) together with the leaf count and the feedback flag. WL
context of radius r: `WL_0(c) = (kind, cell_type)`; `WL_r(c) = hash(WL_{r-1}(c), sorted
(pin, WL_{r-1}(d)) over fan-in cells d, sorted (pin, WL_{r-1}(s)) over fan-out cells s)`.
Signature of c at radius r: `(cone class, WL_r)`.

Mining (train split of the corpus only, per floor): for every cell, `K(c)` = the construct kinds
K of the dictionary kinds `K_dict` = {ff_en, ff_srst, register, adder, subtractor, comparator,
eq_const, mux, mux_tree, counter, fsm} such that some GT instance (`derive_instances`, derived
ones included) containing c has a type in `SCORED_TYPES[K]`. Entry of a signature s: n(s) = number
of train cells with s; count of each K. The entry fires for K when `n(s) >= 3` and the share of K
>= 0.6 (theta_p).

Matcher: a test cell c is labelled K if its signature fires for K. Per K, the cells labelled K form
the candidate graph H_K: two cells are joined when adjacent in the netlist, or when they have
equal signature and read a common net that is not driven by a cell labelled K and not a clock pin.
Each connected component of H_K is one candidate of kind K (status committed, p = 1, cells =
component), a word. Kinds outside `K_dict` (`mux_bit`, `adder_cin`) get no candidates and are not
compared. The radius r is chosen once per floor from {0, 1, 2, 3} as the one with the highest pooled
micro-F1 (2 matched / (counted + GT) over the kinds of `K_dict`) on the corpus **iid test** at that
floor (ties: smaller r); it is then fixed for every other set.

Scoring: the round-2 scorer unchanged (`loki.score.metrics.construct_scores`, `score_p` 0.5, GT
`derive_instances`), kind precision and recall as micro sums over designs, F1 as in `r2lib.summarise`.
Word-level overlap (round-3 definitions, report only): the share q_K of GT instances of kind K with
at least two cells whose fragment coverage Cov_frag >= 0.8 (a fragment is a candidate of the family
of K contained at >= 0.8 in the instance), for the dictionary and for the detectors.

Detector baselines (existing runs, existing code): on E_real f2 the round-2 sets M2N (micro,
uncalibrated), M2C (micro, calibrated), V2N, V2C (VerilogEval, restricted to the 33 test designs);
f3: M3N, M3C, V3N, V3C. On the corpus the same detectors are run at f2 (new `loki re` runs on iid and
ood designs: N uncalibrated, C calibrated with `loki calibrate --floor f2 --split train` on the
corpus train split), nothing else is run. Per kind the detector arm is the better of N and C by
pooled F1 on the evaluated set (conservative: the choice favours the detector).

**H12b (dictionary beats detectors on real designs).** Eligible kinds (>= 10 E_real f2 designs with
GT of the kind, counted from the existing GT before this file was written): adder (31 designs),
subtractor (14), comparator (27), eq_const (25), mux (22), register (41), ff_srst (12) - seven
kinds. For each eligible kind k, on E_real f2 over the designs that have a run in both detector
arms and the dictionary: kind k is **won** when pooled F1(dictionary) >= pooled F1(better detector
arm) + 0.05 and the one-sided paired Wilcoxon signed-rank test (scipy, zero differences dropped,
alpha 0.05, no multiplicity correction) over the designs with GT of k, on the per-design
F1_i = 2 matched_i / (counted_i + GT_i), gives p < 0.05. A kind with fewer than 8 paired designs
is not won (no scaling). Supported: won on >= 4 of the 7 kinds. Not supported: won on <= 1 of
7. Otherwise (2 or 3) inconclusive. Ff_en, counter, fsm and mux_tree (fewer than 10 designs with GT)
are reported, not counted. f3 (second floor) and the corpus ood split are reported, not deciding.
Reachability: the dictionary's real-design F1 can be 0 for any kind (nothing transfers) or
above the detector's; the round-2 detectors' F1 on these kinds is small but non-zero (adder and
register fire in M2N), so 0 to 7 wins are all possible.

**H12b2 (the dictionary generalises over unseen parameter regions).** R = micro-F1 of the dictionary
on the corpus ood test divided by the micro-F1 on the corpus iid test (f2, `K_dict`, pooled). Supported:
R >= 0.80. Not supported: R < 0.50. Otherwise inconclusive. Dependency: if micro-F1 on iid < 0.20 the
ratio says nothing and the status is inconclusive. Reachable: test-only styles (ripple adders,
`index` muxes) change the netlist structure, so R can fall under 0.5; if the signatures capture
function and not structure it stays above 0.8.

Floor stability (measure only): per kind, signatures (cone class only, without WL) with n >= 3 and
share >= 0.6 on the train split at f2 and at f3; shared = the same cone class fires for K on both
floors; reported are the sizes of the two sets, the shared set, the Jaccard, and the share of f3
firing classes lost at f2 and of f2 classes lost at f3 (`l12b_stability.csv`). No status.

### GNN scaling (`l12c_gnn.py`)

`loki.analysis.gnn.train_eval` as in the round-2 L2 experiment (sage, hidden 64, 100 epochs,
lr 0.01, weight decay 5e-4, target `construct_type`, features `node`), floors f2 and f3. Train sizes
n in {36, 72, 144, 288, 576, 840} (3, 6, 12, 24, 48, 70 train designs per family; log2 spacing from
n = 36 to 840, 4.5 doublings), seeds 0, 1, 2 (seed s draws the subset with `random.Random(s)` and
seeds the model). Test sets (one training run is scored on all): corpus iid, corpus ood, micros
(f2 or f3 as trained), VerilogEval held-out (33 designs). Reference arm (report only): the same
model trained on the 117 VerilogEval train designs, seeds 0, 1, 2. Score T(n, s) = macro-F1 over the
`construct_type` classes present in truth or prediction on the pooled nodes of a test set (as
`gnn.metrics`), computed from `predictions-<design>.csv`.

**H12c (transfer improves with corpus size).** On VerilogEval held-out f2: slope b = OLS slope of
mean_s T(n, s) on log2 n over the six sizes, per doubling. 95% CI: percentile bootstrap over the 33
designs (B = 2000, `random.Random(4)`, resample designs, recompute every T and b). Supported:
b >= +0.020 per doubling and CI lower bound > 0. Not supported: CI upper bound < +0.010. Otherwise
inconclusive. Micros f2, corpus iid/ood and f3 are reported with the same slope and CI, not
deciding. Plateau (report): the smallest n whose mean T is within 0.01 of the maximum mean T.
Reachability: a flat or negative curve (distribution shift between synthetic idioms and VerilogEval
logic) gives an upper bound under 0.01; a gain of 0.09 macro-F1 over the range gives b = 0.02.

## Stage 3: bigger designs as a pattern source (RQ-L13, measure)

Designs (Odin III's goldens cover the 19 VTR 7.0 benchmarks plus arm_core and spree, per
`odin3/docs/PHASE3.md`; LU64PEEng is in neither and is attempted last): from
`$VTR_ROOT/vtr_flow/benchmarks/verilog`, smallest source first: stereovision3, sha, mkPktMerge,
blob_merge, stereovision2, spree, bgm, boundtop, raygentop, stereovision1, stereovision0, or1200,
mkSMAdapter4B, LU8PEEng, LU32PEEng, mkDelayWorker32B, arm_core, mcml, LU64PEEng (diffeq1, diffeq2 and
ch_intrinsics, all under 6 kB, are not used). Each is built on f1-k6, f2 and f3 one at a time with Odin III peak
RSS measured (`/usr/bin/time -v`, maximum over the process) under the heavy lock and a hard address
limit of 14 GiB (60% of the VM is 13.8 GB); a design that fails the limit is skipped and recorded
with its failure. Equivalence gate: big designs are built with the Loki equivalence check disabled
(agent default, stated in the paper: big designs are not equivalence-checked, as in Odin III);
`meta.json` records `skipped:big`.

Measures (per design and pooled; small designs = micros + all 150 VerilogEval + corpus train; f3
decisive, f2 reported): module instances and repeated module paths; **repeat groups**: GT word
instances with at least 2 cells and width >= 2 (words.json), grouped by key (type, width, hash
of the footprint-induced subgraph by WL radius 2 over cell types); a group has >= 2 members;
memories (`$mem`/hard-memory words and their sizes); pipelines (register-to-register depth: the
longest register-to-register path in cells and the number of register ranks along it); wide buses
(label buses of width >= 8); shared control fan-out (nets with >= 8 readers that drive a select,
enable or reset pin; and the share of words they reach); FSM count (words with the fsm flag).
Round-2 detectors and the dictionary are run on a big design only if the measured cost is under
1800 s per design (`loki re`) and the dictionary under 300 s; otherwise recorded as measurement
only.

Let share_rep(S) = pooled number of words in repeat groups / pooled number of words with >= 2 cells
and width >= 2, over the design set S at f3.

**H13a (big designs are mostly repeated structure).** Supported: share_rep(big) >= 0.50. Not
supported: < 0.25. Otherwise inconclusive. `big` = the designs of the list above that built; if
fewer than 3 built, inconclusive.

**H13b (big designs repeat more than small ones).** Supported: share_rep(big) - share_rep(small) >=
0.15. Not supported: <= 0.05. Otherwise inconclusive. Same condition on `big`.

**H13c (repeated instances share the dictionary signature).** Over the repeat groups of size >= 2
of the big designs at f2 (the floor where cells absorb neighbours, so signatures can differ), the
share of groups whose members have identical multisets of dictionary signatures (cone class, WL_r
of their cells, r from H12b at f2). Supported >= 0.70, not supported < 0.40, otherwise
inconclusive. Reachability: cells on a module boundary have different WL context in different
instances, so a share below 0.4 is possible; identical induced structure inside the footprint with
identical surroundings gives 1.0.

## Stage 4: what is recoverable in principle (RQ-L14)

### Identifiability (twin set)

Canonical netlist class of a design at a floor: colour refinement (1-WL) on `graph.json` with
initial colour (kind, cell_type, lut_width, `lut_table` canonicalised under input permutation for
luts), directed edges coloured by pin name, ports anonymous (bus names and indices dropped),
6 refinement rounds, class = hash of the sorted multiset of final colours. Colliding twin variants
(same class) are confirmed by exact isomorphism (`networkx` VF2 with the same colours) when the
netlist has at most 400 nodes; larger classes are reported WL-only. Per twin base position: styles
S, netlist classes C at the floor; **style-recovery ceiling** = C / S (the accuracy of the best
possible guesser of the coding style from the netlist under a uniform prior); **collapse** = 1 -
ceiling. Reported per family and floor (f1-k6, f2, f3). The same quantity on the exact isomorphism
classes where confirmable.

Bayes ceiling of a signature classifier (report only): on the corpus (train and test pooled), per
floor and radius, the upper bound on cell-level accuracy of any classifier that sees only the
signature: sum over signatures of the largest kind count over the total, and per kind K the share
of K cells in signatures whose majority kind is K.

**H14a (the flow destroys style information).** Pooled over all twin base positions, ceiling(f3)
<= 0.60 supported (at least 40% of style variants are indistinguishable); >= 0.85 not supported;
otherwise inconclusive.

**H14b (the coarser floor destroys more).** ceiling(f3) - ceiling(f2) >= 0.05 supported; <= 0.00 not
supported; otherwise inconclusive. (Independent of H14a: it compares the two floors whatever the
level.)

### MDL readability

Token description length (DL) of a Verilog text: tokens by the regular expression of
`experiments/round4/mdl.py` (identifiers, numbers, operators and punctuation); comments dropped.
Cost of a text, a two-part code: (1) every keyword, operator and punctuation token t costs
`-log2 p(t)` under a Laplace-smoothed unigram over those tokens estimated on the 156 VerilogEval
references (the DL of a reference is computed leave-one-out, with its own tokens removed from the
counts); (2) the first occurrence of an identifier costs 8 bits (its spelling), a repeated
identifier costs `log2(d)` bits where d is the number of distinct identifiers so far (a back
pointer), a number costs `2 + log2(1 + |value|)` bits. Justification: the references are the
readable RTL the question asks for, so common constructs are cheap; a netlist-like text repeats
few operators but introduces many names and so pays the pointer cost. DL is
normalised by the reference: ratio = DL(candidate) / DL(reference).

Candidates (VerilogEval refs `*_ref.sv`; round-2 Loki outputs: `netlist.v` L0 at f2, f3, and the
`design.v` of the round-2 runs f2-none, f3-none, f2-calib, f3-calib; round-2 LLM samples: the
round-1 `gatebreaker-exp2` samples extracted from `attempt_*.raw.txt`, no new calls; the round-3
M3N/M1N micro runs have no reference text and enter no MDL comparison). AST and CFG similarity
from `loki-exp2-data/l2/astcfg.json`.

**H14c (the score ranks references above recovered RTL).** For each Loki variant, the share of
designs with DL(reference) < DL(candidate). Supported: >= 0.90 for every one of the four `design.v`
variants and for both L0 `netlist.v` variants. Not supported: < 0.70 for at least three of the six.
Otherwise inconclusive. (Reachable: very small references with a longer ref than the netlist are
possible; the candidate is then shorter.)

**H14d (the score tracks round-2 similarity).** Pooled Spearman correlation rho between log ratio
and AST similarity over the (design, variant) pairs of the four `design.v` variants with AST
similarity available (designs pyverilog parses), and the partial rho controlling for log token
count of the candidate (Spearman correlation of the rank residuals). Supported: rho <= -0.30 and
partial rho <= -0.15 with p < 0.05 (two-sided, scipy). Not supported: rho > -0.15. Otherwise
inconclusive. Reported as well: the same for CFG similarity.

The ceiling statement (per kind and floor): the minimum of the Bayes ceiling (signature
classifier) and the style-recovery ceiling of the family that produces the kind, reported as a
table, not a hypothesis.

## Outputs

`corpus.csv`, `corpus_report.csv`, `l12b_*.csv`, `l12c_*.csv`, `l13_*.csv`, `l14_*.csv`,
`r4_status.csv` (the decisions), `paper_tables.py` -> `docs/paper/round4-tables.tex`,
`round4-log.tex` (`\rfs...` macros). CSVs and generated `.tex` regenerate byte for byte (sorted
iteration, fixed seeds, no timestamps).

## Rule additions

Entry 2026-10-25-a (written after the corpus generator and the matcher code existed, before any
corpus build finished and before any dictionary, detector or GNN number was computed; the only
matcher run so far is a smoke test on the 24 train / 6 test pilot designs, whose output is not
kept). None of the thresholds, margins or definitions of the hypotheses changes. The Stage-0 text
above is not edited; the three points below add variants, and the paper reports the hypotheses
under each.

1. Leaf limit. The Stage-0 cone rule limits cuts to 4 leaves. A LUT with more than 4 inputs has no
   cut of at most 4 leaves that contains the LUT itself, so at f2 the cone class of such a cell is a
   placeholder ("wide"). Variant `V1` raises the limit to 6 (exact NPN canonical form for up to 4
   support inputs, a cofactor-sorted semi-canonical form for 5 and 6 inputs; two NPN-equivalent
   functions with symmetric cofactors may get different classes, which only splits a class).
2. Grouping. The Stage-0 rule never lets a clock pin join cells, so plain registers (no enable or
   reset, so no shared control net) stay single-bit candidates. Grouping `G2` lets a shared clock
   net join equal-signature cells for the storage kinds ff_en, ff_srst, register, counter, fsm.
3. Variants: `V0` = the Stage-0 rule as written (4 leaves, clock never joins); `V1` = 6 leaves,
   clock never joins; `V2` = 6 leaves, G2. The radius r is selected per floor and variant. H12b and
   H12b2 are evaluated for V0, V1 and V2; a status is reported for each. Floor stability is
   reported for V0 and V1.

Implementation notes (no rule changes): the register template got a second parameter `rv` (reset
value 0 or all ones) because plain registers produced duplicate text and the family fell to 60
train designs; the corpus is 1,200 designs (840 train, 120 iid, 240 ood). The mux twin set has 4
styles per base (`ternary`, `ifelse`, `case`, `index`; `casez` needs the priority kind), so the
twin set is 396 designs, not 408 (pilot build of the pipeline: 60 of 60 designs).
