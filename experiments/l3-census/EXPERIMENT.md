# Loki L3 census: which composite design patterns occur, and does their footprint change with tool and target?

Plan written 2026-10-30, before the runs. This file is committed and pushed first. A later change
is a dated entry under "Amendments"; the old text stays. Results go in a dated section at the end.

## Plain-English summary

Peter, 2026-10-30: "I like this pattern catalogue (or composite idioms), I think it needs to go bigger
and can be reflected as design pattern and goes down with provenance (the trick being different
synthesis tools might make different provenance paths) so this is a bigger idea" and "why can't we make
this L3 in Loki as I think it should be." Also: "Also note how the design patterns change with target
technology!" This is the first data question for Loki L3 (spec `docs/specs/2026-10-30-l3-patterns-design.md`).
Before building any detector we count how often a handful of seed patterns (FSM, counter, shift
register, LFSR, timer = counter with terminal compare, FSM driving a counter or shift register,
register file / memory, glue logic only) occur in three corpora, and what they look like once
synthesised by two tools for several targets.

Purpose chain (hub `docs/purpose.md`): Loki L Q2.2 (which netlist patterns identify which RTL idioms),
L Q3.1 and L Q3.3 (where a construct is lost; how a target-specific transformation changes its
footprint); Odin III O Q2.4 (target-aware optimisation) is the other side. Measures are structure
measures (which L1 claims appear, counts of cells, whether the pieces are connected); area, speed and
power are not measured. No detectors are built; the output is a measurement.

## Corpora

1. VerilogEval spec-to-rtl references (`*_ref.sv`, top `RefModule`): 156 designs.
2. Round 4 generator (`experiments/round4/gen`, tag `r4`, deterministic): the first 30 designs
   (indices 000 to 029, train split) of each of the 12 families (360 designs).
3. VTR Verilog (`vtr_flow/benchmarks/verilog`, small single-file designs only; chosen by size so each
   `loki re` run stays under 1 GB and 1 minute; the list is in the results).

## Labels (RTL side only, never from netlists)

Per design, from the HDL analysis in Odin III's front end: the L0 `words.json` (word-level IR of the
design after `proc; fsm`, built from the HDL before any mapping: word types `$dff/$sdff/$add/$sub/$eq/
$mem...`, the `fsm` flag of Odin III fsm detection, word edges) plus a fixed list of named source idioms
(a register assigned a concatenation of its own slice = shift; an xor into that concatenation = LFSR).
The rules (`labels_rtl.py`) are written down and unit-tested; no hand labels. Seed patterns:
`fsm`, `counter` (a register word with a feedback loop through `$add/$sub` with a constant), `shift`,
`lfsr`, `timer` (counter plus an `$eq/$ne/$lt/$gt/$ge/$le` against a constant that feeds the counter's
reload or an output), `fsm_counter`, `fsm_shift` (FSM word and counter/shift word in one module with a
word edge path between them), `regfile` (`$mem` word or memory array), `register` (plain `$dff` words
only), `glue` (no flip-flops: "no pattern: keep as gates"). One design may carry several labels.
Frequency: designs with the pattern / designs in the corpus, per corpus.

## Footprints: tools and targets (axes)

Tool x target cells, every labelled design:
- O-gate: Odin III, floor f3 (cmos6 gates), default front (`fsm` auto), `--vtr-compat --nolatches`.
- O-lut: Odin III, floor f2 (LUT6, soft logic, k6_frac arch).
- O-hard: Odin III, floor f1-k6 (LUT6 plus hard blocks: adder chains, multipliers, memories through the
  hardmap onto the same k6_frac_N10_frac_chain_mem32K_40nm architecture). The L0 build supports it, so
  it is run (no VPR).
- Y-gate: Yosys (`external/yosys/build/yosys`) with the Gate-Breaker script: `read_verilog; hierarchy
  -top; proc; fsm; opt; memory; opt; techmap; opt; dfflibmap -liberty cmos_cells.lib; abc -liberty
  cmos_cells.lib; clean`. For Loki the gate netlist is read back through `read_liberty` (cells as
  functions), flattened and written with `write_blif` (gates as `.names`).
