# Loki full LLM run: 137 problems, arms A/B/C, 3 draws

Plan written before the runs. This file is committed and pushed first; its commit SHA is the
plan-provenance SHA for the results. A later change is a dated entry under "Amendments"; the old
text stays. Protocol base: `experiments/llm-pilot/EXPERIMENT.md` (decisions 1 to 14 there stay in
force; only n and the number of draws change).

## Plain-English summary

Question: if an LLM is asked to write the RTL for a flat gate netlist, does it do better when Loki's
structural hints are added? The pilot ran 40 problems once per arm and could not separate the arms
(35/40 against 35/40). This run asks the same question on every eligible problem of the four
quartile files (137 problems), three independent attempts (draws) per problem and arm. Three arms:
A (netlist only), B (netlist plus Loki hints and the designer-prior sentence), C (interface only, no
netlist: a memorisation control). Each attempt is a fresh Sonnet subagent that sees one prompt and
writes one reply file. A reply passes when the generated `TopModule` gives `Mismatches: 0 in M
samples` (M > 0) against the reference testbench in Icarus Verilog 12.0 and uses no hidden harness
module. Nothing about the model calls is made by this lane: it only prepares them.

Purpose chain (hub `docs/purpose.md`): Loki L Q1.2 (do Loki's hints help an LLM recover RTL from a
gate netlist), related L Q1.1 (recovery without hints). Measure: functional pass rate of the
recovered RTL, as pass@1 and pass@3 over the three draws, per quartile and stratified.

## Population (n = 137)

Every problem of `quartiles/{low,mid-low,mid-high,high}_quartile.txt` of the Gate-Breaker VerilogEval
clone (head d60f0b10458746e2fefc2a98fa2455b77a32e8be): 41 + 36 + 36 + 31 = 144 problems. Seven are
excluded; each reason is one of the pilot's own rules. List and values: `excluded.csv`.

| problem | quartile | reason |
| --- | --- | --- |
| Prob018_mux256to1 | Q1 | dataset prompt 69426 B, over the pilot's 40000 B cap (pilot Design: eligible prompts only) |
| Prob052_gates100 | Q2 | prompt 56405 B, over the cap |
| Prob105_rotate100 | Q3 | prompt 79721 B, over the cap |
| Prob115_shift18 | Q4 | prompt 78899 B, over the cap |
| Prob099_m2014_q6c | Q2 | pre-flight: the reference fails its own testbench (testbench ports Y2, Y4 are not ports of the reference); pilot rule: a problem whose reference fails the pre-flight is replaced or dropped |
| Prob028_m2014_q4a | Q2 | arm B hints cannot be built: `loki re` stops because the cmos6 library of Odin III has no latch cell (`$_DLATCH_P_`); pilot rule: fail the problem if hints cannot be made |
| Prob145_circuit8 | Q3 | same latch-cell failure |

The three failing-hint or failing-reference problems are dropped from all arms, so the design stays
paired. Population: Q1 40, Q2 33, Q3 34, Q4 30 (selection.csv). Limitation carried from the pilot:
the cap removes the four largest prompts, so the biggest designs are under-represented. Dropping the
cap would add the four large problems (prompts of 56 to 80 KB, about 18k to 25k tokens for each
arm A or arm B call) and is an amendment, not a default. 7 excluded plus 137 kept equals 144;
pre-flight over the 137 kept: 137 of 137 references pass.

## Arms, prompts, calls

Identical to the pilot's `re` variant (decision 14): same `re` system message (md5
c95998c379b2d7e520c508b25a5a4c92), same 2-shot prefix (md5 e5c9110aadcb958b52750e40a8acb9b5), same
`[BEGIN]`/`[DONE]` format, same arm B hints (`make_hints.py`, `netmap.py`, from the flat netlist
alone, nothing dropped, helper nets for unresolved internal nets), same arm C cut. The scripts in
`experiments/llm-full/` import the pilot's modules (`fullcfg.py` points them at this directory);
nothing is copied. Check: the user-message sha256 of all 120 (problem, arm) pairs shared with the
pilot equals the pilot's `prompt_sizes_re.csv`.

