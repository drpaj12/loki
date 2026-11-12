# Draft replacement for the Loki SaTC paper, section "Does provenance go all the way down to the layout?" (Q-L13 rerun, Odin III 1.6.1)

Not edited into the paper; the paper files are read only for this lane. Numbers are from `results-v161/` (plan commit
29fffbac467dd19d9e631d0b5cce55758114aba1; see EXPERIMENT.md "Results (2026-11-11, v1.6.1)").

## Replacement for the sentences at ~line 191 ("Of 44 designs, 9 finished ... physical label.")

Of 44 designs, 28 finished with a matching layout; of the other 16, nine have no logic cell (pure wires, so there is nothing to lay out) and seven stopped in the 2022 global placer, a limit of that tool, not of provenance. On the 28, all 8,096 extracted cells that are not tap or fill join a placed cell, all 7,941 logic cells chain back to their HDL line, and the 2,961 tap, 24,164 fill, 139 clock-buffer and 16 repair-buffer cells the flow adds carry a physical label. \textbf{Yes: wherever the tools finished, provenance holds down to the layout.} It is a result about cells, not transistors, the join needs the placed design of the golden run, and each chain's weakest step is a medium-confidence link from a mapped gate to the source spans it shares.

## Replacement for the limit (v) at ~line 206

(v)~The layout result covers the 28 designs (25 VerilogEval problems, 3 processor modules, 1 to 2,131 logic cells) that the 2022 place-and-route tools finished; 7 more stop in global placement and 9 have no logic.

## Numbers (old 11-03, Odin III 1.4.0 -> new, Odin III 1.6.1)

| quantity | 11-03 | 11-11 |
|---|---|---|
| designs with LVS match | 9 of 44 | 28 of 44 |
| extracted cells joined (not tap or fill) | 3,676 of 3,676 | 8,096 of 8,096 |
| logic cells with a chain to an HDL line | 3,638 of 3,638 | 7,941 of 7,941 |
| tap / fill / clock buffers / repair buffers | 1,226 / 10,078 / 38 / 0 | 2,961 / 24,164 / 139 / 16 |

Caveat to keep honest in the paper if the chain wording is used: in 1.6.1 the mapped-gate link goes straight to the HDL spans (the elaborated-cell hop of 1.4.0 is gone from the path). Chain-to-HDL-line holds for 7,941 of 7,941; a count that requires the elaborated-cell hop is 0.
The block-recovery numbers (if the table is used): at the layout endpoint 6 of 9 key constructs have a right block (3 of 3 at gates where a key exists; 6 of 9 at lut4, k4 and k6); the two large processors have none at any endpoint.
