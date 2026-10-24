# Loki round 2: f3 vocabulary, head-to-head, evidence ablation, graph sandwich, metric

Run 2026-10-24. Loki `exp/round2` (off origin/main bc83f19), Odin III 1.1.0 (ABI 6,
`odin3/build/release/libodin3.so`, checkout 0b8a0233, slang adapter `libodin3_slang.so`), Python
3.12.3, numpy 2.5.4, scipy 1.18.1, pyverilog 1.3.0, 12 cores, 23 GB VM (peak use of these runs
below 4 GB). Data lives in `work/loki-exp2-data` (not git); this directory holds the scripts and
the summary CSVs, which regenerate byte for byte from the data (`paper_tables.py` rewrites
`docs/paper/round2-tables.tex`). Every Odin III batch ran under `flock -x
/tmp/claude-1000/odin3-heavy.lock` (another lane runs VPR under the same lock). No LLM call of
any kind was made; the LLM figures are the round-1 Gate-Breaker replication
(`work/gatebreaker-exp2`) re-read, plus Odin III elaboration of its saved samples.

## Questions and decision rules

These are not pre-registered. The brief gave the questions but no numeric thresholds; the
thresholds below were set by the implementer during the round, and this file first appears in
commit 38b6f66, after the scripts and the CSVs. They are not time-stamped before the data. A
future round fixes its thresholds in a commit before running.

| RQ | hypothesis | supported when |
|---|---|---|
| L1 | f3 failure is vocabulary, not information: LUT6 re-mapping of the f3 gates recovers close to the f2 rate | micro-F1(LUT6-from-f3) >= 0.8 x micro-F1(native f2) on both the 15 test designs and all 65; not supported below 0.5 on both; else inconclusive |
| L2 | Loki's AST/CFG is below the LLM's on Q1/Q2 but does not fall Q1->Q4; final_equiv is 1.0 | f3-calib mean AST and CFG below the LLM's in Q1 and Q2 (common designs), Q4 mean >= Q1 mean - 0.05 for both, and 150/150 `equivalent`; not supported if Loki is not below the LLM; else inconclusive |
| L4 | one or two of npn/wl/l2/struct carry most of the calibrated performance | the two largest single-family drops in held-out micro-F1 sum to >= 0.8 of (full - priors-only), with full - priors-only >= 0.02; inconclusive if that gap is below 0.02 |
| L5a | bracket width correlates negatively with per-design F1 | Spearman <= -0.2 with p < 0.05 on the primary set (VerilogEval f2, uncalibrated) and the same sign on the calibrated rp 0.1 set; not supported at >= -0.1 |
| L5b | a cheap structural prefilter keeps recall and cuts prover calls | a rule that prunes >= 30% of the `cone_check` calls with zero lost `equivalent` verdicts (offline, no held-out data) |
| L7 | word-level operator F1 separates runs AST/CFG tie | a pair of conditions with mean |dAST| < 0.02 and |dCFG| < 0.02 whose operator type-F1 differs by >= 0.01, and a flatten control that moves AST and CFG by >= 0.04 with operator F1 unchanged |

L8 (LLM with reverse provenance) is deferred by Peter and not run.

## Result in one paragraph

Operator-recovery F1 (RQ-L7) is the one hypothesis the rules support. The LUT6 re-map of the f3
gate netlists (RQ-L1) recovers 14 constructs of 580 over the 65 designs against 16 for the native
f2 floor (micro-F1 ratio 0.87, in-sample: the 65 include the 52 designs the f2 calibration was
fitted on), but on the 15 held-out designs it is 2 against 4 (ratio 0.51), so
the rule gives inconclusive; the data are consistent with the vocabulary explanation but do not
show it; the gate netlist itself matched 0 of 116. On the 150 VerilogEval
designs (RQ-L2) Loki's f3 output has AST 0.763 / 0.460 and CFG 0.751 / 0.743 in Q1 / Q2 (common designs, n = 36 each) against
the language model's AST 0.894 / 0.761 and CFG 0.942 / 0.890 (every paired difference
significant); the AST falls from Q1 to Q4 (all designs, n = 38, 38, 32, 21: 0.754, 0.455, 0.605, 0.505) while the CFG stays flat,
and `final_equiv` is `equivalent` in 150 of 150 runs of every set, which proves equality with the
input netlist only (that netlist passes the official testbench in 128 of 150). The evidence
families (RQ-L4) add nothing over per-detector priors on 49 held-out designs (micro-F1 0.0038
full, 0.0051 priors only); the calibration fit itself sets the npn weight to 0. The bracket width
(RQ-L5) does not correlate with per-design F1 on the registered set (Spearman 0.087, p 0.417),
although it does on calibrated runs listing candidates from p 0.1 (-0.346, p 0.0008, exploratory),
and no structural rule prunes more than 6.7% of the 210 `cone_check` calls without losing a
proved construct.

