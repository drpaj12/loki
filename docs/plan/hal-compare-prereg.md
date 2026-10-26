# Loki word-first detector vs HAL/DANA: pre-registration

Written 2026-10-26, before HAL is built and before any HAL run on any evaluation design. This file
is committed and pushed first; its commit SHA is the pre-registration SHA quoted in the paper. A
later change is a dated entry in "Rule additions" at the end that keeps the old rule; the paper
reports both. Feasibility and sources: `docs/plan/hal-feasibility.md`. Round-5 protocol this extends:
`experiments/round5/EXPERIMENT.md`.

Purpose chain (hub `docs/purpose.md`): Loki **L Q2.4** (can words, control nets and FSMs be found
first) and L Q1.1. Measure: word recovery (precision, recall, purity) against the L0 provenance
ground truth, same designs, same metric code for both tools. This is understanding of what is
recoverable, not area, speed or power.

Tools credited: HAL (Embedded Security Group, MIT licence, tag v4.5.0, commit e7fea566b51e) and
its dataflow plugin, which implements DANA (Albartus, Hoffmann, Temme, Azriel, Paar, TCHES 2020(4),
309-336, doi 10.46586/tches.v2020.i4.309-336). Bib entries: feasibility doc section 5. Nothing of
HAL is vendored; the repo carries our gate-library files, converter and scorer only.

## Question

RQ-H1: on the netlists Loki's word-first detector was evaluated on, does DANA (grouping
flip-flops by shared control nets and by common predecessors and successors, designed for
gate-level cell libraries) recover the L0 register words better than, equal to, or worse than
Loki's word-first detector (which groups by shared clock, enable and reset and joins plain
flip-flops through D-driver and Q-reader words)?

## Inputs

| set | designs | floors | notes |
|---|---|---|---|
| MI | the micro dataset (68 designs at f2, 65 at f3) | f2 (headline), f3 | as round 5 |
| VT | the 33 VerilogEval held-out designs (manifest split test) | f2 (headline), f3 | as round 5 |
| BIG | the 13 round-4 big designs with an ok f2 floor | f2 only | smallest first; 1800 s per run |

E_real = MI + VT, the headline set, as in round 5. The corpus sets CI and CO (synthetic) are not
part of this comparison. Netlist floors: f2 = LUT6 floor, converted to `lut6.hgl` instances; f3 =
cmos6 gate floor (BUF INV NAND2 NOR2 DFF DFFSR), converted to `cmos6.hgl` instances. Floor names
follow the L0 spec (f2 LUT, f3 cmos6). Both tools read the same `netlist.blif` of the floor; HAL
through `loki.hal.blif2hal`. Designs that the converter rejects (for example `.subckt` hard
blocks such as `micro_multiply_hard_block` at f2) or that HAL fails to load are dropped from both
arms and counted per set and floor.

Development data for the converter and the gate libraries: hand-written fixtures and the round-4
corpus train split (loading and function checks only, no scoring). The micro, VerilogEval and BIG
designs are used before the HAL run only for the converter's function round trip (BLIF versus
iverilog, no HAL, no word scoring). No HAL group is scored on any E_real or BIG design before this
file is pushed.

## Ground truth

Same L0 answer key as round 5 (`words.json`, `graph.json`). FF = node of kind `ff` in `graph.json`.
GT word = an L0 storage word (`loki.score.gt.STORAGE`: `$dff`, `$dffe`, `$adff`, `$adffe`, `$sdff`,
`$sdffe`, `$sdffce`, `$dffsr`, `$dffsre`, `$aldff`, `$aldffe`, `$dlatch`, `$adlatch`, `$dlatchsr`)
with a footprint that holds at least 2 FFs; its bit set is footprint intersected with FFs. A
design with no such word contributes nothing to the recall side and its predicted groups count
only on the precision side (they are then wrong by definition). FFs of GT words of width 1 count
as label carriers for purity (a group that joins them is impure), but those words are not scored for
recall.

## Predictions

