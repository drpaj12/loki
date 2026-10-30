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

(none yet)
