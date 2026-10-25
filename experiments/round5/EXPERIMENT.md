# Loki round 5: the word-first detector

Protocol written 2026-10-25, before the word-first detector was run on any evaluation design. This
file is committed and pushed first (Stage 0); its commit SHA is the rule-provenance SHA quoted in
the paper. A later change to a rule is a dated entry in "Rule additions" at the end that keeps the
old rule; the paper reports the result under both rules. Post-data analyses are dated, labelled
exploratory entries and never change a status.

Purpose chain (hub `docs/purpose.md`): Loki L2 (low-level netlist back to behavioural, word-level
HDL), question **L Q2.4**: can words, control nets and FSMs be found first, and the rest built
around them? The measure is understanding of what is recoverable (candidate precision, recall and
word tiling against the Odin III ground truth), not area, speed or power directly. L Q3.1 (the L15
loss audit: which pass loses each construct) is NOT this round: it waits for the Odin III D14
provenance export. The RQ prefix of this round is L16 (L15 stays reserved for the loss audit).

## Questions

- RQ-L16a: do word-first candidates tile the GT words where the round-2 detectors' candidates do
  not (round 3: H9b 0.065)?
- RQ-L16b: does grouping flip-flops by shared clock, enable and reset recover the enabled words
  (round 2: `ff_en` 732 candidates, 1 correct)?
