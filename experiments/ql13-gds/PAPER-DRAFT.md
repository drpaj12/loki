# Draft for the Loki paper: the fourth deep target, the GDS path (Q-L13)

Status: draft from `experiments/ql13-gds` (plan commit 14788c7). The controller merges it into `docs/paper/loki.tex` with the lut4 update.
No number here is outside `results/*.csv`; the paper's own numbers (0.610, 0.754, 0.773) are from Table tab:join. Nothing is cited that was not
fetched; the Odin III silicon flow is described by its manual (`docs/user/silicon-flow.md`, v1.4.0).

## Where it goes

After the three endpoint targets (gates, lut4, k6 with hard blocks) as "Target four: the extracted layout". Purpose: the silicon provenance vision
(a scanned chip checked against a golden that carries provenance). RQ Q-L13.

## Paragraph (LaTeX, in the paper's hev style)

```latex
\subsection{Target four: the netlist read back from a layout}
\label{arg:ql13}

\hev{Hypothesis.} Provenance survives physical design. For every design that the Odin~III silicon flow takes to a layout whose extracted netlist
matches the placed one (LVS match), (a) every logic cell of the netlist read back from the GDS joins to a placed cell without using a name, and
(b) every such cell has a complete chain extracted, GDS, routed, placed, mapped, elaborated, HDL span.

\hev{Measurements.} Odin~III 1.4.0 maps the design onto SKY130 \texttt{sky130\_fd\_sc\_hd} cells (no Yosys), OpenROAD (March 2022 build) places and
routes it, KLayout writes the GDS, Magic extracts the cells and Netgen checks LVS. The extracted cells carry no Odin~III name; the join uses cell type
and location in the placed design. Of 44 designs (40 VerilogEval problems and 4 processor modules, the Q-L12 set), 9 reached LVS match. On those 9,
3676 of 3676 extracted cells that are not tap or fill joined by type and location, and 3638 of 3638 logic cells have a complete chain to an HDL span
(Table~\ref{tab:gds}). Physical design removed no cell, resized 638 times, and added 1226 tap cells, 10078 fill cells and 38 clock-tree buffers, which
carry a physical label and no HDL chain. The weakest link on every chain is the medium-confidence cone link from a mapped gate to the elaborated cells.
The other 35 designs did not reach LVS match: 13 have at most one cell (the floorplan has no rows), 11 stop in placement or global routing, 2 in the
equivalence check and 9 fail LVS. Cutting the extracted netlist into Loki blocks and applying the right-block rule gives 3 of 5 key constructs with a
right block (0.600); the same designs give 3 of 5 at lut4, k4 and k6.

\hev{Interpretation.} Where the flow works, provenance is fully recoverable on the GDS path, without names, for logic cells, and the cells the flow
inserts are labelled as such. The result is for cells, not transistors, for 9 designs of 14 to 1563 logic cells, and it says nothing about the 35
designs the flow could not finish. The join uses the placed design (DEF) of the golden run; a chip scanned without one needs the cell recogniser of the
Leman Russ lane. The block-recovery number rests on 5 constructs and cannot rank the layout endpoint against the others.

\hev{Conclusion.} (a) and (b) are \verdict{SUPPORTED} on the 9 designs with LVS match, and not tested on the other 35 [QL13; Appendix~\ref{rec:ql13}].
```

## Table rows (LaTeX)

```latex
\begin{table}[t]
\caption{Provenance on the GDS path, the 9 designs with LVS match. Logic cells are the Odin III cells; tap, fill and clock-tree buffers are inserted by the flow.}
\label{tab:gds}
\centering
\footnotesize
\begin{tabular}{@{}lrrrrrr@{}}
\toprule
Design & Logic & Tap & Fill & Clock buffers & Join (a) & Chain (b) \\
\midrule
Prob143\_fsm\_onehot & 19 & 4 & 39 & 0 & 1.000 & 1.000 \\
Prob121\_2014\_q3bfsm & 14 & 4 & 46 & 3 & 1.000 & 1.000 \\
Prob055\_conditional & 129 & 30 & 272 & 0 & 1.000 & 1.000 \\
Prob097\_mux9to1v & 143 & 44 & 353 & 0 & 1.000 & 1.000 \\
Prob052\_gates100 & 248 & 70 & 588 & 0 & 1.000 & 1.000 \\
Prob018\_mux256to1 & 404 & 102 & 875 & 0 & 1.000 & 1.000 \\
Prob105\_rotate100 & 604 & 260 & 2073 & 9 & 1.000 & 1.000 \\
Prob115\_shift18 & 514 & 180 & 1469 & 9 & 1.000 & 1.000 \\
picorv32\_pcpi\_div & 1563 & 532 & 4363 & 17 & 1.000 & 1.000 \\
\midrule
All 9 & 3638 & 1226 & 10078 & 38 & 3676/3676 & 3638/3638 \\
\bottomrule
\end{tabular}
\end{table}
```

Right-block share, a row for Table tab:join style (descriptive; 5 constructs, so no interval is meaningful):

```latex
Extracted layout cells (same 9 designs) & 5 & -- & -- & 0.600 \\
```

with, on the same designs and the same key (flip-flops with the same HDL line and column): gates 3 of 3 (no key for the processor module),
lut4 3 of 5, k4 3 of 5, k6 3 of 5.

## Appendix record (one block, for `rec:ql13`)

Question Q-L13: is provenance fully recoverable on the GDS path? Plan 14788c7. Unit: design. n = 44 run, 9 LVS match. Result: join 3676/3676, chain
3638/3638, failure catalogue empty, 35 designs out of scope with their flow errors (EXPERIMENT.md). Verdict: SUPPORTED on the LVS-match designs.
Limits: cells not transistors; OpenROAD 2022 pin; two-layer power grid; DEF used for the join; 5 key constructs.

## Open questions for the controller (Odin III, not fixed here)

1. The silicon flow stops on designs with at most one cell (OpenROAD floorplan with zero rows).
2. The `gds` stage labels clock-tree buffers `physical:repair_buffer`; `placed` and `routed` say `physical:cts_buffer` (38 cells in 4 designs).
3. A tool error text in `equiv` (a path in the message) becomes a privacy refusal and hides the tool's reason.
4. Small designs fail LVS on supply nets.
