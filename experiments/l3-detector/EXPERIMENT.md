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

- 2026-10-30 (during Part A, after the first TEST table was produced; stated so the reader can
  discount it): (1) the hard-target counter rule used "one adder operand constant"; on TUNE the
  incrementers have a 1-bit enable operand, so the rule became "one operand constant or a single
  net" (`narrow_operand`); the change was found by reading TUNE failures, but the first TEST table
  (counter O-hard recall 0.76) had been generated before it, so TEST is not untouched for this one
  rule. (2) `register` and `glue` also read the netlist (flip-flops present or not), since L1
  register claims miss many plain flip-flops; `timer` requires the compare result to reach the
  counter again within `max_depth`; `regfile` has a second signature (at least `regfile_k2` register
  claims, no select claim). These were written from TUNE tables before the first TEST table.
- 2026-10-30 (Part B/C, before any composite was scored): (1) the first composite sources were
  written as `.v` and Odin III refused SystemVerilog constructs of the references; they are `.sv`
  (the `.v` build attempt was moved aside, `build-v-ext-failed`). (2) Composites are hierarchical;
  the first Yosys netlists kept the module hierarchy as `.subckt` blocks (Loki saw no flip-flops,
  part recall 0). The Yosys scripts for the composites now start with `flatten` (census designs were
  single modules); both Yosys cells were rebuilt and re-run (old runs moved to `*-noflatten`). Odin III
  flattens by itself. (3) The pool had 27 usable parts (14 TUNE, 13 TEST), so the number of composites
  is 182 (TUNE 100: 60 pairs, 30 triples, 10 quads; TEST 82: 42, 30, 10), not 200: the TEST pool has
  too few pairs with free ports. (4) `Q084_115_138_141` (TEST) times out at 330 s in the three Odin III
  cells and is excluded there; Y-gate has 178 and Y-lut 181 finished runs of 182. (5) Wiring recall is
  also reported conditional on both endpoint families being detected (`wire_recall_cond`), because
  most composite misses are part misses.

## Results (2026-10-30)

Tracked outputs: `results/partA_table.csv` (TEST and TUNE), `partA_instance.csv`, `partA_misses.csv`,
`partA_design.csv`, `partC_table.csv`, `partC_composite.csv`, `composites.csv`, `split_single.csv`.
Tuned (TUNE only, `loki/l3/catalogue/tuning.json`): min posterior 0, `regfile_k` 2, `regfile_k2`
16, `max_depth` 2, `wire_depth` 4.

### Plain English

The detector finds the simple, strong patterns and fails on the rest. Without false alarms it finds
finite-state machines (precision 0.85 to 0.95, recall 0.95 on the 252 TEST designs), counters (no
false alarms; recall 0.86 to 0.90 on gates and LUTs, 1.0 on the hard-block target once a counter is
read as a hard-adder loop) and glue logic. It does not work for shift registers (precision 0.14 to
0.17: pipelines and delay chains also look like shift registers to Loki L1, and 3 of 6 true shift
registers have no L1 claim), timers (recall 0 to 0.17), register files (recall 0 to 0.31) and, in
the Odin III cells, plain registers (recall 0.78 to 0.80). The LFSR has one TEST design and Loki L1
did not claim it, so it is inconclusive. Most misses are L1 claim absent, not wrong composition. On
the 82 TEST composites the answer to Peter's question is no: the parts are found about 41 to 50% of
the time and the wires between parts 11 to 18%; when both ends of a wire were found the wire was
found in 38 to 61% of cases, below the 0.70 bar. So combined benchmarks do not yet show that "the
ideas work" for L3; they show that the single-part claims (shift register, timer, rotate) must be
fixed first. The Odin III and Yosys cells behave alike; the hard-block cell is better for counters
and worse for composite parts (precision 0.35).

### Part A table (TEST; designs, TP / FP / FN, precision (lower bound), recall (lower bound), label)