- RQ-L16c: does deciding `eq_const` at word level (the cone's support is a word) beat the per-bit
  detector (round 2: 279 candidates, 1 correct)?
- RQ-L16d: does the FSM -> decoder -> control chain become complete more often (round 3: 5/89 on
  the 150 VerilogEval designs)?
- RQ-L16e: do words grown from register words along isomorphic bit-slices, across carry chains,
  reach the datapath constructs that I/O-port propagation did not (round 3: 0.095 within two hops),
  and is that more than a size-matched null reaches?
- RQ-L16f: on big designs, does repetition (repeat groups) give real evidence for the words, against
  a shuffled-group null?

## What the rules were informed by

Known before this file: round-2 counts (candidates per kind, calibrated runs commit almost
nothing); round-3 (loki main b15c079): wrong candidates sit inside real constructs but do not tile
the words (H9b 0.065 on the primary set P), `ff_en` candidates are correct per-bit slices (the miss
is grouping), `eq_const` is a detector problem, I/O-port propagation reaches 0.095 of the datapath
constructs within two hops, 5 of 89 chains complete on the 150 VerilogEval designs; round 4 (loki
main 919d1c2): a signature dictionary mined from synthetic idioms does not transfer (H12b 0/7
kinds), big designs are mostly repeated structure (H13a 0.928 of words in a repeat group, f3), the
style-recovery ceiling is 0.500 at f3. GT counts of the evaluation sets (instances of at least two
cells per kind, from `words.json`, read before this file was written to fix the n of each
hypothesis): micro f2 (68 designs) adder 52, subtractor 18, comparator 112, eq_const 101, mux 41,
register 94, ff_srst 18, ff_en 4; VerilogEval held-out f2 (33 designs) comparator 535, eq_const
529, register 146, ff_en 130, mux 21, adder 7, ff_srst 12, fsm 4; corpus iid f2 (120): register
163, ff_srst 140, ff_en 78, fsm 20; corpus ood f2 (240): register 304, ff_srst 174, ff_en 171,
fsm 40. GT chains (round-3 definition, `l11_chain.analyse`): micro 12, VerilogEval held-out 10,
corpus 0. No word-first detector number of any kind existed before this file.

## Data and environment

Odin III 1.1.0 (ABI 6), Loki main 919d1c2 plus this branch, Wyrd venv of `work/loki-f3-exp`, 12
cores, 23 GB VM, memory use kept under 60%. Read-only reuse: micro dataset
`work/loki-rename-exp/dataset-rebuild` (68 designs at f2 and f1-k6, 65 at f3), VerilogEval L0
dataset `work/loki-veval-exp/dataset` (150 designs; manifest split 117 train / 33 test), the
round-4 corpus `work/loki-exp4-data/corpus` (1,200 designs; split train 840, iid 120, ood 240 by
`corpus.csv`), the round-4 big builds `work/loki-exp4-data/big/<design>/dataset`, round-2 runs
`work/loki-exp2-data`, round-3 runs `work/loki-exp3-data`, round-4 detector runs
`work/loki-exp4-data/runs/{N,C}-f2`. New data under `work/loki-exp5-data/` (not in git).

### Evaluation sets (fixed here)

| set | designs | floor | notes |
|---|---|---|---|
| MI | the micro dataset | f2 (f3, f1-k6 reported) | 68 at f2; designs without a run in every compared arm drop out of that comparison, n is reported |
| VT | the 33 VerilogEval test designs of the manifest split | f2 (f3 reported) | the held-out set of round 4; n shrinks to the designs whose f2 floor is ok and whose runs finish |
| CI | corpus iid test (120 generated, those with an ok f2) | f2 | synthetic, in the train region |
| CO | corpus ood test (240 generated, those with an ok f2) | f2 | synthetic, unseen parameter regions |
| BIG | the 13 round-4 big designs with an ok f2 floor (stereovision3, sha, mkPktMerge, blob_merge, stereovision2, spree, boundtop, raygentop, stereovision1, stereovision0, or1200, mkSMAdapter4B, mkDelayWorker32B) | f2 | smallest f2 graph first; timeout 1800 s per run; a design that times out is recorded and left out |

E_real = MI + VT. E_all = MI + VT + CI + CO.

Development data: **only the corpus train split at f2 and f3** (840 designs, of which a fixed
prefix by name, at most 200 designs, is used for any one iteration). The micro designs, the
VerilogEval designs (all 150, not only the held-out 33), the corpus test splits and the big designs
are not opened by the detector code, its tests, or any development script before the Stage-2 run.
Unit-test fixtures are hand-written netlists. The detector has no fitted parameter: every
threshold is a stated agent default (Stage 1, logged in the paper).

## Stage 1: the detector (not a rule, a description)

Two detectors are added to `loki/re/detectors/` and are opt-in (named in `--detectors`; the default
detector list of `loki re` is unchanged, so every earlier run and calibration reproduces):

- `wordfirst` (runs first). Register words: flip-flops with a clock grouped by shared enable net and
  reset net (the enable and reset of `ff_pattern`'s D-cone analysis) and reset value; control triples
  shared by more flip-flops than 32 are split by the signature of the Q readers; plain flip-flops
  (no enable, no reset) join through the D-driver word or the Q-reader word. Datapath words:
  per-bit cells with an equal NPN class (exact, up to 6 inputs) and a shared control net at the same
  pin role (pin roles are cofactor-count signatures), joined by union-find; carry chains: a
  sum cell (xor3 class) and a carry cell (maj3 class) on one input triple make a full-adder bit,
  and the carry net of bit i being an input of bit i+1 joins the bits (the carry net joins, it does
  not break). Control nets: a net that drives the same pin role on every bit of a word labels the
  word. FSMs: a register word with a feedback path through its own D cone plus at least two
  decoders (word-level `eq_const`) reading it. `eq_const` at word level: a cone whose support is a
  subset of one word's bits (at least two) and whose function has exactly one satisfying (or one
  falsifying) assignment. Propagation: from register and mux words, the readers (forward) and
  drivers (backward) that form isomorphic slices (same cell class and pin) of at least
  max(2, ceil(0.75 k)) bits become new words, across carry chains. Words of no scored kind are
  emitted as `bus` hypotheses.
- `wordgroup` (runs last): links the per-bit hypotheses (`ff_en`, `ff_srst`, `mux_bit`) that lie
  inside a word-first word as its children, and groups per-bit hypotheses that share an enable or
  select net into word hypotheses.

Outputs are ordinary `Candidate`s with claims where the claims table has an operation (`add`,
`sub`, `add_cin`, `eq_const`, `ne_const`, `mux2`), so the prover, the commit step, `loki re`'s
reports, the scorers and the Verilog writer work unchanged. No LLM call. The module and CLI names
are in `docs/user/wordfirst.md`.

## Stage 2: arms, metrics, definitions

Arms (all `loki re --floor <F> --calib none --features none`-style runs, uncalibrated, a 900 s
timeout except BIG): **R2N / R2C** round-2 detectors, uncalibrated / calibrated (existing runs: MI
`M2N`/`M2C`, VT `V2N`/`V2C` restricted to the 33, CI and CO the round-4 `N-f2`/`C-f2` runs; f3:
`M3N`/`M3C`/`V3N`/`V3C`; f1-k6: `M1N`); **W** `--detectors wordfirst`; **WB** `--detectors
wordfirst,hard,ff_pattern,mux,arith,seqfn,fsm,bus,unit,role,wordgroup`. `--features all` (the
default) is used for MI, VT, CI, CO; BIG uses `--features none` for time. Baseline of a kind is the
better of R2N and R2C by pooled F1 on the evaluated set (conservative: the choice favours the
baseline). Run time per run is recorded and tabulated smallest design first.

Scoring is the round-2 scorer unchanged (`loki.score.metrics.construct_scores` through
`score_run`, `score_p` 0.5, GT `derive_instances`). Counted candidates are those of `Pred.counted(0.5)`
of the construct kinds of `SCORED_TYPES` without the hard kinds. Precision, recall and F1 are micro
sums per kind over designs; per-design F1_i = 2 matched_i / (counted_i + GT_i). `K_dict` = {ff_en,
ff_srst, register, adder, subtractor, comparator, eq_const, mux, mux_tree, counter, fsm}.

**Tiling.** The round-3 definitions: the families of `experiments/round4/l12b_overlap.py`; a
fragment of a GT instance g is a counted candidate of the family of g's type with containment in g
at least 0.8; g is covered when the union of its fragments covers at least 0.8 of g; q = covered /
instances over GT instances with at least two cells, one count per (instance, kind of `K_dict`
whose scored types contain its type). Per-design q_i over the designs with at least one instance.
Null tiling q_null: every counted WB candidate is replaced by a uniformly random cell set of the
same size, drawn from the non-I/O non-constant cells of the same design (seed = sha256 of the
design name and draw index, 5 draws, mean).

**Chains.** Round-3 definitions of `experiments/round3/l11_chain.py` (feedback register, decoder,
sink; a chain is complete when all three elements are proposed by a counted candidate of any kind
with J >= 0.5 to the element's footprint, the register as the derived register when its width is
at least 2).

**Seeding.** GT constructs counted: those of `experiments/round3` `L10` (width >= 2 and at least 2
cells; datapath = register, mux, mux_tree, adder, subtractor, comparator, counter; control =
eq_const, fsm). A construct g is seeded by a word Y when |Y & g| >= 2 and |Y & g| / |Y| >= 0.5.
The words are the counted scored-kind candidates plus the live `bus` hypotheses (status not
rejected). D = seeded share of the datapath constructs pooled over E_real, C = the same for
control. Null D_null: each word replaced by a random cell set of the same size and the same
multiset of cell kinds (lut / ff / hard) from the same design, 5 draws, seed as above.

**Repeat groups (BIG).** Key of a counted W candidate = (kind, number of cells, hash of the
footprint-induced subgraph by 2-round colour refinement over (cell kind, cell type, LUT table)),
as in `experiments/round4/l13_measure.py`. A group is the candidates of one design with an equal
key; the candidate has repetition evidence when its group has at least 2 members. F = keep only the
candidates with evidence. Null: per design and kind, the evidence flags are permuted over the
candidates of that kind (the number kept is preserved), 1,000 draws, `random.Random` seeded by
sha256 of the design name; F1_null is the pooled F1 of each draw.

## Hypotheses and numeric decision rules

Statistics: one-sided paired Wilcoxon signed-rank test (`scipy.stats.wilcoxon`, zero differences
dropped, `alternative="greater"`, alpha 0.05), exact one-sided binomial sign test
(`scipy.stats.binomtest`, alpha 0.05) for chains. No multiplicity correction (six hypotheses
with distinct data). A hypothesis whose test has fewer than 8 non-zero paired differences (or fewer
than 8 discordant chains for H16d) is `inconclusive` on the test arm; the rule says so.

**H16a (word tiling beats the detectors on held-out real designs).** On VT at f2, arm WB against
the baseline arm (R2N or R2C, whichever has the higher pooled q): D_q = q(WB) - q(baseline) pooled
over instances. Supported: D_q >= 0.15, q(WB) - q_null(WB) >= 0.10, and the Wilcoxon test on the
per-design q_i (WB minus baseline, designs with an instance) gives p < 0.05. Not supported: D_q <
0.05. Otherwise inconclusive. Also reported: arm W, MI, CI, CO, per kind. Reachability: the
round-3 pooled value of the baseline is 0.065 so D_q >= 0.15 needs q(WB) >= 0.215; VT holds
roughly 1,200 instances of the K_dict kinds, so 0.05 is about 60 instances: all three outcomes are
reachable.

**H16b (word grouping recovers the enabled words).** `ff_en` on E_all at f2: arm WB against the
better of R2N and R2C. Let R and F1 be the pooled recall and F1 of the kind. Supported: R(WB) - R(base)
>= 0.20, F1(WB) - F1(base) >= 0.10, and the Wilcoxon test on the per-design F1_i over the
designs with `ff_en` GT (about 113: 5 real, 108 synthetic) gives p < 0.05. Not supported: R(WB) -
R(base) < 0.05. Otherwise inconclusive. Reported: per set, arm W, ff_srst and register the same
way. Reachability: the baseline recall is near 0 (1 of 732 candidates correct in round 2), so a
gain of 0.20 means at least 20% of about 383 GT words; the not-supported arm is word grouping
failing to separate words (it merges neighbours).

**H16c (word-level eq_const beats per-bit eq_const).** `eq_const` on E_real at f2: arm WB against
the better of R2N and R2C. Supported: F1(WB) - F1(base) >= 0.10 and the Wilcoxon test on the per-design
F1_i over the designs with `eq_const` GT (24 designs: 14 micro, 10 VT) gives p < 0.05. Not
supported: F1(WB) - F1(base) < 0.03. Otherwise inconclusive. Reported: arm W, CI, CO, per set.
Reachability: round-2 eq_const F1 on these sets is near 0 (279 candidates, 1 correct, P set), so
0.10 is about 5 percent of 630 GT words.

**H16d (the chain is complete more often).** On E_real at f2 (22 GT chains), arm WB against R2N
(the round-3 arm): chains complete C(WB) and C(R2N). Supported: C(WB) - C(R2N) >= 5 and the
sign test over the discordant chains (complete in WB only vs complete in R2N only) gives p < 0.05.
Not supported: C(WB) - C(R2N) <= 1. Otherwise inconclusive. Reported: the three element-level
proposal rates, kind-correct rates, FSM recovery (GT `fsm` instances matched by a counted `fsm`
candidate, F1 of kind `fsm`), arm W, and R2C. Round-3 context: 5 of 89 on the 150 VerilogEval
designs. Reachability: 22 chains; the baseline can complete 0 to a few, the gain 5 is 23% of the
chains.

**H16e (words grown from registers reach the datapath, beyond a null).** On E_real at f2, arm W:
D = seeded share of the datapath constructs and D_null (Definitions). Supported: D >= 0.50 and D -
D_null >= 0.25. Not supported: D < 0.25 or D - D_null < 0.10. Otherwise inconclusive. Reported: C
and C_null (control), per kind, arm WB, R2N for comparison, the round-3 value 0.095 (hop <= 2 from
the I/O words, relaxed rule). Reachability: D_null for random words of the same size inside a design
whose GT instances partition every non-I/O cell is not small, which is why the rule needs the gap
and not only the level.

**H16f (repetition is real evidence on big designs).** On BIG at f2, arm W: F1 of all counted
candidates F1_all, F1 of the candidates with repetition evidence F1_F, and the null. Supported:
F1_F - F1_all >= 0.05 and the share of null draws with F1 >= F1_F is <= 0.05. Not supported: F1_F -
F1_all < 0.01 or that share > 0.20. Otherwise inconclusive. If fewer than 3 BIG designs finish,
inconclusive. Reported: per-design and per-kind recall with and without the evidence, arm WB where
it finishes inside 1800 s, the run time of every design.

Also reported without a status: the f3 floor (MI, VT) and f1-k6 (MI) for W and WB against the
f3 and f1 baselines; run times per design; the counts of candidates per kind; the paired
differences with intervals (bootstrap over designs, B = 2000, `random.Random(5)`).

## Gates

ruff and `mypy --strict` clean per CLAUDE.md; the unittest suite passes except the known stale
`test_4b_real_micros_beats_wl` (confirmed by name); new unit tests for the detector. Generated
CSVs and the generated .tex regenerate byte-identically. Tectonic builds `docs/paper/loki.tex`
clean from the worktree and from a `git archive` copy under `/tmp/claude-1000/le5-*`; the tracked
PDF is rebuilt. No `/home/jamiespa` in committed files.

## Outputs

`experiments/round5/`: `r5lib.py` (paths, run sets, loaders), `run_arms.py` (W and WB runs),
`l16_tiling.py`, `l16_kinds.py`, `l16_chain.py`, `l16_seed.py`, `l16_big.py`, `decide.py`
(`r5_status.csv`), `paper_tables.py` (`docs/paper/round5-tables.tex`, `round5-log.tex`, macros
`\rfv...`), CSVs `l16_*.csv`. Sorted iteration, fixed seeds, no timestamps.

## Rule additions

(none yet)

## Reproduce

(filled in when the scripts exist)
