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
