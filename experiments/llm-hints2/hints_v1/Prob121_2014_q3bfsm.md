Loki structural hints for the netlist above. Loki is a netlist analysis program (no language model).
Its output follows between the markers. The worked examples above did not carry hints.
Net names in the hints are wires and ports of the netlist above, except the names w1, w2, ...:
those are helper nets that have no wire of their own; each is defined in the list of helper nets
at the end of the hints, in terms of netlist wires or other helper nets.
[LOKI-HINTS-BEGIN]
# Loki analysis of a gate netlist

## 1. What this is

Loki III analysed the gate-level netlist `netlist.v` (sha256 9ac3f783a2cd, floor f3).
The list below holds Loki's claims about its higher-level structure.
Each claim has a confidence (a probability) and a proof status.
Trust order: proved or derived claims, then unproven claims with high confidence, then candidates.
Committed claims have confidence of at least 0.9; candidates are listed from 0.5 and are unconfirmed.

## 3. Summary

| kind | committed | candidate | rejected |
| --- | --- | --- | --- |
| bus | 2 | 13 | 0 |
| eq_const | 7 | 0 | 0 |
| ff_en | 0 | 2 | 0 |
| ff_srst | 0 | 2 | 0 |

Input cells (in Loki's re-mapped netlist): 29.

Of the committed cells, 3 (in 2 claims) are marked only by attributes on existing cells (form attrs). Those claims are not modules, so the hierarchy below does not show them.

Recovered module hierarchy (a module contains its children):

- h11 eq_const_h11 (eq_const)
- h25 eq_const_h25 (eq_const)
- h27 eq_const_h27 (eq_const)
- h29 eq_const_h29 (eq_const)
- h91 eq_const_h91 (eq_const)
- h92 eq_const_h92 (eq_const)
- h93 eq_const_h93 (eq_const)

## 4. Committed claims

- h11: 1 cell form a comparison against a constant, `Y = (A == 0)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets state[1], state[3]. Outputs: Y = nets _19_. Recovered as module eq_const_h11, instance eq_const_h11_i. Role: datapath.
- h25: 2 cells form a comparison against a constant, `Y = (A == 2)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets reset, x. Outputs: Y = nets _06_. Recovered as module eq_const_h25, instance eq_const_h25_i. Role: datapath.
- h27: 1 cell form a comparison against a constant, `Y = (A == 0)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets reset, x. Outputs: Y = nets _10_. Recovered as module eq_const_h27, instance eq_const_h27_i. Role: datapath.
- h29: 1 cell form a comparison against a constant, `Y = (A == 0)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets reset, state[0]. Outputs: Y = nets _08_. Recovered as module eq_const_h29, instance eq_const_h29_i. Role: datapath.
- h91: 1 cell form a comparison against a constant, `Y = (A == 0)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets _06_, _08_. Outputs: Y = nets _02_. Recovered as module eq_const_h91, instance eq_const_h91_i. Role: datapath.
- h92: 1 cell form a comparison against a constant, `Y = (A != 3)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets state[2], _10_. Outputs: Y = nets _11_. Recovered as module eq_const_h92, instance eq_const_h92_i. Role: datapath.
- h93: 1 cell form a comparison against a constant, `Y = (A != 3)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets state[4], _06_. Outputs: Y = nets _09_. Recovered as module eq_const_h93, instance eq_const_h93_i. Role: datapath.
- h44: 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.9474. Inputs: ctrl = nets w1; slice0 = nets z; slice1 = nets _13_. Role: datapath.
- h45: 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.9315. Inputs: ctrl = nets w2; slice0 = nets z; slice1 = nets _01_. Role: datapath.

## 5. Buses, state machines and roles

Buses:
- h5 (unconfirmed): 2 bits, bit order from wf: bit 0 = w4; bit 1 = w1.
- h6 (unconfirmed): 3 bits, bit order from wf: bit 0 = w1; bit 1 = _05_; bit 2 = w4.
- h7 (unconfirmed): 3 bits, bit order from wf: bit 0 = w5; bit 1 = w2; bit 2 = w6.
- h8 (unconfirmed): 3 bits, bit order from wf: bit 0 = _16_; bit 1 = z; bit 2 = _13_.
- h10 (unconfirmed): 2 bits, bit order from wf: bit 0 = _19_; bit 1 = _10_.
- h12 (unconfirmed): 2 bits, bit order from wf: bit 0 = w6; bit 1 = _05_.
- h15 (unconfirmed): 2 bits, bit order from wf: bit 0 = _11_; bit 1 = _09_.
- h44: 2 bits, bit order from net_id: bit 0 = z; bit 1 = _13_.
- h45: 2 bits, bit order from net_id: bit 0 = z; bit 1 = _01_.
- h46 (unconfirmed): 3 bits, bit order from net_id: bit 0 = _10_; bit 1 = _08_; bit 2 = _06_.
- h47 (unconfirmed): 3 bits, bit order from net_id: bit 0 = _09_; bit 1 = _02_; bit 2 = _17_.
- h80 (unconfirmed): 3 bits, bit order from wf: bit 0 = w4; bit 1 = w1; bit 2 = w6.
- h81 (unconfirmed): 3 bits, bit order from wf: bit 0 = w1; bit 1 = w4; bit 2 = w5.
- h83 (unconfirmed): 3 bits, bit order from wf: bit 0 = w3; bit 1 = _07_; bit 2 = w5.
- h84 (unconfirmed): 3 bits, bit order from wf: bit 0 = _07_; bit 1 = w3; bit 2 = w6.

State machines: none.

Roles of committed claims: datapath: h11, h25, h27, h29, h44, h45, h91, h92, h93.

## 6. Candidates (not committed, unconfirmed)

- h16 (unconfirmed): 3 cells form a flip-flop with enable, `ff_en: 1 bits`. No proof recorded. Confidence 0.9901. Inputs: d = nets _02_; en = nets reset. Outputs: q = nets state[0]. Role: datapath.
- h18 (unconfirmed): 4 cells form a flip-flop with enable, `ff_en: 1 bits`. No proof recorded. Confidence 0.9901. Inputs: d = nets _00_; en = nets state[3]. Outputs: q = nets state[1]. Role: datapath.
- h46 (unconfirmed): 3 cells form a 3-bit bus, `bus: 3 bits`. No proof recorded. Confidence 0.8569. Inputs: ctrl = nets reset; slice0 = nets _10_; slice1 = nets _08_; slice2 = nets _06_. Role: datapath.
- h6 (unconfirmed): 3 cells form a 3-bit bus, `bus: 3 bits`. No proof recorded. Confidence 0.7503. Inputs: slice0 = nets w1; slice1 = nets _05_; slice2 = nets w4. Role: datapath.
- h7 (unconfirmed): 3 cells form a 3-bit bus, `bus: 3 bits`. No proof recorded. Confidence 0.7503. Inputs: slice0 = nets w5; slice1 = nets w2; slice2 = nets w6. Role: datapath.
- h8 (unconfirmed): 3 cells form a 3-bit bus, `bus: 3 bits`. No proof recorded. Confidence 0.7503. Inputs: slice0 = nets _16_; slice1 = nets z; slice2 = nets _13_. Role: datapath.
- h80 (unconfirmed): 3 cells form a 3-bit bus, `bus: 3 bits`. No proof recorded. Confidence 0.7503. Inputs: slice0 = nets w4; slice1 = nets w1; slice2 = nets w6. Role: datapath.
- h81 (unconfirmed): 3 cells form a 3-bit bus, `bus: 3 bits`. No proof recorded. Confidence 0.7503. Inputs: slice0 = nets w1; slice1 = nets w4; slice2 = nets w5. Role: datapath.
- h83 (unconfirmed): 3 cells form a 3-bit bus, `bus: 3 bits`. No proof recorded. Confidence 0.7503. Inputs: slice0 = nets w3; slice1 = nets _07_; slice2 = nets w5. Role: datapath.
- h84 (unconfirmed): 3 cells form a 3-bit bus, `bus: 3 bits`. No proof recorded. Confidence 0.7503. Inputs: slice0 = nets _07_; slice1 = nets w3; slice2 = nets w6. Role: datapath.
- h5 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.6011. Inputs: slice0 = nets w4; slice1 = nets w1. Role: datapath.
- h10 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.6011. Inputs: slice0 = nets _19_; slice1 = nets _10_. Role: datapath.
- h12 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.6011. Inputs: slice0 = nets w6; slice1 = nets _05_. Role: datapath.
- h15 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.6011. Inputs: slice0 = nets _11_; slice1 = nets _09_. Role: datapath.
- h47 (unconfirmed): 3 cells form a 3-bit bus, `bus: 3 bits`. No proof recorded. Confidence 0.5000. Inputs: ctrl = nets _06_; slice0 = nets _09_; slice1 = nets _02_; slice2 = nets _17_. Role: datapath.
- h96 (unconfirmed): 3 cells form a flip-flop with synchronous reset, `ff_srst: 1 bits`. No proof recorded. Confidence 0.5000. Inputs: rst = nets _06_. Role: datapath.
- h97 (unconfirmed): 4 cells form a flip-flop with synchronous reset, `ff_srst: 1 bits`. No proof recorded. Confidence 0.5000. Inputs: rst = nets _06_. Role: datapath.

## 7. Rejected claims

(none)

## 9. What Loki does NOT claim

- Candidates and rejected claims are not statements of fact.
- Module names such as `adder_h1` are Loki's labels built from the kind and the id; they are not the original HDL names, which Loki does not know.

## Helper nets

These nets have no wire of their own in the netlist. Each is defined from netlist wires or other helper nets.

- w1 = NOT(state[4])
- w2 = NOT(state[1])
- w3 = NOT(_10_)
- w4 = NOT(state[2])
- w5 = NOT(state[0])
- w6 = NOT(state[3])
[LOKI-HINTS-END]
Designer prior: designers write RTL from familiar patterns. If a signal looks like a condition, it
probably is one; if a register group looks like an FSM, it probably is one.
