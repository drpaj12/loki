# Q-L10: Loki controls the LLM block by block, against Gate-Breaker whole-netlist prompting (plan, 2026-11-02)

Branch feat/ql10-blocks on loki main 27272bc. Plan written before any model call; this lane makes none. This file and
the two prompt files (`block_prompt.txt`, `block_hint.txt`) are committed and pushed first; that commit SHA is the plan SHA
of the results. A later change is a dated entry under "Amendments"; the old text stays. Reuses by import, changes none of:
`experiments/llm-pilot` (system message, scorer, collect, leak gate), `llm-full` (population, arm A results), `ql9-join`,
`ql8b-anchors`, `ql8c-kind`, `ql6-grow` (the #78 block builder and the #75 M2 kind posterior).

## Peter's words (2026-11-02)

"on the loki front, what I'm interested is as a question is that the loki with LLM is better reverse engineering (so the
provenance comparison is good for saying how good Loki is) and I like the path forward suggested (the block approach) so, we
want to show that Loki can control the reverse engineering (and how the hints don't help) against gatebreaker."

Purpose chain (hub `docs/purpose.md`, Loki rows): reverse engineering of structural netlists (Peter's goal), RQ Q-L10 (new),
related LLM1 to LLM4 (hints v1 DISMISSED, netlist USEFUL, hints v2 +0.10 pass@1 and no pass@3 change) and Q-L9 (anchor-grow-join
blocks right for 0.715 of held-out constructs; M2 kind macro F1 about 0.39). Measure: functional pass (pass@1, pass@3) of the
assembled RTL, block-level agreement with the netlist, share of the Odin III provenance key recovered, tokens per design.

## Plain English

The earlier runs gave the model the whole flat netlist and asked for the whole RTL (Gate-Breaker's way, arm A). Loki's hints
added nothing there. Here Loki does the splitting: it cuts the netlist into the blocks it believes are one construct each (the
Q-L9 joined blocks), the model decodes one block at a time seeing only that block's gates and the nets that cross its boundary,
and a plain script glues the decoded blocks into one design. Two new arms: D (blocks, no hint) and D+h (the same prompt plus
Loki's one-word kind guess for the block, where Loki makes one). Three questions: is D as correct as A where A can run; does D
still work where the netlist is too big to hand over whole (A cannot run); and does the kind guess help, as the hints did not.
Answer key: where the Odin III provenance of the reference names the registers of a construct, we check whether one block holds
that construct and whether the decoded block is correct.

## Hypothesis H-L10 (controller's words)

H-L10: when Loki splits the netlist into its joined blocks and an LLM decodes one block at a time (block netlist + boundary
nets, no hints) and the blocks are assembled into one RTL design, (a) on designs that fit Gate-Breaker's context the result is at
least as correct as arm A, and (b) on designs too large for one prompt it still produces a correct (or per-block correct) design
where arm A cannot run; (c) adding Loki's kind guess as a hint per block does not improve correctness (the hints-do-not-help
result carried to the block setting).

## What the preparation found (no model call; `blocks_summary.csv`, `designs.json`)

Loki's blocks (#78 headline: anchors bank+loop+const, grown to the end, JCOND join at 0.2; blocks above 300 cells never
made; cells in no block grouped by connected component, split by the Fiedler cut or chunked at 300 into `residual` blocks) on the
Gate-Breaker netlists: of the 137 population problems, 15 have no gate cell (outputs are wires and constants; nothing to decode), 95 form one block, 27 form
two or more. So the block approach differs from arm A on 27 of 137 designs; on the 95 single-block designs D is arm A with
a different prompt wrapper (the whole netlist as one block, no two-shot examples, no designer prior). Of the 314 blocks, 221
are `residual` (combinational logic has no flip-flop anchor), 93 have a Loki anchor class. The kind guess exists for 49 blocks
of 31 problems; the D+h prompt differs from the D prompt on those 49 only (the other calls are shared by D and D+h). The
structure-only provenance number (no model): of 47 key constructs (flip-flop sets named by the provenance of the reference, 42
designs), 39 (0.83) are held by one right block.

## Arms (prompts are exact files, frozen in the plan commit)

Model and settings as the full run: one fresh Sonnet subagent per call (`claude-sonnet-5-5`), the `re` system message of
llm-pilot (md5 c95998c379b2d7e520c508b25a5a4c92), call file in the two-delimiter form, byte-identical for the three draws,
no retry, no rewording, same stop rule and blinding statement as `llm-full/EXPERIMENT.md` (restated below).
- A: the Gate-Breaker netlist prompt (llm-pilot `re` variant, two-shot). Not re-run: the full run's outcomes for the same 137
  problems and the same 3 draws are used (`llm-full/results/results.csv`, arm A). Arm A is not defined on the larger designs
  (the dataset prompt is over the pilot's 40000 B cap: the full run excluded them).
- D: one call per block. User message = `block_prompt.txt` with the block's module name (`Block_<k>`), its boundary nets as the only
  ports (single-bit identifiers; `in[3]` is `in_3_`), and the block's cells copied from the netlist; no examples, no hint.
  SHA-256 of `block_prompt.txt`: f934e53b3c52e23c4ad40d76171800e3638dccfb0519851dce6517dba6d11608.
- D+h: D plus `block_hint.txt` (one sentence: Loki's guess "the block looks like <a finite state machine | a counter | a shift
  register | a register file | a bank of registers>", it can be wrong) for a block where the #75 M2 posterior of the joined
  block has an argmax other than glue and the block has 4 cells or more; otherwise the D+h prompt equals the D prompt and the call
  is shared (one reply serves both arms: byte-equal prompts, same draw). SHA-256 of `block_hint.txt`:
  89e41cb49e51fb1ff0762153d6591bc9abad4a781cfef01468f3e1cc80fb7aaa.
- Assembly (`q10_render.assemble`, deterministic, no model): a reply must define `module Block_<k>`; the decoded modules are written
  out and a `TopModule` instantiates them on the netlist wires (a top port bit is connected directly, other nets are wires);
  `assign` statements of the netlist are copied. A missing block, or a reply without its module, is the outcome `assembly`.
- Leak gate: no prompt may hold `$n<k>`, `c<k>`, `loki_`, `Prob<k>`, L0, provenance, key.json, level0 (`build_prompts.leak_hits`,
  the pilot's); 0 hits over the system message, all block prompts and all call files. The hint sentence names no construct of the
  answer key: it is Loki's own guess from the block's graphlet signature.

## Designs, size limit

- `vq`: the 137 problems of the full run (`llm-full/selection.csv`). Arm A has its 3 draws.
- `vbig`: Prob018_mux256to1, Prob052_gates100, Prob105_rotate100, Prob115_shift18, the four VerilogEval problems the full run left out
  for the 40000 B prompt cap (dataset prompts 69426, 56405, 79721, 78899 B). Testbench scoring. Arm A is not run.
- `ext`: processor modules of the suite's external checkouts (picorv32, tinyriscv; serv and darkriscv were not used; not the private
  processor set), synthesized to the same cmos6 gate netlist by the Gate-Breaker recipe (`q10_synth_ext.py`, Yosys 0.55 from the VTR
  build, `flatten` added): listed in `ext_designs.csv`. No reference testbench: scored by sequential equivalence of the assembled RTL
  against the netlist (Yosys flatten and gate map, async set and reset made synchronous on both sides, ABC `dsec`, register
  init 0; the brief's Odin III + ABC was replaced by Yosys + ABC because the Gate-Breaker netlists use cmos6 cells that Yosys
  reads and the VTR build carries ABC; Odin III is not used). Equivalence by `dsec` is a check, not a proof of the testbench.
- Context limit used and how size is measured: the pilot's cap, a dataset prompt of at most 40000 B (the netlist section dominates;
  3.2 bytes per token as in the pilot, so about 12.5k tokens). It is a cost cap, not the model's window; the four `vbig` problems
  fit the model's window (about 18k to 25k tokens) but are over the cap the earlier runs used, and the `ext` netlists are
  larger still. Netlist size is the cell count (parsed) and the prompt bytes; `blocks_summary.csv` has both per block.
- Population limits: 15 `vq` problems have no gate, so D equals a fixed assembly of `assign` statements with no call; they are
  scored (their outcome does not depend on a model) and reported apart. Prob028 and Prob145 (behavioural latches) are not in the
  population, as in the full run.

## Measures

(i) Functional: per (design, arm, draw) the strict `pass` of the pilot scorer (VerilogEval testbench, `Mismatches: 0 in M
samples`, M > 0, no hidden harness module); pass@1 = passes / 3, pass@3 = any of 3 (the full run's definitions), MAJ = at least 2
of 3. For `ext`: `pass` = `dsec` says equivalent.
(ii) Provenance comparison, two parts. Block check: each decoded block is simulated against its own cells on 400 random cycles
(Icarus; `ok`, `mismatch`, `compile`, `inconclusive`, `timeout`); a diagnostic that also exists for designs without a
testbench. Key: a key construct is a set of at least 2 flip-flops that the Odin III provenance of the reference (veval-L0, f3 floor,
`labels.csv`: same construct type and HDL line and column, register named `bus[bit]`) names together, joined to the Gate-Breaker
netlist by register name (`q10_key.py`; extracted from `loki-veval-exp.tar.xz` on F:). A block is right for it when it holds at least
0.8 of its flip-flops and the Jaccard index is at least 0.5. Per design: key constructs with a right block (structure only) and
key constructs with a right block whose decode checks `ok` (recovered correctly), as a share of the key constructs. Limit stated: the
key is at the register level (42 of 141 designs have one; combinational cells have no key because the netlists of the two
syntheses differ and no cell join exists); the name join is not a cell join.
(iii) Tokens: per design and arm, input plus output tokens from the calls (estimate before; the dispatcher's `dispatch-log` and the
meter after).

## Tests and verdict rules (fixed now)

Unit: the design. Primary outcome: MAJ. pass@1 and pass@3 are reported beside it, as in the full run. Headline first (CAD
convention): mean pass@1 difference and the W/L/T on designs, then the strict label.
- H-L10(a) D against A on `vq` (137; the 15 gate-free designs are in A and D with the same outcome pair). Mean pass@1 difference D
  minus A with a problem-level bootstrap 95% interval (2000 resamples, seed 20261102). SUPPORTED when the lower bound of the interval is
  above -0.05 (non-inferior within 0.05, margin set now); CONTRADICTED when the upper bound is below 0; else INCONCLUSIVE. Also exact
  two-sided McNemar on MAJ (discordant designs) for all 137, for the 27 multi-block designs, and for the 95 single-block designs,
  Holm over these three. The multi-block stratum is the only place where the block approach differs from A in structure: the verdict
  on (a) is stated overall and for it separately.
- H-L10(b) D on the designs A cannot run (`vbig` and `ext`). No test against A. Per design pass@1, pass@3 and the block-check share.
  SUPPORTED when at least one design passes in at least one draw and the share of blocks with check `ok` over those designs is at
  least 0.8; CONTRADICTED when no design passes in any draw, or the `ok` share is under 0.5; else INCONCLUSIVE.
- H-L10(c) D+h against D on the designs with at least one block that has a kind guess (31 `vq` problems, plus any in `vbig` and `ext`).
  Exact McNemar on MAJ, mean pass@1 difference with the bootstrap interval, W/L/T. DISMISSED (the hint does not help) when the
  interval of the pass@1 difference lies within [-0.05, +0.05] and no adjusted p is below 0.05 with D+h better; USEFUL when D+h is
  better with adjusted p below 0.05; else INCONCLUSIVE (a positive geomean or difference with an interval touching 0 is
  INCONCLUSIVE, not DISMISSED). Block level: share of guessed blocks with check `ok`, D+h against D.
- Provenance (ii): MEASUREMENT (no verdict): share of key constructs with a right block, and recovered correctly, per arm; D against
  D+h on the same key.
- Family and Holm: the confirmatory family is the MAJ tests above (3 for (a), 1 for (c)); everything else is descriptive.
- No number is tuned on these data. The block builder, join rule, thresholds, models and prompts are fixed by earlier committed work
  and by the files of this commit.

## Pilot, calls, stop rule

Pilot: 10 `vq` designs x arms A (from the full run, draw 1), D and D+h, draw 1: the 9 designs with two or more blocks of which one
has Loki structure (Prob034_dff8, Prob045_edgedetect2, Prob046_dff8p, Prob054_edgedetect, Prob089_ece241_2014_q5a,
Prob118_history_shift, Prob121_2014_q3bfsm, Prob139_2013_q2bfsm, Prob154_fsm_ps2data) plus the single-block design with a kind guess of
lowest hash rank (Prob088_ece241_2014_q5b): 75 calls in 4 batches (`batches-pilot.json`). The controller reads the pilot for failures
of the protocol (assembly rate, replies without the module, token use per call), not for the hypothesis. Then the full run
(`batches.json`) without the 75 pilot calls, three draws; the `ext` calls are the last group (batch field `group`), so the run can stop
before them. Stop rule as the full run: stop when `api_refused` plus `no_file` exceeds 12 and exceeds 10 percent of the calls made, or
when the weekly meter reads 85 percent; unrun calls are `not_run`.

## Blinding deviation (as llm-full, restated)

Subagents keep the harness system prompt and tools and have file and web tools; the reference files and Odin III data sit on the same
disk. The call file carries no problem id, arm, block id or draw; the reply goes to an outbox file named by call number. The
controller repeats the tool-use audit. The `re` system message mentions Loki hints in every arm, D included (a cue, as in A).
A block prompt names the block `Block_<k>` and the nets by the netlist's identifiers.

## Limits, stated before the run

The block prompt has no two-shot examples (the examples are whole designs), so D differs from A in the wrapper as well as the cut;
on the 95 single-block designs that is the whole difference. 221 of 314 blocks are `residual`: Loki's anchors are flip-flop
based, so combinational logic is cut by connectivity, not by construct. Many multi-block designs are bit slices (eight one-cell
registers, ten independent bit gates): a call per slice is cheap but the model sees no word-level context, which is the block
approach's cost. Initial register values are not in a netlist; a reference that initialises its registers can fail a correct decode
(Prob034_dff8 in the dry run needs `initial q = 0`). The block check is a random-input simulation. The key covers registers only.
The estimator of pass@k carries the full run's note: no citation until verified. Draws are independent but not reproducible
(temperature not controlled). The `ext` equivalence check is `dsec` on netlists with register init 0.

## Amendments

- 2026-11-02 (before any model call; plan commit 1987409): preparation finished. Changes to the plan text only; no prompt file changed
  (the two sha256 above still hold).
  1. `ext` is five designs with one draw (not three): picorv32_pcpi_div (2408 cells, 175 blocks), picorv32_pcpi_mul (2586, 128),
     tinyriscv_div (3055, 195), tinyriscv_csr (3535, 90), tinyriscv_clint (1316, 66): 654 blocks, 29 of them with a kind guess. One draw
     because the designs cut into hundreds of blocks (three draws would be 2000 more calls); `ext` gives pass@1 and the block-check share
     only, no pass@3 and no MAJ. Block building took 6 minutes per design at most (one process each). The `ext` calls are the last
     batches (`group` = `ext`), smallest design first, so the run can stop before them. Netlists are generated (`q10_synth_ext.py`), not
     committed; the sha256 of every prompt is in `calls_table.csv`.
  2. The residual blocks (cells no anchor block holds) are the connected components of the uncovered cells, in traversal order,
     chunked at 300 cells; the Fiedler cut named in the first part of this plan is not used. 221 of 314 blocks are residual in `vq` and
     `vbig`; 622 of 654 in `ext` (32 have an anchor class; `blocks_summary.csv`, column kind).
  3. Counts. Blocks: `vq` 209 in 122 designs (15 designs have no gate), `vbig` 105, `ext` 654; 968 in all. Kind guesses: 78 blocks in 38
     designs (47 `vq`, 2 `vbig`, 29 `ext`). Calls (one per unique prompt and draw; a prompt shared by D and D+h is one call): 1772 in
     all: pilot 75 (draw 1, 10 designs, 4 batches); full 1697 = core 1014 (44 batches, three draws) + ext 683 (29 batches, one draw).
  4. Token estimate (prompt bytes / 3.2 plus the system message, plus 113 + 0.36 x cells output tokens per call, the fit of the 40 pilot
     arm A replies; harness overhead of each subagent not included): pilot input 58,229 + output 8,775 = 67,004; full input 2,262,298 +
     output 209,769 = 2,472,067 (core 1,296,838 + 125,370; ext 965,460 + 84,399); all 2,539,071. Per batch 1.7k to 176k tokens. For a
     scale against the meter: the full run moved the weekly meter from 62 to 70 percent over 1233 calls (about 0.0065 points a call); at
     that rate 1772 calls is about 11 points. Our calls are smaller on average (no two-shot prefix), so that is an upper guide, not an
     estimate.
  5. Dry run (`q10_dryrun.py`, `dryrun_result.json`): 402 stub replies for 9 designs (a gate-free one, a combinational one, the single-block
     FSM, three multi-block register or FSM designs, one over-cap problem and tinyriscv_clint), faithful RTL for draw 1 and one of five
     patterns (faithful, outputs tied low, syntax error, no markers, wrong module name) afterwards: 47 design rows, all outcomes as
     expected, 0 timeouts; 380 of 402 blocks check `ok` (the rest are the injected faults); the assembled clint is `equiv` by `dsec`
     and `neq` after every NAND, NOR and NOT output is inverted.
  6. Structure-only provenance number, computed with no model (42 designs with a key, 47 key constructs): 39 have a right block (0.83).

- 2026-11-02 (after the model calls, before the analysis; the controller ran every call, this lane none). Three changes to what was run and
  how it is read; the old text above stays.
  1. The 358 single-block calls were not run (Peter, "option 1": all multi-block designs, all draws). On a single-block design D is arm A's
     netlist in another wrapper, so the call would not test the block cut. 1,339 workflow calls and the 75 pilot calls were run: 1,414 replies,
     none empty, no API error. Consequence for the tests: of the 137 `vq` designs, 15 have no gate (scored without a call), 27 have two or more
     blocks (run, three draws), 1 single-block design (Prob088_ece241_2014_q5b, the pilot's kind-guess design) was run in the pilot with draw 1
     only, and 94 single-block designs were not run. That makes 43 designs with a D row, not the 31 the plan named (the 31 are the `vq` designs
     with a kind guess; only 6 of them are multi-block and were run; the other 25 are single-block, and one of those, Prob088, has one pilot draw that is reported apart). The McNemar family for (a) was three
     tests (all 137, 27 multi-block, 95 single-block). It is now three tests on what was run: the 15 gate-free designs, the 27 multi-block
     designs, and the 42 together; Holm over those three. The verdict of (a) is given for the 27 multi-block designs, the only place the cut
     changes anything. (c) is run on the designs with a hint that were run: 6 multi-block `vq` designs and 2 of the 4 `vbig` designs (8 designs,
     three draws); the 5 `ext` designs (one draw each, all with a hint) are reported apart.
  2. Tool-use audit, 22 of the 1,339 workflow calls broke the call template (the subagent used Bash or Edit on its own reply file; the template
     allows Read and Write only). None read any other file (`tool-deviations.csv`). They touch 27 result rows (D 14, D+h 13) of 10 problems.
     All rows are kept in the headline; the analysis is repeated with the 27 rows removed (a row removed in one arm drops the paired draw in both).
  3. The `ext` diagnostic and the AST/CFG similarity were added to the analysis (no model call). The AST/CFG measure is Gate-Breaker's second
     measure (Peter, 2026-11-02: "Isn't that how gatebreaker is evaluated, so shouldn't we use that too?"), scored for every assembled row of
     `vq` and `vbig` and for arm A on the same (problem, draw); see Results.
  4. AST and CFG similarity (the Gate-Breaker second measure) has no pre-registered rule: it is a measurement, reported with its interval
     and W/L/T, and it changes no verdict of (a), (b) or (c). Tools: `q10_astcfg.py` imports Gate-Breaker's pyverilog AST similarity
     (`gatebreaker-exp2/scripts/metrics.py`, Algorithm 2, depth 3) and the Odin III CFG probe (odin3 commit 77e975e5, Algorithm 3), the two
     files round 2 used, and edits neither. Only the double sum of the CFG kernel is done with numpy (same features and formula, equal to the
     probe's sum to 9 places on the tested pairs; `test_q10_astcfg.py`), because the probe's Python sum needs hours above 2,000 nodes. The
     reference is the VerilogEval `<problem>_ref.sv`; `ext` has none (it is scored against the synthesized netlist, not against RTL), so no
     AST/CFG value is given for `ext`. A value is absent when pyverilog or Odin III cannot read the file.

## Results (2026-11-02)

Generated by `q10_analyze.py` from the copies in `results/` (`summary.md`, `tests.csv`, `per_design.csv`, `part_b.csv`,
`key_recovery.csv`, `tokens_estimate.csv`, `ext_diagnostic.csv`); the plan commit is 1987409 (plan text) and e902ff1 (prompts). Seeded
problem-level bootstrap (seed 20261102, 2000 resamples), first arm named minus second, pass is the strict pass of the pilot scorer.
Headline first (CAD convention), then the label. USEFUL below is the paper's word for "supported under the round's own pre-registered rule".

Coverage: 1,414 replies (75 pilot, 1,339 workflow); 811 result rows, 243 scored (D 144, D+h 99), 568 not run (the single-block
designs). Outcomes: pass 201, runtime (testbench mismatches) 33, neq 9.

### H-L10(a): D against A (headline: no measurable difference where the cut changes anything)

On the 27 multi-block designs D passes 72 of 81 (design, draw) pairs and A 73 of 81: mean pass@1 difference D minus A
-0.012 (95% interval -0.074 to +0.037); draws W/L/T 3/4/74, designs W/L/T 2/3/22 on pass@1; pass@3 26 of 27 for both; MAJ 24 (D) against
25 (A), one discordant design, exact McNemar p = 1.0 (Holm over the three tests: 1.0). Label: INCONCLUSIVE. The plan's rule asked for a lower
bound above -0.05; the bound is -0.074, so non-inferiority within 0.05 is not shown with 27 designs, and the interval does not exclude
a small loss or a small gain.

Other strata (same A draws): the 15 gate-free designs, where D is a script and not a model: D 39 of 45, A 37 of 45, +0.044 (0.000 to +0.133), W/L/T 2/0/43.
All 42 designs: +0.008 (-0.032 to +0.056), draws W/L/T 5/4/117, designs W/L/T 3/3/36, pass@3 39 of 42 for both, MAJ 37 for both; the
plan's rule is met there (SUPPORTED), but 15 of the 42 designs involve no model and no cut, so the multi-block stratum is the verdict.
Adding the one pilot single-block design (Prob088, one draw, both arms pass) changes nothing (+0.008, -0.039 to +0.054).
Sensitivity with the 27 tool-deviation rows removed (both arms of the paired draw dropped): multi-block -0.012 (-0.074 to +0.037),
draws W/L/T 3/4/71, MAJ 23 against 24, same label; all 42: +0.008 (-0.032 to +0.056); same verdicts everywhere.

### H-L10(b): where arm A cannot run (headline: all blocks decode, whole designs pass on 3 of 4 over-cap problems and 1 of 5 processor modules)

`vbig` (D, three draws): 8 of 12 pairs pass: mux256to1 3 of 3, gates100 3 of 3, rotate100 2 of 3, shift18 0 of 3 (pass@3 3 of 4 designs).
`ext` (D, one draw): 1 of 5 equivalent (tinyriscv_div). Block check: 954 of 969 block replies check `ok` (0.985). Plan rule (b): one design
passes in one draw and the `ok` share is at least 0.8: label USEFUL (supported), with the limits below: a whole design passes only if every
block is right (shift18 has 15 of 16 blocks `ok` in two draws and 13 of 16 in the third, and fails in all three), and A cannot be put beside it.
`ext` diagnostic (`q10_extdiag.py`, no model call): each of the 4 D designs and 5 D+h designs with outcome `neq` (and tinyriscv_div) was
rebuilt with the blocks whose reply failed the block check (`mismatch` or `compile`) replaced by the faithful RTL of their own cells and checked again:
all 10 rebuilt designs are `equiv`. So the causes of the 4 D `neq` outcomes are the wrongly decoded blocks the block check named
(div: blocks 0 and 34; mul: 1, 4, 5; csr: 33; clint: 15), and neither the assembly nor the equivalence check method. One more result: in D,
tinyriscv_div has one `mismatch` block (2) and still passes equivalence, so a `mismatch` block is not always observable at the outputs (or the
random-input check is stricter than the design's use of the block). The share of blocks `ok` over the five `ext` designs is 0.99 (646 of 654 in D),
which for 66 to 195 blocks per design leaves the whole-design pass rate low: with a per-block error of 1.5 percent the chance that all 100 blocks are right is about 0.2.

### H-L10(c): the kind-guess hint (headline: D+h is not better, 0.042 behind, W/L/T 1/2/21; too few designs to show it is not worse)

On the 8 designs with a hint that were run (6 multi-block `vq` and 2 `vbig`, three draws each): pass@1 D 0.750, D+h 0.708, D+h minus D -0.042
(-0.125 to 0.000), draws W/L/T 1/2/21, designs W/L/T 0/1/7, pass@3 7 against 7, MAJ 6 against 6, McNemar p = 1.0. Label: INCONCLUSIVE.
The hint is never found better; the interval is not inside +-0.05, so the rule's DISMISSED is not reached with 8 designs. Block level: of 102 hinted
block replies (block, draw) with both arms, 95 check `ok` in D and 95 in D+h; D+h ok and D not 4, D ok and D+h not 4. The 5 `ext` designs
(one draw): D 1 pass, D+h 0 (tinyriscv_div, after one more `mismatch` block in D+h); descriptive. Over all 36 designs run in both arms: -0.037, draws W/L/T 1/3/94.
Sensitivity (deviation rows removed): -0.048 (-0.143 to 0.000), same label.

### Provenance answer key (measurement, no verdict)

Key constructs (flip-flop sets that the Odin III provenance of the reference names together), counted once per (design, draw) row. Eight multi-block
`vq` designs have a key (12 constructs per draw, 36 over their three draws): a right block exists for 12 of 36 (0.33) and the decoded right block checks `ok` for
10 of 36 (0.28); arm D+h gives the same 12 and 10. The two `vbig` designs with a key (rotate100, shift18)
have a right block and a decoded `ok` block for all 6 (1 construct each, 3 draws). The key counts are per row, not per design: the collector sums them over the rows of a design
(the equal D and D+h figures are two arms on the same 8 designs with the same blocks, not a copy). Limit: 34 of the 42 designs with a key are single-block
designs that were not run, so the structure-only 0.83 of the preparation (39 of 47 constructs, all 42 designs) is not comparable with the 12 of 36 here.

### Tokens (estimates, not measured)

Estimates from `calls_table.csv` (prompt bytes / 3.2 plus the system message, output from the pilot fit); harness overhead not included. Arm D per
multi-block `vq` design over 3 draws: about 14,500 tokens; arm A on the same designs, same basis (output taken as the pilot mean 125): about 10,300, so
D is about 1.4 times A. Over-cap `vbig`: about 125,000 per design (3 draws), `ext`: about 156,000 per design (one draw). All 1,414 calls: about 2.08 million estimated tokens
(1.90 million in, 0.17 million out). D+h costs 1 to 2 percent more than D.

### Why 43 problems and what the collector counts

The 43 `vq` designs with a D row are 15 gate-free (3 draws, no call), 27 multi-block (3 draws) and Prob088 (the pilot's single-block design, one draw): the
controller's tally of 127 problem-draws included the 45 gate-free ones, which are not multi-block. The answer-key fields are counted per (design,
draw) row, as above.

### AST and CFG similarity (measurement, no verdict; Gate-Breaker's second measure)

Computed for every assembled `vq` and `vbig` row (pass or not) and for arm A on the same (problem, draw) (`astcfg_rows.csv`, 720 rows; `summary.md`).
D is scored two ways. Assembled (`D-asm`): the file as assembled, with `TopModule` holding only instances of `Block_<k>`. Flattened (`D-flat`): Odin III
`hierarchy; proc; flatten; write_verilog`, top module kept (the control of `f3-recovery/tools/flatten_astcfg.py`). Gate-Breaker's AST and CFG
read one module, so `D-asm` mostly measures that the logic sits in other modules (multi-block mean AST 0.440, CFG 0.393 against A's 0.836 and 0.945): that is not a
fair number for the cut, and the f3 control already showed that flattening moves the scores. `D-flat` is the number to read. But the flatten
rewrites the text as well (Odin III writer), and this writer alone lowers arm A (A as written 0.836 AST / 0.945 CFG; A through the same
flatten 0.742 / 0.922). The headline is therefore `D-flat` against `A-flat`, both through the same writer, which isolates what the cut changes; `D-flat`
against `A-raw` (A as the model wrote it) is given beside it as the Gate-Breaker-literal pair.

Headline (27 multi-block designs; AST on the 23 whose reference pyverilog can parse): D-flat minus A-flat AST -0.037 (-0.063 to -0.014), draws W/L/T 16/53/0,
designs W/L/T 6/17/0; CFG -0.042 (-0.067 to -0.021), draws 19/62/0, designs 6/21/0. Means: AST A-flat 0.742, D-flat 0.704; CFG 0.922 and 0.880.
D-flat minus A-raw: AST -0.132 (-0.174 to -0.091), designs W/L/T 3/20/0; CFG -0.065 (-0.093 to -0.037), 4/23/0. D+h-flat minus D-flat: AST -0.000, CFG +0.000 (hint
changes nothing in the text). On the 15 gate-free designs D-flat is equal to A-flat (AST 0.881 against 0.886 over 12 designs; CFG 0.869 against 0.869 over 13).
`vbig` (D only): D-flat AST 0.748 (4 designs, 9 of 12 draws read), CFG 0.874 (4 designs, 8 of 12). Per quartile (D-flat minus A-flat; designs):
Q1 AST -0.006 (-0.014 to -0.000; 15), CFG -0.002 (-0.007 to +0.003; 15); Q2 -0.051 (-0.095 to -0.014; 12), -0.048 (-0.088 to -0.017; 13); Q3 -0.028
(-0.064 to +0.006; 6), -0.035 (-0.093 to +0.009; 7); Q4 -0.024 (-0.086 to +0.039; 2), -0.052 (-0.082 to -0.019; 5). n per cell: AST is missing for 7 designs
(4 multi-block, 3 gate-free) because pyverilog cannot parse their reference, the same designs in every cell; CFG is missing for 6 to 9 rows per cell where Odin III's reader
refuses the file ("function and task calls are not supported yet" in A's or D's text) and 3 D rows that the flatten could not read.
Reading (all assembled rows, pass or not): the text D assembles is a little less like the reference than A's, by about 0.04 (AST) and 0.04 (CFG) on a 0-1 scale, in about three
designs out of four; the difference is largest in Q2 and absent in Q1 (a one-gate design reads the same either way).
