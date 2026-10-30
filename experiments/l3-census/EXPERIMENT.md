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
