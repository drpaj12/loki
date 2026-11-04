# The Loki III paper

`loki.tex` — the Gate-Breaker-style results paper: how good are the L0, L1 and L2 experiments,
without more intelligence, at recovering structure. IEEEtran, Overleaf-uploadable (compile with
pdfLaTeX; `IMAGE/` holds the shared TikZ styles and `fig_loki.tex`, `joined.bib` the
bibliography).

Every number traces to the experiment records:

- `experiments/rename-l2/EXPERIMENT.md` — the renamed-instance re-run (L0 datasets under the
  cell_type schema, L1 with the hard detector, L2 clustering and the GNN against 1-WL).
- `experiments/f3-recovery/EXPERIMENT.md` — the f3 (cmos6 gate netlist) experiment: the L0
  provenance ceiling, calibrated and uncalibrated L1 on the renamed f3 floors, and the
  L0-stop/L1-stop AST/CFG similarity with the flatten control; the tables and honest notes are
  in that file.
- `work/loki-rename-exp/` and `work/gatebreaker-exp/` — the first experiments on the controller
  machine (kept off-repo; the protocol notes are in the experiment files).
- `experiments/veval-l0/EXPERIMENT.md` and its CSVs — the L0 provenance experiment on the 156
  VerilogEval references (three floors), the complexity quartiles, the feature matrix and the
  sizes. `veval-tables.tex` is generated from them: run
  `python3 experiments/veval-l0/paper_tables.py` to rewrite it (byte-identical on rerun).
- `experiments/quartiles/` — per-quartile (Q1-Q4) tables for the LLM pilot (arms A, B, C, exact
  McNemar per quartile and stratified) and for the Loki-only results. `quartile-tables.tex` is
  generated: run `python3 experiments/quartiles/quartiles.py` (byte-identical on rerun).
- `experiments/l3-census/EXPERIMENT.md` and `results/` -- the Loki L3 pattern census (register row P3C; loki.tex paragraph "Loki L3: design patterns").
- `experiments/llm-full/EXPERIMENT.md` (Results 2026-10-29) and `experiments/llm-full/results/` -- the full LLM run (137 problems, 3 draws, arms A, B, C); loki.tex Section `sec:llm-full`, register rows LLM3 and LLM4. The PDF was not rebuilt in the session that wrote it (no TeX tools on that machine).
- `experiments/ql10-blocks/EXPERIMENT.md` and `results/` -- Q-L10, Loki's blocks decoded one at a time by a language model (register rows QL10-a to QL10-e; loki.tex Section `sec:ql10`, appendix record `rec:ql10`). `python3 experiments/ql10-blocks/q10_analyze.py` rewrites `results/summary.md` and the csv tables from the committed copies (no model call); `q10_astcfg.py` (needs Odin III and the Gate-Breaker scripts) writes `results/astcfg_rows.csv`.
- `experiments/ql11-astcfg-why/EXPERIMENT.md` and `results/` -- Q-L11, AST and CFG similarity for every language-model arm (one scorer) and why higher-level structure is not recovered (register rows QL11-a to QL11-c; loki.tex Sections `sec:endpoints` and `sec:ql11`, appendix record `rec:ql11`). `results/summary.md` is written by `q11_report.py` from the committed csv files (no model call); `q11_rescore.py` and `q11_struct.py` need Odin III, the Gate-Breaker scripts and the Q-L9 result pickle and write `results/astcfg_all.csv` and `results/construct_loss.csv`.
- `experiments/ql12-k4k6/EXPERIMENT.md`, `experiments/ql12-lut4/EXPERIMENT.md` and their `results/` -- Q-L12, back to HDL at the LUT endpoints (register rows QL12-a, QL12-b; loki.tex Section `sec:ql12`, Tables `tab:ql12` and `tab:ql12sbs`, appendix record `rec:ql12`). The paper's FPGA-side endpoints are gates, lut4 (real four-input) and k6; the k4 of the first run is a replicate of k6 for the VerilogEval set.
- `experiments/ql13-gds/EXPERIMENT.md`, `results/summary.md` and `PAPER-DRAFT.md` -- Q-L13, provenance on the GDS path, the fourth deep target (rows QL13-a, QL13-b; Section `sec:ql13`, Table `tab:gds`, the last row of `tab:join`, record `rec:ql13`).
- The Gate-Breaker VerilogEval replication table (`tab:veval`) is in Experiments (rows GB1, GB2 of the register).

