# Result: run `re` (Decision 14)

Purpose: L Q1.2, do Loki hints help an LLM recover RTL from a flat gate netlist. Measure:
functional pass rate per arm (A netlist, B plus Loki hints, C interface only), plus refusal rate.
Model claude-sonnet-5-5 (subagent calls). 40 problems per arm, one draw each: this is a pilot, not
a powered test. Pass is the strict scorer; the Gate-Breaker-equivalent count is a cross-check.
Source: `results/re/{status,results}.csv`, `summary.md` (summarize.py tables), tables below from
`pilot_stats.py --run results/re --standard results/standard`.

Run facts: 120 orders, 118 reply files, 0 refusals. Orders 074 (arm B, Prob128_fsm_ps2) and 077
(arm B, Prob075_counter_2bc) have no resp file: the subagent replied in chat and never wrote it.
Outcome `no-file`; text not recovered; fail in the all-calls view, outside the paired view.
Order 116 (arm B, Prob141_count_clock) used 3 tool calls (the others 2); scored as answered.
Order 073 (`standard` run, arm A) also used 3 tool calls and was scored.

### Pass rate per arm

| view | arm A | arm B | arm C |
| --- | --- | --- | --- |
| all calls, no-file = fail (strict) | 35/40 (0.88) | 35/40 (0.88) | 30/40 (0.75) |
| all calls, no-file = fail (Gate-Breaker-equivalent) | 33/40 (0.82) | 33/40 (0.82) | 29/40 (0.72) |
| answered only (strict) | 35/40 (0.88) | 35/38 (0.92) | 30/40 (0.75) |
| paired set, 38 problems (strict) | 33/38 (0.87) | 35/38 (0.92) | 29/38 (0.76) |
| paired set, 38 problems (Gate-Breaker-equivalent) | 31/38 (0.82) | 33/38 (0.87) | 28/38 (0.74) |

### Pass rate per quartile (strict)

| quartile | view | arm A | arm B | arm C |
| --- | --- | --- | --- | --- |
| Q1 | all calls | 10/10 (1.00) | 10/10 (1.00) | 8/10 (0.80) |
| Q1 | paired | 10/10 (1.00) | 10/10 (1.00) | 8/10 (0.80) |
| Q2 | all calls | 8/10 (0.80) | 9/10 (0.90) | 8/10 (0.80) |
| Q2 | paired | 8/10 (0.80) | 9/10 (0.90) | 8/10 (0.80) |
| Q3 | all calls | 8/10 (0.80) | 9/10 (0.90) | 7/10 (0.70) |
| Q3 | paired | 8/10 (0.80) | 9/10 (0.90) | 7/10 (0.70) |
| Q4 | all calls | 9/10 (0.90) | 7/10 (0.70) | 7/10 (0.70) |
| Q4 | paired | 7/8 (0.88) | 7/8 (0.88) | 6/8 (0.75) |

### Paired tests (exact McNemar, two-sided, paired set n = 38, strict)

| comparison | both pass | first only | second only | neither | p |
| --- | --- | --- | --- | --- | --- |
| B vs A | 33 | 2 | 0 | 3 | 0.5000 |
| A vs C | 28 | 5 | 1 | 4 | 0.2188 |
| B vs C | 28 | 7 | 1 | 2 | 0.0703 |

### Refusal and no-file rate

| run | arm | calls made | ok | refused | no-file | refused + no-file |
| --- | --- | --- | --- | --- | --- | --- |
| standard | A | 30 | 24 | 6 | 0 | 6/30 (0.20) |
| standard | B | 29 | 25 | 4 | 0 | 4/29 (0.14) |
| standard | C | 29 | 24 | 5 | 0 | 5/29 (0.17) |
| re | A | 40 | 40 | 0 | 0 | 0/40 (0.00) |
| re | B | 40 | 38 | 0 | 2 | 2/40 (0.05) |
| re | C | 40 | 40 | 0 | 0 | 0/40 (0.00) |

### `standard` against `re`, problems answered (ok) in both runs (exploratory; the prompts differ)

| arm | problems | pass in standard | pass in re | both | standard only | re only |
| --- | --- | --- | --- | --- | --- | --- |
| A | 24 | 22 | 21 | 21 | 1 | 0 |
| B | 25 | 23 | 23 | 23 | 0 | 0 |
| C | 24 | 15 | 18 | 15 | 0 | 3 |

Reading (data only): in the paired set B passes 2 problems that A fails and A passes none that B
fails (p = 0.50); A passes 5 that C fails and C passes 1 that A fails (p = 0.22); B passes 7 that C
fails and C passes 1 that B fails (p = 0.07). No comparison reaches p < 0.05 at n = 38. The
all-calls B rate equals A because the two B no-file calls count as fail; both of those problems
were passed in arm A. Per-quartile cells have 8 to 10 problems each.

### Deviations from the frozen protocol

- Decision 11: subagents keep the harness system prompt (blinding deviation, accepted).
- Decision 12: the batch-1 `cot` prompt was refused by the API safeguard and replaced by
  `standard`; the `standard` run stopped at 88 of 120 by the decision 13 rule (15 refused).
- Decision 13: refusal = outcome `refused`, never retried or reworded; two views reported.
- Decision 14: `re` has its own system prompt (md5 c95998c379b2d7e520c508b25a5a4c92, 495 bytes);
  same 2-shot examples, user content and answer format. Exact Gate-Breaker fidelity is dropped.
  All 120 calls were run fresh under `re`.
- Correction before any `re` call: the system prompt said `[END]`; changed to `[DONE]` to match
  the user suffix and collect.py (commit d5bb4f7f). The call wrapper is unchanged.
- Orders 074 and 077: `no-file` (above). Order 116: 3 tool calls (above). Order 073 (`standard`):
  3 tool calls, scored.
- `archive_run.py --no-file` and a `no-file` column in the summarize.py status table were added for
  this run (commits after d5bb4f7f); the `standard` summary.md predates the column.
- Subagent calls are not sampled with a controlled temperature; K = 1.
