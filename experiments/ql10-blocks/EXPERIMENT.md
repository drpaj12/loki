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
