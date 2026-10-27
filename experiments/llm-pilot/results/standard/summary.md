# Pilot tables

## Pass rate by quartile and arm

| quartile | arm A | arm B | arm C |
| --- | --- | --- | --- |
| Q1 | 10/10 (1.00) | 10/10 (1.00) | 5/8 (0.62) |
| Q2 | 5/5 (1.00) | 6/6 (1.00) | 5/6 (0.83) |
| Q3 | 4/5 (0.80) | 5/6 (0.83) | 2/5 (0.40) |
| Q4 | 3/4 (0.75) | 2/3 (0.67) | 3/5 (0.60) |
| all | 22/24 (0.92) | 23/25 (0.92) | 15/24 (0.62) |

## Pass rate, Gate-Breaker-equivalent scorer

| quartile | arm A | arm B | arm C |
| --- | --- | --- | --- |
| Q1 | 10/10 (1.00) | 10/10 (1.00) | 5/8 (0.62) |
| Q2 | 5/5 (1.00) | 6/6 (1.00) | 5/6 (0.83) |
| Q3 | 4/5 (0.80) | 5/6 (0.83) | 2/5 (0.40) |
| Q4 | 3/4 (0.75) | 2/3 (0.67) | 3/5 (0.60) |
| all | 22/24 (0.92) | 23/25 (0.92) | 15/24 (0.62) |

## Paired A/B

| both pass | A only | B only | neither | problems |
| --- | --- | --- | --- | --- |
| 21 | 0 | 0 | 2 | 23 |
B minus A = 0 problems (discordant pairs 0).

## Outcome codes

| outcome | arm A | arm B | arm C |
| --- | --- | --- | --- |
| no-output | 0 | 0 | 0 |
| cheat | 0 | 0 | 0 |
| syntax | 0 | 0 | 0 |
| compile | 0 | 0 | 1 |
| compile-timeout | 0 | 0 | 0 |
| runtime | 2 | 2 | 8 |
| timeout | 0 | 0 | 0 |
| no-result | 0 | 0 | 0 |
| pass | 22 | 23 | 15 |

## Pass rate with refusals and paired set

| arm | ok | refused | not run | pass | refused = fail | answered only | paired set |
| --- | --- | --- | --- | --- | --- | --- | --- |
| A | 24 | 6 | 10 | 22 | 22/30 (0.73) | 22/24 (0.92) | 18/19 (0.95) |
| B | 25 | 4 | 11 | 23 | 23/29 (0.79) | 23/25 (0.92) | 18/19 (0.95) |
| C | 24 | 5 | 11 | 15 | 15/29 (0.52) | 15/24 (0.62) | 13/19 (0.68) |

Paired set: 19 problems answered in all of ABC.
Ok calls with tool-call count other than 2: 073 A Prob128_fsm_ps2 (3 tool calls).

## Loki-label agreement (arm B, counts)

- arm B problems with hints read: 25
- FSM candidate present: 0; of those the L0 ground truth says FSM: 0; FSM hint wrong or absent against ground truth: 0
- bus candidate present: 5; hint agrees with `buses_wide`: 19 of 24
- claims labelled datapath: 99 of 99 role-labelled (99 kept claims)
- uptake (exploratory regex): FSM hint with state register steering logic in the RTL 0 of 0; bus hint with a vector of the hinted width 2 of 5
- right for the wrong reason: B passes with a wrong FSM or bus hint 5; B failures with right hints 2
