# Loki L0 -> L1 -> L2 on renamed micro benchmarks (cell_type schema, T17 hard detector)

Run 2026-10-23. Odin III 1.1.0 (`odin3/build/release/libodin3.so`), Loki `exp/rename-l2` at
802f58f (origin/main: cell_type in graph labels #32, T17 hard detector with `unmap` #33, #14
final_equiv fix #34), Wyrd origin/main 050f694. Python 3.12.3, numpy 2.5.4, scipy 1.18.1,
scikit-learn 1.9.1, networkx 3.7, torch 2.14.1+cpu, torch_geometric 2.8.1, ORCA e146a8b.
Experiment dir `/home/jamiespa/odin3-ws/work/loki-rename-exp` (not a git repo); scripts and
calibration files live on the branch under `experiments/rename-l2/`. The first experiment's
notes are preserved as `EXPERIMENT-1-before-cell-type.md`.

## Result in one paragraph

The full L0 -> L1 -> L2 pipeline is naming-neutral on the rebuilt micro dataset. L0 rebuilds
under the cell_type schema with 0 check errors (68 designs, f1/f2 for all, f3 for 65), the
renamed dataset (269 netlists, 105,646 identifiers) inverse-maps to the original token for
token, and all 476 L1 runs of each variant pair produce byte-identical scores: base and renamed
`score.json` digests match for the calibrated (204 runs), uncalibrated (204) and repo-calibration
(68) sets. The hard detector (T17) is the new recovery win on f1: `hard_mul` P/R/F1 1.000/1.000/
1.000 (30 of 30) and `hard_add` calibrated P 0.985 R 1.000 F1 0.993 (67 of 67; with `--calib none`
323 of the 390 counted `hard_add` are unmatched (the declined-adder proposals the calibration
prunes)). f2 stays
calibration-bound: micro-fit calibration gives macro-F1 0.108 (counted 91, matched 19, ECE 0.217),
`--calib none` 0.075 (933/35, ECE 0.650), and the repo's pre-T17 `calib/f2.json` 0.072 (13/7,
ECE 0.089, reproducing the first experiment's 13/7 exactly). L2 runs all four analyses on floor
f2: the GNN (node+graphlet+WL+NPN features) scores test macro-F1 0.424 against the 1-WL
baseline's 0.272 (accuracy 0.886 vs 0.849, 3,932 test nodes) and its `metrics.json` is
byte-identical on the renamed graph; cluster quality is identical for 271 of 272 partitions, and
the one difference is a spectral-clustering nondeterminism that reproduces on the base dataset
alone (not naming). Two real defects surfaced and are reported below: the first experiment's
rename script renamed library (`.blackbox`) cell types (fixed here; with T17 live it removed all
hard recovery from renamed f1), and L2 spectral clustering is not deterministic across processes.

## Protocol

1. L0 rebuild under the cell_type schema: `loki bench init --suite micro` (68 designs),
   `wyrd run --jobs 3 --mem-budget 8G` (136 runs, 68 designs x 2 architectures, under the
   heavy lock), `loki assemble`, `loki check` (0 errors). Floors built: `f1-k6`, `f1-earch`
   and `f2` for all 68 designs, `f3` for 65 (three hard-block Verilog designs are refused by
   the gate-level reader: unresolved module `adder`/`multiply`).
2. Rename, then verify: every net, `.cname`, design module name and floor directory becomes a
   seeded HMAC token; library cell types, pin names and `.blackbox` bodies stay. The verifier
   inverse-maps every token and requires token-for-token equality with the original netlist,
   byte-identical library blocks, and no numbered identifier left outside the map.
3. L0 provenance check: the renamed netlists are the same netlists by construction (step 2);
   the end-to-end check is L1 itself: base and renamed runs are scored against the same
   original-named answer key, and the per-run `score.json` files must be byte-identical.
4. L1: calibration fitted on the 52 micro train designs per floor (`f2`, `f1-k6`, `f1-earch`;
   T17 changed the proposals, so the old file is stale for this detector set). Six projects run
   through `wyrd run`: base and renamed x {micro-fit calibration, `--calib none` (the
   uncalibrated view), repo `calib/f2.json` f2-only (continuity with the first experiment)}.
   Base runs are scored with `loki score-all`; renamed runs have their overlay and report
   translated through the inverse rename map and are scored with the same `score_run`.
5. L2 on the renamed floors: `loki analyze` over the L0 `graph.json` (labels are the answer
   key). L2's numeric code parses `int(id[1:])`, so the renamed L2 input is the same graph with
   a seeded permutation of every identifier (node ids and edge net ids), not the HMAC text
   tokens of the BLIF; labels are identical on both sides. Cluster quality (modularity, NMI
   against module_path) and the GNN baseline against the 1-WL colour baseline are compared on
   the base and renamed inputs. The GNN refuses designs with no construct-labelled train-kind
   node (spec 9); the six port/const-only micro designs are dropped from both inputs by the
   same filter.

## L0 dataset (rebuilt)

`loki assemble`: 68 designs, `loki check`: 0 errors. Split: 52 train, 16 test designs
(manifest split rule unchanged).

| floor | designs ok | nodes | edges | label rows | unlabelled rows | writer / anon equivalence |
|---|---|---|---|---|---|---|
| f1-k6 | 68 | 7,896 | 13,158 | 7,896 | 0 | 68 / 68 equivalent |
| f1-earch | 68 | 7,896 | 13,158 | 7,896 | 0 | 68 / 68 equivalent |
| f2 | 68 | 13,545 | 39,291 | 13,545 | 0 | 68 / 68 equivalent |
| f3 | 65 | 50,047 | 80,141 | 50,047 | 0 | 65 / 65 equivalent |

Differences from the first experiment's dataset: the two hard-block designs that Odin III 1.0
refused on f1 (`micro_adder_hard_block`, `micro_hard_adder_cin_propagation`) now build (68
designs, not 66), the `f3` floor now builds for 65 designs, every label carries `cell_type`
(the 22 unlabelled f1 rows are gone), and `f1-k6`/`f1-earch` netlists remain byte-identical for
all 68 designs (the two f1 floors are duplicates, so their metrics are not independent).
28 designs carry at least one hard cell on f1 (27 on each f1 floor) and only one design
(`micro_multiply_hard_block`) on f2, where the hard cells map to LUTs.

## Rename scheme and the library-name bug found in the first script

`experiments/rename-l2/tools/rename_dataset.py`, seed 20261022 (same as the first experiment):
token = `HMAC-SHA256(seed | design | kind | original)` first 10 hex digits, `a` net, `c` cell,
`m` design module, `z` floor directory. 269 netlists and 105,646 identifiers renamed.

The first experiment's script renamed the library (`.blackbox`) model names as well
(`multiply` -> `m1b35bd4768`, and the `.subckt` references with it), because a BLIF library
block writes `.blackbox` *inside* the `.model .. .end` range while the script classified the
model by the next `.blackbox` marker. Self-consistent, so the netlist still parsed, and invisible
to L1 on that branch because there was no hard detector: all eight detectors ignored library cell
types. With T17 live the renamed f1 floors lose every hard proposal (`unmap` finds no `adder` or
`multiply` cell type, so no `unmap` facts and no `hard` hypothesis); on the buggy renamed dataset
54 of 204 scored runs differed from base; the 55 affected design/floors are the 27 hard-cell
designs' two f1 floors plus `micro_multiply_hard_block` f2 (one of them had no scored
prediction change). The script is fixed: a model block is classified by whether `.blackbox` appears
inside it, library lines are copied verbatim, and `rename-map.json` now holds only design module
names (`top`). The verifier (`verify_rename.py`) inverse-maps every token of every renamed
netlist and requires token-for-token equality with the original, byte-identical library blocks
and no `n<k>` identifier outside the map: 269 netlists, 0 failures, no extra files in the named
dataset. A direct check on `micro_adder_hard_block` f1 shows `unmap` records 2 recovered
`hard_add` on both sides after the fix.