## Protocol and results

All numbers below are in the CSVs of this directory; `paper_tables.py` turns them into
`docs/paper/round2-tables.tex` and `round2-log.tex`, whose `\rt...` macros the paper cites.

### RQ-L1: LUT6 re-map of the f3 netlist

`l1_lutmap.py` (one process, Odin III Python API): per design `read_blif <f3 netlist.blif>; abc
--lut 6; write_blif`, the script of the f2 floor's mapping step applied to the gate netlist. Odin
III drops `.cname` in `abc` and its BLIF-exchange provenance is `DERIVED` with no source cells, so
`blifmap.py` recovers the cover: bit-parallel simulation signatures (512 random vectors over the
primary inputs and flip-flop outputs, flip-flops identified by `.cname`) match each LUT output to
the f3 net of the same function; the cover of a LUT is the cone of that net back to the nets whose
signatures equal the LUT's input signatures; a flip-flop covers itself and the buffers that copy
its output. Of 8,712 LUTs, 2,000 (23.0%) implement a function that is no f3 net (ABC
resynthesised); they take the gates of their consumers' covers whose primary-input support lies
inside their own, minus what the LUTs below them cover, and 153 are left with an empty cover
(`l1_cover.csv`). `l1_run.py` runs `loki re --floor f2` on the LUT netlist (`.cname L<k>` added),
translates the overlay and report cell lists to gate cnames and the bus nets through the LUT
output map, and scores with `score_run` against the unchanged f3 floor. The comparison is the
native f2 floor of the same designs with the same calibration
(`experiments/rename-l2/calib/f2.json`, fitted on the 52 micro train designs; not refit),
calibrated and `--calib none`. Hard kinds (`hard_add`, `hard_mul`, `hard_mem`) share the word
types of `adder` and `mul` and need a hard cell; they are kept in `l1_kinds.csv` and left out of
the totals and averages.

| set | split | runs | counted | matched | GT | micro-F1 | macro-F1 |
|---|---|---|---|---|---|---|---|
| f3 gates, calibrated (f3 table) | test | 15 | 0 | 0 | 116 | 0.000 | 0.000 |
| LUT6 from f3, calibrated | test | 15 | 68 | 2 | 116 | 0.022 | 0.076 |
| native f2, calibrated | test | 15 | 72 | 4 | 116 | 0.043 | 0.153 |
| LUT6 from f3, calibrated | all | 65 | 92 | 14 | 580 | 0.042 | 0.062 |
| native f2, calibrated | all | 65 | 88 | 16 | 579 | 0.048 | 0.095 |
| LUT6 from f3, none | all | 65 | 921 | 31 | 580 | 0.041 | 0.049 |
| native f2, none | all | 65 | 930 | 32 | 579 | 0.042 | 0.070 |

Status: **inconclusive** by the rule (ratio 0.87 pooled and in-sample, since the 65 designs
include the 52 calibration fit designs; 0.51 on the 15-design test split, which has 2 and 4
matches). The vocabulary explanation is consistent with the data, not shown by them. The pooled matches fall on the same kinds (adders 6 against 7,
mux_bit 6 against 6). Caveats: the calibration is the f2 table, not refit on the LUT6-from-f3
netlists; GT counts differ by one (580 against 579); the cover is a functional reconstruction (23.0% of LUTs resynthesised), and it moves
Jaccard values.

### RQ-L7: operator-recovery F1

