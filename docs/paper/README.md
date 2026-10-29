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
- `experiments/llm-full/EXPERIMENT.md` (Results 2026-10-29) and `experiments/llm-full/results/` -- the full LLM run (137 problems, 3 draws, arms A, B, C); loki.tex Section `sec:llm-full`, register rows LLM3 and LLM4. The PDF was not rebuilt in the session that wrote it (no TeX tools on that machine).
- The Gate-Breaker VerilogEval replication table (`tab:veval`) is in Experiments (rows GB1, GB2 of the register).

Tables marked `[TODO: ...]` are numbers not yet measured.
- The suite tree (`IMAGE/fig_yggdrasil.tex`, with `IMAGE/odin3-tikz-styles.tex`) is a byte-identical copy of
  the hub's `images/src/` files (Yggdrasil III hub, `drpaj12/YggdrasilIII`). `make_blind_tree.py`
  (run in `docs/paper`) writes `IMAGE/blind/fig_yggdrasil.tex`, the same figure with the suite and tool
  names, the three wells and the self-cited baseline replaced by placeholders, as the Odin III paper's
  `make_blind.py` does. No build uses it yet (there is no blind build of this paper).

## Step 2 structure (2026-10-28)

`loki.tex` is written as hypothesis, experiment, result, verdict (USEFUL, POSSIBLY GOOD, INCONCLUSIVE,
DISMISSED). Support files, all in `docs/paper/`:

- `hypotheses.md` (the register, one row per hypothesis), `innovations.md`, `outline.md`, `terms.md`.
- `make_register.py` writes `register.tex` (the appendix research log) from `hypotheses.md`.
- `make_glossary.py` writes `glossary.tex` and `terms.md` from one term list; `check_terms.py --tex loki.tex`
  must report 0 use-before-definition findings.
- `split_tables.py` splits the generated `round*-tables.tex` and `hal-tables.tex` into `gen/*-macros.tex`
  (the number macros) and one `gen/tab-*.tex` per table, so the paper prints only the tables of the kept
  hypotheses. Rerun it after the generated files change.
- Bibliography: `luuthesis` (J. Luu, PhD thesis, University of Toronto, 2014) joins `jamiesonthesis`
  (P. A. Jamieson, PhD thesis, University of Toronto, 2007) for the Glossary. The PDFs live only in
  `work/mimir-papers/` and are never committed.
- Build: `tectonic -X compile build/loki-local.tex -Z search-path=docs/paper` (the wrapper selects the OT1 font encoding).
- Tests for `make_register.py`, `make_glossary.py` and `split_tables.py`: `tests/test_paper_tools.py` (determinism plus a small fixture each).
- `gen/quartile-*`, `gen/tab-q-*`, `gen/tab-veval-*` (untracked) are leftovers of an earlier `split_tables.py` that also split `quartile-tables.tex` and `veval-tables.tex`; the paper inputs those two files directly and does not use them.