Tables marked `[TODO: ...]` are numbers not yet measured.
- The suite tree is no longer in this paper (2026-11-02: it appears only in the Odin III paper and on GitHub); the Introduction has the Loki flow figure `IMAGE/fig_loki_flow.tex` instead, and `IMAGE/fig_loki.tex` is the pipeline figure of the Methodology. 

## Cleanup for reading (2026-11-02)

`loki.tex` now tells the current story in the main text (summary, step-by-step Background, method as it stands
including L3 anchors, growth and join, results with a what-did-not-work table, the language-model
section, discussion, future work with Q-L10, conclusion). The round-by-round records are Appendix
`app:records` in time order (rounds 1 to 6, HAL, LLM pilot, FSM encoding, L3 census and detector,
graphlets, Q-L4 to Q-L9), then the f3 detail, then the research log (`register.tex`) last. Nothing
was deleted. Build with the Odin-style wrapper `build/loki-local.tex` (see below); the Overleaf zip
is `loki-paper-overleaf.zip` in `~/odin3-ws/PAPERS`.

## Step 2 structure (2026-10-28)

`loki.tex` is written as hypothesis, experiment, result, verdict (USEFUL, POSSIBLY GOOD, INCONCLUSIVE,
DISMISSED). Support files, all in `docs/paper/`:

- `hypotheses.md` (the register, one row per hypothesis), `innovations.md`, `outline.md`, `terms.md`.
- `make_register.py` writes `register.tex` (the appendix research log) from `hypotheses.md`.
- `make_glossary.py` writes `terms.md` from `terms.json` (the Background defines each term in prose, tagged `% def:<key>`; no glossary file); `check_terms.py --tex loki.tex`
  must report 0 use-before-definition findings.
- `split_tables.py` splits the generated `round*-tables.tex` and `hal-tables.tex` into `gen/*-macros.tex`
  (the number macros) and one `gen/tab-*.tex` per table, so the paper prints only the tables of the kept
  hypotheses. Rerun it after the generated files change.
- Bibliography: `luuthesis` (J. Luu, PhD thesis, University of Toronto, 2014) joins `jamiesonthesis`
  (P. A. Jamieson, PhD thesis, University of Toronto, 2007) for the Background. The PDFs live only in
  `work/mimir-papers/` and are never committed.
- Build: from `docs/paper`, `latexmk -pdf -interaction=nonstopmode -outdir=build loki.tex` with the system TeX Live (`IEEEtran.cls` and `IEEEtran.bst` sit beside `loki.tex`, see `IEEEtran-NOTICE.md`; no font wrapper needed). Last checked: 59 pages, 0 undefined references.
- Tests for `make_register.py`, `make_glossary.py` and `split_tables.py`: `tests/test_paper_tools.py` (determinism plus a small fixture each).
- `gen/quartile-*`, `gen/tab-q-*`, `gen/tab-veval-*` (untracked) are leftovers of an earlier `split_tables.py` that also split `quartile-tables.tex` and `veval-tables.tex`; the paper inputs those two files directly and does not use them.

## Structured arguments (2026-11-02)

The Results and the language-model section of `loki.tex` are structured arguments with seven fixed parts (Hypothesis, Implication, Experiment, Methodology, Measurements, Interpretation, Conclusion with the verdict). Register-row ids are pointers to the research log. The as-run narrative of the full run, hints version 2 and the per-quartile tables is in appendix records `sec:llm-full-rec`, `sec:llm-hints2-rec` and `sec:quartiles-rec`. The Background gives sources and ties each subsection to the experiments. The Implication parts are the authors' reasoning.