## L1 results

Scoring is the L1 runbook's: `score_run` at Jaccard 0.5, one-to-one greedy matching of committed
predictions (`counted`) against L0 word/derived instances of the same kind. Macro-F1 averages
the per-kind F1 over the kinds that have both a ground-truth count and at least one counted
prediction on that floor; a kind with no counted prediction has no F1 and is listed with `n/a`
precision. Renamed numbers equal the base numbers exactly (see naming neutrality); the tables
below are base, and apply to both.

Totals: micro-fit calibration f1 271 counted / 107 matched / 688 GT (macro-F1 0.354), f2 91 /
19 / 686 (0.108), pooled ECE 0.217; `--calib none` f1 1,128 / 126 / 688 (0.202), f2 933 / 35 /
686 (0.075), ECE 0.650; repo calibration f2 13 / 7 / 686 (0.072), ECE 0.089.

### f2, all three calibration settings

| kind | calib counted | calib matched | calib P | calib R | calib F1 | none counted | none matched | none P | none R | none F1 | repo counted | repo matched | repo P | repo R | repo F1 | gt |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| adder | 9 | 9 | 1.000 | 0.134 | 0.237 | 10 | 10 | 1.000 | 0.149 | 0.260 | 4 | 4 | 1.000 | 0.060 | 0.113 | 67 |
| adder_cin | 2 | 1 | 0.500 | 0.015 | 0.029 | 5 | 2 | 0.400 | 0.030 | 0.056 | 1 | 0 | 0.000 | 0.000 | 0.000 | 67 |
| comparator | 0 | 0 | n/a | 0.000 | n/a | 79 | 1 | 0.013 | 0.009 | 0.010 | 0 | 0 | n/a | 0.000 | n/a | 116 |
| counter | 0 | 0 | n/a | 0.000 | n/a | 1 | 0 | 0.000 | 0.000 | 0.000 | 0 | 0 | n/a | 0.000 | n/a | 2 |
| eq_const | 0 | 0 | n/a | 0.000 | n/a | 538 | 0 | 0.000 | 0.000 | 0.000 | 0 | 0 | n/a | 0.000 | n/a | 102 |
| ff_en | 0 | 0 | n/a | 0.000 | n/a | 56 | 2 | 0.036 | 0.500 | 0.067 | 0 | 0 | n/a | 0.000 | n/a | 4 |
| ff_srst | 0 | 0 | n/a | 0.000 | n/a | 122 | 0 | 0.000 | 0.000 | 0.000 | 0 | 0 | n/a | 0.000 | n/a | 9 |
| hard_add | 0 | 0 | n/a | 0.000 | n/a | 0 | 0 | n/a | 0.000 | n/a | 0 | 0 | n/a | 0.000 | n/a | 67 |
| hard_mul | 0 | 0 | n/a | 0.000 | n/a | 0 | 0 | n/a | 0.000 | n/a | 0 | 0 | n/a | 0.000 | n/a | 30 |
| mux | 7 | 1 | 0.143 | 0.020 | 0.036 | 7 | 1 | 0.143 | 0.020 | 0.036 | 6 | 1 | 0.167 | 0.020 | 0.036 | 49 |
| mux_bit | 71 | 6 | 0.085 | 0.122 | 0.100 | 71 | 6 | 0.085 | 0.122 | 0.100 | 0 | 0 | n/a | 0.000 | n/a | 49 |
| mux_tree | 0 | 0 | n/a | 0.000 | n/a | 0 | 0 | n/a | 0.000 | n/a | 0 | 0 | n/a | 0.000 | n/a | 3 |
| register | 0 | 0 | n/a | 0.000 | n/a | 40 | 11 | 0.275 | 0.117 | 0.164 | 0 | 0 | n/a | 0.000 | n/a | 94 |
| subtractor | 2 | 2 | 1.000 | 0.074 | 0.138 | 4 | 2 | 0.500 | 0.074 | 0.129 | 2 | 2 | 1.000 | 0.074 | 0.138 | 27 |

