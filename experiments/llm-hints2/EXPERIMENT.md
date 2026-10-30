# Loki hints v2 on Q3 and Q4: linked hints, 4 arms, 3 draws

Plan written before the runs, dated 2026-10-30. This file is committed and pushed first; its commit
SHA is the plan-provenance SHA for the results. A later change is a dated entry under "Amendments";
the old text stays. Protocol base: `experiments/llm-full/EXPERIMENT.md` (scorer, MAJ, draws, stop
rule, dispatch route stay as there; only the arms, the prompt and the population change).

## Plain-English summary

The full run (llm-full) found that Loki hints v1 did not help: arm A (netlist only) and arm B (netlist
plus hints) were level (A minus B +0.010, interval -0.017 to +0.036). Two defects of that test are
fixed here. First, the v1 claims were weak (no counter kind, empty FSM claims, duplicates, every role
"datapath", nothing about what a register does). Second, the model was never told what the hints are
or how to use them, and could not show that it did. This run gives the model better claims (Loki
claims v2, Part A of the brief), written as one plain-English line per claim with a probability, and
linked into the netlist as a comment on the line of each cell the claim covers. The prompt explains
the hints and asks the model to name the claims it used. Test set: the 64 Q3 and Q4 problems of the
llm-full selection (Q3 34, Q4 30), where arm A was not at the ceiling (Q3 0.86, Q4 0.79 pass@1).

Purpose chain (hub `docs/purpose.md`): Loki L Q1.2 (do Loki's hints help a language model recover RTL
from a gate netlist). Measure: functional pass rate of the recovered RTL under the llm-full strict
scorer, MAJ (at least 2 of 3 draws) as the unit, plus pass@1. Gate-Breaker (section VI) recommends
bus clustering, datapath versus control classification and partitioning as tool help; v2 claims
carry those three.

## Hypotheses

- LLM5 (hints v2 help): the model recovers working RTL more often with v2 hints linked in the
  netlist than from the netlist alone. Test: B2 against A2.
- LLM6 (the model uses the hints): if it does, hints with the wrong content (W) hurt. Test: W against
  A2, expected W < A2; and the use rate (CLAIMS-USED not none) and the pass rate per claim kind when
  a claim of that kind was named.
- Separating the prompt change from better hints: B1' (hints v1 with the new prompt) against A2 and
  B2 against B1'.

## Population (n = 64)

The Q3 (34) and Q4 (30) problems of `experiments/llm-full/selection.csv`, same exclusions. Q1 and Q2
are left out: arm A passed 0.96 and 0.92 there, no room for a gain. Memorisation is not controlled
here (no interface-only arm; Peter 2026-10-30: obfuscate later with ABC).

## Arms (64 problems x 3 draws = 192 calls per arm, 768 calls)

| arm | netlist | hints | prompt |
| --- | --- | --- | --- |
| A2 | flat netlist | none | new prompt, Notes section, no hint explanation |
| B1' | flat netlist | hints v1 (the llm-full hints, unchanged) | new prompt with hint explanation and CLAIMS-USED |
| B2 | netlist with `// loki hN ...` comments on covered cells | hints v2 | as B1' |
| W | netlist with comments of the wrong claims | hints v2 content moved to other cells/nets of the same netlist, kinds and p kept | as B1' |

New prompt: the Gate-Breaker system prompt as close as possible, plus for every arm one section
"Notes:" before `[BEGIN]` (at most about 10 lines), and for hint arms an explanation of the hints
(what a claim, p, proved and candidate mean; candidates can be wrong) and a required last line after
`[DONE]`: `CLAIMS-USED: h7,h2,...` or `none`. The scorer reads only between the markers
(unchanged). Hints never contain names from the reference RTL; the v1 leak gate (0 hits on the system
message, the user messages and the call files) is kept.

Calls: one fresh Sonnet subagent per call, the llm-full mechanism (call file, outbox file, Sonnet
dispatcher subagents, at most 6 batches of at most 24 calls each), no retry, no rewording. This lane
builds the call files and makes no model call.

