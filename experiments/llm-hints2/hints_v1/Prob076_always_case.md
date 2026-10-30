Loki structural hints for the netlist above. Loki is a netlist analysis program (no language model).
Its output follows between the markers. The worked examples above did not carry hints.
Net names in the hints are wires and ports of the netlist above, except the names w1, w2, ...:
those are helper nets that have no wire of their own; each is defined in the list of helper nets
at the end of the hints, in terms of netlist wires or other helper nets.
[LOKI-HINTS-BEGIN]
# Loki analysis of a gate netlist

## 1. What this is

Loki III analysed the gate-level netlist `netlist.v` (sha256 384196b52ee9, floor f3).
The list below holds Loki's claims about its higher-level structure.
Each claim has a confidence (a probability) and a proof status.
Trust order: proved or derived claims, then unproven claims with high confidence, then candidates.
Committed claims have confidence of at least 0.9; candidates are listed from 0.5 and are unconfirmed.

## 3. Summary

| kind | committed | candidate | rejected |
| --- | --- | --- | --- |
| bus | 5 | 10 | 0 |
| eq_const | 1 | 0 | 0 |

Input cells (in Loki's re-mapped netlist): 68.

Of the committed cells, 19 (in 5 claims) are marked only by attributes on existing cells (form attrs). Those claims are not modules, so the hierarchy below does not show them.

Recovered module hierarchy (a module contains its children):

- h49 eq_const_h49 (eq_const)

## 4. Committed claims

- h49: 1 cell form a comparison against a constant, `Y = (A == 0)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets sel[0], sel[2]. Outputs: Y = nets _018_. Recovered as module eq_const_h49, instance eq_const_h49_i. Role: datapath.
- h56: 4 cells form a 4-bit bus, `bus: 4 bits`. No proof recorded. Confidence 0.9474. Inputs: ctrl = nets w1; slice0 = nets w2; slice1 = nets w13; slice2 = nets w19; slice3 = nets w20. Role: datapath.
- h61: 4 cells form a 4-bit bus, `bus: 4 bits`. No proof recorded. Confidence 0.9474. Inputs: ctrl = nets _021_; slice0 = nets _023_; slice1 = nets w8; slice2 = nets w14; slice3 = nets _056_. Role: datapath.
- h63: 4 cells form a 4-bit bus, `bus: 4 bits`. No proof recorded. Confidence 0.9474. Inputs: ctrl = nets _016_; slice0 = nets _017_; slice1 = nets _034_; slice2 = nets _044_; slice3 = nets _055_. Role: datapath.
- h64: 3 cells form a 3-bit bus, `bus: 3 bits`. No proof recorded. Confidence 0.9474. Inputs: ctrl = nets w4; slice0 = nets _012_; slice1 = nets w12; slice2 = nets w18. Role: datapath.
- h65: 4 cells form a 4-bit bus, `bus: 4 bits`. No proof recorded. Confidence 0.9474. Inputs: ctrl = nets w5; slice0 = nets w7; slice1 = nets w10; slice2 = nets w16; slice3 = nets w22. Role: datapath.

## 5. Buses, state machines and roles

Buses:
- h12 (unconfirmed): 2 bits, bit order from wf: bit 0 = _002_; bit 1 = _001_.
- h52 (unconfirmed): 3 bits, bit order from net_id: bit 0 = _018_; bit 1 = _013_; bit 2 = w3.
- h53 (unconfirmed): 3 bits, bit order from net_id: bit 0 = _013_; bit 1 = _027_; bit 2 = _016_.
- h55 (unconfirmed): 2 bits, bit order from net_id: bit 0 = w1; bit 1 = _014_.
- h56: 4 bits, bit order from net_id: bit 0 = w2; bit 1 = w13; bit 2 = w19; bit 3 = w20.
- h57 (unconfirmed): 2 bits, bit order from net_id: bit 0 = w3; bit 1 = _014_.
- h58 (unconfirmed): 3 bits, bit order from net_id: bit 0 = _015_; bit 1 = _033_; bit 2 = _043_.
- h59 (unconfirmed): 2 bits, bit order from net_id: bit 0 = _021_; bit 1 = _010_.
- h60 (unconfirmed): 2 bits, bit order from net_id: bit 0 = _021_; bit 1 = _027_.
- h61: 4 bits, bit order from net_id: bit 0 = _023_; bit 1 = w8; bit 2 = w14; bit 3 = _056_.
- h62 (unconfirmed): 2 bits, bit order from net_id: bit 0 = _010_; bit 1 = _016_.
- h63: 4 bits, bit order from net_id: bit 0 = _017_; bit 1 = _034_; bit 2 = _044_; bit 3 = _055_.
- h64: 3 bits, bit order from net_id: bit 0 = _012_; bit 1 = w12; bit 2 = w18.
- h65: 4 bits, bit order from net_id: bit 0 = w7; bit 1 = w10; bit 2 = w16; bit 3 = w22.
- h183 (unconfirmed): 2 bits, bit order from net_id: bit 0 = _013_; bit 1 = w3.

State machines: none.

Roles of committed claims: datapath: h49, h56, h61, h63, h64, h65.

## 6. Candidates (not committed, unconfirmed)

- h52 (unconfirmed): 3 cells form a 3-bit bus, `bus: 3 bits`. No proof recorded. Confidence 0.8569. Inputs: ctrl = nets sel[2]; slice0 = nets _018_; slice1 = nets _013_; slice2 = nets w3. Role: datapath.
- h53 (unconfirmed): 3 cells form a 3-bit bus, `bus: 3 bits`. No proof recorded. Confidence 0.8569. Inputs: ctrl = nets _002_; slice0 = nets _013_; slice1 = nets _027_; slice2 = nets _016_. Role: datapath.
- h183 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.8191. Inputs: ctrl = nets sel[2]; slice0 = nets _013_; slice1 = nets w3. Role: datapath.
- h55 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.7503. Inputs: ctrl = nets _013_; slice0 = nets w1; slice1 = nets _014_. Role: datapath.
- h57 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.7503. Inputs: ctrl = nets _001_; slice0 = nets w3; slice1 = nets _014_. Role: datapath.
- h58 (unconfirmed): 3 cells form a 3-bit bus, `bus: 3 bits`. No proof recorded. Confidence 0.7503. Inputs: ctrl = nets _014_; slice0 = nets _015_; slice1 = nets _033_; slice2 = nets _043_. Role: datapath.
- h60 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.7503. Inputs: ctrl = nets _019_; slice0 = nets _021_; slice1 = nets _027_. Role: datapath.
- h62 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.7503. Inputs: ctrl = nets _009_; slice0 = nets _010_; slice1 = nets _016_. Role: datapath.
- h12 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.6011. Inputs: slice0 = nets _002_; slice1 = nets _001_. Role: datapath.
- h59 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.5000. Inputs: ctrl = nets sel[1]; slice0 = nets _021_; slice1 = nets _010_. Role: datapath.

## 7. Rejected claims

(none)

## 9. What Loki does NOT claim

- Candidates and rejected claims are not statements of fact.
- Module names such as `adder_h1` are Loki's labels built from the kind and the id; they are not the original HDL names, which Loki does not know.

## Helper nets

These nets have no wire of their own in the netlist. Each is defined from netlist wires or other helper nets.

- w1 = AND(NOT(_013_), NOT(sel[0]))
- w2 = OR(NOT(data4[0]), NOT(w1))
- w3 = AND(NOT(sel[2]), NOT(_001_))
- w4 = NOT(_010_)
- w5 = NOT(_027_)
- w6 = NOT(data2[0])
- w7 = AND(NOT(w5), NOT(w6))
- w8 = OR(NOT(data0[1]), NOT(_021_))
- w9 = NOT(data2[1])
- w10 = AND(NOT(w5), NOT(w9))
- w11 = NOT(data1[1])
- w12 = AND(NOT(w4), NOT(w11))
- w13 = OR(NOT(data4[1]), NOT(w1))
- w14 = OR(NOT(data0[2]), NOT(_021_))
- w15 = NOT(data2[2])
- w16 = AND(NOT(w5), NOT(w15))
- w17 = NOT(data1[2])
- w18 = AND(NOT(w4), NOT(w17))
- w19 = OR(NOT(data4[2]), NOT(w1))
- w20 = OR(NOT(data4[3]), NOT(w1))
- w21 = NOT(data2[3])
- w22 = AND(NOT(w5), NOT(w21))
[LOKI-HINTS-END]
Designer prior: designers write RTL from familiar patterns. If a signal looks like a condition, it
probably is one; if a register group looks like an FSM, it probably is one.