f1 (f1-k6 = f1-earch), micro-fit calibration / `--calib none`:

| kind | calib counted | calib matched | calib P | calib R | calib F1 | none counted | none matched | none P | none R | none F1 | gt |
|---|---|---|---|---|---|---|---|---|---|---|---|
| adder | 0 | 0 | n/a | 0.000 | n/a | 0 | 0 | n/a | 0.000 | n/a | 67 |
| adder_cin | 1 | 0 | 0.000 | 0.000 | 0.000 | 1 | 0 | 0.000 | 0.000 | 0.000 | 67 |
| comparator | 0 | 0 | n/a | 0.000 | n/a | 38 | 1 | 0.026 | 0.009 | 0.013 | 116 |
| eq_const | 0 | 0 | n/a | 0.000 | n/a | 335 | 0 | 0.000 | 0.000 | 0.000 | 102 |
| ff_en | 7 | 2 | 0.286 | 0.500 | 0.364 | 7 | 2 | 0.286 | 0.500 | 0.364 | 4 |
| ff_srst | 0 | 0 | n/a | 0.000 | n/a | 109 | 0 | 0.000 | 0.000 | 0.000 | 9 |
| hard_add | 68 | 67 | 0.985 | 1.000 | 0.993 | 390 | 67 | 0.172 | 1.000 | 0.293 | 67 |
| hard_mul | 30 | 30 | 1.000 | 1.000 | 1.000 | 30 | 30 | 1.000 | 1.000 | 1.000 | 30 |
| mux | 64 | 1 | 0.016 | 0.020 | 0.018 | 64 | 1 | 0.016 | 0.020 | 0.018 | 49 |
| mux_bit | 99 | 6 | 0.061 | 0.122 | 0.081 | 99 | 6 | 0.061 | 0.122 | 0.081 | 49 |
| register | 1 | 1 | 1.000 | 0.011 | 0.021 | 55 | 19 | 0.345 | 0.202 | 0.255 | 94 |
| subtractor | 0 | 0 | n/a | 0.000 | n/a | 0 | 0 | n/a | 0.000 | n/a | 29 |