- Y-lut: Yosys `proc; fsm; opt; memory; opt; techmap; opt; abc -lut 6; clean`, `write_blif`
  (LUT6 soft logic, no hard resources: carry, multiplier and memory are all expanded).
Yosys has no hard-block target in this census; the Y-vs-O difference on hard resources is stated as
the next step (Yosys `synth_vtr`-style with the VTR arch cell library) in the results.
A build or run that fails is excluded for that cell and listed.

## Measures per pattern instance and cell (tool x target)

`loki re --intent --calib none --features none --floor <f3|f2|f1-k6> --seed 1` (detectors of the hint
runs), reading `intent.json`. Per labelled design and cell:
1. Cell counts by kind (gates/LUTs, flip-flops, hard) from the netlist.
2. L1 claims that appear: counts of claim kinds (fsm, counter, shift_reg, lfsr, register, ...) and,
   for FSM claims, the encoding call of the claim facts (one-hot or binary, from the flip-flop count
   against the state count) when present.
3. Expected-claim hit: pattern present as claimed kinds (fsm -> an FSM claim; counter -> counter;
   shift -> shift_reg; lfsr -> lfsr; timer -> counter; fsm_counter -> FSM and counter; fsm_shift -> FSM
   and shift_reg; regfile/register -> register). Matching is at design level (pattern instance =
   design-level, since names are anonymised and Yosys names are unrelated); stated as a limit.
4. Connectedness: for a composite pattern with two expected claims, whether some combinational path of
   at most 3 gates (through glue only, not through other flip-flops) joins a flip-flop of one claim to
   the other in either direction, in the netlist of that cell.
5. Provenance path: the construct-chain depth available. Odin III cells carry the L0 label chain
   (`construct_types`, e.g. `$sdff|$sub|$mux`); Yosys netlists carry none for the Loki ingest (the
   `src` attribute is dropped by write_blif, not studied). Reported as the mean number of distinct
   construct types per labelled cell for O-cells and 0 for Y-cells.

Report per pattern x cell: n, fraction with the expected claim, fraction connected (composites), mean
cell counts, FSM encoding counts. Differences between tools at the same target (O-gate vs Y-gate,
O-lut vs Y-lut) and between targets for the same tool (O-gate vs O-lut vs O-hard) are called out with
the counts; no significance test is claimed (a measurement, not a hypothesis test).

## Stop rules and limits

Memory at most 6 GB; `/mnt/c` below 15 GB free stops; weekly meter at 100 stops. No LLM, no VPR. Outputs
outside the worktree (`work/l3-out`); only scripts, small CSVs and this file are committed.

## Amendments

