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
- The Gate-Breaker VerilogEval replication table (`tab:veval`) fills in as that run lands.

Tables marked `[TODO: ...]` are numbers not yet measured.
