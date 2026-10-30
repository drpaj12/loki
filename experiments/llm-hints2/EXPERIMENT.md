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
