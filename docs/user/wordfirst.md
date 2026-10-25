# The word-first detector

Round 5 adds two opt-in detectors to `loki re` (L Q2.4: can words, control nets and FSMs be found
first, and the rest built around them?). They are not in the default detector list, so earlier
runs and calibration files reproduce.

    loki re netlist.blif --floor f2 --detectors wordfirst              # word-first only
    loki re netlist.blif --floor f2 \
        --detectors wordfirst,hard,ff_pattern,mux,arith,seqfn,fsm,bus,unit,role,wordgroup

Module: `loki/re/detectors/wordfirst.py` (`WordFirstDetector`, `WordGroupDetector`).

## `wordfirst` (runs before the per-bit detectors)

- Register words: flip-flops of one clock grouped by their strongest shared enable and reset nets
  (the D-cone analysis of `ff_pattern`); a group is split further by the control candidates shared
  by some but not all members when every part keeps two flip-flops; a group of more than 32 and
  plain flip-flops (no shared control) are split by the signature of the Q readers and the D
  driver. Output: `register`, `ff_en` and `ff_srst` words labelled by the control net.
- Mux words: 2:1 mux cells that share one select net (`mux`, with a `mux2` claim).
- Carry chains: the support-based chains of the `arith` detector, so the carry net joins the bits
  (`adder`, `subtractor`, `adder_cin`, with claims).
- Word-level `eq_const`: a cone whose support lies inside one register word (or the primary
  inputs) and is a single minterm (`eq_const` / `ne_const` claim).
- FSMs: a register word that passes a feedback-coupling test (every D cone reads a Q bit of the
  word and some cone reads at least two distinct bits), with the next-state cone as the
  footprint. No decoder is required (the `decoders` parameter only counts the word-level
  `eq_const` decoders inside the word). The test is necessary, not sufficient: it over-generates,
  because counters (carry chain), LFSRs (XOR taps) and any word whose bits feed each other pass it
  and are proposed as `fsm`; a plain shift register does not (one Q bit per cone) unless a stage
  also reads another bit. Nothing distinguishes an FSM from these. Round 5 measured the share
  by ground-truth kind (exploratory entry 2026-10-25-c of `experiments/round5/EXPERIMENT.md`).
  The Stage-0 text required at least two decoders; that rule can be selected for comparison with
  the environment variable `LOKI_WF_FSM_RULE=stage0` (default `round5`, the evaluated rule).
- Propagation: readers and drivers of a known word (registers, mux words, adder words) that form
  isomorphic slices of at least max(2, ceil(0.75 k)) bits become `bus` words, two levels deep.

## `wordgroup` (runs last)

Links the per-bit hypotheses (`ff_en`, `ff_srst`, `mux_bit`) to the word that contains them as
children and groups per-bit hypotheses that share an enable or reset net into word hypotheses.

## Agent defaults

Group split above 32 flip-flops; refinement only when every part keeps two flip-flops; support
limit 16 for `eq_const`; growth threshold 0.75 and depth 2; at most 4,000 seeds. No parameter is
fitted. The experiment is `experiments/round5/EXPERIMENT.md`.
