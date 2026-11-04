# Q-L13: is provenance fully recoverable on the GDS path? (plan, 2026-11-03)

Branch exp/ql13-gds on loki main 36ae727. No model call anywhere in this lane. This file is committed and pushed first; that
commit SHA is the plan SHA of the results. A later change is a dated entry under "Amendments"; the old text stays.
Reuses by import, changes none of: `loki/prov_steps.py` (reader and `resolve`), `ql12-k4k6` (netlist reader, block builder, key
and right-block rule), `ql12-lut4`, `ql10-blocks` (gates), `ql9-join` (the join rule inside the builder).

## Peter's words (2026-11-03)

"Can we test out loki provenance results on the GDS path (L0) to see if it is fully recoverable and document that in the Loki
reverse engineering paper as a 4th deep target?"

Purpose: Loki path, and the silicon provenance vision (a scanned chip checked against provenance for fab hardware Trojans).
RQ Q-L13. Measures: provenance chain completeness (share of extracted logic cells with a full chain back to an HDL line),
name-free join completeness, Loki L0 block recovery (structure only, no model) at the extracted-cell endpoint, beside gates,
lut4, k4 and k6 on the same designs.

## Plain English

Odin III v1.4.0 can take a design to a routed SKY130 layout (GDS) and read the cells back out of the GDS with Magic. Each step
writes a provenance file. The question is whether, after all that physical design, every logic cell read back from the layout
can still be followed to the line of Verilog it came from, without using any cell name (the extracted cells have none; the join
uses cell type and position). Separately, we cut the extracted cell netlist into blocks with Loki's block builder and ask how
often one block is the right block for a register group of the HDL, as in the earlier endpoints. No model is called; this is
structure only.

## Definitions

- Flow: `tools/silicon/silicon_flow.py` of Odin III v1.4 (steps read, elab, map, equiv, netlist, place, route, gds, extract, lvs,
  recover), `--prov` files on, SKY130 `sky130_fd_sc_hd`, OpenROAD March 2022 pin, Magic, Netgen, KLayout of the v1.4 lane
  installs. No Yosys. A design is **LVS-match** when the `lvs` step check result is `match`.
- Stages of a chain (provenance step files): `extracted` (Magic cell, id `MASTER@X,Y`) -> `gds` -> `routed` -> `placed` ->
  `gates` (Odin III mapped cell) -> `ir` (elaborated cell) -> `hdl` (source span). Link kinds: `location_match` (extracted to gds,
  name-free), `id`, `name`, `cone` (gates to ir), `fine` (ir to hdl).
- Extracted cell classes (by the master and the DEF component it joins to, never by a guess): `tap`, `fill` (fill, decap, diode),
  `logic` (joins a component that exists in the Odin III netlist, `s00_link` dump, at any master: a resized cell is still
  logic), `cts_buffer`, `repair_buffer`, `hold_buffer` (components inserted by that OpenROAD sub-step), `unjoined` (no DEF
  component found). "Removed" counts Odin III cells with no extracted cell.
- (a) name-free join: an extracted cell that is not tap or fill has a `location_match` link to a placed object. Share = joined /
  (extracted cells that are not tap or fill).
- (b) full chain: a `logic` extracted cell whose `resolve()` reaches stage `hdl` (through `ir` to a source span), with the path
  passing the stages above in order. Share = full chain / (logic extracted cells + unjoined extracted cells that are not tap or
  fill, which cannot have a chain). Inserted buffers (cts, repair, hold) are counted apart with their link kind
  (`physical_origin`); they are not in this denominator.
- Weakest link on a chain is reported (exact, high, medium: `cone` is medium by the v1.4 rule).

## Hypothesis H-L13 (controller's words)

H-L13: for every design whose flow ends in LVS match, (a) every logic cell of the extracted (from GDS) netlist joins name-free to
a placed cell (share 1.0), and (b) every such logic cell has a complete provenance chain extracted -> placed -> mapped -> elab ->
HDL line (share 1.0). Physical cells the flow inserts (tap, fill, CTS buffer, resize) are counted apart, each with its link kind;
a logic cell without an HDL chain is a failure of (b) and goes into a failure catalogue with its cause.

Labels (memory cad-reporting-convention): headline share and W/L/T-style counts first (designs with share 1.0 / below 1.0 /
not applicable), then SUPPORTED per design when its share is 1.0, CONTRADICTED when below 1.0; overall SUPPORTED only if every
LVS-match design is SUPPORTED. A design that fails the flow or does not reach LVS match is outside the hypothesis and reported
with its error; it is not fixed in Odin III (an open question to the controller).

Descriptive, no verdict: Loki block recovery without a model at the extracted-cell netlist (the paper's Table tab:join rule: the
share of key constructs that have a right block; 0.610 gates / 0.754 k4 / 0.773 k6 on the benchmark) and the same on the same
designs at gates, lut4, k4, k6.

## Designs

The Q-L12 set: the 40 VerilogEval problems that pass the ceiling filter of Q-L12 (`ql12-k4k6/results/stubcheck.csv`, outcome
`pass` at both k4 and k6) and the 4 processor modules (picorv32_pcpi_div, tinyriscv_clint, tinyriscv_csr, tinyriscv_div;
picorv32_pcpi_mul is not readable by Odin III, as in Q-L12). VerilogEval reference `*_ref.sv`, top `RefModule`; Prob151 and Prob156
use the same patched copies as the l3-census and are in the filter's exclusion anyway. Run smallest first (source size). The clock
port is `clk` when the module has one, else none (CTS off). A design the flow cannot take (a latch, a construct the SKY130 library
lacks, a tool error) is reported with its error.

## Steps

1. Flow per design: `tools/heavy-run` (ODIN3_HEAVY_OK=1), jobs 1, out dir `work/ql13-out/<design>`. Record status, equiv-check, LVS,
   cell counts by class, runtime, disk (`results/flow.csv`).
2. `tools/silicon/schema_check.py` on each `prov` directory; read with `loki/prov_steps.py`; (a), (b) per design, failure
   catalogue (cell, stage where the chain breaks, link kind, cause) (`results/chain.csv`, `results/catalogue.csv`).
3. Endpoint "gds": the extracted cell netlist (connectivity from the hierarchical Magic SPICE, cell functions from `lib/sky130hd.o3lib`)
   written as a BLIF of `.names` covers and `.latch`; labels from the chain (a flip-flop's HDL line and column, never guessed; a cell
   with no chain stays `unknown`); the Q-L12 block builder (cell class `O-lut`, the class of soft-logic LUT netlists, the only
   one with a trained grow model for LUT-like cells; no retuning) and the Q-L12 right-block rule on flip-flop key constructs
   (>= 2 flip-flops with the same HDL line and column; a block is right when it holds >= 0.8 of them and Jaccard >= 0.5). Same
   function on the same designs at gates (`ql10-blocks`), lut4, k4, k6 from the stored block files of those runs.
4. Results, a draft paragraph and table rows for the Loki paper's fourth deep target.

## Limits, stated before the run

The `extracted` stage holds cells, not transistors. OpenROAD is the March 2022 pin; the power grid is met1 rails and met4 straps
(two layers). The join uses the DEF of the golden run (a real scanned chip has no DEF). The sky130 library is drive strength 1,
no latches, no tri-states. Small designs only; the processor modules may exceed the flow. Key constructs at the gds endpoint come
from the chain, so the block recovery there is a measure of structure given the answer key the flow itself provides, not of an
unlabelled chip. Block counts are small (few designs have >= 2 flip-flops under one construct), so shares are descriptive. The
cell class `O-lut` is a stand-in for the unseen SKY130 gate class.

## Amendments
