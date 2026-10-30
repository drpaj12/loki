# Loki L3 v0: does L3 work on single patterns, and on built composite benchmarks?

Plan written 2026-10-30, before the runs. This file is committed and pushed first. A later change
is a dated entry under "Amendments"; the old text stays. Results go in a dated section at the end.

## Plain-English summary

Peter, 2026-10-30: "Can you make benchmarks with by combining ideas from these to make bigger
benchmarks and then could we test this out - the 2 choice seems to make sense to see if we the ideas
work - we can start labelling these Q23 or Q24 or Q124 and then let's test out Loki L3 - before doing
that is the L3 working for the cases - does it work for non-composites too (as in patterns of basic
ideas." And, on the go-ahead: "Build it out and test it. Plan it build it and test it."

Two questions, in this order. Part A: does an L3 detector find the basic patterns (FSM, counter,
shift register, LFSR, timer, register file, plain register, glue) in single designs, without false
alarms? Part B and C: if we build bigger benchmarks by wiring known designs together (names
Q035_146 = Prob035 and Prob146), does the L3 composite detector find the parts and the wires
between them? Hypothesis (Peter's words): combining ideas into bigger benchmarks lets us "see if the
ideas work", i.e. L3 finds the patterns. The L3 v0 detector reads Loki L1 claims (`loki re
--intent`) and the netlist, and uses a JSON catalogue (one entry per pattern, one signature per
target); it never reads a label.

Purpose chain (hub `docs/purpose.md`): Loki L1/L2 purpose (recover behavioural, hierarchical HDL; say
why a construct is not recovered); hub L Q2.2, L Q3.1, L Q3.3. Measure: precision and recall per
pattern, per tool and per target, on held-out designs (TEST). Area, speed and power are not touched.

## Detector v0 (what is built)

- `loki/l3/`: catalogue loader, signature interpreter, small BLIF graph, single-pattern detector,
  composite detector. Catalogue: `loki/l3/catalogue/<id>.json` (schema 1, sorted keys), one entry per
  basic kind: `fsm`, `counter`, `shift`, `lfsr`, `timer` (= counter + terminal compare), `regfile`,
  `register`, `glue`. Each entry has one signature per target: `gate` and `lut` (L1 claims used
  directly) and `lut+hard` (hardmap: a counter is a `hard_add` claim whose sum bits reach, through
  at most `max_depth` combinational cells, the D pins of flip-flops whose Q reach the adder inputs,
  with one adder operand constant: the one-hot lesson, target-aware).
- A signature is: required L1 claim kinds per role, constraints (`compare_on` = a compare claim whose
  input nets include the role's Q nets; `feedback` = the register loop above; `min_count` = number of
  claims), and negative conditions (`forbid` other detected entries). `register` forbids fsm,
  counter, shift, lfsr, regfile; `glue` requires no sequential claim.
- Instances: claims that share a Q net are merged (highest posterior kept). A claim with status
  `rejected` is ignored.
- Miss attribution: each missed truth is "L1 claim absent" (no claim of a required kind) or "L3
  composition wrong" (all required kinds present, a constraint failed).
- Tuned on TUNE only (grid, F1 pooled over the five cells, ties go to the simpler value): `regfile`
  min register-claim count k in {2,3,4,6,8}; `max_depth` for `feedback`/`comb` in {2,4,6,8}; minimum
  claim posterior in {0, 0.5, 0.9}. Written to `loki/l3/catalogue/tuning.json` before TEST is read.
- Composite detector (Part C): the detected single-pattern instances are the parts; a wire A to B is
  a forward walk from A's state nets (Q nets) through combinational cells of at most `max_depth`
  cells (stopping at flip-flops) that reaches a net of B's inputs (every claim net of B except Q,
  clock, reset); depth 0 = `direct`, 1 to `max_depth` = `comb`; the shared clock/reset wire is not
  scored (every composite has it). A composite claim is `{pattern: "<kind>+<kind>...", parts, wires,
  p}`; p is the log-odds sum of spec 6.2 with hand-set terms (part prior 0, each part claim its own
  posterior as log-odds, direct wire +2, comb wire +2 - 0.5 depth, a missing wire 0) and is reported,
  not thresholded. Tuned on TUNE: `max_depth` in {2,4,6,8}. No proof step (structural only).

## Measures and the rule (fixed now)

Part A: per pattern x cell, on TEST designs with a built netlist and a finished `loki re`: design
level TP, FP, FN, TN, precision = TP/(TP+FP), recall = TP/(TP+FN). Truth is the RTL-side census label
(`labels_rtl.csv`, five hand labels in `manual_labels.csv`). 90% bootstrap over designs (2000
resamples, seed 1, 5th percentile = lower bound) for both. For Odin III cells, instance level for the
patterns that have one register word per instance (fsm, counter, timer): a detected instance maps to
the register words whose footprint (words.json) holds its flip-flops (graph.json edges: net to
driver node); it is true when one of those words carries the label; instance precision = true
detected / detected, instance recall = true words matched / true words. Yosys netlists have no names:
design level only. Per cell the five cells are the census cells O-gate, O-lut, O-hard (Odin III f3,
f2, f1-k6) and Y-gate, Y-lut (Yosys); the 14 Yosys designs whose async-reset flip-flops come back as
`.subckt` stay excluded in the Y cells (census `excluded_ffsub.csv`).
Part C: on TEST composites, per cell: part recall and precision (set of (kind) parts per composite,
min(truth count, detected count) per kind), wiring recall and precision at kind level (a truth wire is
(from kind, to kind); a detected wire matches when the same ordered kind pair is detected; direction
counts), per truth via kind (direct, comb) recall, and whole-composite exact match (parts and wires
equal as multisets, no extra wires). Every composite miss is attributed: part miss (a truth part not
detected, so Part A) or wiring miss (all parts detected, a wire absent).

The rule (reported per pattern or per via kind and per cell, CAD-style first: the hit counts
TP/FP/FN and the percentages, then the label): a single-pattern detector is **WORKING** on TEST when
precision >= 0.80 and recall >= 0.80 and both lower bounds >= 0.80; **INCONCLUSIVE** when both point
estimates >= 0.80 but a lower bound < 0.80, or fewer than 5 truth-positive TEST designs; **NOT
WORKING** when a point estimate < 0.80. Composite wiring is **WORKING** when wiring recall >= 0.70 with
the same lower-bound reading. A pattern's family verdict is the list of its per-cell labels.

## Split (fixed now)

Part A: `results/split_single.csv` (all 519 labelled census designs; committed with this plan). Rare
patterns (lfsr, fsm_counter, fsm_shift, timer, shift) are alternated between TEST and TUNE in name
order so each side has some; every other design goes by sha256 of its name (even = TUNE). TUNE has 267
designs, TEST 252 (TEST pattern counts: fsm 43, counter 21, timer 7, shift 6, regfile 13, lfsr 1, glue
99, register 74): lfsr and the composite labels have so few TEST designs that their labels will be
INCONCLUSIVE by construction; this is stated, not hidden. Part B/C: the constituent problems of the
composites are the VerilogEval references that are in the same split (a problem on the TUNE side only
feeds TUNE composites and the reverse), so TEST composites use only constituent problems that appear
in no TUNE composite.

## Part B: composite benchmarks (Peter's option 2)

- Generator `compose.py`: seeded (20261030), deterministic. Parts: VerilogEval reference modules
  (`RefModule`, renamed `P<nnn>`) that are single-module, have a `clk` input, are labelled with at
  least one of fsm, counter, shift, lfsr, timer, regfile, and build and finish `loki re` in all five
  cells without the async-reset limit (a part dropped for a cell is not used: the pool is the
  intersection). Round 4 family modules are not used (the pool is big enough; stated).
- Composite = 2 (60%), 3 (30%) or 4 (10%) parts with distinct problem numbers, one composite per
  distinct part set; target about 200 (100 TUNE, 100 TEST; the pool decides the actual number, which
  is stated in the results). Each part keeps its own reset and data inputs as top inputs (`p<k>_<port>`)
  except `clk`, which is shared; every part output is a top output so nothing is optimised away.
- Wires, ground truth by construction: control (a 1-bit output bit of A drives a 1-bit input of B),
  data (an output of A drives a multi-bit input of B, truncated or zero-extended), handshake (A to B
  and B to A, two ports each); via `direct` (`assign` only) or `comb` (the value is ANDed with a fresh
  1-bit top input first); the wire list (from part, to part, type, via) is written to
  `truth.json`. A part's inputs are used at most once; a composite whose parts have no free port
  for a wire is skipped.
- Naming (Peter: "labelling these Q23 or Q24 or Q124"): Q followed by the VerilogEval problem
  numbers, 3 digits each, in ascending order, joined by underscores: Q035_146 = Prob035 + Prob146,
  Q035_146_154 = three parts. One composite per part set, so the name is unique.
- Every composite is synthesised in the five cells (census `build_odin.py` / `build_yosys.py` through
  a manifest override) and run with `loki re --intent` (census `run_re.py` settings).

## Stop rules and limits

Memory at most 8 GB; `/mnt/c` below 15 GB free stops; weekly meter 100 stops (commit first). No LLM,
no VPR, no change to odin3. Outputs outside the worktree (`work/l3d-out`); committed: scripts,
catalogue, tests, small CSV/JSON results, this file. `loki re` capped at 330 s and 6 GB per run (a
timeout is an excluded cell). No closed rebuild-and-test loop (spec item, a later question).
Pre-run fix: `loki re` KeyError on Prob153_gshare (Odin III cells) is fixed in
`loki/intent/groups.py` (`_feeders` indexed a flip-flop without support; no claim semantics change)
with a regression test; the Yosys netlist of `vtr_ch_intrinsics_nolatches` is re-run to check.

## Amendments

(none yet)
