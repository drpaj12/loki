# Hints v2 summary (64 problems, 3 draws, strict: no pass = fail)

## pass@k per arm and quartile

| stratum | arm | problems | pass@1 | pass@3 | MAJ (>=2 of 3) |
| --- | --- | --- | --- | --- | --- |
| Q3 | A2 | 34 | 0.853 | 0.882 | 30/34 (0.88) |
| Q3 | B1p | 34 | 0.853 | 0.882 | 30/34 (0.88) |
| Q3 | B2 | 34 | 0.873 | 0.882 | 30/34 (0.88) |
| Q3 | W | 34 | 0.863 | 0.882 | 30/34 (0.88) |
| Q4 | A2 | 30 | 0.744 | 0.933 | 24/30 (0.80) |
| Q4 | B1p | 30 | 0.800 | 0.933 | 26/30 (0.87) |
| Q4 | B2 | 30 | 0.933 | 0.933 | 28/30 (0.93) |
| Q4 | W | 30 | 0.789 | 0.867 | 25/30 (0.83) |
| all | A2 | 64 | 0.802 | 0.906 | 54/64 (0.84) |
| all | B1p | 64 | 0.828 | 0.906 | 56/64 (0.88) |
| all | B2 | 64 | 0.901 | 0.906 | 58/64 (0.91) |
| all | W | 64 | 0.828 | 0.875 | 55/64 (0.86) |

## Mean pass@1 difference (problem-level bootstrap 95% interval, seed fixed)

- B2 minus A2: +0.099 [+0.052, +0.151]
- B2 minus B1p: +0.073 [+0.031, +0.115]
- W minus A2: +0.026 [-0.021, +0.073]
- B1p minus A2: +0.026 [-0.021, +0.073]

## Paired tests, primary: at least 2 of 3 draws (Holm over 9)

| comparison | stratum | problems | first only | second only | p | p (Holm) |
| --- | --- | --- | --- | --- | --- | --- |
| B2 vs A2 | Q3 | 34 | 0 | 0 | 1.0000 | 1.0000 |
| B2 vs A2 | Q4 | 30 | 4 | 0 | 0.1250 | 1.0000 |
| B2 vs A2 | all (stratified) | 64 | 4 | 0 | 0.1250 | 1.0000 |
| B2 vs B1p | Q3 | 34 | 0 | 0 | 1.0000 | 1.0000 |
| B2 vs B1p | Q4 | 30 | 2 | 0 | 0.5000 | 1.0000 |
| B2 vs B1p | all (stratified) | 64 | 2 | 0 | 0.5000 | 1.0000 |
| W vs A2 | Q3 | 33 | 0 | 0 | 1.0000 | 1.0000 |
| W vs A2 | Q4 | 26 | 2 | 2 | 1.0000 | 1.0000 |
| W vs A2 | all (stratified) | 59 | 2 | 2 | 1.0000 | 1.0000 |

## Paired tests, secondary: any draw passes (Holm over 9)

| comparison | stratum | problems | first only | second only | p | p (Holm) |
| --- | --- | --- | --- | --- | --- | --- |
| B2 vs A2 | Q3 | 34 | 0 | 0 | 1.0000 | 1.0000 |
| B2 vs A2 | Q4 | 30 | 0 | 0 | 1.0000 | 1.0000 |
| B2 vs A2 | all (stratified) | 64 | 0 | 0 | 1.0000 | 1.0000 |
| B2 vs B1p | Q3 | 34 | 0 | 0 | 1.0000 | 1.0000 |
| B2 vs B1p | Q4 | 30 | 0 | 0 | 1.0000 | 1.0000 |
| B2 vs B1p | all (stratified) | 64 | 0 | 0 | 1.0000 | 1.0000 |
| W vs A2 | Q3 | 33 | 0 | 0 | 1.0000 | 1.0000 |
| W vs A2 | Q4 | 26 | 0 | 2 | 0.5000 | 1.0000 |
| W vs A2 | all (stratified) | 59 | 0 | 2 | 0.5000 | 1.0000 |