- 137 problems x 3 arms = 411 prompts; x 3 draws = 1233 calls (the brief's 1296 minus 7 x 9).
- Leak gate (`build_prompts.leak_hits`): 0 hits on the system message, all 411 user messages and all
  1233 call files.
- Draws are independent fresh subagents given byte-identical call files. The call file carries no
  draw number, problem id, arm or path.
- One call file per call: `run/calls/call-NNNN.txt` = system message, then user message, with two
  delimiter lines. The subagent reads that file and writes its whole reply (the `[BEGIN]`..`[DONE]`
  block) to `run/outbox/resp-NNNN.txt`. `collect_full.py` copies the outbox file to the call's
  `reply_path` `run/responses/<arm>/<draw>/<problem>.txt`, so the subagent never sees a problem id.
  Template text: `CALL-INSTRUCTIONS.md`.
- Order: draw-major (draw 1 for every problem, then draw 2, then draw 3); inside a draw by arm A
  user-message size ascending; per problem arms in the pilot's A/B parity order, then C. A partial
  run is therefore balanced per problem and complete for the smallest problems first.
- Batches: `batches.json`, 54 batches of 24 consecutive calls (8 problems x 3 arms), never spanning
  a draw (each draw ends in a batch of 3). The controller checks the weekly meter between batches.
- Token estimate (prompt bytes / 3.2 as in the pilot, plus mean pilot reply size per arm): input
  3,197,745 tokens, output 157,413, total 3,355,158 over 1233 calls; per batch 33k to 206k input
  tokens. This excludes the harness overhead of each subagent (its own system prompt, CLAUDE.md,
  memory index and tool schemas), which the repo does not measure: read it from the meter after
  batch 1.

## Scoring and statistics

Scorer: the pilot's `score.py` (strict `pass`; `gb_pass` beside it), unchanged, timeouts pinned (30 s
simulation, 60 s compile). A valid run has `timeout` and `compile-timeout` counts of 0.

Unit: the problem. For problem p and arm a, c is the number of passing draws (0 to 3). A call with
no reply, an API refusal or a declined reply is a fail (strict view, as the pilot); the paired view
(problems where every call of both arms in a comparison was answered) is reported beside it.

- pass@k per problem: the unbiased estimator `1 - C(n-c, k) / C(n, k)` with n = 3 draws and k = 1,
  3 (so pass@1 = c/3 and pass@3 = 1 when c >= 1). No citation is given for the estimator here: the
  candidate source (Chen et al. 2021) is not yet verified, and Gate-Breaker's `sv-iv-analyze` uses
  a different, "any of k" definition. The paper text must verify the source before citing. Reported per arm and
  quartile as the mean over problems.
- Tests need one yes/no value per problem and arm. Primary: MAJ = the problem passes in at least 2 of
  its 3 draws. Secondary: ANY = pass@3 equals 1. Draws are exchangeable, so draw-by-draw pairing is
  not used.
- Comparisons: A against B (does Loki help) and B against C (does the netlist matter beyond
  memorisation). A against C is reported as exploratory.
- Per quartile: exact two-sided McNemar test on the discordant problems (`pilot_stats.mcnemar`).
- Stratified test over the four quartiles: the matched-pairs form of the Cochran-Mantel-Haenszel
  test (strata = quartiles, each problem a matched pair). Its exact version is used: the discordant
  problems of all strata are pooled and tested against p = 0.5 with the exact two-sided binomial
  (the same function as McNemar on the pooled counts). Pooling is valid because under the null each
  discordant problem is equally likely to favour either arm in every stratum.
- Family: the 10 tests per outcome definition (2 comparisons x (4 quartiles + the stratified test)),
  Holm step-down adjustment over the 10; the primary outcome MAJ is the confirmatory family, ANY is
  reported with its own Holm family. The mean pass@1 difference with a problem-level bootstrap 95%
  interval (2000 resamples, seed 20261029) is descriptive.
- A claim needs an adjusted p below 0.05 in the primary family. Per-quartile cells of 30 to 40
  problems have little power; a null result is reported as such.
