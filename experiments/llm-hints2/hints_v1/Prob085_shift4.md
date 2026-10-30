Loki structural hints for the netlist above. Loki is a netlist analysis program (no language model).
Its output follows between the markers. The worked examples above did not carry hints.
Net names in the hints are wires and ports of the netlist above, except the names w1, w2, ...:
those are helper nets that have no wire of their own; each is defined in the list of helper nets
at the end of the hints, in terms of netlist wires or other helper nets.
[LOKI-HINTS-BEGIN]
# Loki analysis of a gate netlist

## 1. What this is

Loki III analysed the gate-level netlist `netlist.v` (sha256 44d5197b8f15, floor f3).
The list below holds Loki's claims about its higher-level structure.
Each claim has a confidence (a probability) and a proof status.
Trust order: proved or derived claims, then unproven claims with high confidence, then candidates.
Committed claims have confidence of at least 0.9; candidates are listed from 0.5 and are unconfirmed.

## 3. Summary

| kind | committed | candidate | rejected |
| --- | --- | --- | --- |
| bus | 2 | 12 | 0 |
| eq_const | 2 | 4 | 0 |

Input cells (in Loki's re-mapped netlist): 32.

Of the committed cells, 7 (in 2 claims) are marked only by attributes on existing cells (form attrs). Those claims are not modules, so the hierarchy below does not show them.

Recovered module hierarchy (a module contains its children):

- h20 eq_const_h20 (eq_const)
- h22 eq_const_h22 (eq_const)

## 4. Committed claims

- h20: 1 cell form a comparison against a constant, `Y = (A == 0)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets load, ena. Outputs: Y = nets _10_. Recovered as module eq_const_h20, instance eq_const_h20_i. Role: datapath.
- h22: 1 cell form a comparison against a constant, `Y = (A != 3)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets load, data[3]. Outputs: Y = nets _26_. Recovered as module eq_const_h22, instance eq_const_h22_i. Role: datapath.
- h32: 3 cells form a 3-bit bus, `bus: 3 bits`. No proof recorded. Confidence 0.9474. Inputs: ctrl = nets _14_; slice0 = nets w2; slice1 = nets w7; slice2 = nets w12. Role: datapath.
- h34: 4 cells form a 4-bit bus, `bus: 4 bits`. No proof recorded. Confidence 0.9474. Inputs: ctrl = nets _10_; slice0 = nets w5; slice1 = nets w10; slice2 = nets w15; slice3 = nets w16. Role: datapath.

## 5. Buses, state machines and roles

Buses:
- h7 (unconfirmed): 2 bits, bit order from wf: bit 0 = _08_; bit 1 = w3.
- h8 (unconfirmed): 2 bits, bit order from wf: bit 0 = _08_; bit 1 = w8.
- h9 (unconfirmed): 2 bits, bit order from wf: bit 0 = _08_; bit 1 = w13.
- h14 (unconfirmed): 2 bits, bit order from wf: bit 0 = _14_; bit 1 = w16.
- h15 (unconfirmed): 2 bits, bit order from wf: bit 0 = _14_; bit 1 = w5.
- h16 (unconfirmed): 2 bits, bit order from wf: bit 0 = _14_; bit 1 = w15.
- h17 (unconfirmed): 2 bits, bit order from wf: bit 0 = _14_; bit 1 = w10.
- h18 (unconfirmed): 2 bits, bit order from wf: bit 0 = _26_; bit 1 = _14_.
- h21 (unconfirmed): 2 bits, bit order from wf: bit 0 = _26_; bit 1 = w16.
- h30 (unconfirmed): 2 bits, bit order from net_id: bit 0 = _10_; bit 1 = _14_.
- h31 (unconfirmed): 4 bits, bit order from net_id: bit 0 = _14_; bit 1 = w4; bit 2 = w9; bit 3 = w14.
- h32: 3 bits, bit order from net_id: bit 0 = w2; bit 1 = w7; bit 2 = w12.
- h33 (unconfirmed): 2 bits, bit order from net_id: bit 0 = _10_; bit 1 = _26_.
- h34: 4 bits, bit order from net_id: bit 0 = w5; bit 1 = w10; bit 2 = w15; bit 3 = w16.

State machines: none.

Roles of committed claims: datapath: h20, h22, h32, h34.

## 6. Candidates (not committed, unconfirmed)

- h62 (unconfirmed): 1 cell form a comparison against a constant, `Y = (A != 3)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets q[0], _10_. Outputs: Y = nets w5. Role: datapath.
- h63 (unconfirmed): 1 cell form a comparison against a constant, `Y = (A != 3)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets q[1], _10_. Outputs: Y = nets w10. Role: datapath.
- h64 (unconfirmed): 1 cell form a comparison against a constant, `Y = (A != 3)`. Proof derived from h62 (proof transfer). Confidence 0.9999. Inputs: A = nets q[2], _10_. Outputs: Y = nets w15. Role: datapath.
- h65 (unconfirmed): 1 cell form a comparison against a constant, `Y = (A != 3)`. Proof derived from h62 (proof transfer). Confidence 0.9999. Inputs: A = nets q[3], _10_. Outputs: Y = nets w16. Role: datapath.
- h31 (unconfirmed): 4 cells form a 4-bit bus, `bus: 4 bits`. No proof recorded. Confidence 0.8569. Inputs: ctrl = nets _08_; slice0 = nets _14_; slice1 = nets w4; slice2 = nets w9; slice3 = nets w14. Role: datapath.
- h30 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.7503. Inputs: ctrl = nets ena; slice0 = nets _10_; slice1 = nets _14_. Role: datapath.
- h7 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.6011. Inputs: slice0 = nets _08_; slice1 = nets w3. Role: datapath.
- h8 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.6011. Inputs: slice0 = nets _08_; slice1 = nets w8. Role: datapath.
- h9 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.6011. Inputs: slice0 = nets _08_; slice1 = nets w13. Role: datapath.
- h14 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.6011. Inputs: slice0 = nets _14_; slice1 = nets w16. Role: datapath.
- h15 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.6011. Inputs: slice0 = nets _14_; slice1 = nets w5. Role: datapath.
- h16 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.6011. Inputs: slice0 = nets _14_; slice1 = nets w15. Role: datapath.
- h17 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.6011. Inputs: slice0 = nets _14_; slice1 = nets w10. Role: datapath.
- h18 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.6011. Inputs: slice0 = nets _26_; slice1 = nets _14_. Role: datapath.
- h21 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.6011. Inputs: slice0 = nets _26_; slice1 = nets w16. Role: datapath.
- h33 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.6011. Inputs: ctrl = nets load; slice0 = nets _10_; slice1 = nets _26_. Role: datapath.

## 7. Rejected claims

(none)

## 9. What Loki does NOT claim

- Candidates and rejected claims are not statements of fact.
- Module names such as `adder_h1` are Loki's labels built from the kind and the id; they are not the original HDL names, which Loki does not know.

## Helper nets

These nets have no wire of their own in the netlist. Each is defined from netlist wires or other helper nets.

- w1 = NOT(q[1])
- w2 = AND(NOT(_14_), NOT(w1))
- w3 = NOT(data[0])
- w4 = AND(NOT(w3), NOT(_08_))
- w5 = OR(NOT(q[0]), NOT(_10_))
- w6 = NOT(q[2])
- w7 = AND(NOT(_14_), NOT(w6))
- w8 = NOT(data[1])
- w9 = AND(NOT(w8), NOT(_08_))
- w10 = OR(NOT(q[1]), NOT(_10_))
- w11 = NOT(q[3])
- w12 = AND(NOT(_14_), NOT(w11))
- w13 = NOT(data[2])
- w14 = AND(NOT(w13), NOT(_08_))
- w15 = OR(NOT(q[2]), NOT(_10_))
- w16 = OR(NOT(q[3]), NOT(_10_))
[LOKI-HINTS-END]
Designer prior: designers write RTL from familiar patterns. If a signal looks like a condition, it
probably is one; if a register group looks like an FSM, it probably is one.