Design level, bootstrap 90% over designs. Cells: O-gate, O-lut, O-hard, Y-gate, Y-lut.

| pattern | cell | designs | TP | FP | FN | precision | recall | label |
|---|---|---|---|---|---|---|---|---|
| fsm | O-gate | 252 | 41 | 7 | 2 | 0.854 (0.767) | 0.953 (0.895) | INCONCLUSIVE |
| fsm | O-lut | 252 | 41 | 5 | 2 | 0.891 (0.809) | 0.953 (0.895) | WORKING |
| fsm | O-hard | 252 | 41 | 5 | 2 | 0.891 (0.805) | 0.953 (0.895) | WORKING |
| fsm | Y-gate | 238 | 36 | 2 | 2 | 0.947 (0.879) | 0.947 (0.879) | WORKING |
| fsm | Y-lut | 239 | 36 | 3 | 2 | 0.923 (0.846) | 0.947 (0.881) | WORKING |
| counter | O-gate | 252 | 18 | 0 | 3 | 1.0 (1.0) | 0.857 (0.714) | INCONCLUSIVE |
| counter | O-lut | 252 | 18 | 0 | 3 | 1.0 (1.0) | 0.857 (0.714) | INCONCLUSIVE |
| counter | O-hard | 252 | 21 | 0 | 0 | 1.0 (1.0) | 1.0 (1.0) | WORKING |
| counter | Y-gate | 238 | 18 | 0 | 2 | 1.0 (1.0) | 0.9 (0.778) | INCONCLUSIVE |
| counter | Y-lut | 239 | 18 | 0 | 2 | 1.0 (1.0) | 0.9 (0.778) | INCONCLUSIVE |
| shift | O-gate | 252 | 3 | 15 | 3 | 0.167 (0.0) | 0.5 (0.111) | NOT WORKING |
| shift | O-lut | 252 | 3 | 15 | 3 | 0.167 (0.0) | 0.5 (0.111) | NOT WORKING |
| shift | O-hard | 252 | 3 | 17 | 3 | 0.15 (0.0) | 0.5 (0.111) | NOT WORKING |
| shift | Y-gate | 238 | 2 | 12 | 3 | 0.143 (0.0) | 0.4 (0.0) | NOT WORKING |
| shift | Y-lut | 239 | 2 | 12 | 3 | 0.143 (0.0) | 0.4 (0.0) | NOT WORKING |
| lfsr | O-gate | 252 | 0 | 4 | 1 | 0.0 (0.0) | 0.0 (0.0) | INCONCLUSIVE |
| lfsr | O-lut | 252 | 0 | 4 | 1 | 0.0 (0.0) | 0.0 (0.0) | INCONCLUSIVE |
| lfsr | O-hard | 252 | 0 | 4 | 1 | 0.0 (0.0) | 0.0 (0.0) | INCONCLUSIVE |
| lfsr | Y-gate | 238 | 0 | 3 | 1 | 0.0 (0.0) | 0.0 (0.0) | INCONCLUSIVE |
| lfsr | Y-lut | 239 | 0 | 3 | 1 | 0.0 (0.0) | 0.0 (0.0) | INCONCLUSIVE |
| timer | O-gate | 252 | 1 | 5 | 6 | 0.167 (0.0) | 0.143 (0.0) | NOT WORKING |
| timer | O-lut | 252 | 1 | 0 | 6 | 1.0 (1.0) | 0.143 (0.0) | NOT WORKING |
| timer | O-hard | 252 | 0 | 0 | 7 | 1.0 (1.0) | 0.0 (0.0) | NOT WORKING |
| timer | Y-gate | 238 | 0 | 5 | 6 | 0.0 (0.0) | 0.0 (0.0) | NOT WORKING |
| timer | Y-lut | 239 | 1 | 0 | 5 | 1.0 (1.0) | 0.167 (0.0) | NOT WORKING |
| regfile | O-gate | 252 | 0 | 3 | 13 | 0.0 (0.0) | 0.0 (0.0) | NOT WORKING |
| regfile | O-lut | 252 | 1 | 1 | 12 | 0.5 (0.0) | 0.077 (0.0) | NOT WORKING |
| regfile | O-hard | 252 | 1 | 1 | 12 | 0.5 (0.0) | 0.077 (0.0) | NOT WORKING |
| regfile | Y-gate | 238 | 0 | 2 | 13 | 0.0 (0.0) | 0.0 (0.0) | NOT WORKING |
| regfile | Y-lut | 239 | 4 | 1 | 9 | 0.8 (0.5) | 0.308 (0.1) | NOT WORKING |
| register | O-gate | 252 | 58 | 11 | 16 | 0.841 (0.762) | 0.784 (0.703) | NOT WORKING |
| register | O-lut | 252 | 59 | 12 | 15 | 0.831 (0.754) | 0.797 (0.718) | NOT WORKING |
| register | O-hard | 252 | 59 | 8 | 15 | 0.881 (0.807) | 0.797 (0.718) | NOT WORKING |
| register | Y-gate | 238 | 56 | 10 | 10 | 0.848 (0.766) | 0.848 (0.773) | INCONCLUSIVE |
| register | Y-lut | 239 | 57 | 7 | 10 | 0.891 (0.82) | 0.851 (0.775) | INCONCLUSIVE |
| glue | O-gate | 252 | 99 | 0 | 0 | 1.0 (1.0) | 1.0 (1.0) | WORKING |
| glue | O-lut | 252 | 99 | 0 | 0 | 1.0 (1.0) | 1.0 (1.0) | WORKING |
| glue | O-hard | 252 | 99 | 0 | 0 | 1.0 (1.0) | 1.0 (1.0) | WORKING |
| glue | Y-gate | 238 | 99 | 2 | 0 | 0.98 (0.955) | 1.0 (1.0) | WORKING |
| glue | Y-lut | 239 | 99 | 2 | 0 | 0.98 (0.956) | 1.0 (1.0) | WORKING |

