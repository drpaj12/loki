# Q-L12 lut4: back to HDL at a real four-input LUT endpoint (plan, 2026-11-03)

Branch exp/ql12-lut4 on loki main 99f3636 (after #88, the Q-L12 results). This lane PREPARES: it makes no model call. The
controller runs the calls (Workflow) after the count and token estimate. This file is committed and pushed first; that commit
SHA is the plan SHA of the results. A later change is a dated entry under "Amendments"; the old text stays.

## Peter's words (2026-11-03)

"Let's just do the 4 endpoint, then add the 3 results - let's not worry about bigger."

Purpose chain (hub `docs/purpose.md`, Loki rows): reverse engineering of structural netlists (Peter's goal), at three real endpoints:
gates, four-input LUTs, six-input LUTs. RQ: Q-L12 (`experiments/ql12-k4k6`). Measures: functional pass@1 of the assembled RTL,
Gate-Breaker's two similarity measures (AST, CFG; the Q-L11 scorer), share of the Odin III provenance key recovered by one right block.

## Why this experiment (the Q-L12 finding)

Q-L12 (`ql12-k4k6/EXPERIMENT.md`, Results) found that its "k4" and "k6" are both the six-input mapper: LUTs of 1 to 6 inputs, and k6 only
adds hard adders. For the VerilogEval set the prompts are byte-identical (120 of 121 arm A and 1584 of 1610 arm D prompts), so those two
endpoints are replicates, not two LUT sizes. No four-input LUT netlist was ever built. This experiment builds it: the same designs, the
same mapper, the same flow, with ABC told to make LUTs of at most four inputs.

## Plain English

At the gates endpoint the model sees gates. At Q-L12's "k6" it sees lookup tables of up to six inputs. Here it sees the same designs
after the Odin III mapper packs the logic into lookup tables of at most four inputs. A four-input table hides fewer gates than a
six-input one, so there are more cells and each says less. Two ways to ask for the HDL, exactly as in Q-L12: arm D (Loki cuts the netlist
into blocks, the model decodes one block at a time, a script glues the decoded blocks) and arm A (the whole netlist in one prompt,
Gate-Breaker's method applied to a LUT netlist). The question is the Q-L12 question at the endpoint that was missing: does the block
decode hold up against gates, and does the whole-netlist prompt fall behind it?

## Definitions

- gates: the cmos6 gate netlist (Q-L10 and Q-L11 rows). k6: the Q-L12 "k6" rows (Odin III, six-input LUTs plus hard adders; the repository's
  name is `f1-k6`). The Q-L12 "k4" rows are the same six-input mapper without the adder map; they are not used here, because they are not
  a four-input LUT netlist (a note, not a result).
- lut4 (this experiment, cell class `O-lut`, floor `f2`): the Odin III soft-logic LUT netlist (BLIF `.names` covers and `.latch`
  flip-flops, no hard blocks) with LUTs of at most four inputs. How K is set: the Loki floor script for f2 ends with `lower; abc --lut 6`;
  `abc --lut <K>` is the Odin III pass option that passes K to ABC (`odin3/docs/PHASE3.md`, script language: `{K}` is the LUT size, from
  `abc --lut <K>`). `l4_census.py` replaces `--lut 6` by `--lut 4` in that script, in its own process only, and calls
  `loki.build.build_floor` as the l3-census does; the Odin III log of each build prints `K=4`. `read_arch` needs an architecture file;
  the VTR `k4_N4_90nm.xml` of the checkout is used (four-input LUTs, no hard blocks). Odin III is the build `build/rel-main2`, read only.
- Everything else (netlist reader, glue rule, blocks, prompts, assembly, checks) is the Q-L12 code, imported unchanged through
  `l4_env.py`; the top-level port bits keep their original names, every other net is `w<k>`.

## Hypothesis H-L12 carried to lut4 (amendment of Q-L12, written before any call)

H-L12 carried to the endpoint "lut4" unchanged:
(a) D at lut4 not lower than D at gates (non-inferior within 0.05), pass@1 primary, AST flat and CFG flat secondary;
(b) A lower than D at lut4.
Same tests, bootstrap (2000 resamples, seed 20261103), labels and Holm family as `ql12-k4k6/EXPERIMENT.md`, with lut4 as the endpoint.
The confirmatory family is the two pass@1 tests (a) and (b) at lut4 (exact McNemar on MAJ, Holm over the two). Headline first: mean
difference and W/L/T over designs, then the strict label (a positive difference whose interval touches zero is INCONCLUSIVE).
Descriptive, no verdict: lut4 minus k6 for D and for A (same problems, same draws).

## Design set, arms, prompts

- Designs: those of the Q-L12 reduced run: the VerilogEval problems of the Q-L10 set that pass the ceiling filter, plus the four
  processor modules (`picorv32_pcpi_mul` cannot be read by Odin III). Ceiling filter re-run at lut4 (`q12_stubcheck` logic): a design
  whose faithful decode of the lut4 netlist does not pass the testbench has no call.
- Prompts: the frozen `ql12-k4k6/block_prompt_lut.txt` (sha256 cbacc539...) and `a_prompt_lut.txt` (sha256 7639439...), read from
  that directory (not copied), the same system message (`re`, md5 c95998c379b2d7e520c508b25a5a4c92), the same 2-shot prefix, the same
  two-delimiter call file. The prompts say "LUT-level netlist (BLIF)" without a size, so no edit is needed for K=4.
- Subset as Q-L12 amendment 9: arm A on every design with an A call (prompt body at most 40000 B); arm D on the designs of at most 64
  blocks. One draw for the processor modules, three for the VerilogEval problems. Call numbers start at 1 in the new run root
  `work/ql12l4-out`; `work/ql12-out` is never modified.
- Stop rule, blinding statement, tool-use audit and limits: as `ql12-k4k6/EXPERIMENT.md` (the limits there hold; one more: the lut4
  netlists are Odin III builds with a different `read_arch` file than the k6 rows, which does not change soft-logic mapping but is a
  difference of tool input).

## Amendments

- 2026-11-03 (before any model call; plan commit 0bf0c8d): preparation finished. The plan text above is unchanged; the frozen prompt
  files were not touched (sha256 checked in `l4_calls.py` and in `test_l4.py`). Findings:
  1. Netlists. 51 VerilogEval/processor designs built (`l4_census.py`, Odin III `build/rel-main2`, f2 with `abc --lut 4`, read_arch
     `k4_N4_90nm.xml`): every `ve_*` build `ok` except `ve_Prob046_dff8p` (`fail`: both equivalence checks `error`; the same status as its
     census build at six inputs, files written, the design passes the stubcheck, so it is kept as in Q-L12), and `picorv32_pcpi_mul`
     `skipped` (Odin III front end, as in Q-L12). Max LUT inputs: 4 in every lut4 netlist (51 of 51; `results/netcheck.csv`,
     `l4_netcheck.py`); the k4 and k6 netlists of Q-L12 reach 6. Counts over the 44 designs of the set (non-glue LUTs / glue cells
     (constants, buffers) / flip-flops / hard adders): lut4 4235 / 339 / 1047 / 0; k4 (six-input mapper) 3066 / 339 / 1047 / 0; k6 3111 / 339 /
     1047 / 198. The four-input mapping needs 38 percent more LUTs than the six-input one for the same flip-flops.
  2. Ceiling filter at lut4 (`results/stubcheck.csv`, the Q-L12 test): the same 7 problems fail as at k4 and k6 (Prob071, Prob088,
     Prob089, Prob118, Prob139, Prob151, Prob156; reasons as Q-L12 amendment 2), 40 VerilogEval problems pass. Designs of the test set:
     40 VerilogEval problems + 4 processor modules.
  3. Blocks (`blocks_summary.csv`). 631 blocks over the 44 designs. 12 problems are only constants and buffers (no block, no call; their
     D row is the fixed assembly, as Q-L12). Three designs have more than 64 blocks and so no D call (amendment 9 rule of Q-L12):
     Prob092_gatesv100 (298), Prob017_mux2to1v (100) and, new at lut4, Prob105_rotate100 (75 blocks; 2 at the six-input mapper).
     They keep their arm A call.
  4. Calls (`counts.csv`, `counts_full.csv`): 529 calls = A 121 + D 408 (reduced run); 23 batches of at most 24 (`batches.json`, `run-batches.json`
     compact form, `batches-D.json` without arm A, same call numbers). For the record the full call set (all blocks) is 1948 (A 121, D 1827).
     A is over the 40000 B cap (no A row, `a_limit.csv`) for picorv32_pcpi_div (47352 B), tinyriscv_div (56617 B) and tinyriscv_csr
     (74129 B); A runs on `tinyriscv_clint` and on all 40 VerilogEval problems (3 draws each, 1 for clint: 121).
  5. Token estimate (estimate, not measurement; Q-L12 method: prompt bytes / 3.2 plus the system message as input; output 113 per call + 0.36
     per gate-level cell of the design shared over blocks by LUT-cell share; harness overhead of each subagent not included): arm A 316,723 in +
     20,099 out; arm D 411,962 in + 53,696 out; together 728,685 in + 73,795 out = 802,480. Per batch 16.2k to 103.5k. Q-L12 moved the weekly
     meter about 8 points for 1074 calls; 529 calls is about 4 points on that rate.
  6. Leak gate: 0 hits over the system message, 408 block prompts, 121 A prompts and all 529 call files (`l4_calls.py` stops on a hit). The user
     message of all 529 call files was re-hashed and equals `calls_table.csv` prompt_sha256 (0 mismatches).
  7. Dry run (`l4_dryrun.py`, `dryrun_result.json`): 156 stub replies for 9 designs (constants only, one-block combinational, register designs,
     FSMs, a mux tree, a shift register, `tinyriscv_clint`), faithful RTL for draw 1 and one of five fault patterns afterwards: 50 design rows,
     0 unexpected outcomes, 0 timeouts, 120 of 131 blocks check `ok` (the rest are the injected faults), the AST/CFG scorer returned values for
     12 rows. `l4_analyze.py` ran on the dry rows (numbers are stub data and not used).
  8. Reuse. The Q-L12 modules are imported unchanged through `l4_env.py`, which sets `ENDPOINTS = {"lut4": ("O-lut", "f2")}`, the output
     directory, the census tree and a template reader that reads the frozen prompts from `ql12-k4k6`. `ql12-k4k6` is not modified (git diff
     against main is empty). `l4_dryrun.py` is a copy of `q12_dryrun.py` with the lut4 endpoint and design list.
  9. Analysis (`l4_analyze.py`): the tests of the plan (a), (b), the descriptive A-at-lut4 minus A-at-gates, and lut4 minus k6 for D and A,
     for pass@1, AST flat and CFG flat; `results/side_by_side.csv` puts gates, lut4 and k6 in one table (all designs with data, and the
     designs all three share). Holm over the two pass@1 McNemar tests (a, all designs) and (b).

## Results (2026-11-03)

Generated tables: `results/summary.md`, `results/tests.csv` and `results/side_by_side.csv` (`l4_analyze.py`). They are built from
`results/results.csv`, `results/blocks.csv` and `results/astcfg_rows.csv` (`l4_run.py collect`, `l4_run.py astcfg`). Call status:
`results/status.csv`. Tool-use audit: `results/tool-audit.tsv`.

### Plain English

With real four-input LUTs, the result of Q-L12 holds and becomes even. The block decode (D) passes about as often as at gates.
Its RTL is as close to the reference in AST and CFG, slightly closer in AST. The whole-netlist prompt (A) is no longer ahead of D:
- D passes more draws than A on 2 designs (Prob064_vector3, Prob097_mux9to1v).
- A passes more draws than D on 3 designs (Prob052_gates100, Prob115_shift18, Prob154_fsm_ps2data).
- They tie on 33 designs.

The four-input netlists are about 37 percent larger in LUT count than the six-input ones (4235 against 3066 LUTs). Every measure stays
within a few points of six-input LUTs and gates. Across these three endpoints, finer LUTs neither help nor hurt recovery on designs of
this size.

### Run

529 calls, one fresh `claude-sonnet-5-5` subagent each, no retry. 528 `ok`. Call 255 is `no_file`: it replied in chat and did not
write its outbox. The stop rule was never near.

The weekly meter read 44 before the run and 47 after. Output tokens summed from the subagent transcripts: 0.77M. Cache reads were
46.7M. These are harness totals.

Tool-use audit: no call touched another call's file or the repository.
- Call 101 wrote its own outbox through Bash.
- Call 529 edited its own outbox after writing it.

### H-L12 at lut4 (headline first, then the label; unit = design, bootstrap 95 percent interval)

| test | measure | difference | interval | designs W/L/T | label |
| --- | --- | --- | --- | --- | --- |
| (a) D lut4 minus D gates | pass@1 | +0.008 | (-0.089, +0.106) | 5/3/33 | INCONCLUSIVE |
| (a) | AST flat | +0.006 | (+0.001, +0.011) | 16/4/12 | SUPPORTED |
| (a) | CFG flat | -0.004 | (-0.020, +0.006) | 9/8/18 | SUPPORTED |
| (b) D minus A at lut4 | pass@1 | -0.026 | (-0.105, +0.044) | 2/3/33 | INCONCLUSIVE |
| (b) | AST flat | -0.015 | (-0.039, +0.006) | 8/13/11 | INCONCLUSIVE |
| (b) | CFG flat | -0.009 | (-0.052, +0.044) | 5/19/11 | INCONCLUSIVE |

Exact McNemar on MAJ: p = 1.000 for (a) and for (b). Holm-adjusted p is 1.000 for both.

Verdict:
- H-L12(a) at lut4: SUPPORTED on AST and CFG, INCONCLUSIVE on pass@1, the primary measure. This is the same as at k4 and k6.
- H-L12(b) at lut4: INCONCLUSIVE. A is not lower than D.

Descriptive, no verdict:

| comparison | measure | difference | interval |
| --- | --- | --- | --- |
| A lut4 minus A gates | pass@1 | +0.019 | (-0.046, +0.083) |
| D lut4 minus D k6 | pass@1 | -0.033 | (-0.122, +0.057) |
| D lut4 minus D k6 | AST | -0.002 | |
| D lut4 minus D k6 | CFG | -0.002 | |
| A lut4 minus A k6 | pass@1 | -0.033 | (-0.075, +0.000) |

The A lut4 minus A k6 pass@1 difference is 0/3/37 over designs.

Side by side (mean over the designs all three endpoints share; `results/side_by_side.csv`):

| arm | measure | gates | lut4 | k6 |
| --- | --- | --- | --- | --- |
| D | pass@1 (41) | 0.846 | 0.854 | 0.886 |
| D | AST flat (32) | 0.784 | 0.789 | 0.791 |
| D | CFG flat (35) | 0.877 | 0.873 | 0.875 |
| A | pass@1 (36) | 0.926 | 0.944 | 0.972 |
| A | AST flat (32) | 0.805 | 0.806 | 0.805 |
| A | CFG flat (36) | 0.903 | 0.885 | 0.883 |

Provenance (arm D): key constructs with a right block, and with a right block whose decode checks `ok`:
- draw 1: 10 of 23, of which 7 check `ok`.
- draw 2: 4 of 8, of which 3 check `ok`.
- draw 3: 4 of 8, of which 4 check `ok`.

Processor modules (one draw):
- D: tinyriscv_csr `pass` (15 of 16 blocks `ok`).
- D: picorv32_pcpi_div `neq` (2 of 5 blocks `ok`).
- D: tinyriscv_div `error` (5 of 7 blocks `ok`).
- D: tinyriscv_clint `error` (4 of 5 blocks `ok`).
- A: tinyriscv_clint `neq`.

### Limits

The limits of Q-L12 apply: small designs, a random-simulation block check, and an equivalence check for the processor modules that
is not a proof. Prob092, Prob017 and Prob105 have no D row at lut4 (more than 64 blocks). Prob105 does have D rows at k4 and k6, so
it is not in the D lut4-minus-k6 pairs.
