# Loki

Reverse engineering of structural netlists (LUT, hard-block and gate-level) back to hierarchical, word-level
Verilog, with a Bayesian hypothesis flow over Odin III's provenance IR. Status: specs and plans in
`docs/specs/` and `docs/plans/` (L0 ground-truth dataset, L1 Bayesian hypotheses, L2 analysis plugins).

Loki is part of **Yggdrasil** (the project / world tree), the suite of Odin III
(<https://github.com/drpaj12/odin3>), Wyrd-I (<https://github.com/drpaj12/wyrd>), Loki and Midgard (the Verilog
Town game). Loki depends on the `odin3` Python package and never changes the Odin III core.

License: MIT.