`opf1.py`. Key: the word cells of `words.json` of the floor (classes add, sub, mul, neg, eq, ne,
lt, le, gt, ge, mux ($mux, $pmux), reg (every flip-flop word); width = max(A_WIDTH, B_WIDTH),
WIDTH for mux and reg). Run: counted hypotheses (committed, or live with p_comp >= 0.5) mapped
by kind (adder, adder_cin, hard_add: add; subtractor: sub; hard_mul: mul; comparator and eq_const:
their `op`; mux: mux; register: reg of width |q|; `mux_bit`, `ff_en`, `ff_srst` as width 1
only when their cells lie in no counted `mux` or `register`). Score: multiset precision, recall
and F1, `type` (class only) and `tw` (class and width); location-free. `l7_rescore.py` rescored 16
run sets (rename-l2 f1-k6, f1-earch, f2; f3-recovery; the round-2 sets). LLM side
(`l2_llm_ops.py`): the 613 functionally correct round-1 samples elaborated with
`read_verilog --nolatches --vtr-compat` and the L0 front, 0 elaboration errors.

| condition (15 f3 test designs) | AST | CFG | ops recovered | type-F1 |
|---|---|---|---|---|
| L0-stop gate netlist | 0.4044 | 0.6468 | 0 | 0.0000 |
| L1 calibrated | 0.4044 | 0.6468 | 0 | 0.0000 |
| L1 uncalibrated | 0.4155 | 0.6394 | 1,161 | 0.0173 |
| L1 uncalibrated, flattened | 0.4576 | 0.6941 | 1,161 | 0.0173 |

Floors (type-F1, calibrated, pooled): f1-k6 0.349 and f2 0.070 over the 68 micro designs; f3 gates 0.000 over the 15 test designs.
Status: **supported**. Calibrated against uncalibrated L1 tie on AST (+0.0111) and CFG (-0.0075)
while type-F1 moves by 0.0173; the flatten control raises AST by 0.0422 and CFG by 0.0547 with
the operator F1 unchanged. Caveats: the separating level is small (the uncalibrated detectors
count mostly wrong constructs), and the unchanged operator F1 under flattening is by construction
(the metric reads the recovery record, AST and CFG read the text); the calibrated f3 run ties
with L0-stop on all three metrics (0.0), so there it does not separate.

### RQ-L2: head-to-head on the 150 VerilogEval designs

Calibrations fitted with `loki calibrate --split train` on the VerilogEval dataset (117 train
designs, f2 and f3; f3 took 70 minutes, one process). `loki re` on all 150 netlists (f2, f3) x
{calibrated, `--calib none`}: 600 runs, all `ok`, none timed out; plus 150 f2 runs with
`--rp-min-p 0.1` for RQ-L5. Output Verilog scored against `<Prob>_ref.sv` with the round-1 AST
(pyverilog depth 3) and CFG (odin3 probe, common width, sigma 0.5; skipped above 12,000 nodes)
for six variants (`l2_astcfg.py`): f3 and f2 L0 netlists, and `design.v` of the four runs. 21
references fail pyverilog (SystemVerilog), so 129 designs have an AST value; 6 f3 outputs
exceed the CFG limit (`l2_coverage.csv`). The LLM figures are `gatebreaker-exp2/data/results.json`
(per design means over correct samples; 36 Q1 and 37 Q2 designs, 73 in all).

| quartile | LLM AST | Loki f3 AST (common) | LLM CFG | Loki f3 CFG (common) | Loki f3 AST (all designs) |
|---|---|---|---|---|---|
| Q1 | 0.894 | 0.763 | 0.942 | 0.751 | 0.754 |
| Q2 | 0.761 | 0.460 | 0.890 | 0.743 | 0.455 |
| Q3 | -- | -- | -- | -- | 0.605 |
| Q4 | -- | -- | -- | -- | 0.505 |

(Loki f3 is the calibrated run. The comparison with the LLM and the decision rule use the
"common" rows of `l2_headtohead.csv` (Loki restricted to the designs both are scored on, n = 36
in Q1 and Q2). The "all designs" column is used only for the four-quartile trend: n = 38, 38,
32, 21 designs with an AST value for Q1 to Q4, 129 in all; its CFG is 0.750, 0.741, 0.750, 0.768.
The 21 references that fail to parse are excluded from every AST value.) Mean paired differences Loki minus LLM are in `l2_paired.csv` (Wilcoxon p < 1e-4 in every
f3-calibrated cell, < 0.003 for every variant). Operator type-F1 on the common Q1+Q2 designs: LLM 0.465 (precision 0.637,
recall 0.366), Loki f2 calibrated 0.081, f2 uncalibrated 0.074 (`l2_ops.csv`).