## Paired tests, secondary, pre-stated: the 36 problems with v2 claims, at least 2 of 3 draws (own Holm family) (Holm over 9)

| comparison | stratum | problems | first only | second only | p | p (Holm) |
| --- | --- | --- | --- | --- | --- | --- |
| B2 vs A2 | Q3 | 13 | 0 | 0 | 1.0000 | 1.0000 |
| B2 vs A2 | Q4 | 23 | 4 | 0 | 0.1250 | 1.0000 |
| B2 vs A2 | all (stratified) | 36 | 4 | 0 | 0.1250 | 1.0000 |
| B2 vs B1p | Q3 | 13 | 0 | 0 | 1.0000 | 1.0000 |
| B2 vs B1p | Q4 | 23 | 2 | 0 | 0.5000 | 1.0000 |
| B2 vs B1p | all (stratified) | 36 | 2 | 0 | 0.5000 | 1.0000 |
| W vs A2 | Q3 | 12 | 0 | 0 | 1.0000 | 1.0000 |
| W vs A2 | Q4 | 19 | 2 | 2 | 1.0000 | 1.0000 |
| W vs A2 | all (stratified) | 31 | 2 | 2 | 1.0000 | 1.0000 |

## Verdicts (rule fixed in EXPERIMENT.md)

- LLM5, B2 vs A2: INCONCLUSIVE (mean +0.099 [+0.052, +0.151], stratified Holm p 1.0000, minimum gain +0.05)
- LLM6, W vs A2: not supported (MAJ: W only 2, A2 only 2; stratified Holm p 1.0000; B2 use rate 107/192; pass@1 W minus A2 +0.026 over all problems; 5 problems left out of the W tests)
- Secondary (problems with claims), B2 vs A2: MAJ B2 only 4, A2 only 0, stratified Holm p 1.0000 (not a verdict)

## Use of the claims (CLAIMS-USED line)

| arm | calls naming a claim | calls with the line | calls |
| --- | --- | --- | --- |
| B1p | 116 | 190 | 192 |
| B2 | 107 | 192 | 192 |
| W | 60 | 191 | 192 |

| kind (B1p) | calls using it | pass | calls offered it, not using | pass |
| --- | --- | --- | --- | --- |
| adder | 0 | 0 | 38 | 36 |
| adder_cin | 0 | 0 | 18 | 16 |
| bus | 33 | 30 | 97 | 85 |
| counter | 6 | 6 | 0 | 0 |
| datapath_unit | 5 | 4 | 13 | 9 |
| eq_const | 76 | 62 | 85 | 77 |
| ff_en | 4 | 3 | 34 | 22 |
| ff_srst | 19 | 19 | 73 | 64 |
| fsm | 7 | 6 | 17 | 15 |
| register | 21 | 18 | 20 | 15 |
| shift_reg | 3 | 2 | 0 | 0 |
| subtractor | 2 | 2 | 22 | 22 |

| kind (B2) | calls using it | pass | calls offered it, not using | pass |
| --- | --- | --- | --- | --- |
| counter | 24 | 24 | 0 | 0 |
| eq_const | 11 | 10 | 7 | 7 |
| fsm | 57 | 57 | 0 | 0 |
| lfsr | 3 | 3 | 0 | 0 |
| register | 6 | 6 | 0 | 0 |
| shift_reg | 15 | 15 | 0 | 0 |

| kind (W) | calls using it | pass | calls offered it, not using | pass |
| --- | --- | --- | --- | --- |
| counter | 19 | 19 | 5 | 4 |
| eq_const | 4 | 4 | 14 | 10 |
| fsm | 33 | 27 | 24 | 19 |
| lfsr | 1 | 1 | 2 | 1 |
| register | 4 | 4 | 2 | 2 |
| shift_reg | 3 | 3 | 12 | 12 |
