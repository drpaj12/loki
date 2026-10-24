# Loki L0 provenance on the VerilogEval references (veval-L0)

Run 2026-10-24. Loki `exp/veval-l0` (off origin/main 07aee68), Odin III 1.1.0 (ABI 6,
`odin3/build/release/libodin3.so`, checkout d0921d4e, slang adapter `libodin3_slang.so`), Wyrd
8e5edb2, pyverilog 1.3.0, Python 3.12.3, 12 cores, 23 GB VM. Data lives in
`work/loki-veval-exp` (not a git repo, dataset 1.3 GB); this directory holds the scripts and the
summary outputs. VerilogEval refs: `external/verilog-eval/dataset_spec-to-rtl/*_ref.sv`, 156 files
(a local copy without `.git`; the design.json provenance records the pinned commit d60f0b10 of
`loki bench`).

## Result in one paragraph

Of the 156 refs, 150 build on all three floors (`f1-k6`, `f2`, `f3`), 2 are skipped by Odin III's
SystemVerilog reader (`Prob151`, `Prob156`: `odin3: ODIN3_ERR_PARSE read_slang: ... an explicit
4-bit cast is not supported`, both Q4) and 4 fail Loki's own equivalence gate (`Prob031_dff`,
`Prob046_dff8p`, `Prob078_dualedge`, `Prob145_circuit8`; see Caveats). `loki check`: 0 errors.
On f3 the 150 designs have 54,306 gate nodes; every node is labelled, cell-typed and has an HDL
span (label_cov, cell_type_cov, hdl_cov geometric mean 1.000), the 150 module scopes of the 150
reference modules are all present (module_cov 1.000) and signal_cov (recovered leaf signal names
over declared reference signals) has geometric mean 0.986 (arithmetic mean 1.029; over 1 only
for 2 designs, where flattened array elements add names). Quartiles by the paper's absolute
bins: Q1 38, Q2 39, Q3 37, Q4 36 designs. Features present in at least one design: arithmetic 21,
select/mux 45, storage 67, fsm 16, control 50, buses 150 (multi-bit buses 96).

## Protocol

1. `build_project.py` writes the Wyrd project (same layout as `loki bench init --suite
   verilog-eval`: `designs/<id>/<id>.sv` + `design.json`, top `RefModule`) from the local refs.
   Differences from `bench init`: no clone, one architecture (`k6_frac_N10_frac_chain_mem32K_40nm`),
   designs listed smallest source (line count) first. Floors: `f1` (expands to `f1-k6`), `f2`, `f3`.
2. `wyrd run --jobs 3 --mem-budget 8G` under `flock -x /tmp/claude-1000/odin3-heavy.lock`, then
   `loki assemble` and `loki check`. Wyrd peak RSS about 4.6 GB, well under 60% of the VM.
3. `complexity_csv.py` reuses `work/gatebreaker-exp2/scripts/complexity.py` unchanged (paper
   eq. 2; absolute bins Q1 3-23, Q2 24-111, Q3 112-1064, Q4 1065-1326). pyverilog AST for 60
   refs, regex fallback for the other 96 (the documented deviation). The 156 scores equal the
   gatebreaker-exp2 scores exactly. Output: `complexity.csv`.
4. `summarize.py` reads the assembled dataset and writes `l0-ceiling-veval.csv`, `sizes.csv`,
   `features.csv`, `benchmark.csv` (problem id, quartile, ref line count, f3 node count) and
   `stats.json` (means, medians, geometric means, feature coverage). A second run gives
   byte-identical files.

### Feature rules (per design, from the f3 floor)

| column | rule |
|---|---|
| arithmetic | words of type `$add $sub $mul $div $mod $neg $pos $pow $alu $macc` (distinct word instances) |
| select | words of type `$mux $pmux $bmux $demux` |
| storage | register words: `$dff $dffe $adff $adffe $sdff $sdffe $sdffce $dffsr $aldff $dlatch $adlatch` |
| fsm | 1 if any word has the snapshot fsm flag, else 0 |
| control | 1 if any `labels.csv` row has role `control` or `mixed`, else 0 |
| buses | distinct non-empty `bus_name` in `labels.csv` (includes single-bit port names) |
| buses_wide | extra column: distinct `bus_name` with some `bit_index >= 1` (multi-bit buses) |

The paper maps count 0 to x, 1 to check, 2 or more to check-check. Because `buses` counts every
named signal it is at least 1 for all designs and at least 2 for 147; `buses_wide` is the
count the paper's "bus" row more likely means (agent default, both are committed).

## Caveats

- `--nolatches` turns inferred-latch paths into x and `lower --async sync` turns asynchronous
  resets into synchronous clears, so some netlists can be non-equivalent to the reference (same
  caveat as `work/gatebreaker-exp2/EXPERIMENT.md`).