Instance level (Odin III cells, TEST, register words of the HDL word IR as truth; Yosys has no names,
design level only), `partA_instance.csv`:

| pattern | cell | TP | FP | FN | precision (lb) | recall (lb) | label |
|---|---|---|---|---|---|---|---|
| fsm | O-gate | 40 | 7 | 1 | 0.851 (0.762) | 0.976 (0.929) | INCONCLUSIVE |
| fsm | O-lut | 40 | 5 | 1 | 0.889 (0.805) | 0.976 (0.929) | WORKING |
| fsm | O-hard | 40 | 5 | 1 | 0.889 (0.805) | 0.976 (0.929) | WORKING |
| counter | O-gate | 21 | 0 | 6 | 1.0 (1.0) | 0.778 (0.607) | NOT WORKING |
| counter | O-lut | 21 | 0 | 6 | 1.0 (1.0) | 0.778 (0.607) | NOT WORKING |
| counter | O-hard | 28 | 0 | 0 | 1.0 (1.0) | 1.0 (1.0) | WORKING |
| timer | O-gate | 1 | 5 | 10 | 0.167 (0.0) | 0.091 (0.0) | NOT WORKING |
| timer | O-lut | 1 | 0 | 10 | 1.0 (1.0) | 0.091 (0.0) | NOT WORKING |
| timer | O-hard | 0 | 0 | 14 | 1.0 (1.0) | 0.0 (0.0) | NOT WORKING |

Where the misses come from (`partA_misses.csv`, TEST design x cell counts): fsm, counter (gate and
LUT cells), lfsr, shift: all `l1_absent` (no L1 claim of the required kind). Counter on O-hard: none
left after the narrow-operand rule. Timer: 3 to 4 `l1_absent` (no compare claim) and 3 to 7
`l3_composition` (compare present but its result does not reach the counter). Register file:
`l3_composition` in the Odin III cells and `l1_absent` for 10 of 13 in Y-gate. Plain register:
`l3_composition` (a false shift or FSM detection forbids it).

