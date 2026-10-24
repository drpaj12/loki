# Loki f3 experiment: provenance ceiling and L1 recovery on the cmos6 gate netlist

Run 2026-10-23. Loki `exp/f3-recovery` at 660d445 (off origin/main aa83e65; cell_type schema,
T17 hard detector, the #14 gate-Verilog final-equivalence fix, the paper). Odin III 1.1.0
(`/home/jamiespa/odin3-ws/odin3/build/release/libodin3.so`, ABI 6). Dataset: the rebuilt
cell_type-schema L0 at `work/loki-rename-exp/dataset-rebuild` (68 designs, f3 floor for 65)
and its renamed twin `dataset-rebuild-renamed` (seed 20261022, library names preserved).
Experiment data lives in `work/loki-f3-exp`; the scripts and the f3 calibration file are on
the branch under `experiments/f3-recovery/`.

## Question

On the cmos6 gate netlist (`f3`, Gate-Breaker's AND/OR/NOT library): what is the L0
provenance ceiling, how well does L1 recover from RENAMED gates, are buses and control-vs-data
reconstructed, and how good are AST/CFG similarity at L0-stop vs L1-stop (the L1 delta)?

## Result in one paragraph

The f3 provenance ceiling is complete for labels (all 50,047 gate nodes labelled, cell-typed
and HDL-spanned; 112/113 module scopes and 611/666 leaf signal names recovered). L1 recovers
nothing on f3 under the protocol's calibration: zero constructs are counted or committed
against 144 ground-truth instances, buses are proposed 2,569 times and match none of the 120
ground-truth buses, and the only perfect score, datapath role F1 1.000, is vacuous because f3
provenance has no control cells to confuse it with. The base and renamed runs are
byte-identical (digest 9368cfc26303), so naming is neutral there too. Because L1 commits
nothing, L1-stop Verilog equals the input netlist and the AST/CFG delta is exactly 0.0 in
every quartile; an uncalibrated diagnostic commits 1,535 hypotheses and moves the means
barely (+0.011 AST, -0.007 CFG), and a flatten control of that committed design beats the
gate netlist (AST +0.053, CFG +0.056), showing the paper's top-module metrics penalise
Loki's committed hierarchy rather than reward it.

## Protocol

1. **L0 ceiling** (`tools/l0_ceiling.py`): for every design with an f3 floor, count graph
   nodes, label rows, rows with a `cell_type`, rows with an HDL span, distinct `module_path`
   scopes, and distinct original signal names (leaf names from `key.json` ports and nets).
   Compare with the reference RTL's module, instance and declared-signal counts
   (pyverilog 1.3; `tools/sanitize_refs.py` writes structure-preserving syntax-fixed copies
   for the micro sources pyverilog rejects).
2. **L1** (`tools/run_l1.py`): fit a fresh f3 calibration on the 50 train designs with f3
   floors (`loki calibrate --floor f3 --split train`), then run `loki re` on the 15 test
   designs' f3 netlists, base and renamed, smallest netlist first. Each run uses the
   micro-fit f3 calibration (`--calib calib/f3.json`), all detectors, all features. The
   renamed run's overlay/report is translated through the inverse rename map and scored with
   `loki.score.metrics.score_run` against the same original-named answer key; both variants'
   `score.json` are written with `loki.schemas.dump_json` so the neutrality digest compares
   bytes. The hard detector is f1-only by design (`unmap` runs only on f1 floors with hard
   cells), so f3 has no hard proposals; that is a property of the flow, not a failure.
3. **AST/CFG** (`tools/astcfg.py`): per test design, compare the reference micro RTL with
   (a) L0-stop: the f3 gate netlist as structural Verilog (`netlist.v`), and (b) L1-stop:
   `design.v` written by `loki re` after its raise/submodule commits. AST similarity is the
   paper's pyverilog Algorithm 2 (depth 3, kind-normalized, best Jaccard per reference
   subtree, mean). CFG similarity is Algorithm 3 from the odin3 CFG probe
   (`work/odin3-cfg/tools/cfg-probe/odin3_cfg.py`, common width, sigma 0.5) over Odin III's
   elaborated AST. Designs are ranked by f3 node count; quartile means are over that rank.

## TODO numbers

(filled from the runs below)

## L0 ceiling (65 f3 designs, 50,047 gate nodes)

The answer key is complete at the gate level: every graph node has a label row, every row
carries a `cell_type` (the cmos6 cell name) and every row carries an HDL file, line and
column span into the reference source. What the provenance reconstructs beyond the labels
is the hierarchy and the original signal names, and there the coverage is high but not
complete: 112 distinct module scopes against 113 module definitions in the references
(99.1%, 54 of 65 designs complete) and 611 distinct leaf signal names against 666 declared
signals (91.7%, 44 of 65 designs complete, median 100%, minimum 55.6%). The module gap is
mostly reference-side: generate blocks elaborate away branches (`if_generate`,
`case_generate`) and unused submodules are dropped, so the reference file declares modules
the chosen parameters never build. The signal gap is the synthesis side: internal nets that
the mapping created or merged have no original name left, which is why the L0 ceiling is a
ceiling and not an oracle.

| metric | recovered | reference | coverage |
|---|---|---|---|
| labelled nodes | 50,047 | 50,047 nodes | 1.000 |
| rows with `cell_type` | 50,047 | 50,047 rows | 1.000 |
| rows with HDL span | 50,047 | 50,047 rows | 1.000 |
| module scopes | 112 | 113 modules | 0.991 |
| leaf signal names | 611 | 666 declared signals | 0.917 |

Per-design rows: `l0-ceiling.csv` and `l0-ceiling.json` in this directory.

## L1 test set, ground truth and calibration

The f3 manifest gives 65 designs; the L0 split rule puts 15 of them in test (23,098 gate
nodes; the largest is `micro_bm_arithmetic_unused_bits` at 15,225 nodes) and 50 in train
(26,949 nodes). Ground truth over the 15 test floors: 17 `adder`, 17 `adder_cin`, 20
`comparator`, 16 `eq_const`, 2 `ff_srst`, 17 `hard_add`, 11 `hard_mul`, 7 `mux`, 7
`mux_bit`, 22 `register`, 8 `subtractor`; 120 buses. Roles over the 15 test floors: 20,541
datapath, 912 mixed, 1,551 io, 18 const, 76 unknown, and **zero control** cells anywhere on
f3 (f1 has 4, f2 none), so the control-vs-data question has no f3 answer key; only the
datapath side is scorable. The hard kinds (`hard_add` 17, `hard_mul` 11) are L0 construct
types whose f3 cells are gates: the hard detector is f1-only by design (`unmap` runs only on
f1 floors holding hard cells), so those are unreachable at f3 and excluded from the L1
macro-F1 by the "no counted prediction" rule.

The calibration file is fitted on the 50 train designs' f3 floors with the branch build
(`loki calibrate --dataset ... --floor f3 --split train`) and committed at
`experiments/f3-recovery/calib/f3.json`.

## L1 results (f3 calibration, the protocol's setting)

Thirty runs (15 test designs, base and renamed; 856 s base, 849 s renamed, the largest design
`micro_bm_arithmetic_unused_bits` 604 s), all stopping at `fixed_point`, all
`final_equiv = equivalent`. Base and renamed score digests are identical
(sha256 9368cfc26303...), so the renamed netlists contribute no decision bit at f3 either.

The calibrated result is the strict one: **no construct is counted** (0 counted, 0 matched
against 144 ground-truth instances; macro-F1 0.0), and **no hypothesis is committed at all**.
The fitted f3 priors are strongly negative because the gate-level detectors are imprecise on
the train floors (e.g. `arith/comparator` -9.24 from 31,036 proposals with 2 true), so the
highest calibrated confidence anywhere in the 15 designs is a bus at p=0.764, below the
0.9 commit threshold; the recovered Verilog is byte-identical to the input gate netlist in
15 of 15 designs. Buses are proposed but never match: 2,569 counted bus hypotheses against
120 ground-truth buses, 0 matched (precision 0.0, recall 0.0; no matched bus to report a
width or bit order for). The role detector labels every logic cell `datapath`, which is
100% correct only because the f3 answer key has no `control` cells: datapath P/R/F1
1.000/1.000/1.000 over 20,541 cells, control n/a (0 GT, 0 predictions). The hard kinds are
unreachable by design (`unmap` is f1-only) and have no counted prediction.

| kind | GT | calib counted | calib matched | calib F1 | none counted | none matched | none P | none R | none F1 |
|---|---|---|---|---|---|---|---|---|---|
| adder | 17 | 0 | 0 | n/a | 1 | 1 | 1.000 | 0.059 | 0.111 |
| adder_cin | 17 | 0 | 0 | n/a | 0 | 0 | n/a | 0.000 | n/a |
| comparator | 20 | 0 | 0 | n/a | 14 | 0 | 0.000 | 0.000 | 0.000 |
| eq_const | 16 | 0 | 0 | n/a | 1,141 | 0 | 0.000 | 0.000 | 0.000 |
| ff_srst | 2 | 0 | 0 | n/a | 7 | 0 | 0.000 | 0.000 | 0.000 |
| hard_add | 17 | 0 | 0 | n/a | 0 | 0 | n/a | 0.000 | n/a |
| hard_mul | 11 | 0 | 0 | n/a | 0 | 0 | n/a | 0.000 | n/a |
| mux | 7 | 0 | 0 | n/a | 0 | 0 | n/a | 0.000 | n/a |
| mux_bit | 7 | 0 | 0 | n/a | 0 | 0 | n/a | 0.000 | n/a |
| register | 22 | 0 | 0 | n/a | 3 | 1 | 0.333 | 0.045 | 0.080 |
| subtractor | 8 | 0 | 0 | n/a | 0 | 0 | n/a | 0.000 | n/a |
| **macro-F1 / totals** | 144 | **0** | **0** | **0.0** | 1,166 | 2 | | | **0.0382** |

The `--calib none` columns are a diagnostic, not the protocol's setting: they show what the
detectors propose before calibration prunes it. Even uncalibrated, only 2 of 144 construct
instances match (one adder, one register); the volume is `eq_const` (1,141 counted, 0
matched) and `comparator` (14, 0). Buses are 2,835 counted, 0 matched. The uncalibrated
setting is naming-neutral too (digest ce26d3ad0b90...), and it commits 1,535 hypotheses in
11 of 15 designs (mostly `eq_const` and bus groups), which is what makes the L1-stop Verilog
differ from the input for the AST/CFG diagnostic below. Calibration is worth less than a
hundredth of an F1 point here and costs every commit; the honest reading is that the f3
detector set does not recover the construct ground truth, calibrated or not, and the
calibration correctly says so by committing nothing.

Buses and roles:

| question | calib | no calib |
|---|---|---|
| bus counted / matched / GT | 2,569 / 0 / 120 | 2,835 / 0 / 120 |
| bus P / R / F1 | 0.000 / 0.000 / 0.000 | 0.000 / 0.000 / 0.000 |
| datapath P / R / F1 (GT 20,541) | 1.000 / 1.000 / 1.000 | 1.000 / 1.000 / 1.000 |
| control P / R / F1 (GT 0) | n/a | n/a |

## AST/CFG at L0-stop vs L1-stop

L0-stop is the f3 gate netlist (`netlist.v`); L1-stop is `design.v` after the raise/submodule
commits. Reference is the micro RTL (5 of the 15 test references needed the mechanical
pyverilog sanitization: `lpm_all`, `match5_str_arch`, `param_override`, `parameter_2`,
`if_generate`). Designs ranked by f3 node count; quartile 0 smallest.

Under the protocol's calibrated setting, L1 commits nothing, so L1-stop is byte-identical to
L0-stop and the delta is exactly 0.0 for every design and quartile (AST over 15 designs, CFG
over 13; `match5_str_arch` and `arithmetic_unused_bits` exceed the CFG probe's practical
O(n^2) size limit of 12,000 nodes and are reported n/a). That is the answer to "how much
better does L1 make it" at f3: no better, because the calibrated flow makes no changes.

| quartile (n) | AST L0 | AST L1 | dAST | CFG L0 (n) | CFG L1 | dCFG |
|---|---|---|---|---|---|---|
| 0 (4) | 0.4428 | 0.4428 | 0.0000 | 0.7909 (4) | 0.7909 | 0.0000 |
| 1 (4) | 0.3765 | 0.3765 | 0.0000 | 0.4224 (4) | 0.4224 | 0.0000 |
| 2 (4) | 0.3969 | 0.3969 | 0.0000 | 0.7013 (4) | 0.7013 | 0.0000 |
| 3 (3 AST / 1 CFG) | 0.4003 | 0.4003 | 0.0000 | 0.7507 (1) | 0.7507 | 0.0000 |
| mean (15 AST / 13 CFG) | 0.4044 | 0.4044 | 0.0000 | 0.6468 | 0.6468 | 0.0000 |

The `--calib none` diagnostic is where L1 actually edits the netlist, so it is the only place
the metrics can move. It does not help: AST rises by +0.0111 on average but the per-quartile
deltas are mixed (-0.0151, -0.0009, +0.0573, +0.0004), and CFG falls by -0.0075
(-0.0133, -0.0124, +0.0001, +0.0055). The commits are mostly wrong `eq_const`/bus pieces, so
this is not evidence for or against the recovery; it is evidence that the top-module
Algorithms 2 and 3 do not reward Loki's committed hierarchy. A flatten control on the
uncalibrated L1-stop (Odin III `hierarchy --top top; proc; flatten; write_verilog`) is
reported below as the "what if the cells were inlined" view.

| diagnostic (no calib) | AST L0 | AST L1 | dAST | CFG L0 | CFG L1 | dCFG |
|---|---|---|---|---|---|---|
| quartile 0 (4) | 0.4428 | 0.4277 | -0.0151 | 0.7909 | 0.7776 | -0.0133 |
| quartile 1 (4) | 0.3765 | 0.3756 | -0.0009 | 0.4224 | 0.4099 | -0.0124 |
| quartile 2 (4) | 0.3969 | 0.4542 | +0.0573 | 0.7013 | 0.7014 | +0.0001 |
| quartile 3 (3 AST / 1 CFG) | 0.4003 | 0.4007 | +0.0004 | 0.7507 | 0.7561 | +0.0055 |
| mean | 0.4044 | 0.4155 | +0.0111 | 0.6468 | 0.6394 | -0.0075 |

The flatten control (`tools/flatten_astcfg.py`) inlines the committed hierarchy with the Odin
III CLI (`--top top; hierarchy --top top; proc; flatten; write_verilog`) and truncates the
file to the flattened top (Odin III's IR cannot delete the dead committed modules, and both
tools refuse a multi-root file). Against the same references the inlined L1 design beats the
gate netlist on both metrics: AST 0.4576 against 0.4044 (+0.0533; L1-stop itself is 0.4155)
over all 15 designs, and CFG 0.6941 against 0.6382 (+0.0559; L1-stop 0.6296) over the 12
designs the probe can finish. The control includes `proc` lowering, so it measures "the
recovered logic with its hierarchy inlined", not only inlining. The reading: the paper's
Algorithms 2 and 3 read one module, so they score the top-level text, and Loki's L1 commits a
hierarchy; a recovery that produces hierarchy is systematically penalised until it is
flattened. That is a metric limitation for netlist-to-RTL comparison, not a property of the
recovery.

| flatten control (no calib) | AST | CFG |
|---|---|---|
| L0-stop gate netlist | 0.4044 (15) | 0.6382 (12) |
| L1-stop committed hierarchy | 0.4155 (15) | 0.6296 (12) |
| L1-stop flattened | 0.4576 (15) | 0.6941 (12) |
| delta flat - L0 | +0.0533 | +0.0559 |




## Limitations and honest notes

- The f3 floor exists for 65 of 68 micros; `micro_adder_hard_block`,
  `micro_hard_adder_cin_propagation` and `micro_multiply_hard_block` are refused by the gate
  reader (unresolved library modules), so their hard blocks are outside this measurement.
- The hard detector is f1-only by design: `unmap` runs only when the floor is f1 and the
  graph holds hard cells. The 17 `hard_add` and 11 `hard_mul` f3 ground-truth instances have
  no detector coverage and no counted prediction, so they are excluded from the macro-F1 by
  the no-counted-prediction rule; read the macro-F1 as "over the kinds the f3 flow can
  propose", not over all 11 GT kinds.
- The control-vs-data question has no f3 answer key: zero `control` role labels in all
  50,047 f3 rows. The datapath F1 1.000 is vacuous (every logic cell predicted datapath).
- Four of the 15 test references needed mechanical pyverilog sanitization (trailing comma,
  `defparam`, empty `#()`, implied-generate wrappers); the sanitizer records exactly which.
  The CFG side reads the originals through Odin III, so only the AST metric sees the fixed
  copies.
- The CFG similarity is Algorithm 3 as implemented by the odin3 probe: pure-Python
  shortest-path histograms and a pairwise kernel, $O(n^2)$ in CFG nodes. It completes for 13
  of 15 designs at L0/L1 (12 after flatten, where `proc` lowering grows the graph) and is
  reported n/a above 12,000 CFG nodes (`match5_str_arch`, `arithmetic_unused_bits`). No
  approximation was substituted; the quartile-3 CFG mean is therefore one design at L1.
- The calibrated L1-stop is byte-identical to L0-stop in all 15 designs, so the primary
  AST/CFG delta of 0.0 is exact by construction, not a measurement of two similar files.
- The uncalibrated diagnostic is not the protocol's setting; it is included because the
  calibrated flow commits nothing and the metrics would otherwise have no L1-stop to measure.
  Its AST/CFG numbers describe what Loki's wrong commits do to the metrics, not recovery
  quality.
- The flatten control includes Odin III `proc` lowering of the committed function modules, so
  it is "hierarchy inlined and processes lowered", not pure inlining. Dead committed modules
  cannot be removed from the IR, so the flattened file is truncated to its top module for the
  metrics; both choices are noted here because they are tool properties.
- Calibration is fitted on micros only (50 train designs); the ready suite-level
  `calib/f3.json` in the repo is a different population and was not used.

## Data and commands

Data under `/home/jamiespa/odin3-ws/work/loki-f3-exp`:

- `l0-ceiling.json`, `l0-ceiling.csv` — the per-design L0 ceiling.
- `calib/f3.json` — the f3 calibration (copy committed at
  `experiments/f3-recovery/calib/f3.json`).
- `runs/base`, `runs/renamed` — the 30 calibrated L1 runs (`score.json` next to each run).
- `runs-nocalib/base`, `runs-nocalib/renamed` — the 30 uncalibrated diagnostic runs.
- `scores/analysis.json`, `scores/analysis-nocalib.json` — per-kind/bus/role aggregates and
  the base==renamed digests; `scores/buses-*.json` — the bus match detail (all empty).
- `astcfg-l0-l1.json`, `astcfg-nocalib.json`, `astcfg-flat.json` — the AST/CFG tables.
- `designs-v/refs-sanitized/` — the 15 mechanically fixed reference copies.
- Logs: `/home/jamiespa/odin3-ws/work/loki-f3-exp/logs/` (one line per run) and
  `/tmp/claude-1000/f3-*.log`.

    export ODIN3_ROOT=/home/jamiespa/odin3-ws/odin3
    export ODIN3_LIB=$ODIN3_ROOT/build/release/libodin3.so
    export PYTHONPATH=$ODIN3_ROOT/plugins/python
    E=/home/jamiespa/odin3-ws/work/loki-f3-exp
    T=$E/.venv/bin
    $T/python experiments/f3-recovery/tools/l0_ceiling.py dataset-rebuild ref-sanitized ...
    $T/loki calibrate --dataset work/loki-rename-exp/dataset-rebuild --floor f3 \
        --split train --out $E/calib/f3.json --odin3-root $ODIN3_ROOT
    $T/python experiments/f3-recovery/tools/run_l1.py run --variant base ... --calib $E/calib/f3.json
    $T/python experiments/f3-recovery/tools/run_l1.py score --variant renamed ... --rename-map ...
    $T/python experiments/f3-recovery/tools/analyze_f3.py $E/runs $E/scores/analysis.json
    $T/python experiments/f3-recovery/tools/buses_f3.py $E/runs/base dataset-rebuild $E/scores/buses-base.json
    $T/python experiments/f3-recovery/tools/astcfg.py $E/runs/base dataset-rebuild ref refs-sanitized $E/astcfg-l0-l1.json
    $T/python experiments/f3-recovery/tools/flatten_astcfg.py $E/runs-nocalib/base dataset-rebuild ref refs-sanitized $E/astcfg-flat.json