## Statistics

Unit: the problem. Primary: B2 against A2 on MAJ, exact two-sided McNemar on discordant problems
stratified over Q3 and Q4 (pooled discordant pairs, binomial p = 0.5, as llm-full). Planned tests
(Holm family): B2 vs A2, B2 vs B1', W vs A2, each as stratified (Q3, Q4 and pooled: 9 tests). Holm
over the 9. Descriptive: mean pass@1 difference with a problem-level bootstrap 95% interval (2000
resamples, seed 20261030). Use rate and pass rate per claim kind are reported as counts, not tested
in the family.

## Verdict rule and minimum gain

Planned minimum gain: +0.05 in mean pass@1 (B2 minus A2). Verdicts, as the full run:
USEFUL / POSSIBLY GOOD only with Holm p < 0.05 and the 95% interval excluding 0 (USEFUL when the
interval also lies above the minimum gain, POSSIBLY GOOD otherwise); DISMISSED when the interval
rules out the planned minimum gain (upper end below +0.05); otherwise INCONCLUSIVE. LLM6 is
supported when W minus A2 is negative with Holm p < 0.05 and the use rate in B2 is above 0.5.
Power note: with 64 problems and arm A near 0.75, a +0.05 gain is only detectable if discordant
pairs are several; an INCONCLUSIVE outcome is the likely alternative to a clear effect and is
reported as such.

## Stop rule

