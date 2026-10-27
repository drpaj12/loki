# Pilot tables

## Pass rate by quartile and arm

| quartile | arm A | arm B | arm C |
| --- | --- | --- | --- |
| Q1 | 10/10 (1.00) | 10/10 (1.00) | 8/10 (0.80) |
| Q2 | 8/10 (0.80) | 9/10 (0.90) | 8/10 (0.80) |
| Q3 | 8/10 (0.80) | 9/10 (0.90) | 7/10 (0.70) |
| Q4 | 9/10 (0.90) | 7/8 (0.88) | 7/10 (0.70) |
| all | 35/40 (0.88) | 35/38 (0.92) | 30/40 (0.75) |

## Pass rate, Gate-Breaker-equivalent scorer

| quartile | arm A | arm B | arm C |
| --- | --- | --- | --- |
| Q1 | 10/10 (1.00) | 10/10 (1.00) | 8/10 (0.80) |
| Q2 | 8/10 (0.80) | 9/10 (0.90) | 8/10 (0.80) |
| Q3 | 8/10 (0.80) | 9/10 (0.90) | 7/10 (0.70) |
| Q4 | 7/10 (0.70) | 5/8 (0.62) | 6/10 (0.60) |
| all | 33/40 (0.82) | 33/38 (0.87) | 29/40 (0.72) |

## Paired A/B

| both pass | A only | B only | neither | problems |
| --- | --- | --- | --- | --- |
| 33 | 0 | 2 | 3 | 38 |
B minus A = 2 problems (discordant pairs 2).

## Outcome codes

| outcome | arm A | arm B | arm C |
| --- | --- | --- | --- |
| no-output | 0 | 0 | 0 |
| cheat | 0 | 0 | 0 |
| syntax | 0 | 0 | 0 |
| compile | 1 | 0 | 1 |
| compile-timeout | 0 | 0 | 0 |
| runtime | 4 | 3 | 9 |
| timeout | 0 | 0 | 0 |
| no-result | 0 | 0 | 0 |
| pass | 35 | 35 | 30 |

## Pass rate with refusals and paired set

| arm | ok | refused | no-file | not run | pass | refused = fail | answered only | paired set |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| A | 40 | 0 | 0 | 0 | 35 | 35/40 (0.88) | 35/40 (0.88) | 33/38 (0.87) |
| B | 38 | 0 | 2 | 0 | 35 | 35/40 (0.88) | 35/38 (0.92) | 35/38 (0.92) |
| C | 40 | 0 | 0 | 0 | 30 | 30/40 (0.75) | 30/40 (0.75) | 29/38 (0.76) |

Paired set: 38 problems answered in all of ABC.
Ok calls with tool-call count other than 2: 116 B Prob141_count_clock (3 tool calls).

## Loki-label agreement (arm B, counts)

- arm B problems with hints read: 38
- FSM candidate present: 2; of those the L0 ground truth says FSM: 1; FSM hint wrong or absent against ground truth: 2
- bus candidate present: 18; hint agrees with `buses_wide`: 24 of 37
- claims labelled datapath: 762 of 762 role-labelled (762 kept claims)
- uptake (exploratory regex): FSM hint with state register steering logic in the RTL 1 of 2; bus hint with a vector of the hinted width 7 of 18
- right for the wrong reason: B passes with a wrong FSM or bus hint 13; B failures with right hints 2