- Also reported: outcome codes per arm and draw, refusal and no-file rates, label agreement and
  uptake counts from the pilot `summarize.py` for arm B (secondary, counts only), model id from the
  subagent, and the pilot's 40 problems as a subset (their prompts are byte-equal to the pilot's;
  the pilot's single draw is shown beside this run, not pooled with it).

## Stop rule

Calls are never retried and never reworded (pilot decision 13). An API safeguard refusal is
`api_refused`; a subagent that declines or answers in chat without writing the file is `no_file`.
After each batch the controller counts non-ok calls among the calls made. Stop and report when the
count of `api_refused` plus `no_file` exceeds 12 and also exceeds 10 percent of the calls made, or
when the weekly usage meter reads 85 percent. A stopped run is analysed as run; unrun calls are
`not_run` (fail in the strict view) and the analysis says how many.

## Blinding deviation (decision 11, restated)

Subagents keep the harness system prompt and tools; the pilot system message cannot replace it. Each
call is a fresh subagent with no prior turns, but it has file and web tools loaded, and the workspace
CLAUDE.md and a memory index in context. The reference files sit on the same disk; only observed
behaviour keeps the model from them. The call file carries no problem id and the reply goes to an
outbox file named by call number, which reduces what the prompt reveals; it does not change the
deviation. The pilot's transcript audit found no tool use other than Read of its own call file and
Write or Edit of its own reply file; the controller repeats that audit (tool names per call) for this
run and any exception stays scored and is listed. The `re` system prompt mentions Loki hints in every
arm, including A and C (a cue, the same in all arms). Calls are not sampled at a controlled
temperature, which is why draws are independent but not reproducible.

## Dry run (no model)

`dryrun_full.py` writes fake replies into an outbox for six problems (reference solutions as
`TopModule`, or a wrong module, a syntax error, a reply without markers) over all three arms and
draws by a fixed pass pattern, then runs outbox placement, `collect.py`, `score.py` and the analysis.
Every call without a reply is `not_run`. Result in `dryrun_result.json`: all 54 fake replies score as
expected, 0 timeouts, pass counts per (arm, problem) match, pass@1 and pass@3 means match the
hand-computed values (arm A 0.5556 and 0.8333 on the six problems), the paired tests and Holm run.

## Amendments

- 2026-10-29 (before any model call): preparation committed after the plan commit 5a780d4. The
  scripts, `selection.csv`, `excluded.csv`, `hints_stats.csv`, `hint_failures.csv`,
  `prompt_sizes_full.csv` (sha256 of every user message), `batches.json` and `dryrun_result.json`
  are tracked; `run/` (prompts, call files, calls.jsonl, hints) is git-ignored and rebuilt by
  `make_hints_full.py` then `build_full.py`. Leak gate: 0 hits (system message, 411 user messages,
  1233 call files). User-message hashes equal the pilot's for all 120 shared (problem, arm) pairs.
  Dry run: 54 fake replies score as expected, 0 timeouts. Wording fix to the plan text only: the
  exclusion reason for Prob099 reads "ports Y2, Y4 not in the reference" in `excluded.csv`.
- 2026-10-29 (before any model call): dispatch route. The call subagents are as planned (one fresh
  Sonnet subagent per call, the CALL-INSTRUCTIONS.md template verbatim, no resumed subagent, no
  retry or rewording). They are spawned by a Sonnet dispatcher subagent acting for the controller,
  not by the controller session itself, so that 1233 replies do not pass through the controller's
  context. One dispatcher runs at most 6 batches (144 calls), checks the weekly meter before each
  batch and stops at 85 percent, writes `run/dispatch-log.tsv` and `run/status.csv`, and reports
  counts only. The controller checks the meter between dispatcher runs. The first dispatcher first
  runs one blinding probe (not a problem: which tools and files the subagent can see, its model
  name), logged to `run/responses/blinding-probe-full.txt`, because a subagent spawned by a subagent
  may see a different tool set than the pilot's. The dispatcher records the tool-call count each
  call reports; the transcript audit after the run checks every call used only Read of its call file
  and Write of its outbox file.
