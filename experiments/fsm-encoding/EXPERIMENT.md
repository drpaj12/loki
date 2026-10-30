# Loki FSM encoding experiment: does speculating the target's encoding recover more FSMs?

Plan written 2026-10-30, before the runs. This file is committed and pushed first. A later change
is a dated entry under "Amendments"; the old text stays. Results go in a dated section at the end.

## Plain-English summary

When Odin III maps a design, its `fsm` pass can rewrite the state register: with `auto` it makes
a one-hot register below 32 states (same rule as Yosys fsm_recode), so the FSM that Loki sees in
a netlist may not have the encoding the designer wrote. Loki's FSM detector today walks the state
space from state 0, which is wrong for one-hot (state 0 is not a legal one-hot code), and one of
its evidence terms (`fsm_detect` marked, +4.61) cannot fire on a gate netlist. This experiment asks
two things. First, how much does the target transformation fool the current detector (stage 1,
measurement only). Second, does Loki recover more when it speculates which transformation was
applied, i.e. when it has competing kinds `fsm_onehot` and `fsm_binary` with their own features
(stage 2 and 3). Stage 1 is committed before any detector change.

Purpose chain (hub `docs/purpose.md`): Loki L3 (say why a construct is not recovered: which step
fooled the unmapping) and L Q3.3 (hub #62: how a target-specific transformation changes a
construct's netlist footprint, and does Loki recover more when it speculates the transformation).
Odin III O Q2.4 is the other side (the target allows one-hot recoding). Measures: FSM recall and
precision, accuracy of the encoding call, states recovered, calibration (ECE) of the fsm
confidences. These are structure-recovery measures; area/speed/power are not touched.

## Corpus

Round 4 generator (`experiments/round4/gen`, tag `r4`, deterministic): the 100 `fsm` designs
(3 to 16 states; binary, one-hot or gray HDL encoding; Moore or Mealy; 1 to 3 inputs; case or
if/else) as positives. Negatives (no FSM in the HDL, but flip-flop groups that the detector could
call an FSM): 20 each of `counter`, `shifter`, `register`, `pipeline`, `regfile` (family indices
70 to 89: the iid split plus the first 10 ood designs). `dpfsm` is excluded (an FSM with a
datapath: truth is ambiguous). Total 200 designs. The VerilogEval FSM problems are not in the
measured population: their truth (states, transitions) is not available without hand work.

## Arms (Odin III synthesis, `--vtr-compat --nolatches`, then `lower; abc; dfflibmap/--lut 6`)

The front script is the L0 front with the `fsm` step varied (set from the experiment driver; no
change to Loki or Odin III):
- `onehot`: `proc; fsm -encoding one-hot; opt; flatten; opt -full; wreduce`
- `binary`: `proc; fsm -encoding binary; opt; flatten; opt -full; wreduce`
- `none`: `proc; opt; flatten; opt -full; wreduce` (the HDL's own encoding survives)

Floors: f3 (cmos6 gates, as in the hint runs) and f2 (LUT6, k6_frac_N10_frac_chain_mem32K_40nm).
So 200 designs x 3 arms x 2 floors = 1200 builds. A build that Odin III skips or fails is
excluded for that cell and listed.

## Ground truth per FSM design and arm

- State register: the flip-flops whose `key.json` name starts with `state.` (the generated
  register is always named `state`; the arms keep the name, checked).
- States and transitions: the reachable states from S0 and the distinct (source, destination)
  state pairs, parsed from the generated Verilog text (arm independent). Checked against the
  Odin III log (`fsm: extracting ... N states`, transition table) in the two recoded arms; a
  disagreement is reported, and the Odin III log value is used for that design.
- Encoding after the target transformation: the Odin III log line `fsm: recoding '<x>' with
  <enc> encoding (...)` in the recoded arms (`one-hot` or `binary`); in the `none` arm, and for a
  design whose FSM Odin III did not extract, the HDL encoding (`onehot` -> one-hot, `binary` ->
  binary, `gray` -> other). Odin III is not changed; the log is read through the Python capture.

## Measures

For a netlist, a hypothesis is counted when its status is not rejected and `p_comp >= 0.5` (the
`score_p` of `loki.score`). An FSM-kind hypothesis (`fsm`, and in stage 3 `fsm_onehot`,
`fsm_binary`) matches the truth when the Jaccard index of its flip-flop set with the truth
flip-flop set is >= 0.5.
- Recall (per design): 1 when some counted FSM-kind hypothesis matches. Reported as a fraction
  of the positives.
- Precision (pooled): matching counted FSM-kind hypotheses over all counted FSM-kind hypotheses,
  over positives and negatives. False-positive rate on negatives reported too.
- Encoding accuracy: fraction of matched designs whose predicted encoding equals the truth. The
  current detector makes no encoding call (reported n/a); the new detector's call is
  the kind (`fsm_onehot` / `fsm_binary`; `fsm` = other/unknown).
- States recovered: of the positives with a counted match, the fraction whose reported state
  count equals the truth; mean of reported over true.
- Calibration: ECE (10 equal-width bins over p_comp) of all FSM-kind hypotheses against the
  match label, per arm and floor.
- Runs use `--calib none` (the defaults in `bayes.py`), the detector list of the hint runs
  (`wordfirst,hard,ff_pattern,mux,arith,seqfn,fsm,bus,unit,role,wordgroup`), seed 1. The shipped
  `calib/f2.json` and `calib/f3.json` are not used: they were fitted before the new kinds exist
  and a refit on this population would be circular. New log-odds in stage 2 are hand-set,
  written down in the commit, and not fitted on the measured designs.

## Rule for the verdicts (stage 3)

Same designs, same arms, same floors: paired by design. Per cell (3 arms x 2 floors) and per
measure (recall; state-count correct) the difference d = new - old per positive design takes
values in {-1, 0, 1}. 95 % percentile bootstrap CI of mean(d) over designs (10000 resamples, seed
20261030); two-sided bootstrap p; Holm over the 12 tests (6 cells x 2 measures). A cell is
USEFUL only if Holm p < 0.05 and the CI excludes 0 on the positive side. Guard: the pooled
precision of the new detector must not fall more than 0.05 below the old one in the cell, else
the cell is NOT USEFUL regardless of recall. Negative significant difference: HARMFUL. Anything
else: NOT USEFUL (no detectable effect). The encoding-accuracy and ECE results are descriptive
(Wilson CI for the accuracy); they get no verdict. Failed or null hypotheses are dismissed to the
log in the results section, not hidden.

## Stages

0. This plan (commit, push).
1. Measurement with the current detector: `run_stage1.py`, tables in `results/stage1/`. Commit and
   push before any detector change.
2. Detector: `fsm_onehot` and `fsm_binary` kinds, features, hint text, tests.
3. Re-run, same table, verdicts.
4. Results section, register rows, paper paragraph, PR (not merged).

Outputs live outside the worktree (`work/fsmenc-out`); only scripts, small CSVs and this file are
committed.

## Amendments

- 2026-10-30 (before stage 1 scoring): the truth for states and transitions is the exact
  reachable set computed from the generated Verilog (first matching `x == c` branch, else the
  default, for every input value), in every arm. The Odin III `extracting` line counts statically
  dead states (`else` after all input values are covered) and the recode line sometimes keeps
  them (15 of 100 designs in the one-hot arm differ, 6 in the binary arm); the optimiser removes
  the dead state's flip-flop, so the netlist holds the exact reachable set. The Odin III log
  value is kept in `truth.odin_states` of the scoring and is not used. The encoding is read from
  the `mapping auto encoding to` line (it covers "existing encoding is already a packed binary
  encoding", where no recode line is printed). All 600 builds (200 designs x 3 arms, f3 and f2)
  ended `ok`.

## Stage 1 results (2026-10-30): the current detector (Loki at 414e159)

Plain English: the target's recoding hides most FSMs from the current detector. The detector
almost always proposes the state register as an FSM (93 to 99 % of the designs have a
hypothesis on the right flip-flops), but it counts it (`p_comp >= 0.5`) in only 13 % of the
designs in the one-hot arm on gates, against 33 % for the HDL's own encoding. The FSM
hypothesis is mostly outvoted by competing hypotheses on the same cells. The detector makes no
encoding call, and when it counts an FSM the reported state count is right in about 60 to 90 %
of the cases (one-hot on gates: 3 of 13).

`results/stage1/summary.csv` (100 positives, 100 negatives per cell; counted = committed, or live
with `p_comp >= 0.5`; defaults calibration; truth as above):

| arm | floor | recall | proposed at any p | precision | negatives with a counted FSM | states exact among matched | ECE |
| --- | --- | --- | --- | --- | --- | --- | --- |
| one-hot | f3 | 0.13 | 0.99 | 0.700 (14/20) | 4 | 3/13 | 0.678 |
| one-hot | f2 | 0.35 | 0.99 | 0.867 (39/45) | 5 | 23/35 | 0.647 |
| binary | f3 | 0.35 | 0.93 | 0.917 (44/48) | 4 | 24/35 | 0.739 |
| binary | f2 | 0.49 | 0.93 | 0.915 (54/59) | 5 | 43/49 | 0.588 |
| none (HDL) | f3 | 0.33 | 0.95 | 0.907 (39/43) | 4 | 20/33 | 0.714 |
| none (HDL) | f2 | 0.51 | 0.95 | 0.919 (57/62) | 5 | 39/51 | 0.595 |

Encoding accuracy: n/a (the current detector makes no encoding call). Per-design rows:
`results/stage1/per_design.csv`. Scripts: `fsmlib.py`, `build_arms.py`, `run_re.py`,
`score_fsm.py`. Run data: `work/fsmenc-out` (outside the repo).

## Stage 2-4 paused 2026-10-30 by the controller

Stage 2-4 paused 2026-10-30 by the controller: loki/intent (PR #62) FSM claims to be measured on
this corpus instead. No PR is opened from this branch. Check made in stage 1: the `fsm_detect`
feature (+4.61) never fired, in 0 of 600 stage-1 FSM runs (every report says `not-applicable` on
gate and LUT netlists). A draft detector (kinds `fsm_onehot`, `fsm_binary`, a one-hot table and
unit tests) was started in the working tree and is not committed.

## Amendment 2026-10-30 (before the v2 runs): stages 2-4 replaced by "v2 measurement"

The controller paused stages 2-4 (no detector change). Replacement: measure the v2 FSM claims of
`loki re --intent` (`loki/intent`, merged in loki #62) on the same corpus, the same 600 builds
(200 designs x 3 arms x 2 floors, build outputs reused, no Odin III change), the same truth, and the
same scorer extended for v2. Branch `exp/fsm2-onehot` (from `exp/fsm-encoding`, merged with
`origin/main`).

Peter's hypothesis, 2026-10-30, verbatim: "FSM guesses by Loki are simply is this a feedback path
... so the feedback path is a level 1 guess of FSM - then the question of what is between the
feedback path ... if the FSM is one-hot encoded as it might be when targetting an FPGA, still
there's how the one-hotness of STATE bits is turned on by other STATE bits."
Testable form: "Reading how state bits turn each other on lets Loki recover one-hot FSMs about as
well as binary ones."

Run: `loki.re.main <netlist> --floor <f> --calib none --detectors <stage 1 list> --seed 1 --intent
--intent-calib calib/intent-f3.json` (the shipped table, fitted before this experiment, constant
p = 0.95 for `fsm`; used for both floors; no refit on this population). Outputs in
`work/fsmenc-out/v2`.

Scoring (script `score_v2.py`):
- A v2 FSM claim is a claim of `kind == "fsm"`, `source == "seq"` in `intent.json`, counted when its
  status is not rejected and `p >= 0.5`. It matches the truth when the Jaccard index of its state
  nets `facts.q` with the truth state nets (`key.json` nets named `state[i]`) is >= 0.5.
- Recall (positives with a counted matching claim), precision (matching counted claims over all
  counted FSM claims, positives and negatives), encoding accuracy (`params.encoding` one-hot /
  binary / other against the truth encoding, among matched designs, Wilson CI), states exact
  (`params.states` equals the reachable-state count), transitions exact (the claim's transition
  graph is isomorphic to the truth transition graph, with the claim's `start` state mapped to S0;
  count-only agreement of distinct (src, dst) pairs also reported).
- Stage 1 numbers are rescored with the same code path for the paired comparison (stage 1 `fsm`
  hypotheses with the stage 1 rule, unchanged).

Rule: paired by design. d = v2 - stage 1 recall per positive design in each of the 6 cells
(arm x floor), values in {-1, 0, 1}; 95 % percentile bootstrap CI over designs (10000 resamples,
seed 20261030), two-sided bootstrap p, Holm over the 6 tests. A cell where v2 is better needs Holm
p < 0.05 and a CI above 0; the pooled precision of v2 must not fall more than 0.05 below stage 1
in that cell. Hypothesis test: for v2, per floor and pooled over floors, the paired difference
recall(one-hot) - recall(binary) over the same 100 designs, bootstrap CI as above. "About as well" =
the CI lies inside +-0.10: SUPPORTED. Otherwise NOT SUPPORTED. Failed outcomes are reported in the
results section, not hidden.
