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

(none before the first call)