- **HAL**: `dataflow.analyze` groups (Python route) or `groups.txt` rows (CLI route); each group is
  the set of gate (instance) names, which the converter keeps equal to the L0 node ids. Groups of
  at least 2 FFs are words. Two DANA settings, fixed here: **A** = the tool default of
  `min_group_size` as built (the value is read from the built plugin and recorded, not chosen by
  us); **B** = `min_group_size` 2. No `--sizes`, no `bad_group_size`, other options default, no
  hint derived from the answer key. Headline HAL arm = the setting with the higher pooled F1_J on
  E_real at f2 (conservative for the comparison: the choice favours HAL); both are reported.
- **Loki**: the round-5 `W` arm (`--detectors wordfirst`, existing runs under
  `work/loki-exp5-data/runs/W-<set>-<floor>`, not rerun): counted candidates (`Pred.counted(0.5)`)
  of kind `register`, cells intersected with FFs, at least 2 FFs. The round-5 `WB` arm is reported
  as a second row. No Loki rerun and no change to the detector.

## Metrics (one code path: `loki.hal.wordscore`, used for both tools)

Per design, then summed (micro-pooled) over a set; per-design values for the paired test. P =
predicted words, G = GT words.

- **Exact precision / recall**: the share of P whose FF set equals a GT word's FF set; the share of
  G exactly equalled by some P.
- **Matched precision / recall / F1_J** (headline): one-to-one greedy matching by Jaccard >= 0.5
  (`loki.score.match.match_greedy`, the matching of round-5 `construct_scores` for the kind
  `register`); precision = matched / |P|, recall = matched / |G|, F1 = 2 matched / (|P| + |G|).
  A cross-check asserts that Loki's matched count equals `construct_scores` for kind `register`
  whenever the GT instances are the derived `register` instances (test, not a result).
- **Purity**: sum over P of the largest overlap of a group with one GT word (any width, label =
  GT word id), over the sum of |group|. Unlabelled FFs count as impure.
- **Completeness** (inverse purity): sum over G of the largest overlap with one P group, over the
  sum of |word|.
- **FF coverage**: the share of FFs in GT words (>= 2 bits) that lie in some P group.
- **Descriptive only**: number of groups, HAL clock/enable/reset/set net counts per group, run
  time. Control-net recovery is not scored here: `words.json` carries no control-net answer key.
  FSMs are not found by DANA and are not scored in this comparison.

## Decision rule

Statistic: one-sided paired Wilcoxon signed-rank (`scipy.stats.wilcoxon`, zero differences
dropped, alpha 0.05) on per-design F1_i = 2 matched_i / (|P_i| + |G_i|) over the designs of E_real
at f2 with at least one GT word and one converted/loaded netlist in both arms; fewer than 8
non-zero paired differences makes the outcome `inconclusive`. Let D = pooled F1_J(Loki W) minus
pooled F1_J(HAL headline arm) on E_real at f2.

- **Loki ahead**: D >= 0.05 and Wilcoxon (Loki greater) p < 0.05.
- **HAL ahead**: D <= -0.05 and Wilcoxon (HAL greater) p < 0.05.
- **Comparable**: |D| < 0.05.
- Otherwise **inconclusive**.

Purity and completeness are reported with the same two arms and are not part of the rule. f3 (HAL on
cmos6 gates versus Loki f3), BIG (per design, smallest first, no test) and the per-set split MI /
VT are reported, not decided. Reachability: E_real holds on the order of 100 GT words of at least
2 FFs in MI and several hundred in VT, so 0.05 is a handful of words in MI and tens in VT; all four
outcomes are reachable.

## Stop rules

- A converted netlist that HAL rejects: the parser error is recorded; the design is dropped from
  both arms. If more than 20 percent of the designs of a set at a floor are dropped, stop, report
  the cause and do not score that set/floor.
- HAL run time limit 900 s per design (BIG 1800 s). A timeout drops the design from both arms and
  is listed.
- HAL needs a source change, or the library description cannot express a floor cell: stop and
  report; do not patch HAL.
- Any change of the converter or the `.hgl` files after the first HAL run on an E_real design is a
  dated "Rule additions" entry; results are then reported under both versions.
- No tuning of DANA options on E_real or BIG. The two settings above are the only ones.

## What is NOT done

No LLM call, no Loki rerun, no heavy lock for the prep (the HAL build and the sweeps take the lock
later), no change to Odin III, VTR or Loki detector code, no use of `hal-benchmarks`.

## Rule additions

(none)
