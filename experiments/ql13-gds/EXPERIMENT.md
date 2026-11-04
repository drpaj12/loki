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

- 2026-11-03 (during the run; plan commit 14788c7; the analysis code was written on the stored comparator run and the first finished
  runs, and items 3 and 4 were fixed while the 44 runs were coming in, before the full tables; stated here, not hidden):
  1. Staging for the four processor modules (code unchanged, nothing in Odin III changed). The first attempt failed at `read` for all
     four: `include_not_found: 'defines.v'` (tinyriscv) and `ambiguous_top` (picorv32.v has several modules and the flow's
     `read_verilog` needs one top). `ql13_flow.stage_source` now copies `defines.v` beside the tinyriscv source and, for
     `picorv32_pcpi_div`, writes the module verbatim from `module` to `endmodule` (it instantiates no other module and uses no macro
     outside `ifdef` branches). The four were run again (`--redo`); the first attempts are kept as `status.attempt1.json`.
  2. Runs that stopped at LVS leave step files up to `lvs` and no `index.json` (the index is written last). For descriptive use only,
     `ql13_chain.partial_prov` copies the step files with an index built from their headers and sha256 values; such rows have
     `partial` 1 in the CSVs and are outside the hypothesis.
  3. Key at the gds endpoint. The chain gives an HDL line and column (the first span of the mapped cell), not a construct type, so
     the key here is flip-flops with the same line and column. For the comparison, the same key (without the type) is computed at
     gates, lut4, k4 and k6 (`results/prior_key.csv`, columns `coarse_*`). The Q-L12 key with the type is in the `key_*` columns.
  4. Class of an extracted cell is read at the end of its chain (the label at `placed`), not at the `gds` stage: the `gds` stage
     labels the clock-tree buffers `physical:repair_buffer` while `placed` and `routed` label them `physical:cts_buffer`
     (38 cells in the 9 LVS-match designs, `gds_label_mismatch` in `chain.csv`). This is an Odin III v1.4 labelling inconsistency, not fixed here.

## Results (2026-11-03)

Generated tables: `results/summary.md` (`ql13_report.py`) from `results/flow.csv`, `chain.csv`, `catalogue.csv`, `weakest.csv`,
`gds_blocks.csv`, `gds_key.csv`, `prior_key.csv`. Flow: Odin III 1.4.0 (debug build of the v1.4 lane), OpenROAD `f12e2f474` (March 2022),
Magic 8.3.465, Netgen 1.5.272, KLayout 0.30.12, SKY130A `sky130_fd_sc_hd`. Run root and flow code: Odin III read only.

### Plain English

Of 44 designs, 9 went through the whole flow to an LVS match. For those 9, every logic cell read back from the layout joined to a
placed cell without a name (3676 of 3676 cells that are not tap or fill), and every logic cell had a complete chain
extracted -> gds -> routed -> placed -> mapped -> elaborated -> HDL span (3638 of 3638). Nothing was removed by physical design,
638 resize events changed a cell's master but not its identity, and the flow added tap, fill and clock-tree cells that carry a
physical label instead of an HDL chain. So on the designs where the flow works, provenance is fully recoverable on the GDS path.

That is 9 of 44. The other 35 are outside the hypothesis, and most of them are small: 13 have one cell or none (the OpenROAD
floorplan makes zero rows and the Tcl driver stops), 11 more stop in placement or routing (OpenROAD errors on 2 to 399 cells), 2 stop in
`equiv`, and 9 place and route, then fail LVS (in the two LVS logs read, Prob044 and Prob087, the cell supply pins VPWR, VPB and VNB
form nets of their own that have no match in the reference; the cause was not traced further). The flow was not changed to fix any of these.

For the 9 failed-LVS runs the step files are readable up to `lvs`; on those the shares were also 1.0 (descriptive, partial runs).

Block recovery without a model on the extracted-cell netlist is a small sample: 5 key constructs in the 9 designs, 3 with a right
block; the same designs give 3 of 5 at lut4, k4 and k6 and 3 of 3 at gates (gates has no key for the processor module). The only
large design with a key, `picorv32_pcpi_div`, has no right block at gds, lut4, k4 or k6 (gates has no key for it).

### H-L13 (headline first, then the label)

| quantity | LVS-match designs (n = 9) | label |
|---|---|---|
| (a) name-free join, non-filler extracted cells | 3676 of 3676 = 1.000 | SUPPORTED |
| (b) full chain to an HDL line, logic cells | 3638 of 3638 = 1.000 | SUPPORTED |
| designs with both shares 1.0 / below 1.0 / out of scope | 9 / 0 / 35 | |

Overall: SUPPORTED on the 9 designs where the flow reaches LVS match (every one of them is SUPPORTED); not tested on the 35 where it does not.
Weakest link on every chain: `medium` (the `cone` link from a mapped gate to the elaborated cells, by the v1.4 rule); all other links
are `exact` or `high`. Failure catalogue: 0 cells (`results/catalogue.csv` has the header only). The measure can say no: a unit test
cuts a join and a cone link and the cells land in the catalogue (`test_ql13.py`).

### The 9 LVS-match designs