As llm-full: stop when `api_refused` plus `no_file` exceeds 12 and exceeds 10 percent of calls made,
or at the weekly meter reading 85 percent (the controller's rule at run time).

## Amendments

- 2026-10-30 (before any model call): preparation, committed after the plan commit 999c4cf.
  What was built and how it differs from the plan text above:
  1. Claims v2 are a new layer, `loki/intent/` (Part A of the brief), read by `loki re --intent`
     as `intent.json`; the L1 loop and its scoring are not changed. Sequential claims (counter,
     shift register, LFSR, multi-mode register, state machine) come from the flip-flop groups of
     the final graph; each is checked against the original netlist (`loki.intent.verify`, 512
     random vectors, independent of Loki's graph) and dropped if it fails (0 of 58 failed, 1
     could not be checked). Overlay claims (comparison, adder, bus, ...) are shown only when
     their probability is at least 0.9 under `calib/f3.json`; one- and two-gate comparisons and
     the `datapath_unit` container are left out.
  2. Probabilities. Overlay claims print `p_comp` of a run with `calib/f3.json`. Sequential claims
     print the posterior mean of Beta(1,1) after the checks, per kind (`calib/intent-f3.json`).
     The fit is in-sample: the 73 other llm-full problems (Q1, Q2) contain no sequential logic,
     so the 57 checked claims all come from the 64 problems of this run (counter 11, FSM 18,
     shift register 26, LFSR 1, register 1); the checks use netlist semantics only, never the
     reference RTL or any model result. A kind with one claim has p=0.67. Roles carry the
     probability of the claim whose sink a control net is; data roles carry none.
  3. Arm B1' uses the frozen v1 hint blocks (`hints_v1/`, regenerated at 414e159): they rebuild the
     llm-full arm B user messages for 64 of 64 problems (sha256 equal). Arm W moves every wire
     name of every claim inside its class (primary input, state output, other wire; the clock
     is never used) by a seeded permutation per problem; the comments in the netlist move with
     them.
  4. Prompt: the system message is the llm-full `re` message (md5 checked). The user message
     ends with a format instruction (`Notes:` of at most 10 lines, then [BEGIN] ... [DONE]; hint
     arms add the last line `CLAIMS-USED:`), and hint arms carry a paragraph that explains
     claim, p, proved and candidate (a v1 version for B1', which has uncalibrated
     confidences). `promptv2.py` has the exact text. 28 of the 64 problems have no v2 claim
     (small combinational or dff-only designs): their B2 and W prompts say so.
  5. Build result: 64 problems x 4 arms = 256 prompts, 768 calls, 33 batches (11 per draw, the
     last of each draw has 16 calls). Leak gate: 0 hits on the system message, the 256 user
     messages and the 768 call files. Largest user message 68644 bytes (B1p, Prob118, about
     21.5k tokens), arm means A2 7.0 kB, B1p 17.1 kB, B2 9.5 kB, W 9.5 kB. Token estimate
     (prompt bytes / 3.2 plus the mean pilot reply per arm): input 2,583,393, output 95,424.
     Dry run (`dryrun_result.json`): 72 fake replies score as expected, 0 timeouts, the
     CLAIMS-USED fields and the analysis run.

- 2026-10-30 (before any model call): fix round after review of PR 62. Nothing below depends on
  any model result; there is none. These amendments supersede the wording of the amendment above
  where they differ.
  1. Arm W, new construction (supersedes "inside its class"). The first W kept every claim inside
     the classes input / state / other wire, so its `// loki` comments landed on largely the same
     flip-flops as the true ones (mean tag overlap 0.63; 17 problems at or above 0.64; Prob041_dff8r
     1.0), which made W only weakly wrong. Now every net a claim names (`wires`, `nets`, the net
     fields of `facts`, bus bits, `net_roles` keys) is moved by a seeded map to a wire that no claim
     names and whose driving line carries no true tag, across classes (`netlink.permutation`);
     ids, kinds, p, text and format are kept. Where the claims cover most of a small netlist the
     free wires run out: a net the hint text never prints then reuses an untagged wire (W has fewer
     tags), and a printed net takes a tagged line whose true tags exclude every claim that names
     it. Of 40 seeded candidates per problem (`hints2-w:<problem>:<k>`) the one with the fewest
     shared (line, claim id) tags is kept, so W is a function of the problem name. Result
     (`wrong_overlap.csv`, `wrong_overlap.py`; 36 problems with claims; a tag is a (line, claim id)
     pair): share of the true tags that W also has on the same line, mean 0.182, max 0.333; share of
     W's tags that are true, mean 0.280, max 0.857; 13 of 36 problems below 0.2 on the worse of the
     two, 31 of 36 at or below 0.5. The aim of 0.2 per problem is not reached for every problem; it
     cannot be where one claim covers most of a small netlist. The 5 problems above 0.5
     (Prob041_dff8r, Prob086_lfsr5, Prob136_m2014_q6, Prob121_2014_q3bfsm, Prob133_2014_q3fsm) are
     marked `excluded` and are left out of every comparison with W (W vs A2) in the analysis; their
     calls are still made. Size: W user messages are 98.7% of B2's in bytes (hint text 95.6%).
  2. p of sequential claims (counter, shift register, LFSR, register, state machine) is a per-kind
     constant: the Laplace posterior of "the extracted next-state function matched the netlist it
     was extracted from" (57 of 57 held). It measures that the extraction is consistent with the
     netlist, not that the claim states the designer's intent. The analysis must not treat the
     per-claim p as informative, and none of the analyses uses p as a covariate. p of overlay
     claims is the calibrated `p_comp` of `calib/f3.json`.
  3. Calibration is in-sample only. `calib_intent_report.csv` has train_n 0 for every kind: all 57
     checked claims come from the 64 problems of this run, so there is no held-out or
     out-of-sample calibration figure for the intent claims.
  4. The earlier statement that v2 is "not worse than v1" in calibration (A6) is withdrawn.
     `l1_calibration_compare.csv` counts 0 v2 claims on the L1 benchmark (v2_counted 0, because v2
     overlay claims need p of at least 0.9), so the comparison of ECE is vacuous. No claim of
     improved or equal calibration is made.
  5. Secondary analysis, stated before the calls: 28 of the 64 problems have no v2 claim (their B2
     equals A2 plus the prompt text, and W equals B2). The same rule (MAJ, exact McNemar stratified
     over Q3 and Q4, 9 tests, Holm) is also run on the 36 problems with at least one v2 claim, as
     its own Holm family. It is labelled secondary and gives no verdict; the verdict stays with the
     64-problem primary. `analyze_hints2.py` prints it.
  6. Confound: A2 has no hint explanation and no `CLAIMS-USED` line, B1', B2 and W have both. B2 vs
     A2 therefore differs by the hints and by those two prompt parts together; B2 vs B1' (same
     prompt) isolates the content of the hints.
  7. Prompt wording: "candidate" now covers every claim that is not proved, including a claim
     checked on sampled inputs only; for a proved claim p is Loki's own estimate of the
     reliability of its checks (see 2), not a measure of designer intent.
  8. LLM6 sign: W minus A2 is negative when W-only problems are fewer than A2-only problems in the
     MAJ discordant counts (the counts that give its p), not the pass@1 difference.
  9. Leak gate extended: besides the v1 patterns (0 hits), the identifiers of the reference RTL
     that are not ports, keywords, numeric-literal digits, comments, or words of the netlist, the
     dataset prompt, the system message or our fixed templates (30 names over the 64 problems) are
     searched as whole words in the system message, the 256 user messages and the 768 call files:
     0 hits.
  10. Build after the fixes: 768 calls, 33 batches, estimated tokens in 2,592,156, out 95,424;
     the v1 blocks rebuild the llm-full arm B messages for 64 of 64 problems; every `hN` of
     `hints_v1/` has a kind (checked by the build). Dry run: 72 fake replies as expected, 0
     timeouts, CLAIMS-USED fields and analysis run.