- 2026-10-30 (before any scoring; changes to the text above, found while building the tooling):
  1. Link depth. The connectedness test reports the smallest number of combinational cells (0 to 8,
     BFS through `.names` and hard blocks, stopping at flip-flops) from a flip-flop of one claim to the
     D pin of a flip-flop of the other, in either direction. "Connected" in the tables means depth
     0 to 6 (the spec's `max_depth` default); the depths themselves are in `per_design.csv`.
     Hard-block pins named out/sumout/cout/o/y/q (or containing "out") count as outputs.
  2. Labels. `counter` needs the `$add`/`$sub` word of the loop to have a constant operand
     (an accumulator is not a counter); `regfile` is an array declaration, a `$mem` word or at least
     4 enabled register words (a register file written as separate regs); `shift` and `lfsr` come from
     the named source idioms listed in `labels_rtl.py`. Odin III's `read_slang` refuses the 4-bit enum
     cast `States'(...)` of Prob151 and Prob156 and the state variables typed `States`; the Odin III
     builds of those two use a copy with the cast removed and the variables plain `logic` (`patch_src.py`,
     same logic); Yosys reads the originals. Three references whose Odin III build fails equivalence
     (Prob046_dff8p, Prob078_dualedge, Prob145_circuit8: negedge, dual-edge, latch) are labelled by
     hand from the source, listed with the reason in `results/manual_labels.csv`; they have Yosys
     netlists only. `vtr_ch_intrinsics_nolatches` (memory module not defined) has no label.
  3. Corpus: the VTR set is `single_ff`, `diffeq1`, `diffeq2`, `ch_intrinsics_nolatches`.
  4. Yosys `Y-lut`: the first attempt (v1) left enable/reset flip-flops as `$_SDFFE_*` cells in the
     BLIF, so Loki saw no flip-flops; it was discarded (moved to `Y-lut-v1`, not used) and rebuilt with
     `dfflegalize` to plain and async-reset D flip-flops (initialised flip-flops kept) before `abc -lut 6`.
     Designs that Yosys refuses are excluded for that cell and listed (inferred latch in `always_comb`
     with the Gate-Breaker script, 6 FSM references).
  5. Each `loki re` run is capped at 330 s wall and 6 GB address space; a timeout is an excluded cell.

## Results (2026-10-30)

MEASUREMENT, not a hypothesis test: the plan fixed no threshold and no detector was built. Tracked
outputs are in `results/` (`labels_rtl.csv`, `manual_labels.csv`, `frequency.csv`, `pattern_cell.csv`,
`pattern_claims.csv`, `fsm_encoding.csv`, `coverage.csv`, `excluded_ffsub.csv`, `per_design.csv`); the
netlists and `loki re` runs stay in `work/l3-out` (not committed). Scripts: `l3lib.py`, `build_odin.py`,
`build_yosys.py`, `patch_src.py`, `label.py`, `labels_rtl.py`, `run_re.py`, `blifgraph.py`,
`analyze.py`; `test_l3_census.py` tests the labeller and the BLIF reach.

### Plain English

Across 519 labelled designs (156 VerilogEval references, 360 round 4 designs, 3 VTR designs) the
seed patterns are mostly small: 78 designs hold an FSM (15%), 44 a counter (8.5%), 11 a shift register,
2 an LFSR, 12 a timer (counter plus a terminal compare), 27 a register file, and the composites are
rare: 3 designs have an FSM that drives a shift register and exactly 1 (Prob156, the fancy timer)
combines an FSM with counters and a shift register. 199 designs (38%) have no flip-flop at all (glue
logic only). The composite patterns Peter's idea is about are therefore not common in these corpora;
they are common in the failures (the two Gate-Breaker hard cases), which is itself a finding.

Does the footprint change with tool and target? Yes, in four visible ways. (1) Target: on the
`lut+hard` target (Odin III with hardmap on the VTR architecture) a counter is no longer a counter
claim: all 43 counter designs lose the `counter` claim and gain a `hard_add` claim (an `adder` chain)
instead; on gates and LUTs 37 of 43 keep it. (2) Tool: for the same gate target, a timer's terminal
compare shows as a separate comparison claim next to the counter in 7 of 9 Yosys gate netlists and in
only 2 of 11 Odin III gate netlists, because Odin III folds the compare into the counter logic; a
Yosys gate netlist is about four times larger than an Odin III one (cmos_cells decomposes into
2-input gates; mean `.names` for FSM designs 338 against 83) while on LUT6 the two tools are close (17.6
against 15.1). (3) Encoding: both tools recode FSMs to one-hot on gates and LUTs alike, so the encoding
call is one-hot for 70 of 78 Odin III gate netlists and 69 of 73 Yosys gate netlists; the target does
not change it here, because both flows use the same size rule. (4) Provenance: an Odin III cell carries
a construct chain (mean 1.1 to 5.9 distinct construct types per labelled cell by pattern and cell); a Yosys
netlist read back through BLIF carries none (0).

Connectedness could not be shown: of the 4 composite designs no pair of claims is joined by a
flip-flop-D path of at most 8 gates in any cell. In the three FSM-plus-shift-register references the
FSM reaches the shift register through output logic, not through its D pins (the register shifts
unconditionally), so a D-to-D link is the wrong signature for them; the link to look for is
state to output decode, which the next step adds.

### Coverage

| cell | designs | netlist built | `loki re` done | async-reset flip-flop designs excluded |
|---|---|---|---|---|
| O-gate (Odin III f3 cmos6) | 520 | 519 | 516 | 0 |
| O-lut (Odin III f2 LUT6) | 520 | 520 | 519 | 0 |
| O-hard (Odin III f1-k6 hardmap) | 520 | 520 | 519 | 0 |
| Y-gate (Yosys, Gate-Breaker script) | 520 | 514 | 508 | 14 |
| Y-lut (Yosys abc -lut 6) | 520 | 514 | 512 | 14 |

Not built: O: `vtr_ch_intrinsics_nolatches` (memory module not defined) in O-gate; the three
references whose Odin III build fails equivalence (Prob046_dff8p, Prob078_dualedge, Prob145_circuit8,
Prob031_dff on f2 and f1-k6) are listed in the build logs. Y: six FSM references that Yosys refuses
with "Latch inferred for signal next" (Prob095, 096, 137, 146, 152, 155), under the Gate-Breaker script.
`loki re` stops: 330 s timeouts for Prob144_conwaylife (O-gate, Y-gate), vtr_diffeq1 (O-gate, Y-gate,
Y-lut), vtr_diffeq2 (Y-gate), Prob030_popcount255 (Y-gate) and Prob153_gshare (Y-gate); `loki re`
internal error `KeyError(<id>)` for Prob153_gshare (O-gate, O-lut, O-hard) and
vtr_ch_intrinsics_nolatches (Y-gate, Y-lut): a Loki fault on a netlist with a memory or a large
array, recorded here and not fixed in this PR. The 14 designs excluded in the Y cells use async
reset: the Yosys BLIF carries those flip-flops as `.subckt`, which Loki reads as hard blocks and not as
flip-flops (a limit of the readback, listed in `excluded_ffsub.csv`). Labelled by hand, listed with the
reason in `manual_labels.csv`: Prob046, Prob078, Prob145 (Odin III build fails), Prob151 and Prob156
(Odin III fsm detection does not flag the patched copy).

### Frequency (designs with the pattern; instances in brackets; labels from the RTL side)

| pattern | VerilogEval (156) | round 4 (360, first 30 per family) | VTR (3) | all (519) |
|---|---|---|---|---|
| fsm | 18 | 60 | 0 | 78 |
| counter | 14 (151) | 30 | 0 | 44 (181) |
| shift | 11 | 0 | 0 | 11 |
| lfsr | 2 | 0 | 0 | 2 |
| timer | 12 (148) | 0 | 0 | 12 (148) |
| fsm_counter | 1 | 0 | 0 | 1 |
| fsm_shift | 3 | 0 | 0 | 3 |
| regfile | 2 | 24 | 1 | 27 |
| register (only) | 35 | 130 | 2 | 167 |
| glue (no flip-flop) | 83 | 116 | 0 | 199 |

The 128 counter instances of Prob153_gshare are a table of 2-bit saturating counters (the label counts
register words). Round 4 `fsm` counts the 30 `fsm` and the 30 `dpfsm` designs (an FSM plus an
accumulator; an accumulator is not a counter under the constant-operand rule, so `dpfsm` is not an
`fsm_counter`). Round 4 has no shift register, LFSR or timer (its `shifter` family is a combinational
shift of the input).

### Footprint per pattern and cell (hit = the expected L1 claim kinds appear; designs)

| pattern | O-gate | O-lut | O-hard | Y-gate | Y-lut |
|---|---|---|---|---|---|
| fsm (fsm claim) | 76/78 | 76/78 | 76/78 | 71/73 | 71/73 |
| counter (counter claim) | 37/43 | 37/43 | 0/43 (hard_add 43/43) | 38/41 | 38/41 |
| timer (counter + compare claim on its nets) | 2/11 | 1/11 | 0/11 (hard_add 11/11) | 7/9 | 2/9 |
| shift (shift_reg or lfsr claim) | 5/10 | 5/11 | 6/11 | 4/9 | 4/10 |
| lfsr (lfsr claim) | 1/2 | 1/2 | 1/2 | 1/2 | 1/2 |
| fsm_shift (fsm and shift_reg claims) | 2/3 | 2/3 | 2/3 | 1/2 | 1/2 |
| fsm_counter (fsm and counter claims) | 0/1 | 0/1 | 0/1 | 0/1 | 0/1 |
| regfile (register/ff claim) | 19/25 | 26/26 | 26/26 | 8/25 | 25/25 |
| register only (register/ff claim) | 69/167 | 96/167 | 105/167 | 25/154 | 84/155 |
| glue (no sequential claim) | 199/199 | 199/199 | 199/199 | 198/198 | 199/199 |

Connected composites (flip-flop-D path of at most 6 gates between the two claims): 0 of 3 fsm_shift
and 0 of 1 fsm_counter designs in every cell (`depth_*` columns of `per_design.csv` are -1: no path
within 8 gates). Cells per design (mean `.names` + latches) are in `pattern_cell.csv`; the claim
kinds that appear around each pattern are in `pattern_claims.csv`.

FSM encoding call (designs, fsm claims of the design): O-gate one-hot 70, plus 4 with a second claim
of unknown encoding, binary 1, coded 1, no claim 2; O-lut one-hot 53 plus 21 with extra claims of
unknown encoding; O-hard 57 plus 17; Y-gate one-hot 69, coded 2, none 2; Y-lut one-hot 48 plus 21
with extra claims. Soft LUT targets therefore give more than one FSM claim per design (cause not
investigated); the gate targets mostly give one.

### Differences called out (tool and target)

1. Target changes the counter claim: gate and LUT soft logic keep `counter` (0.86 Odin III, 0.93 Yosys);
   the hardmap target replaces it with `hard_add` in every counter design (43/43) and in every timer
   (11/11), and the shift-register designs show 1795 `hard_add` claims in total over 11 designs (cause not
   investigated).
2. Tool changes what stays visible at the same target: timer compare 7/9 (Yosys gate) against 2/11
   (Odin III gate); register-file register claims 8/25 (Yosys gate) against 19/25 (Odin III gate) and
   25/25 (Yosys LUT) against 26/26 (Odin III LUT); `eq_const` claims in Yosys gate netlists are many
   (3009 around register-only designs against 357) (probably because the gate library decomposes comparisons into 2-input gates; not tested).
3. Encoding is the same across tools and across gate/LUT targets (one-hot); the FSM claim count per
   design differs (soft LUT targets duplicate).
4. Provenance path: observed for Odin III (construct chain, mean 1.4 to 5.9 distinct construct types
   per labelled cell), absent for the Yosys netlist read back as BLIF (0).

### Surprising

- The two Gate-Breaker seed failures cannot be used as they are in either flow. Odin III's `read_slang`
  refuses their 4-bit enum cast `States'(...)`. Yosys with the Gate-Breaker script reads them, but
  `|state === 1'bx` and the `default: next = 4'bx` make it return the outputs as constant `x`: the
  gate netlist has no flip-flops and 0 cells (Prob151: `assign done = 1'hx` for all three outputs;
  Prob156: `fcount` constant 0). On a patched copy Odin III builds them; `loki re` v2 then finds no
  `fsm`, `counter` or `shift_reg` claim on Prob156 in any cell (only `ff_en`, `ff_srst`, `bus`,
  `eq_const`, `hard_add`), so the motivating timer is a total miss of the sequential claims, the case
  an L3 composite has to explain.
- Six FSM references that Odin III builds are refused by Yosys (inferred latch in `always_comb`).
- 14 async-reset designs come out of the Yosys flow with flip-flops that Loki cannot read from BLIF.
- The `fsm` pass recodes to one-hot in both tools, so the encoding claim is one-hot for almost every
  FSM; the claim reads binary or coded for only 2 to 3 designs per cell (Prob151 reads binary on
  Odin III).

### Limits

Labels come from the Odin III word IR plus fixed source idioms, with five hand labels listed;
matching of a label to a claim is at design level, so a design with several instances of a pattern
counts once (the instance column of the frequency table counts register words). Composite
connectedness is tested only as a flip-flop-D path; the 4 composite designs are too few for any
rate. The round 4 sample is the first 30 designs per family, not all 1200. VTR is 3 small designs. No
vtr big designs, no VPR. Not done and the next steps: Yosys on a hard-block target (VTR architecture
cell library) to compare tools on `lut+hard`; an output-side link test for FSM-to-datapath
composites; instance-level matching for Odin III netlists through the L0 labels; the census of all
1200 round 4 designs and the 33 VTR designs.