### Family verdicts (Part A, rule of the plan)

- fsm: WORKING in 4 of 5 cells (O-gate INCONCLUSIVE: precision lower bound 0.77).
- counter: WORKING on O-hard; INCONCLUSIVE on the other four (recall lower bound 0.71 to 0.78).
- shift: NOT WORKING in 5 of 5 (precision 0.14 to 0.17). lfsr: INCONCLUSIVE (1 TEST design).
- timer: NOT WORKING in 5 of 5 (recall 0 to 0.17). regfile: NOT WORKING in 5 of 5.
- register: NOT WORKING on O-gate, O-lut, O-hard (recall 0.78 to 0.80); INCONCLUSIVE on Y-gate, Y-lut.
- glue: WORKING in 5 of 5.

### Part B

182 composites (TUNE 100, TEST 82) named Q<nnn>_<nnn>[_<nnn>...] from 27 VerilogEval parts (14 TUNE,
13 TEST, disjoint); wire types control, data, handshake; via direct or comb; ground truth in
`work/l3d-out/composites/<name>/truth.json` (not committed; regenerated by `compose.py`, seed
20261030). All 182 built in the five cells (Odin III 3 x 182, Yosys 2 x 182); `loki re` finished on
181 (Odin III), 178 (Y-gate) and 181 (Y-lut).

### Part C table (TEST composites; kind-level matching)

| cell | composites | part recall | part precision | wiring recall (lb) | wiring recall given both ends | wiring precision | recall direct | recall comb | exact | part-miss composites | wiring-miss composites | label |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| O-gate | 81 | 0.41 | 0.443 | 0.159 (0.105) | 0.595 | 0.367 | 0.145 | 0.173 | 2 | 68 | 5 | NOT WORKING |
| O-lut | 81 | 0.438 | 0.46 | 0.172 (0.117) | 0.614 | 0.379 | 0.145 | 0.198 | 2 | 66 | 6 | NOT WORKING |
| O-hard | 81 | 0.495 | 0.351 | 0.115 (0.067) | 0.375 | 0.356 | 0.092 | 0.136 | 0 | 62 | 14 | NOT WORKING |
| Y-gate | 79 | 0.407 | 0.539 | 0.153 (0.1) | 0.489 | 0.401 | 0.151 | 0.156 | 2 | 66 | 5 | NOT WORKING |
| Y-lut | 81 | 0.443 | 0.534 | 0.178 (0.123) | 0.483 | 0.446 | 0.158 | 0.198 | 2 | 65 | 6 | NOT WORKING |

Verdict (rule: wiring recall >= 0.70): NOT WORKING in 5 of 5 cells. Of the composites that miss,
62 to 69 of 82 miss because a part is not found (Part A) and 5 to 14 because all parts are found and a
wire is not. Exact whole-composite matches: 0 to 2 of 82 per cell.

### Limits

Matching is at kind level (families fsm, counter, shift; counter includes timer, shift includes
LFSR): a wire matches when an ordered kind pair is detected, so two parts of one kind cannot be told
apart and a part with two kinds (Prob063, Prob154) counts for both. The Yosys netlist has no part
names. Round 4 family modules were not used. `regfile` parts were not wired. The tuning grids are
small and the rare patterns have 1 to 7 TEST designs. The counter rule for the hard-block cell was
changed after a first TEST look (Amendments). The `loki re` KeyError on Prob153_gshare (three Odin
III cells) and on the Yosys netlist of `vtr_ch_intrinsics_nolatches` is fixed (`loki/intent/groups.py`,
test `tests/test_intent_groups.py`); all five re-runs finish. No closed rebuild-and-test loop.