`hard_add` GT counts every L0 `$add` word (62 in the 66 first-experiment designs, 67 now); the
hard detector recovers all 67 on both f1 floors, and the micro-fit calibration keeps precision
0.985 by pruning the 390 unconditional proposals to 68. `hard_mul` is perfect. f2 has no hard
proposals: `unmap` runs on f1 floors only by design, and f2's hard cells are LUT-mapped except
one design. The f2 picture is unchanged from the first experiment: adder and subtractor are
precise but low-recall, `eq_const`/`comparator` false positives dominate the uncalibrated view,
and the micro-fit calibration suppresses `register`/`ff_srst` recall almost entirely.

Buses, roles and hierarchy (base; renamed identical):

| floor | setting | bus counted | bus matched | bus P | bus R | hier_f | datapath F1 | control F1 |
|---|---|---|---|---|---|---|---|---|
| f1-k6 / f1-earch | micro calib | 28 | 1 | 0.036 | 0.003 | 0.277 | 0.676 | 0.000 |
| f1-k6 / f1-earch | no calib | 57 | 3 | 0.053 | 0.008 | 0.484 | 0.676 | 0.000 |
| f2 | micro calib | 604 | 0 | 0.000 | 0.000 | 0.146 | 0.000 | n/a |
| f2 | no calib | 328 | 2 | 0.006 | 0.005 | 0.353 | 0.999 | n/a |
| f2 | repo calib | 337 | 0 | 0.000 | 0.000 | 0.055 | 0.999 | n/a |

The repo-calibration f2 row reproduces the first experiment exactly (337 counted, 0 matched,
datapath 0.999). The micro-fit calibration makes the f2 role classifier commit nothing
(datapath F1 0), while its bus proposals triple (604 counted, still 0 matched); calibration is
the lever on both, not naming.