- 2026-10-30 (amendment 11, before the calls): the weekly stop is raised from 85 to 97 percent. Peter,
  2026-10-30: "Don't stop - go until 97% and then we'll talk". This replaces the 85 percent in the
  stop rule above; the refusal stop rule is unchanged. The calls ran with the 97 percent stop. The
  meter never passed 89 percent.

## Results (2026-10-30)

Plan written before the runs; the verdict rules are the ones that plan set, applied unchanged. No
model call and no re-scoring was done for this section. Tracked outputs are in `results/`
(`results.csv`, `summary.md`, `dispatch-log.tsv`, `status.csv`, `transcript-audit.txt`,
`blinding-probe-hints2.txt`); the call files, prompts and replies stay in the git-ignored `run/`,
no raw replies are committed.

### Plain English

All 768 calls were made: 762 produced a file (ok) and 6 did not (no_file: calls 107, 120, 160, 230,
342, 639; the model replied in chat and wrote no file), 0 api_refused, 0 timeouts. Outcomes: pass 645,
runtime 109, compile 8.

The primary test did not find a gain. Under the rule fixed in advance (a problem counts if it
passes in at least 2 of 3 draws; exact stratified McNemar; Holm over 9 tests) B2 against A2 is
INCONCLUSIVE: 4 problems only B2 passes, 0 only A2 passes, Holm p = 1.0. The test is underpowered:
A2 already passes 54 of 64 problems by that measure, so only a handful of problems can differ, and
4 against 0 cannot reach p < 0.05 after Holm.

The softer measures point the same way, on Q4. Mean pass@1 on Q4 is A2 0.744, B1p 0.800, B2 0.933,
W 0.789; on Q3 all arms sit at 0.85 to 0.87. Over all 64 problems B2 minus A2 is +0.099 with
interval [+0.052, +0.151], and B2 minus B1p is +0.073 [+0.031, +0.115]. Pass@3 is 0.906 for A2, B1p
and B2 (W 0.875): the v2 hints make single draws more consistent, they do not raise the best-of-3
ceiling. When a B2 call names a claim, it passes: FSM claims used in 57 B2 calls, 57 pass; counter 24
of 24. In W (wrong claims) FSM claims used in 33 calls, 27 pass, against 24 calls where an FSM claim
was offered and not used, 19 pass (0.82 against 0.79: no difference). A used wrong FSM hint passed less
often than a used right one (27/33 against 57/57), but on different problems: not a paired test.

