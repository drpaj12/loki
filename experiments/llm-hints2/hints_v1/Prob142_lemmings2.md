Loki structural hints for the netlist above. Loki is a netlist analysis program (no language model).
Its output follows between the markers. The worked examples above did not carry hints.
Net names in the hints are wires and ports of the netlist above, except the names w1, w2, ...:
those are helper nets that have no wire of their own; each is defined in the list of helper nets
at the end of the hints, in terms of netlist wires or other helper nets.
[LOKI-HINTS-BEGIN]
# Loki analysis of a gate netlist

## 1. What this is

Loki III analysed the gate-level netlist `netlist.v` (sha256 eb3d5b9f8aae, floor f3).
The list below holds Loki's claims about its higher-level structure.
Each claim has a confidence (a probability) and a proof status.
Trust order: proved or derived claims, then unproven claims with high confidence, then candidates.
Committed claims have confidence of at least 0.9; candidates are listed from 0.5 and are unconfirmed.

## 3. Summary

| kind | committed | candidate | rejected |
| --- | --- | --- | --- |
| adder | 0 | 0 | 2 |
| bus | 0 | 8 | 0 |
| eq_const | 2 | 0 | 6 |

Input cells (in Loki's re-mapped netlist): 15.

Recovered module hierarchy (a module contains its children):

- h8 eq_const_h8 (eq_const)
- h11 eq_const_h11 (eq_const)

## 4. Committed claims

- h8: 1 cell form a comparison against a constant, `Y = (A != 3)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets bump_right, ground. Outputs: Y = nets w2. Recovered as module eq_const_h8, instance eq_const_h8_i. Role: datapath.
- h11: 1 cell form a comparison against a constant, `Y = (A != 3)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets bump_left, ground. Outputs: Y = nets w5. Recovered as module eq_const_h11, instance eq_const_h11_i. Role: datapath.

## 5. Buses, state machines and roles

Buses:
- h5 (unconfirmed): 2 bits, bit order from wf: bit 0 = next[1]; bit 1 = w1.
- h6 (unconfirmed): 2 bits, bit order from wf: bit 0 = aaah; bit 1 = next[1].
- h7 (unconfirmed): 2 bits, bit order from wf: bit 0 = w5; bit 1 = w2.
- h9 (unconfirmed): 2 bits, bit order from wf: bit 0 = w4; bit 1 = next[0].
- h10 (unconfirmed): 2 bits, bit order from wf: bit 0 = w6; bit 1 = w4.
- h18 (unconfirmed): 3 bits, bit order from net_id: bit 0 = walk_left; bit 1 = walk_right; bit 2 = w6.
- h46 (unconfirmed): 2 bits, bit order from wf: bit 0 = aaah; bit 1 = w1.
- h47 (unconfirmed): 2 bits, bit order from wf: bit 0 = w7; bit 1 = next[0].

State machines: none.

Roles of committed claims: datapath: h8, h11.

## 6. Candidates (not committed, unconfirmed)

- h5 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.6011. Inputs: slice0 = nets next[1]; slice1 = nets w1. Role: datapath.
- h6 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.6011. Inputs: slice0 = nets aaah; slice1 = nets next[1]. Role: datapath.
- h7 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.6011. Inputs: slice0 = nets w5; slice1 = nets w2. Role: datapath.
- h9 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.6011. Inputs: slice0 = nets w4; slice1 = nets next[0]. Role: datapath.
- h10 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.6011. Inputs: slice0 = nets w6; slice1 = nets w4. Role: datapath.
- h46 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.6011. Inputs: slice0 = nets aaah; slice1 = nets w1. Role: datapath.
- h47 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.6011. Inputs: slice0 = nets w7; slice1 = nets next[0]. Role: datapath.
- h18 (unconfirmed): 3 cells form a 3-bit bus, `bus: 3 bits`. No proof recorded. Confidence 0.5000. Inputs: ctrl = nets state[1]; slice0 = nets walk_left; slice1 = nets walk_right; slice2 = nets w6. Role: datapath.

## 7. Rejected claims

- h1: Loki tested a 2-bit adder (`Y = A + B`) on 6 cells and the proof showed it differs (truth_table), counterexample A[0]=0,A[1]=0,B[0]=0,B[1]=0.
- h3: Loki tested a 2-bit adder (`Y = A + B`) on 5 cells and the proof showed it differs (truth_table), counterexample A[0]=0,A[1]=0,B[0]=0,B[1]=0.
- h12: Loki proposed a comparison against a constant (`Y = (A == 0)`) on 1 cell; rejected: commit failed: ODIN3_ERR_INVALID_ARG.
- h13: Loki proposed a comparison against a constant (`Y = (A == 1)`) on 2 cells; rejected: commit failed: ODIN3_ERR_INVALID_ARG.
- h14: Loki proposed a comparison against a constant (`Y = (A != 1)`) on 3 cells; rejected: commit failed: ODIN3_ERR_INVALID_ARG.
- h15: Loki proposed a comparison against a constant (`Y = (A == 7)`) on 5 cells; rejected: commit failed: ODIN3_ERR_INVALID_ARG.
- h16: Loki proposed a comparison against a constant (`Y = (A == 3)`) on 2 cells; rejected: commit failed: ODIN3_ERR_INVALID_ARG.
- h49: Loki proposed a comparison against a constant (`Y = (A == 0)`) on 1 cell; rejected: commit failed: ODIN3_ERR_INVALID_ARG.

## 9. What Loki does NOT claim

- Candidates and rejected claims are not statements of fact.
- Module names such as `adder_h1` are Loki's labels built from the kind and the id; they are not the original HDL names, which Loki does not know.

## Helper nets

These nets have no wire of their own in the netlist. Each is defined from netlist wires or other helper nets.

- w1 = NOT(state[0])
- w2 = OR(NOT(bump_right), NOT(ground))
- w3 = NOT(walk_right)
- w4 = AND(NOT(w2), NOT(w3))
- w5 = OR(NOT(bump_left), NOT(ground))
- w6 = AND(NOT(w5), NOT(state[1]))
- w7 = AND(NOT(w6), NOT(state[0]))
[LOKI-HINTS-END]
Designer prior: designers write RTL from familiar patterns. If a signal looks like a condition, it
probably is one; if a register group looks like an FSM, it probably is one.