## Naming neutrality

For each paired set, the sha256 over every run's `score.json` (design name + bytes) is identical:

| set | runs per side | base digest | renamed digest |
|---|---|---|---|
| micro-fit calibration, f1-k6/f1-earch/f2 | 204 | 7a7a604879ee | 7a7a604879ee |
| `--calib none`, f1-k6/f1-earch/f2 | 204 | 8ed7789cc7e0 | 8ed7789cc7e0 |
| repo `calib/f2.json`, f2 | 68 | 7efee198c910 | 7efee198c910 |

This is stronger than the first experiment's check because the hard detector is live: the
renamed runs traverse `unmap`, the hard facts, the hard commit (`+inf` evidence) and the
`cell_type`-bearing labels. Naming contributes no decision bit on these 68 designs under any of
the three settings. The re-verification also caught the rename-script bug above: with the
buggy renamed dataset the calibrated pair differed on 54 of 204 runs, all of them in designs
with library cells.

## L2 results

Floor f2, base and renamed. 74 analyses per variant (68 cluster + 5 region-export attempts, 4
of which found a LUT to anchor, + GNN), 0 failures, about 117 s each.

Cluster quality (mean over 68 designs; kmeans/affinity/spectral/Louvain on node features):

| method | designs | mean modularity | mean NMI(module_path) | mean clusters |
|---|---|---|---|---|
| affinity | 68 | -0.2264 | 0.2708 | 65.35 |
| kmeans | 68 | -0.2912 | 0.3220 | 6.16 |
| louvain | 68 | 0.4220 | 0.1360 | 12.38 |
| spectral | 68 | 0.3620 (renamed 0.3617) | 0.1378 | 13.90 |