`final_equiv`: `equivalent` in 150 of 150 runs of each of the four sets (`l2_equiv.csv`). What
that proves: the flattened `design.v` is formally equal to the input netlist (`equiv-check`);
Loki's output is as correct as its input and no more. It does not prove correctness against the
reference RTL: the round-1 self-check finds the input netlist passes the official testbench in
128 of the 150 designs (inferred latches, asynchronous resets, `casez`). The calibrated f3 flow
commits 14 hypotheses in 7 designs, so its output is nearly the L0 netlist.

Status: **inconclusive** by the rule. Loki is below the LLM on AST and CFG in Q1 and Q2 (yes),
`final_equiv` is 150/150 (yes), and Q4 is not within 0.05 of Q1 (no: the AST falls 0.754 to
0.505; the CFG is flat). Caveats: Q3 and Q4 have no LLM figure (round 1 ran Q1 and Q2 only);
the AST is computed on the 129 designs pyverilog parses, the LLM's AST only on its correct samples.

### RQ-L4: evidence-family ablation

`l4_ablate.py`. Collect: the DEFAULTS flow on the f2 train designs of the micro dataset (52) and
VerilogEval (117), `design_data` per design. Fit: `loki.score.calibrate.fit` on the data with one
family stripped (its features removed from every prediction; for `wl` the node table is also
emptied) and its weight set to 0 in the file. Run: `loki re` on the 49 held-out designs (16
micro, 33 VerilogEval) per ablation (and `--calib none`), scored; macro-F1, micro-F1 with a 2,000
resample design bootstrap, ECE and the AUC of p_comp over live hypotheses. `loki re` emits no
`l2_` feature (feature occurrences in the train flow: struct 33,821, wl 1,480, npn 567, l2 0), so
that family is not applicable.

| calibration | counted | matched | micro-F1 | 95% interval | macro-F1 | ECE | AUC |
|---|---|---|---|---|---|---|---|
| defaults | 1,708 | 26 | 0.0159 | 0.0036-0.0873 | 0.113 | 0.841 | 0.437 |
| full | 10 | 3 | 0.0038 | 0.0000-0.0381 | 0.145 | 0.061 | 0.886 |
| without npn | 10 | 3 | 0.0038 | 0.0000-0.0381 | 0.145 | 0.061 | 0.886 |
| without wl | 13 | 3 | 0.0038 | 0.0000-0.0376 | 0.145 | 0.024 | 0.930 |
| without struct | 11 | 4 | 0.0051 | 0.0000-0.0496 | 0.163 | 0.056 | 0.884 |
| priors only | 14 | 4 | 0.0051 | 0.0000-0.0494 | 0.163 | 0.026 | 0.918 |

Status: **inconclusive** (full minus priors-only = -0.0013, below the 0.02 floor of the rule).
Fitted weights (`l4_weights.csv`): full npn 0.0, wl 0.5, struct 0.1: the fit itself zeroes npn and
shrinks the others, which is why removing a family changes nothing. Caveats: the held-out GT is
dominated by one design (`ve_Prob153_gshare`: about 1,300 of the 1,558 instances, 512 comparator and
510 eq_const) where nothing is matched; the AUC pools differ between rows (calibration rejects more
hypotheses), so it is not a like-for-like ranking comparison.

### RQ-L5: graph sandwich

`l5_sandwich.py`: must = cells of committed elements of `reverse-provenance.json`, may = must plus
candidate elements with p_comp >= `--rp-min-p`; width = candidate fraction of the cells. Per-design
F1 = 2 matched / (counted + gt) over designs with GT. H5a primary set: VerilogEval f2
uncalibrated (90 designs with GT). Soundness against the union of the scored GT footprints.

| set | designs with GT | Spearman width | p | Spearman must | must precision | must recall | may recall |
|---|---|---|---|---|---|---|---|
| f2 uncalibrated (primary) | 90 | 0.087 | 0.417 | 0.485 | 0.840 | 0.240 | 0.625 |
| f2 calibrated, rp 0.5 | 90 | -0.203 | 0.055 | 0.819 | 0.821 | 0.025 | 0.188 |
| f2 calibrated, rp 0.1 | 90 | -0.346 | 0.0008 | 0.819 | 0.821 | 0.025 | 0.447 |
| f3 uncalibrated | 90 | -0.124 | 0.243 | 0.168 | 0.792 | 0.347 | 0.727 |