- Failures (4 designs, reported as `fail`, absent from the dataset for all floors):
  `Prob031_dff` (the ref has `initial q = 1'hx`; the writer-vs-Odin BLIF check says `differs`
  on f1/f2, f3 was equivalent) and `Prob046_dff8p`, `Prob078_dualedge`, `Prob145_circuit8`
  (negedge flip-flops; `equiv-check` returns an error status for both comparisons). Loki
  records the run as failed rather than forcing the floor in.
- ref_modules, ref_instances and ref_signals come from pyverilog where it parses the ref
  (130 of 150) and a regex fallback otherwise (20); the regex counts are approximate and the
  reference signal count is the weakest number here. Complexity scores use the same 60/96
  AST/regex split as gatebreaker-exp2.
- f1-earch is not built (agent default); f2 and f3 do not depend on the architecture.

## Agent defaults and fixes needed to run

- Loki hard-coded `read_verilog --nolatches --vtr-compat`, which Odin III refuses for
  SystemVerilog, and the Python host never registered the slang adapter, so all 156 refs were
  skipped at first. Fixed on this branch (`loki/odin.py`, `loki/build.py`, tests): `.sv` sources
  read with `--nolatches` only, and `register_slang` loads `$ODIN3_SLANG_LIB` or
  `libodin3_slang.so` beside `$ODIN3_LIB` and registers `odin3_read_slang` (cffi, once per
  process). `.v` flows are unchanged.
- One architecture (k6), f1-earch skipped.
- Wyrd's default `other_mem` of 2 GB killed `Prob144_conwaylife` (peak 4.3 GB); it was rerun
  with a temporary `WYRD_CONFIG` copy setting `other_mem = "8G"` (`--jobs 1 --mem-budget 12G`),
  and then built.
- `buses_wide` added beside `buses`; `stats.json` and `benchmark.csv` are extra outputs.

## Numbers

Run counts and wall time: first `wyrd run` 156 runs, 3:09 wall (151 ok, 4 fail, 1 oom);
second pass 5 reruns, 1:14 wall (conwaylife ok, 4 fail again). `summarize.py` takes about
70 s (pyverilog). Split (manifest rule): f3 designs 117 train, 33 test.

L0 ceiling (f3, 150 designs; geometric mean): label_cov 1.000, cell_type_cov 1.000, hdl_cov
1.000, module_cov 1.000, signal_cov 0.986. Totals: 54,306 nodes and label rows, 150 of 150
module scopes, 841 recovered signal names against 745 reference signals.

Sizes (mean / median; all 150 designs; `stats.json` has the per-quartile n):

| floor | nodes | cells | nets |
|---|---|---|---|
| f1-k6 | 163.5 / 14.0 | 114.6 / 5.0 | 218.3 / 12.0 |
| f2 | 111.4 / 13.5 | 62.5 / 4.0 | 93.5 / 10.0 |
| f3 | 362.0 / 25.0 | 313.2 / 13.5 | 344.2 / 21.0 |

Per quartile (mean / median):

| floor, metric | Q1 (38) | Q2 (39) | Q3 (37) | Q4 (36) |
|---|---|---|---|---|
| f1-k6 nodes | 6.3 / 5.0 | 100.2 / 26.0 | 109.4 / 18.0 | 453.9 / 26.5 |
| f2 nodes | 6.1 / 5.0 | 100.0 / 26.0 | 77.4 / 13.0 | 269.8 / 26.5 |
| f3 nodes | 9.9 / 8.0 | 238.2 / 32.0 | 260.6 / 28.0 | 972.1 / 51.5 |
| f3 cells | 5.2 / 3.5 | 169.2 / 12.0 | 232.0 / 14.0 | 877.8 / 43.5 |
| f3 nets | 8.4 / 7.0 | 221.1 / 20.0 | 252.8 / 25.0 | 926.0 / 48.5 |

Feature coverage (designs with count >= 1; per quartile Q1/Q2/Q3/Q4; designs with >= 2):

| feature | >= 1 | Q1 | Q2 | Q3 | Q4 | >= 2 |
|---|---|---|---|---|---|---|
| arithmetic | 21 | 2 | 4 | 7 | 8 | 9 |
| select | 45 | 3 | 10 | 12 | 20 | 12 |
| storage | 67 | 0 | 0 | 31 | 36 | 12 |
| fsm | 16 | 0 | 0 | 1 | 15 | 0 |
| control | 50 | 1 | 4 | 15 | 30 | 0 |
| buses | 150 | 38 | 39 | 37 | 36 | 147 |
| buses_wide | 96 | 3 | 35 | 22 | 36 | 55 |

The quartile column in `sizes.csv` and `features.csv` is the complexity quartile of the ref.