271 of the 272 partition records are identical between base and renamed. The single difference
is `micro_bm_DL_4_16_encoder` spectral (same cluster count 6, modularity 0.0086 vs -0.0079,
different assignment). It is not a naming effect: re-running spectral on the *base* dataset in
fresh processes gives modularity -0.0079, -0.0410 and 0.0252 on three trials. Spectral
clustering (ARPACK embedding + k-means) is not deterministic across processes, against L2 spec
3's byte-identical determinism requirement; kmeans, affinity and Louvain are stable. Reported,
not fixed (core change, out of this experiment's scope).

GNN (SAGE, 100 epochs, features node+graphlet+WL+NPN, target construct_type, L0 split, 62
designs the GNN accepts; the six port/const-only designs are refused with spec 9's
`UNLABELLED_MESSAGE` and dropped from both sides by the same filter):

| metric | GNN | 1-WL baseline | majority | logreg |
|---|---|---|---|---|
| test macro-F1 | 0.4241 | 0.2717 | 0.0674 | 0.2550 |
| test accuracy | 0.8863 | 0.8492 | 0.7792 | 0.8512 |
| test nodes / designs | 3,932 / 13 | 3,932 / 13 | 3,932 / 13 | 3,932 / 13 |

The GNN beats the 1-WL baseline (`beats_wl` true). Base and renamed `metrics.json` and
`vocab.json` are byte-identical, and the four region exports have identical node/edge counts, so
L2's numbers depend on graph structure and the library-visible `cell_type`, not on the
identifier numbering. The LUT merge ceiling the spec names still applies: a LUT's label is its
primary construct, so accuracy cannot reach 1.

## What changed since the first experiment

1. Dataset: 68 designs (not 66), f1/f2 rebuilt on Odin III 1.1.0, labels carry `cell_type`,
   `f3` exists (65 designs), 100% labelled rows, and all 269 floors are writer/anon equivalent.
2. Detectors: T17 `hard` with `unmap` is live, so hard library words are recoverable on f1,
   where the first experiment had no detector and hard cells were opaque (`unmap` not on main).
   This is the largest recovery change: f1 `hard_mul` 30/30 and `hard_add` 67/67 (calibrated).
3. Calibration: the committed `calib/f2.json` was fitted before T17; this run fits new per-floor
   files on the 52 micro train designs (weights struct 0.0, wl 0.6, npn 0.3 for f2) and also
   reports the old file for continuity. The old file's f2 numbers are unchanged (13/7).
4. Rename tool: library (`.blackbox`) model names are no longer renamed. The first
   experiment's renamed dataset had them renamed, which T17 turns into a total loss of hard
   recovery; the first experiment's "library semantics stay" claim was not true for those names.
5. Naming neutrality is re-tested with the hard detector live, so it now covers the `unmap`
   fact path and the hard commit rule, not only the eight original detectors.
6. L2 exists: cluster quality and the GNN baseline against 1-WL are measured on base and
   renamed inputs; the first experiment had only the L2 skeleton to describe.

## Limitations and honest notes

- The two f1 floors are byte-identical netlists, so f1-k6 and f1-earch metrics are duplicates,
  not independent evidence.
- `hard_add`/`hard_mul` ground truth is the L0 construct type (`$add`, `$mul`); hard words whose
  L0 type is neither do not enter the scored GT (the reported hard F1 is against the
  construct-labelled words, not every library instance). f2 hard GT has no detector coverage.
- L2's numeric code requires `n<k>` ids; the renamed L2 input is a seeded permutation of the
  numbering, not the HMAC text tokens. Labels (the answer key) are identical on both sides, so
  L2's comparison tests id/order dependence, not label leakage.
- Spectral clustering is nondeterministic across processes (one design, reproduced on the base
  dataset); this is a Loki L2 defect, not a naming effect.
- Calibration is fitted on micros only (52 train designs); the committed all-suite file is a
  different population and its f2 numbers are reported separately.
- Wyrd's history-based per-step memory cap killed one run on each `--calib none` project
  (`micro_bm_arithmetic_unused_bits__f2`, estimated cap below the ~90 MB the run needs); it was
  re-run standalone with `loki re` into the same run directory and scored normally.

## Data and logs

All under `/home/jamiespa/odin3-ws/work/loki-rename-exp`:

- `datasets/l0-rebuild/` Wyrd L0 project (68 designs x 2 architectures, 136 runs).
- `dataset-rebuild/` assembled L0 dataset (68 designs, four floors).
- `dataset-rebuild-renamed/` 269 renamed netlists, `manifest.json`, `rename-map.json`;
  `verify-rename.json` sits next to it (the renamed dir holds netlists only).
- `runs-rebuild/{base-calib,renamed-calib,base-nocalib,renamed-nocalib,base-repocalib,renamed-repocalib}/`
  Wyrd projects (204 or 68 runs each).
- `scores-rebuild/{base-*,renamed-*}/` `scores.json`, `scores.md`, `detector-per-design.json`,
  `detector-aggregate.json`; `analysis-all.json` the six-set summary with digests.
- `l2-rebuild/{base,renamed}/` cluster partitions, exports, `gnn/metrics.json`, `l2-status.json`;
  `l2-rebuild/dataset-renamed/` the renamed graph dataset; `l2-rebuild/gnn-subset-*` the GNN
  labelled subsets; `l2-rebuild/summary.json` the L2 comparison.
- `tools/` (on the branch at `experiments/rename-l2/tools/`): `rename_dataset.py`,
  `verify_rename.py`, `make_l1_project.py`, `score_runs.py`, `analyze_l1.py`,
  `make_l2_dataset.py`, `run_l2.py`, `report_l2.py`.
- Calibration files on the branch: `experiments/rename-l2/calib/{f2,f1-k6,f1-earch}.json`.
- Logs: `/tmp/claude-1000/rn2-*.log`, per-analysis logs under `/tmp/claude-1000/rn2-l2-logs/`.

## Commands used

    export ODIN3_ROOT=/home/jamiespa/odin3-ws/odin3
    export ODIN3_LIB=$ODIN3_ROOT/build/release/libodin3.so
    export PYTHONPATH=$ODIN3_ROOT/plugins/python
    export VTR_ROOT=/home/jamiespa/odin3-ws/external/vtr-verilog-to-routing
    W=/home/jamiespa/odin3-ws/work/loki-rename2
    E=/home/jamiespa/odin3-ws/work/loki-rename-exp
    python3 -m venv --system-site-packages $W/.venv
    $W/.venv/bin/pip install ruff mypy cffi
    $W/.venv/bin/pip install --no-deps --no-build-isolation -e $W
    $W/.venv/bin/pip install --no-deps --no-build-isolation /tmp/claude-1000/rn2-wyrd
    $W/.venv/bin/pip install numpy scipy scikit-learn networkx
    $W/.venv/bin/pip install torch --index-url https://download.pytorch.org/whl/cpu
    $W/.venv/bin/pip install torch_geometric
    $W/.venv/bin/loki tools fetch-orca
    $W/.venv/bin/loki bench init --suite micro --odin3-root $ODIN3_ROOT --out $E/datasets/l0-rebuild
    flock -x /tmp/claude-1000/odin3-heavy.lock $W/.venv/bin/wyrd run \
        --project $E/datasets/l0-rebuild --jobs 3 --mem-budget 8G
    $W/.venv/bin/loki assemble --project $E/datasets/l0-rebuild --out $E/dataset-rebuild
    $W/.venv/bin/loki check $E/dataset-rebuild
    $W/.venv/bin/python $W/experiments/rename-l2/tools/rename_dataset.py \
        --source $E/dataset-rebuild --out $E/dataset-rebuild-renamed
    $W/.venv/bin/python $W/experiments/rename-l2/tools/verify_rename.py \
        --dataset $E/dataset-rebuild --renamed $E/dataset-rebuild-renamed --out $E/verify-rename.json
    for f in f2 f1-k6 f1-earch; do $W/.venv/bin/loki calibrate --dataset $E/dataset-rebuild \
        --floor $f --split train --out $W/experiments/rename-l2/calib/$f.json \
        --odin3-root $ODIN3_ROOT; done
    $W/.venv/bin/python $W/experiments/rename-l2/tools/make_l1_project.py --dataset <ds> \
        --floors f1-k6,f1-earch,f2 --calib <calib dir|none> --score-dataset $E/dataset-rebuild \
        --odin3-root $ODIN3_ROOT --out $E/runs-rebuild/<variant>
    flock -x /tmp/claude-1000/odin3-heavy.lock $W/.venv/bin/wyrd run \
        --project $E/runs-rebuild/<variant> --jobs 3 --mem-budget 8G [--force]
    $W/.venv/bin/loki score-all $E/runs-rebuild/<base variant>/runs \
        --dataset $E/dataset-rebuild --out $E/scores-rebuild/<variant>
    $W/.venv/bin/python $W/experiments/rename-l2/tools/score_runs.py --variant <variant> \
        --runs $E/runs-rebuild/<renamed variant>/runs --dataset $E/dataset-rebuild \
        --rename-map $E/dataset-rebuild-renamed/rename-map.json \
        --out $E/scores-rebuild/<variant>
    $W/.venv/bin/python $W/experiments/rename-l2/tools/analyze_l1.py \
        --set base-calib=... --set renamed-calib=... --out $E/scores-rebuild/analysis-all.json
    $W/.venv/bin/python $W/experiments/rename-l2/tools/make_l2_dataset.py \
        --dataset $E/dataset-rebuild --out $E/l2-rebuild/dataset-renamed
    $W/.venv/bin/python $W/experiments/rename-l2/tools/run_l2.py --dataset <ds> --floor f2 \
        --out $E/l2-rebuild/<variant> --gnn-subset $E/l2-rebuild/gnn-subset-<variant>
    $W/.venv/bin/python $W/experiments/rename-l2/tools/report_l2.py \
        --variant base=$E/l2-rebuild/base --variant renamed=$E/l2-rebuild/renamed \
        --out $E/l2-rebuild/summary.json
