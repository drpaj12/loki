# Q-L12: back to HDL at k4 and k6, with pass@1, AST and CFG (plan, 2026-11-03)

Branch exp/ql12-k4k6 on loki main 9c3f0f3 (after #84, Q-L11). This lane PREPARES: it makes no model call. The controller
runs the calls (Workflow) after the count and token estimate. This file and the two prompt files (`block_prompt_lut.txt`,
`a_prompt_lut.txt`) are committed and pushed first; that commit SHA is the plan SHA of the results. A later change is a
dated entry under "Amendments"; the old text stays. Reuses by import, changes none of: `ql10-blocks` (block rules, assembly
idea, AST/CFG scorer, analysis helpers), `ql9-join`, `ql8b-anchors`, `ql6-grow` (block builder), `llm-pilot` (system message,
scorer, collect, leak gate), `llm-full` (the 2-shot prefix and the arm A prompt layout).

## Peter's words (2026-11-03)

"So does the results that we generate for the paper have results for k4 and k6? There's no gate breaker to compare against, but
it's interesting there status?" then "We should have the back to HDL steps and the measure of AST and CFG as well since that's
the point".

Purpose chain (hub `docs/purpose.md`, Loki rows): reverse engineering of structural netlists (Peter's goal). RQ: Q-L10 and
Q-L11 continued at the two endpoints where the problem is larger (k4, k6). Q-L11 found that every model reply so far is for
the gates endpoint only. Measures: functional pass@1 and pass@3 of the assembled RTL, Gate-Breaker's two similarity measures
(AST, CFG; the Q-L11 scorer), share of the Odin III provenance key recovered by one right block, tokens per design.
Known without a model (paper Table tab:join, Q-L9): the right-block share of Loki's blocks is 0.610 at gates, 0.754 at k4
and 0.773 at k6.

## Plain English

At the gates endpoint the model was given gates. Here it is given the same designs after the Odin III mapper has packed
the gates into lookup tables (k4) and into lookup tables plus hard adders (k6). A lookup table hides several gates, so there
are fewer cells but each one says more, and the structure is harder to see. Two ways to ask the model for the HDL. Arm D
(Loki's way, the Q-L10 arm): Loki cuts the netlist into blocks, the model decodes one block at a time, a script glues the
decoded blocks. Arm A (Gate-Breaker's way, applied to a LUT netlist; Gate-Breaker itself has no LUT endpoint): the whole
netlist in one prompt. The question is whether Loki's blocks, which are better at k4 and k6, hold up there, and whether the
whole-netlist prompt falls behind.

## Definitions (the repository's names)

- gates: the cmos6 gate netlist of Gate-Breaker (Yosys cells NOT, NAND, NOR, DFF); the existing Q-L10 / Q-L11 rows.
- k4 ("f2", cell class `O-lut`): the Odin III soft-logic LUT netlist of the VerilogEval reference RTL, BLIF `.names` covers and
  `.latch` flip-flops. The mapper is the six-input one (LUTs of 1 to 6 inputs); "k4" is the repository's name for this floor.
- k6 ("f1-k6", cell class `O-hard`): the hard-block map of the same mapper and architecture
  (`k6_frac_N10_frac_chain_mem32K_40nm`): LUTs plus hard `adder` blocks (`.subckt adder`), flip-flops.
  The VerilogEval designs of this set that contain a hard block: Prob156_review2015_fancytimer (18 adders).
- Both from `work/l3-out/build/{O-lut,O-hard}/ve_<problem>/` (the l3-census builds, Odin III 1.2.0, read only), for the
  VerilogEval problems. For the processor modules the same builds (`loki.build.build_floor`) are made by `q12_synth_ext.py`
  into `work/ql12-out/census`. The top-level port bits keep their original names (the design interface, as in the gate
  netlists and the Gate-Breaker prompt); every other net is `w<k>`; no other original name reaches a prompt.

## Hypothesis H-L12 (controller's words)

H-L12: Loki's block-by-block decode (arm D, the Q-L10 prompt carried to LUT blocks) recovers the HDL at k4 and at k6 with pass@1
and AST/CFG similarity (a) not lower than D at gates on the same problems, because the blocks are better there (0.754 / 0.773
against 0.610), and (b) the whole-netlist arm A (Gate-Breaker's method applied to a LUT netlist) is lower than D at k4 and
k6.

## Arms (prompts are exact files, frozen in the plan commit)

Model and settings as the full run and Q-L10: one fresh Sonnet subagent per call (`claude-sonnet-5-5`), the `re` system message of
llm-pilot (md5 c95998c379b2d7e520c508b25a5a4c92), call file in the two-delimiter form, byte-identical for the three draws, no
retry, no rewording, same stop rule and blinding statement as `llm-full/EXPERIMENT.md`.
- D: one call per block. User message = `block_prompt_lut.txt` with the block's module name (`Block_<k>`), its boundary nets as
  the only ports (single-bit identifiers), and the block's cells as BLIF. It is the Q-L10 block prompt with the same
  instructions; only the netlist form changed ("gate-level netlist" to "LUT-level netlist (BLIF)", the netlist as BLIF, and
  one paragraph that says what `.names`, `.latch` and `.subckt adder` mean). SHA-256: see "Frozen prompts" below. No example, no
  hint.
- A: the Gate-Breaker `re` prompt of the full run (llm-pilot `re` variant, 2-shot prefix of md5 e5c9110aadcb958b52750e40a8acb9b5
  unchanged, so the two worked examples are gate-level), whole design in one prompt, the dataset prompt text with "gate-level
  netlist" replaced by "LUT-level netlist (BLIF)", the notation paragraph, and the whole BLIF with the prompt identifiers
  (`a_prompt_lut.txt`). Context limit: the cap of the earlier runs, a prompt body (without the prefix) of at most 40000 B (a
  cost cap, 3.2 bytes per token, about 12.5k tokens; not the model's window). A design over the cap has no A row; they are listed
  in `a_limit.csv` and in the results.
- D+h (hint arm) is not run: Q-L10 found the kind hint does not help, and the brief asks for D and A.
- Assembly (`q12_render.assemble`, deterministic, no model): a reply must define `module Block_<k>`; the decoded modules are written
  out and a `TopModule` (interface and widths of the Gate-Breaker netlist of the same design) instantiates them on the netlist
  wires (a top port bit is connected to the original bit, other nets are wires `t_<id>`). A missing block, or a reply without its
  module, is the outcome `assembly`. Every cell of the netlist (constants and buffers too) is in exactly one block.
- Leak gate: no prompt may hold `$n<k>`, `c<k>`, `loki_`, `Prob<k>`, L0, provenance, key.json, level0 (`build_prompts.leak_hits`,
  the pilot's); 0 hits over the system message, all block prompts, the A prompts and all call files.

## Designs

The Q-L10 set: the 43 `vq` problems that Q-L10 ran (28 with cells at gates, 15 without a gate), the 4 over-cap problems of
`vbig` (Prob018, Prob052, Prob105, Prob115) and the 5 processor modules of `ext`. At k4 and k6 the 15 gate-free `vq` problems
still have cells (buffers and constants) and get calls: a call per block, as every other design. Every design is run in full: all
blocks, all draws, including the designs that cut into one block (Q-L10 skipped those; here D on a one-block design is the
LUT netlist in the block wrapper, and the call count with the multi-block designs only is reported beside the full count).
Draws: 3 for `vq` and `vbig`, 1 for `ext` (as Q-L10). Processor modules: `picorv32_pcpi_mul` cannot be read by Odin III
(`picorv32.v:2264:34: non-constant index into 'next_rd' is not supported`); the source is not edited, so `ext` is four designs at k4
and k6. Prob028 and Prob145 (behavioural latches) are not in the set, as before.

## Checks and measures

(i) Block check, per block before assembly: equivalence of the decoded block with its own LUT block by random simulation (Icarus
Verilog, 400 random cycles; `ok`, `mismatch`, `compile`, `inconclusive`, `timeout`; a register still unknown in the reference is
not compared), the check Q-L10 ran at gates; the reference is the faithful Verilog of the block's covers (`q12_render.stub_module`).
(ii) Design check: VerilogEval testbench where one exists (the strict `pass` of the pilot scorer: `Mismatches: 0 in M samples`),
else (processor modules) sequential equivalence of the assembled RTL against the netlist (Yosys flatten, `async2sync`, ABC `dsec`,
register init 0, timeout 600 s). Equivalence is a check, not a proof.
(iii) pass@1 = passes / 3, pass@3 = any of 3, MAJ = at least 2 of 3 (the full run's definitions); for `ext` one draw: pass@1 only.
(iv) AST and CFG similarity to the VerilogEval reference: the Q-L11 scorer (`ql10-blocks/q10_astcfg.py`, Gate-Breaker `metrics.py`
Algorithm 2 and the Odin III CFG probe, numpy kernel), same writer both sides: "flat" (the assembled design flattened to one
module by Odin III, arm A written through the same flatten step; the headline) and "as written" (raw). No AST/CFG for `ext` (no
reference RTL). A value is absent when pyverilog or Odin III cannot read the file.
(v) Provenance: a key construct is a set of at least 2 flip-flops that the Odin III labels (`labels.csv` of the census build, cell
name join, no name guess) give the same construct type and HDL line and column. A block is right for it when it holds at least
0.8 of its flip-flops and the Jaccard index is at least 0.5 (the right-block rule). Per design and arm D: key constructs with a
right block (structure only), and with a right block whose decode checks `ok`. Block recovery without a model (the 0.754 / 0.773 of
the paper) is the structure-only number on the benchmark; this one is on the VerilogEval designs and is a measurement.
(vi) Tokens: per design and arm, from the calls (estimate before; dispatcher log and meter after).

## Tests and verdict rules (fixed now, as Q-L10)

Unit: the design (problem). Seeded problem-level bootstrap, 2000 resamples, seed 20261103. Headline first (CAD reporting
convention): mean difference and W/L/T over designs, then the strict label; a positive difference with an interval touching zero is
INCONCLUSIVE, not DISMISSED.
- H-L12(a), per endpoint: D at the endpoint minus D at gates (Q-L10 rows, same problems and draws, `ql10-blocks/results/results.csv`
  arm D), pass@1 (primary), AST flat and CFG flat (secondary, same rule). SUPPORTED (not lower) when the lower bound of the interval is
  above -0.05 (non-inferior within 0.05, margin set now); CONTRADICTED when the upper bound is below 0; else INCONCLUSIVE. Strata:
  all designs of the set with a gates row, and the multi-block-at-gates designs. 15 gate-free `vq` designs are a script at gates
  and a model at k4 and k6; they are reported apart and in the all-designs figure.
- H-L12(b), per endpoint: D minus A at the endpoint, on designs where both run (A not over the cap), pass@1 (primary), AST flat and CFG
  flat. SUPPORTED (A lower) when the lower bound of D minus A is above 0; CONTRADICTED when the upper bound is below 0; else
  INCONCLUSIVE. Exact two-sided McNemar on MAJ as a second view. Where A cannot run, D stands alone: per design pass@1, pass@3, block
  check share.
- Also reported, no verdict: A at the endpoint minus A at gates (full-run arm A rows), `ext` pass@1 and block check share, the provenance
  numbers of (v), tokens.
- Family and Holm: the confirmatory family is the four pass@1 tests (a) and (b) at k4 and k6 (bootstrap interval rule, and exact McNemar
  on MAJ for the paired view, Holm over the four); everything else is descriptive.
- No number is tuned on these data. The block builder, join rule, thresholds, models and prompts are fixed by earlier committed work and by
  the files of this commit.

## Calls, order, stop rule

One call per (design, endpoint, arm, block, draw); an A call is one per (design, endpoint, draw). `batches.json`: all calls, about 24 per
batch, never spanning a draw; `group` is `core` (vq and vbig, 3 draws) or `ext` (one draw), `ext` last; designs smallest first (total
block prompt bytes), inside a design arm A then the blocks of D, so the arms are interleaved. `batches-D.json` is the same calls
without arm A (same call numbers), in case the controller runs D first. Stop rule as the full run: stop when `api_refused` plus
`no_file` exceeds 12 and exceeds 10 percent of the calls made, or when the weekly meter reads 85 percent; unrun calls are `not_run`.
Counts and the token estimate per arm and endpoint are in the first amendment, from `counts.csv`.

## Blinding deviation (as llm-full and Q-L10, restated)

Subagents keep the harness system prompt and tools and have file and web tools; the reference files and Odin III data sit on the same disk.
The call file carries no problem id, arm, block id, endpoint or draw; the reply goes to an outbox file named by call number. The controller
repeats the tool-use audit. The `re` system message says "flat gate-level netlist" and mentions Loki hints in every arm (a cue, as in A); it is
kept byte-identical to the earlier runs, so at k4 and k6 it describes the netlist as gate-level while the prompt says LUT-level.

## Limits, stated before the run

The two worked examples of the A prefix are gate-level designs (the prefix is pinned by md5; a LUT-level pair would be a different method).
The block prompt has no examples, so D differs from A in the wrapper as well as in the cut; on a one-block design that is the whole difference.
The census netlists are Odin III builds of the reference RTL, not the Yosys gate netlists the gates rows used: the same designs, a different
synthesis, so a difference between endpoints is also a difference of tool. Register initial values are not in a netlist; a reference that
initialises its registers can fail a correct decode. The block check is a random-input simulation; the key covers flip-flop constructs only.
`picorv32_pcpi_mul` is missing at k4 and k6 (Odin III front end). Output-token estimates use the gate-level cell count of the design (the pilot's fit),
shared over blocks by LUT-cell share: an assumption, not a measurement. The estimator of pass@k carries the full run's note: no citation until
verified. Draws are independent but not reproducible (temperature not controlled).

## Frozen prompts

SHA-256: `block_prompt_lut.txt` cbacc5394283bbc8147f7cfd80c8e6393028dcf1a40e338012d459b7783de93e;
`a_prompt_lut.txt` 7639439931d2f2aea16f007746bb244ac7530b1d3690850d89f93e95376d61cb.

## Amendments

- 2026-11-03 (before any model call; plan commit 766d88e): preparation finished. The plan text above is unchanged; the two prompt files
  are unchanged (their sha256 hold). Changes and findings of the preparation:
  1. Glue. The plan said every cell is in one block. As in Q-L10 (where `assign` statements and constants were glue), constants (`.names`
     with no input) and buffers (`.names a y` with the row `1 1`) are `assign` statements of the `TopModule` and in no block
     (`q12_nl.Cell.glue`). Without this, the bit-slice designs would cost one call per wire. A design whose cells are all glue has no block
     and no call at that endpoint (its D row is the fixed assembly, a script): 13 of the VerilogEval problems at k4 (the gate-free ones of
     Q-L10, less those with LUT cells).
  2. Ceiling filter (new, before any call). `q12_stubcheck.py` assembles the faithful decode of the whole LUT netlist and scores it with the
     VerilogEval testbench (`results/stubcheck.csv`): 80 of 94 design-endpoint pairs pass. The 14 that do not (7 problems, both endpoints) have a
     netlist that is not the function of the reference, so no reply can pass: Prob088, Prob089, Prob118 (asynchronous reset in the reference;
     the BLIF latch has none), Prob151, Prob156 (Odin III builds a patched copy of the reference, the testbench runs the original), Prob071
     (Odin III reads the `casez` with `z` as a constant), Prob139 (not explained). They have no call. The designs of the test set are
     therefore 40 problems per endpoint (not 47) and 4 processor modules (`picorv32_pcpi_mul` not built). Prob156 was the only VerilogEval
     problem of the set with hard adders, so at k6 hard blocks occur only in the processor modules. For the processor modules the faithful
     decode is the equivalence reference by construction (no ceiling test).
  3. Blocks. Loki's blocks at k4 / k6 for the 40 + 4 designs (`blocks_summary.csv`): Loki cuts a vector of independent bit gates into one
     block per bit at these endpoints (Prob092_gatesv100 298 blocks, Prob017_mux2to1v 100, Prob043_vector5 20, Prob097_mux9to1v 15; at gates
     they were 2, 2, 10 and 2 blocks). Those bit-slice designs cost most of the D calls (see counts). The 1-cell blocks give the model no word-level context.
  4. Counts (`counts.csv`; one call per prompt and draw; 3 draws for `core`, 1 for `ext`): all calls 3462 (D 3221, A 241): core 3408, ext 54.
     Batches of about 24: 147 (`batches.json`), 135 for D alone (`batches-D.json`). Per endpoint:
     k4: D 1610, A 121; k6: D 1611, A 120. D on the multi-block designs only (the Q-L10 rule): k4 1598, k6 1599 (no saving, because at these
     endpoints almost every design cuts into several blocks). D on designs of at most 64 blocks (leaving out the bit-slice designs
     Prob092 and Prob017): k4 416, k6 417. Arm A runs on 40 problems per endpoint under the 40000 B cap, including the four over-cap problems
     of `vbig` (their LUT netlists fit; at gates A could not run) and, among the processor modules, only `tinyriscv_clint` at k4 (39923 B).
     A is over the cap (no A row; `a_limit.csv`) for picorv32_pcpi_div (70574 B at k4, 66917 B at k6), tinyriscv_div (89181 / 77830 B),
     tinyriscv_csr (120880 / 136371 B) and tinyriscv_clint at k6 (40598 B).
  5. Token estimate (an estimate, not a measurement: prompt bytes / 3.2 plus the system message per call as input; output 113 per call +
     0.36 per gate-level cell of the design, the fit of the 40 pilot arm A replies, shared over the blocks by LUT-cell share; harness overhead
     of each subagent not included): k4 D alone 1,259,843 in + 191,764 out = 1,451,607; k4 D + A 1,614,318 + 211,863 = 1,826,181.
     k6 D alone 1,262,111 + 191,881 = 1,453,992; k6 D + A 1,603,055 + 211,393 = 1,814,448. Both endpoints, D alone 2,521,954 + 383,645 =
     2,905,599; D + A 3,217,373 + 423,256 = 3,640,629. Per batch 6.0k to 133.9k tokens. Scale against the meter: Q-L10 moved the weekly meter
     about 0.0065 points a call (1233 calls, 8 points); 3462 calls at that rate is about 22 points, an upper guide (many block calls here are
     one-cell blocks, much smaller than Q-L10's average).
  6. Leak gate: 0 hits over the system message, 3221 block prompts, 241 A prompts and all 3462 call files (`q12_build.py calls` stops on a hit).
  7. Dry run (`q12_dryrun.py`, `dryrun_result.json`): 305 stub replies for 9 designs (a constants-only one, a one-block combinational one, two
     multi-block register designs, an FSM, a mux tree, an over-cap shift register, a LUT-and-adder processor module), faithful RTL for draw 1
     and one of five patterns (faithful, outputs of block 0 tied low, syntax error, no markers, wrong module name) afterwards: 87 design rows,
     all outcomes as expected (0 unexpected, 0 timeouts), 244 of 262 blocks check `ok` (the rest are the injected faults), the assembled
     `tinyriscv_clint` is `equiv` by `dsec` and `neq` with one LUT inverted, the AST/CFG scorer returned values for 20 rows. Two defects the
     dry run found are fixed in the code: a sum of minterms gives X after an unknown reset where the reference does not (the stub now writes
     a Shannon tree of `?:`), and ABC cannot read the sync-reset flops Yosys makes (`dffunmap` added to the equivalence preparation).
  8. Deviations from the brief's wording: the block check is the Q-L10 one (400 random cycles in Icarus Verilog against the faithful Verilog of
     the block's covers), not Odin III + ABC `cec`; Q-L10 did not use Odin III + ABC for it. The design check of the processor modules uses
     Yosys + ABC `dsec` as Q-L10 did. Odin III is used (read only) for the netlists, the block builder's graphlet pass and the AST/CFG flatten.
  9. Run choice (Peter 2026-11-03, before any call; recorded here before the first call): the reduced run. Arm A on every design that has an
     A call, and arm D on the designs of at most 64 blocks, i.e. without D on the bit-slice designs Prob092_gatesv100 and Prob017_mux2to1v
     (counts row "D designs of at most 64 blocks"). Both endpoints: 1074 calls (k4 537 = D 416 + A 121; k6 537 = D 417 + A 120). One endpoint
     per run, k4 first, then k6. Order, batching and template unchanged: the calls of `batches.json` filtered to the endpoint and the
     subset, in their order and batch (batches shrink to the kept calls; 50 batches at k4). Prob092 and Prob017 still get arm A; for them
     the D-vs-A and D-vs-gates comparisons have no D row, and the analysis states this. Before the run the user message of all 537 k4 call
     files was hashed and equals `calls_table.csv` prompt_sha256 (0 mismatches). The stop rule is unchanged (85 percent weekly meter, checked
     before the run and between the endpoints; refused plus no-file above 12 and above 10 percent of calls made, checked after each batch).