H5a status: **not supported** on the registered primary set; the negative correlation on the
calibrated rp 0.1 run is post hoc (exploratory) and not part of the verdict. The committed
fraction correlates with F1 trivially (committed cells are the matches). H5b
(`l5_prefilter.py`): 210 `cone_check` calls across the round-2 runs (166 end `equivalent`) and
2,876 `truth_table` calls; exhaustive over (kind, feature, bin) rules of the features the
hypotheses carry, the largest rule with zero lost `equivalent` verdicts is `adder/out_reads=no`
with 14 calls (6.7%); status **not supported**. Caveat: the rule search is on the same data and
is an upper bound, not a measured saving; the soundness truth set holds scored word types only,
so a committed `bus` or `datapath_unit` outside them counts against must precision.

## Run counts

| item | count |
|---|---|
| LUT6 re-maps (Odin III) | 65 |
| `loki re` runs, RQ-L1 | 260 (65 designs x {LUT6, native} x {calibrated, none}) |
| `loki re` runs, RQ-L2 | 750 (150 x {f2, f3} x {calibrated, none} + 150 rp 0.1) |
| `loki re` runs, RQ-L4 | 294 (49 x 6) and 169 `design_data` collections |
| calibrations fitted | 2 (VerilogEval f2, f3) + 5 (ablations) |
| AST/CFG scorings | 150 designs x (reference + 6 variants) |
| LLM samples elaborated | 613 |
| LLM calls | 0 |

## Agent defaults and deviations

- RQ-L1 uses the micro-fit f2 calibration unchanged (no refit on LUT6-from-f3 netlists).
- Hard kinds are excluded from the totals and macro averages (shared word types).
- The cover reconstruction (signature matching, fill rule for resynthesised LUTs) is mine; the
  brief named only the Odin III script.
- RQ-L2 calibrations are fitted on the VerilogEval train split, not the repo's `calib/f2.json`.
- Operator F1 class and width definitions, and the de-duplication of bit-level hypotheses, are
  mine (above).
- RQ-L4 pools micro and VerilogEval f2 for fit and test; the `l2` family is not applicable.
- RQ-L5 primary set is the uncalibrated VerilogEval f2 run, chosen by the implementer
  (not time-stamped before the data); rp 0.1 is secondary.
- The odin3 CFG probe worktree no longer exists; `odin3_cfg.py` was extracted unchanged from odin3
  commit 77e975e5 (`git show`, the commit round 1 used) into the data directory.
- pyverilog writes `parsetab.py` and `parser.out` into its working directory; both were deleted.
- RQ-L5b is measured offline; no flag was added to `loki/re`.

## Data and commands

Data under `/home/jamiespa/odin3-ws/work/loki-exp2-data`: `l1/lut` (LUT netlists, `cover.json`),
`l1/runs`, `l2/calib`, `l2/runs`, `l2/astcfg.json`, `l2/llm_ops.json`, `l4/` (pickle, calibrations,
runs), `cfg-probe/`.

    export ODIN3_ROOT=/home/jamiespa/odin3-ws/odin3 ODIN3_LIB=$ODIN3_ROOT/build/release/libodin3.so
    export PYTHONPATH=<loki checkout>:$ODIN3_ROOT/plugins/python:experiments/round2
    L=/tmp/claude-1000/odin3-heavy.lock
    flock -x $L python experiments/round2/l1_lutmap.py <rename dataset-rebuild> <data>/l1/lut
    flock -x $L python experiments/round2/l1_run.py run --set lut --cond calib  # also native, none
    python experiments/round2/l1_run.py score --set lut --cond calib; python ... l1_run.py table
    flock -x $L python experiments/round2/l2_run.py calibrate --floor f2        # and f3
    flock -x $L python experiments/round2/l2_run.py run --floor f2 --cond calib # f3, none
    flock -x $L python experiments/round2/l2_astcfg.py
    flock -x $L python experiments/round2/l2_llm_ops.py
    flock -x $L python experiments/round2/l4_ablate.py collect; l4_ablate.py fit
    flock -x $L python experiments/round2/l4_ablate.py run; python ... l4_ablate.py table
    python experiments/round2/l7_rescore.py; l5_sandwich.py; l5_prefilter.py; l2_report.py
    python experiments/round2/paper_tables.py
