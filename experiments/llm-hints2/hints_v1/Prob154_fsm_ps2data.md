Loki structural hints for the netlist above. Loki is a netlist analysis program (no language model).
Its output follows between the markers. The worked examples above did not carry hints.
Net names in the hints are wires and ports of the netlist above, except the names w1, w2, ...:
those are helper nets that have no wire of their own; each is defined in the list of helper nets
at the end of the hints, in terms of netlist wires or other helper nets.
[LOKI-HINTS-BEGIN]
# Loki analysis of a gate netlist

## 1. What this is

Loki III analysed the gate-level netlist `netlist.v` (sha256 f3ba1294794e, floor f3).
The list below holds Loki's claims about its higher-level structure.
Each claim has a confidence (a probability) and a proof status.
Trust order: proved or derived claims, then unproven claims with high confidence, then candidates.
Committed claims have confidence of at least 0.9; candidates are listed from 0.5 and are unconfirmed.

## 3. Summary

| kind | committed | candidate | rejected |
| --- | --- | --- | --- |
| bus | 1 | 9 | 0 |
| eq_const | 3 | 0 | 0 |
| ff_srst | 0 | 6 | 0 |
| register | 1 | 0 | 0 |

Input cells (in Loki's re-mapped netlist): 89.

Of the committed cells, 24 (in 1 claims) are marked only by attributes on existing cells (form attrs). Those claims are not modules, so the hierarchy below does not show them.

Recovered module hierarchy (a module contains its children):

- h7 register_h7 (register)
  - h48 eq_const_h48 (eq_const)
  - h51 eq_const_h51 (eq_const)
- h49 eq_const_h49 (eq_const)

## 4. Committed claims

- h7: 6 cells form a 2-bit register, `register: 2 bits`. No proof recorded. Confidence 0.9731. Inputs: clk = nets clk; d = nets _002_, _000_; rst = nets reset. Outputs: q = nets done, state[1]. Recovered as module register_h7, instance register_h7_i. Role: datapath.
- h48: 2 cells form a comparison against a constant, `Y = (A == 2)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets reset, state[2]. Outputs: Y = nets _000_. Recovered as module eq_const_h48, instance eq_const_h48_i. Role: datapath.
- h51: 2 cells form a comparison against a constant, `Y = (A == 2)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets reset, state[1]. Outputs: Y = nets _002_. Recovered as module eq_const_h51, instance eq_const_h51_i. Role: datapath.
- h49: 1 cell form a comparison against a constant, `Y = (A == 0)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets done, state[0]. Outputs: Y = nets w26. Recovered as module eq_const_h49, instance eq_const_h49_i. Role: datapath.
- h69: 24 cells form a 24-bit bus, `bus: 24 bits`. No proof recorded. Confidence 0.9931. Inputs: ctrl = nets w1; slice0 = nets out_bytes[0]; slice1 = nets out_bytes[1]; slice10 = nets out_bytes[10]; slice11 = nets out_bytes[11]; slice12 = nets out_bytes[12]; slice13 = nets out_bytes[13]; slice14 = nets out_bytes[14]; slice15 = nets out_bytes[15]; slice16 = nets out_bytes[16]; slice17 = nets out_bytes[17]; slice18 = nets out_bytes[18]; slice19 = nets out_bytes[19]; slice2 = nets out_bytes[2]; slice20 = nets out_bytes[20]; slice21 = nets out_bytes[21]; slice22 = nets out_bytes[22]; slice23 = nets out_bytes[23]; slice3 = nets out_bytes[3]; slice4 = nets out_bytes[4]; slice5 = nets out_bytes[5]; slice6 = nets out_bytes[6]; slice7 = nets out_bytes[7]; slice8 = nets out_bytes[8]; slice9 = nets out_bytes[9]. Role: datapath.

## 5. Buses, state machines and roles

Buses:
- h8 (unconfirmed): 2 bits, bit order from wf: bit 0 = w1; bit 1 = _013_.
- h9 (unconfirmed): 8 bits, bit order from wf: bit 0 = w2; bit 1 = w3; bit 2 = w4; bit 3 = w5; bit 4 = w6; bit 5 = w7; bit 6 = w8; bit 7 = w9.
- h10 (unconfirmed): 8 bits, bit order from wf: bit 0 = out_bytes[0]; bit 1 = out_bytes[1]; bit 2 = out_bytes[2]; bit 3 = out_bytes[3]; bit 4 = out_bytes[4]; bit 5 = out_bytes[5]; bit 6 = out_bytes[6]; bit 7 = out_bytes[7].
- h11 (unconfirmed): 8 bits, bit order from wf: bit 0 = w10; bit 1 = w11; bit 2 = w12; bit 3 = w13; bit 4 = w14; bit 5 = w15; bit 6 = w16; bit 7 = w17.
- h12 (unconfirmed): 8 bits, bit order from wf: bit 0 = out_bytes[8]; bit 1 = out_bytes[9]; bit 2 = out_bytes[10]; bit 3 = out_bytes[11]; bit 4 = out_bytes[12]; bit 5 = out_bytes[13]; bit 6 = out_bytes[14]; bit 7 = out_bytes[15].
- h13 (unconfirmed): 8 bits, bit order from wf: bit 0 = w18; bit 1 = w19; bit 2 = w20; bit 3 = w21; bit 4 = w22; bit 5 = w23; bit 6 = w24; bit 7 = w25.
- h14 (unconfirmed): 8 bits, bit order from wf: bit 0 = out_bytes[16]; bit 1 = out_bytes[17]; bit 2 = out_bytes[18]; bit 3 = out_bytes[19]; bit 4 = out_bytes[20]; bit 5 = out_bytes[21]; bit 6 = out_bytes[22]; bit 7 = out_bytes[23].
- h69: 24 bits, bit order from net_id: bit 0 = out_bytes[0]; bit 1 = out_bytes[1]; bit 2 = out_bytes[2]; bit 3 = out_bytes[3]; bit 4 = out_bytes[4]; bit 5 = out_bytes[5]; bit 6 = out_bytes[6]; bit 7 = out_bytes[7]; bit 8 = out_bytes[8]; bit 9 = out_bytes[9]; bit 10 = out_bytes[10]; bit 11 = out_bytes[11]; bit 12 = out_bytes[12]; bit 13 = out_bytes[13]; bit 14 = out_bytes[14]; bit 15 = out_bytes[15]; bit 16 = out_bytes[16]; bit 17 = out_bytes[17]; bit 18 = out_bytes[18]; bit 19 = out_bytes[19]; bit 20 = out_bytes[20]; bit 21 = out_bytes[21]; bit 22 = out_bytes[22]; bit 23 = out_bytes[23].
- h70 (unconfirmed): 2 bits, bit order from net_id: bit 0 = _000_; bit 1 = _002_.
- h71 (unconfirmed): 2 bits, bit order from net_id: bit 0 = _016_; bit 1 = _003_.

State machines: none.

Roles of committed claims: datapath: h7, h48, h49, h51, h69.

## 6. Candidates (not committed, unconfirmed)

- h9 (unconfirmed): 8 cells form an 8-bit bus, `bus: 8 bits`. No proof recorded. Confidence 0.8581. Inputs: slice0 = nets w2; slice1 = nets w3; slice2 = nets w4; slice3 = nets w5; slice4 = nets w6; slice5 = nets w7; slice6 = nets w8; slice7 = nets w9. Role: datapath.
- h10 (unconfirmed): 8 cells form an 8-bit bus, `bus: 8 bits`. No proof recorded. Confidence 0.8581. Inputs: slice0 = nets out_bytes[0]; slice1 = nets out_bytes[1]; slice2 = nets out_bytes[2]; slice3 = nets out_bytes[3]; slice4 = nets out_bytes[4]; slice5 = nets out_bytes[5]; slice6 = nets out_bytes[6]; slice7 = nets out_bytes[7]. Role: datapath.
- h11 (unconfirmed): 8 cells form an 8-bit bus, `bus: 8 bits`. No proof recorded. Confidence 0.8581. Inputs: slice0 = nets w10; slice1 = nets w11; slice2 = nets w12; slice3 = nets w13; slice4 = nets w14; slice5 = nets w15; slice6 = nets w16; slice7 = nets w17. Role: datapath.
- h12 (unconfirmed): 8 cells form an 8-bit bus, `bus: 8 bits`. No proof recorded. Confidence 0.8581. Inputs: slice0 = nets out_bytes[8]; slice1 = nets out_bytes[9]; slice2 = nets out_bytes[10]; slice3 = nets out_bytes[11]; slice4 = nets out_bytes[12]; slice5 = nets out_bytes[13]; slice6 = nets out_bytes[14]; slice7 = nets out_bytes[15]. Role: datapath.
- h13 (unconfirmed): 8 cells form an 8-bit bus, `bus: 8 bits`. No proof recorded. Confidence 0.8581. Inputs: slice0 = nets w18; slice1 = nets w19; slice2 = nets w20; slice3 = nets w21; slice4 = nets w22; slice5 = nets w23; slice6 = nets w24; slice7 = nets w25. Role: datapath.
- h14 (unconfirmed): 8 cells form an 8-bit bus, `bus: 8 bits`. No proof recorded. Confidence 0.8581. Inputs: slice0 = nets out_bytes[16]; slice1 = nets out_bytes[17]; slice2 = nets out_bytes[18]; slice3 = nets out_bytes[19]; slice4 = nets out_bytes[20]; slice5 = nets out_bytes[21]; slice6 = nets out_bytes[22]; slice7 = nets out_bytes[23]. Role: datapath.
- h16 (unconfirmed): 5 cells form a flip-flop with synchronous reset, `ff_srst: 1 bits`. No proof recorded. Confidence 0.7503. Inputs: d = nets _003_; rst = nets _011_. Outputs: q = nets state[0]. Role: datapath.
- h18 (unconfirmed): 3 cells form a flip-flop with synchronous reset, `ff_srst: 1 bits`. No proof recorded. Confidence 0.7503. Inputs: d = nets _000_; rst = nets reset. Outputs: q = nets state[1]. Role: datapath.
- h20 (unconfirmed): 3 cells form a flip-flop with synchronous reset, `ff_srst: 1 bits`. No proof recorded. Confidence 0.7503. Inputs: d = nets _001_; rst = nets _011_. Outputs: q = nets state[2]. Role: datapath.
- h23 (unconfirmed): 3 cells form a flip-flop with synchronous reset, `ff_srst: 1 bits`. No proof recorded. Confidence 0.7503. Inputs: d = nets _002_; rst = nets reset. Outputs: q = nets done. Role: datapath.
- h71 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.7503. Inputs: ctrl = nets _011_; slice0 = nets _016_; slice1 = nets _003_. Role: datapath.
- h8 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.6011. Inputs: slice0 = nets w1; slice1 = nets _013_. Role: datapath.
- h4 (unconfirmed): 8 cells form a flip-flop with synchronous reset, `ff_srst: 2 bits`. No proof recorded. Confidence 0.5000. Inputs: d = nets _003_, _001_; rst = nets _011_. Outputs: q = nets state[0], state[2]. Role: datapath.
- h6 (unconfirmed): 6 cells form a flip-flop with synchronous reset, `ff_srst: 2 bits`. No proof recorded. Confidence 0.5000. Inputs: d = nets _002_, _000_; rst = nets reset. Outputs: q = nets done, state[1]. Role: datapath.
- h70 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.5000. Inputs: ctrl = nets reset; slice0 = nets _000_; slice1 = nets _002_. Role: datapath.

## 7. Rejected claims

(none)

## 9. What Loki does NOT claim

- Candidates and rejected claims are not statements of fact.
- Module names such as `adder_h1` are Loki's labels built from the kind and the id; they are not the original HDL names, which Loki does not know.

## Helper nets

These nets have no wire of their own in the netlist. Each is defined from netlist wires or other helper nets.

- w1 = NOT(done)
- w2 = NOT(out_bytes_r[0])
- w3 = NOT(out_bytes_r[1])
- w4 = NOT(out_bytes_r[2])
- w5 = NOT(out_bytes_r[3])
- w6 = NOT(out_bytes_r[4])
- w7 = NOT(out_bytes_r[5])
- w8 = NOT(out_bytes_r[6])
- w9 = NOT(out_bytes_r[7])
- w10 = NOT(out_bytes_r[8])
- w11 = NOT(out_bytes_r[9])
- w12 = NOT(out_bytes_r[10])
- w13 = NOT(out_bytes_r[11])
- w14 = NOT(out_bytes_r[12])
- w15 = NOT(out_bytes_r[13])
- w16 = NOT(out_bytes_r[14])
- w17 = NOT(out_bytes_r[15])
- w18 = NOT(out_bytes_r[16])
- w19 = NOT(out_bytes_r[17])
- w20 = NOT(out_bytes_r[18])
- w21 = NOT(out_bytes_r[19])
- w22 = NOT(out_bytes_r[20])
- w23 = NOT(out_bytes_r[21])
- w24 = NOT(out_bytes_r[22])
- w25 = NOT(out_bytes_r[23])
- w26 = AND(NOT(done), NOT(state[0]))
[LOKI-HINTS-END]
Designer prior: designers write RTL from familiar patterns. If a signal looks like a condition, it
probably is one; if a register group looks like an FSM, it probably is one.