What this does and does not show. It does not show, under the pre-stated rule, that v2 hints help.
It also does not show they do not: the test could not have said yes on this ceiling. The pass@1
interval and the claim-use table suggest B2 helps on Q4 and that the model reads and uses FSM and
counter claims. This is a pointer to a better-powered test (harder problems, lower A2 ceiling), not
a verdict.

### Headline

| stratum | arm | problems | pass@1 | pass@3 | MAJ |
| --- | --- | --- | --- | --- | --- |
| Q3 | A2 / B1p / B2 / W | 34 | 0.853 / 0.853 / 0.873 / 0.863 | 0.882 all | 30/34 all |
| Q4 | A2 | 30 | 0.744 | 0.933 | 24/30 |
| Q4 | B1p | 30 | 0.800 | 0.933 | 26/30 |
| Q4 | B2 | 30 | 0.933 | 0.933 | 28/30 |
| Q4 | W | 30 | 0.789 | 0.867 | 25/30 |
| all | A2 | 64 | 0.802 | 0.906 | 54/64 |
| all | B1p | 64 | 0.828 | 0.906 | 56/64 |
| all | B2 | 64 | 0.901 | 0.906 | 58/64 |
| all | W | 64 | 0.828 | 0.875 | 55/64 |

Mean pass@1 difference (problem-level bootstrap 95% interval): B2 minus A2 +0.099 [+0.052, +0.151];
B2 minus B1p +0.073 [+0.031, +0.115]; W minus A2 +0.026 [-0.021, +0.073]; B1p minus A2 +0.026
[-0.021, +0.073].

### Verdicts

- LLM5 (hints v2 help; B2 vs A2): INCONCLUSIVE. Stratified MAJ discordant 4 against 0, Holm p = 1.0000
  (Q3 0, 0; Q4 4, 0). Mean pass@1 +0.099 [+0.052, +0.151] is above the minimum gain of 0.05 but the
  pre-stated MAJ rule is not met. Secondary (pass@3): 0 against 0. Secondary on the 36 problems with
  claims (own Holm family, no verdict): 4 against 0, Holm p = 1.0000. B2 vs B1p (prompt held fixed):
  2 against 0, Holm p = 1.0000, pass@1 +0.073 [+0.031, +0.115].
- LLM6 (the model uses the hints; W vs A2): not supported (DISMISSED in the register). MAJ W only 2,
  A2 only 2, Holm p = 1.0000, 59 problems (5 left out as too similar to the true claims); pass@1 W
  minus A2 +0.026, wrong sign for the hypothesis. Use rate: B2 107 of 192 calls name a claim (B1p
  116, W 60).

Claim use (CLAIMS-USED line), selected rows: B2 fsm 57 calls using, 57 pass; counter 24, 24; shift_reg
15, 15; eq_const 11, 10. W fsm 33 using, 27 pass; fsm offered not used 24, 19 pass.

### Deviations

1. Stop rule: amendment 11 above (97 percent). The meter never passed 89 percent, so no stop fired.
2. Transcript audit (`results/transcript-audit.txt`): 768 calls audited, 0 touched any path other
   than their own call file and outbox file, 0 used other tools. 26 used more than the expected two
   tool calls: paged Reads, double Writes, and 6 calls (0173, 0238, 0240, 0493, 0749, 0751) that
   used Edit twice on their own outbox file, a deviation from the Write-only
   instruction. All are scored as made.
3. Blinding: as in llm-full, the call subagents were not blind to the workspace context (probe
   `results/blinding-probe-hints2.txt`: the workspace CLAUDE.md, the memory index, the caveman hook,
   the Agent, Bash, Edit, Read, Skill, ToolSearch, Write and Docs tools). Evidence from behaviour only.
4. Six no_file calls (107, 120, 160, 230, 342, 639) are scored as failures (strict: no pass = fail).
5. Confound and power: A2 differs from B2 by hints and by the hint explanation and CLAIMS-USED line;
   B2 vs B1p isolates the hint content. A2 is near ceiling (MAJ 0.84), so the primary test is
   underpowered. p of sequential claims is a per-kind constant and was not used as a covariate.
