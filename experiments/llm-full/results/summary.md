# Full run summary (137 problems, 3 draws, strict: no pass = fail)

## pass@k per arm and quartile

| stratum | arm | problems | pass@1 | pass@3 | MAJ (>=2 of 3) |
| --- | --- | --- | --- | --- | --- |
| Q1 | A | 40 | 0.958 | 1.000 | 38/40 (0.95) |
| Q1 | B | 40 | 0.983 | 1.000 | 40/40 (1.00) |
| Q1 | C | 40 | 0.550 | 0.650 | 21/40 (0.53) |
| Q2 | A | 33 | 0.919 | 0.970 | 32/33 (0.97) |
| Q2 | B | 33 | 0.949 | 1.000 | 31/33 (0.94) |
| Q2 | C | 33 | 0.616 | 0.758 | 20/33 (0.61) |
| Q3 | A | 34 | 0.863 | 0.882 | 29/34 (0.85) |
| Q3 | B | 34 | 0.843 | 0.882 | 29/34 (0.85) |
| Q3 | C | 34 | 0.578 | 0.676 | 21/34 (0.62) |
| Q4 | A | 30 | 0.789 | 0.900 | 24/30 (0.80) |
| Q4 | B | 30 | 0.700 | 0.867 | 24/30 (0.80) |
| Q4 | C | 30 | 0.489 | 0.667 | 15/30 (0.50) |
| all | A | 137 | 0.888 | 0.942 | 123/137 (0.90) |
| all | B | 137 | 0.878 | 0.942 | 124/137 (0.91) |
| all | C | 137 | 0.560 | 0.686 | 77/137 (0.56) |

## Mean pass@1 difference (problem-level bootstrap 95% interval, seed fixed)

- A minus B: +0.010 [-0.017, +0.036]
- B minus C: +0.319 [+0.241, +0.394]
- A minus C: +0.328 [+0.246, +0.406]

## Paired tests, primary: problem passes in at least 2 of 3 draws

| comparison | stratum | problems | first only | second only | p | p (Holm) |
| --- | --- | --- | --- | --- | --- | --- |
| A vs B | Q1 | 40 | 0 | 2 | 0.5000 | 1.0000 |
| A vs B | Q2 | 33 | 1 | 0 | 1.0000 | 1.0000 |
| A vs B | Q3 | 34 | 0 | 0 | 1.0000 | 1.0000 |
| A vs B | Q4 | 30 | 2 | 2 | 1.0000 | 1.0000 |
| A vs B | all (stratified) | 137 | 3 | 4 | 1.0000 | 1.0000 |
| B vs C | Q1 | 40 | 19 | 0 | 0.0000 | 0.0000 |
| B vs C | Q2 | 33 | 12 | 1 | 0.0034 | 0.0273 |
| B vs C | Q3 | 34 | 9 | 1 | 0.0215 | 0.1504 |
| B vs C | Q4 | 30 | 12 | 3 | 0.0352 | 0.2109 |
| B vs C | all (stratified) | 137 | 52 | 5 | 0.0000 | 0.0000 |

## Paired tests, secondary: pass@3 (any draw passes)

| comparison | stratum | problems | first only | second only | p | p (Holm) |
| --- | --- | --- | --- | --- | --- | --- |
| A vs B | Q1 | 40 | 0 | 0 | 1.0000 | 1.0000 |
| A vs B | Q2 | 33 | 0 | 1 | 1.0000 | 1.0000 |
| A vs B | Q3 | 34 | 0 | 0 | 1.0000 | 1.0000 |
| A vs B | Q4 | 30 | 2 | 1 | 1.0000 | 1.0000 |
| A vs B | all (stratified) | 137 | 2 | 2 | 1.0000 | 1.0000 |
| B vs C | Q1 | 40 | 14 | 0 | 0.0001 | 0.0011 |
| B vs C | Q2 | 33 | 8 | 0 | 0.0078 | 0.0625 |
| B vs C | Q3 | 34 | 8 | 1 | 0.0391 | 0.2734 |
| B vs C | Q4 | 30 | 10 | 4 | 0.1796 | 1.0000 |
| B vs C | all (stratified) | 137 | 40 | 5 | 0.0000 | 0.0000 |