| design | logic | tap | fill | CTS buffers | resize events | seconds | disk MB |
|---|---|---|---|---|---|---|---|
| Prob143_fsm_onehot | 19 | 4 | 39 | 0 | 5 | 3.5 | 3.8 |
| Prob121_2014_q3bfsm | 14 | 4 | 46 | 3 | 0 | 5.1 | 4.3 |
| Prob055_conditional | 129 | 30 | 272 | 0 | 18 | 30.4 | 11.2 |
| Prob097_mux9to1v | 143 | 44 | 353 | 0 | 19 | 36.4 | 16.4 |
| Prob052_gates100 | 248 | 70 | 588 | 0 | 8 | 42.4 | 17.0 |
| Prob018_mux256to1 | 404 | 102 | 875 | 0 | 143 | 134.7 | 74.6 |
| Prob105_rotate100 | 604 | 260 | 2073 | 9 | 104 | 201.2 | 59.2 |
| Prob115_shift18 | 514 | 180 | 1469 | 9 | 138 | 204.8 | 59.9 |
| picorv32_pcpi_div | 1563 | 532 | 4363 | 17 | 203 | 751.5 | 185.1 |
| total | 3638 | 1226 | 10078 | 38 | 638 | | |

Totals over the 9: 14980 extracted cells. No hold buffer, repair buffer or tie cell was inserted, no Odin III cell was removed or
renamed, and no extracted cell carries an Odin III name (`extracted_odin_names` 0). The `equiv` check was `equivalent` in all 9.
`schema_check.py` passed on all 9 `prov` directories. Total flow time for all 44 runs 2249 s; disk of the run root 1.2 GB; host disk
41 GB free before and after (`df -h /mnt/c`).

### The 35 designs outside the hypothesis (errors as the flow reported them; see `results/summary.md` for each)

- 13 x place: `openroad_flow.tcl, 51 empty command name ""`: one cell or none, "Added 0 rows".
- 4 x place `GPL-0305` RePlAce diverged; 1 x `GPL-0304`; 2 x `GPL-0302` (use a higher density); 1 x `PPL-0024` (402 pins, 349 possible; Prob092_gatesv100);
  2 x global routing "net not properly covered" (`GRT-0076`); 1 x `net7 initial #node != #rpin` (tinyriscv_csr).
- 2 x equiv: Prob046_dff8p (`latch $n21 is clocked by internal net`: a negative-edge clock), tinyriscv_clint (`undriven net raddr_o[0] reaches
  primary output; pass --allow-undriven`). The flow turned both into a privacy refusal (`absolute or home path in equiv header.check.detail`);
  the tool's own last line is in `flow.csv`.
- 9 x lvs: 8 x `Netlists do not match`, 1 x `Top level cell failed pin matching` (tinyriscv_div, the largest layout, 7181 extracted cells, 772 s).

Questions for the controller (not fixed here): (1) the tiny-design floorplan with zero rows; (2) the `gds`-stage label `physical:repair_buffer` for CTS buffers
against `physical:cts_buffer` at `placed` and `routed` (38 cells in 4 designs); (3) the privacy check turning an `equiv` tool error into a path refusal;
(4) the LVS supply-net mismatch of small designs.

### Block recovery without a model (right block for a flip-flop key construct; key = same HDL line and column)

| design | gds | gates | lut4 | k4 | k6 |
|---|---|---|---|---|---|
| Prob105_rotate100 | 1 / 1 | 1 / 1 | 1 / 1 | 1 / 1 | 1 / 1 |
| Prob115_shift18 | 1 / 1 | 1 / 1 | 1 / 1 | 1 / 1 | 1 / 1 |
| Prob121_2014_q3bfsm | 1 / 1 | 1 / 1 | 1 / 1 | 1 / 1 | 1 / 1 |
| picorv32_pcpi_div | 0 / 2 | no key | 0 / 2 | 0 / 2 | 0 / 2 |
| pooled (right / key) | 3 / 5 = 0.600 | 3 / 3 = 1.000 | 3 / 5 = 0.600 | 3 / 5 = 0.600 | 3 / 5 = 0.600 |

The other five designs of the 9 have no flip-flops (or none in a key construct) and no key. Cell counts differ by endpoint (for example
Prob105: 613 cells at gds, 1007 at gates, 402 at lut4, 303 at k4 and k6). On the benchmark the share is 0.610 at gates, 0.754 at k4 and 0.773 at k6
(paper Table tab:join); 5 constructs cannot say whether the gds endpoint is above or below them. The LVS-failed `tinyriscv_div` (partial
run, 1 key construct) has 0 of 1 at every endpoint but gates (no key). Q-L12 key with construct type at k4/k6/lut4 is in `prior_key.csv`.

### Limits of this result

- 9 of 44 designs reach LVS match; the finding holds for them. They are 8 VerilogEval problems and 1 processor module, 14 to 1563 logic cells.
- The `extracted` stage holds cells, not transistors. The join is on cell type and DEF-placement location (a real scanned chip has no DEF).
- OpenROAD is the March 2022 pin, the power grid is two layers (met1 rails, met4 straps), the library is drive strength 1 without latches.
- The `cone` link is `medium` by definition: a mapped gate maps to the RTL objects whose spans it shares, so the chain is complete but coarse at that step.
- Block recovery: 5 key constructs, grouping by line and column without a construct type, cell class `O-lut` as a stand-in, no retuning.
