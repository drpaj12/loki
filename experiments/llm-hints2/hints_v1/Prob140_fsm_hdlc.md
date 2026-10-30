Loki structural hints for the netlist above. Loki is a netlist analysis program (no language model).
Its output follows between the markers. The worked examples above did not carry hints.
Net names in the hints are wires and ports of the netlist above, except the names w1, w2, ...:
those are helper nets that have no wire of their own; each is defined in the list of helper nets
at the end of the hints, in terms of netlist wires or other helper nets.
[LOKI-HINTS-BEGIN]
# Loki analysis of a gate netlist

## 1. What this is

Loki III analysed the gate-level netlist `netlist.v` (sha256 f1b66731d35a, floor f3).
The list below holds Loki's claims about its higher-level structure.
Each claim has a confidence (a probability) and a proof status.
Trust order: proved or derived claims, then unproven claims with high confidence, then candidates.
Committed claims have confidence of at least 0.9; candidates are listed from 0.5 and are unconfirmed.

## 3. Summary

| kind | committed | candidate | rejected |
| --- | --- | --- | --- |
| adder_cin | 0 | 0 | 1 |
| bus | 2 | 16 | 0 |
| eq_const | 22 | 2 | 0 |
| ff_en | 0 | 1 | 0 |
| ff_srst | 0 | 16 | 0 |
| register | 0 | 2 | 0 |

Input cells (in Loki's re-mapped netlist): 41.

Of the committed cells, 9 (in 2 claims) are marked only by attributes on existing cells (form attrs). Those claims are not modules, so the hierarchy below does not show them.

Recovered module hierarchy (a module contains its children):

- h15 eq_const_h15 (eq_const)
- h16 eq_const_h16 (eq_const)
- h46 eq_const_h46 (eq_const)
  - h45 eq_const_h45 (eq_const)
  - h48 eq_const_h48 (eq_const)
  - h146 eq_const_h146 (eq_const)
- h50 eq_const_h50 (eq_const)
  - h17 eq_const_h17 (eq_const)
  - h51 eq_const_h51 (eq_const)
  - h139 eq_const_h139 (eq_const)
- h153 eq_const_h153 (eq_const)
- h154 eq_const_h154 (eq_const)
  - h155 eq_const_h155 (eq_const)
  - h170 eq_const_h170 (eq_const)
- h161 eq_const_h161 (eq_const)
- h164 eq_const_h164 (eq_const)
- h165 eq_const_h165 (eq_const)
- h166 eq_const_h166 (eq_const)
- h167 eq_const_h167 (eq_const)
- h168 eq_const_h168 (eq_const)
- h177 eq_const_h177 (eq_const)
- h178 eq_const_h178 (eq_const)

## 4. Committed claims

- h15: 1 cell form a comparison against a constant, `Y = (A == 0)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets err, state[4]. Outputs: Y = nets w8. Recovered as module eq_const_h15, instance eq_const_h15_i. Role: datapath.
- h16: 1 cell form a comparison against a constant, `Y = (A == 0)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets state[5], state[8]. Outputs: Y = nets w9. Recovered as module eq_const_h16, instance eq_const_h16_i. Role: datapath.
- h46: 3 cells form a comparison against a constant, `Y = (A == 0)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets disc, flag, state[0]. Outputs: Y = nets w6. Recovered as module eq_const_h46, instance eq_const_h46_i. Role: datapath.
- h45: 1 cell form a comparison against a constant, `Y = (A == 0)`. Proof derived from h15 (proof transfer). Confidence 0.9999. Inputs: A = nets disc, state[0]. Outputs: Y = nets w4. Recovered as module eq_const_h45, instance eq_const_h45_i. Role: datapath.
- h48: 2 cells form a comparison against a constant, `Y = (A != 0)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets disc, state[0]. Outputs: Y = nets w5. Recovered as module eq_const_h48, instance eq_const_h48_i. Role: datapath.
- h146: 1 cell form a comparison against a constant, `Y = (A == 0)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets flag, w5. Outputs: Y = nets w6. Recovered as module eq_const_h146, instance eq_const_h146_i. Role: datapath.
- h50: 3 cells form a comparison against a constant, `Y = (A != 0)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets reset, err, state[2], state[3]. Outputs: Y = nets w13. Recovered as module eq_const_h50, instance eq_const_h50_i. Role: datapath.
- h17: 1 cell form a comparison against a constant, `Y = (A == 0)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets err, state[3]. Outputs: Y = nets w11. Recovered as module eq_const_h17, instance eq_const_h17_i. Role: datapath.
- h51: 1 cell form a comparison against a constant, `Y = (A == 0)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets reset, state[2]. Outputs: Y = nets w12. Recovered as module eq_const_h51, instance eq_const_h51_i. Role: datapath.
- h139: 1 cell form a comparison against a constant, `Y = (A != 3)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets w11, w12. Outputs: Y = nets w13. Recovered as module eq_const_h139, instance eq_const_h139_i. Role: datapath.
- h153: 4 cells form a comparison against a constant, `Y = (A == 2)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets reset, in, w6. Outputs: Y = nets _04_. Recovered as module eq_const_h153, instance eq_const_h153_i. Role: datapath.
- h154: 2 cells form a comparison against a constant, `Y = (A == 3)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets w6, w9, w13. Outputs: Y = nets w14. Recovered as module eq_const_h154, instance eq_const_h154_i. Role: datapath.
- h155: 1 cell form a comparison against a constant, `Y = (A != 3)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets w6, w9. Outputs: Y = nets w10. Recovered as module eq_const_h155, instance eq_const_h155_i. Role: datapath.
- h170: 1 cell form a comparison against a constant, `Y = (A == 0)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets w10, w13. Outputs: Y = nets w14. Recovered as module eq_const_h170, instance eq_const_h170_i. Role: datapath.
- h161: 2 cells form a comparison against a constant, `Y = (A != 2)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets reset, w1. Outputs: Y = nets w3. Recovered as module eq_const_h161, instance eq_const_h161_i. Role: datapath.
- h164: 2 cells form a comparison against a constant, `Y = (A == 1)`. Proved equivalent by truth table. Confidence 0.9558. Inputs: A = nets state[7], _16_. Outputs: Y = nets _03_. Recovered as module eq_const_h164, instance eq_const_h164_i. Role: datapath. Conflicts with 2 more not listed.
- h165: 2 cells form a comparison against a constant, `Y = (A == 1)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets state[8], _16_. Outputs: Y = nets _01_. Recovered as module eq_const_h165, instance eq_const_h165_i. Role: datapath.
- h166: 2 cells form a comparison against a constant, `Y = (A == 1)`. Proof derived from h165 (proof transfer). Confidence 0.9999. Inputs: A = nets state[5], _16_. Outputs: Y = nets _02_. Recovered as module eq_const_h166, instance eq_const_h166_i. Role: datapath.
- h167: 2 cells form a comparison against a constant, `Y = (A == 1)`. Proof derived from h165 (proof transfer). Confidence 0.9999. Inputs: A = nets state[2], _16_. Outputs: Y = nets _06_. Recovered as module eq_const_h167, instance eq_const_h167_i. Role: datapath.
- h168: 2 cells form a comparison against a constant, `Y = (A == 1)`. Proof derived from h165 (proof transfer). Confidence 0.9999. Inputs: A = nets state[3], _16_. Outputs: Y = nets _07_. Recovered as module eq_const_h168, instance eq_const_h168_i. Role: datapath.
- h177: 2 cells form a comparison against a constant, `Y = (A == 1)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets state[4], w3. Outputs: Y = nets _05_. Recovered as module eq_const_h177, instance eq_const_h177_i. Role: datapath.
- h178: 1 cell form a comparison against a constant, `Y = (A == 0)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets _17_, w14. Outputs: Y = nets _09_. Recovered as module eq_const_h178, instance eq_const_h178_i. Role: datapath.
- h54: 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.9644. Inputs: ctrl = nets w3; slice0 = nets _00_; slice1 = nets _05_. Role: datapath.
- h57: 7 cells form a 7-bit bus, `bus: 7 bits`. No proof recorded. Confidence 0.9234. Inputs: ctrl = nets _16_; slice0 = nets _03_; slice1 = nets _01_; slice2 = nets _02_; slice3 = nets _04_; slice4 = nets _06_; slice5 = nets _07_; slice6 = nets _08_. Role: datapath.

## 5. Buses, state machines and roles

Buses:
- h8 (unconfirmed): 2 bits, bit order from wf: bit 0 = w1; bit 1 = w7.
- h11 (unconfirmed): 6 bits, bit order from wf: bit 0 = _11_; bit 1 = _12_; bit 2 = w7; bit 3 = _13_; bit 4 = _15_; bit 5 = _14_.
- h12 (unconfirmed): 2 bits, bit order from wf: bit 0 = _17_; bit 1 = _05_.
- h13 (unconfirmed): 5 bits, bit order from wf: bit 0 = _06_; bit 1 = _07_; bit 2 = _05_; bit 3 = _02_; bit 4 = _01_.
- h14 (unconfirmed): 2 bits, bit order from wf: bit 0 = w4; bit 1 = w6.
- h53 (unconfirmed): 2 bits, bit order from net_id: bit 0 = _17_; bit 1 = w3.
- h54: 2 bits, bit order from net_id: bit 0 = _00_; bit 1 = _05_.
- h55 (unconfirmed): 2 bits, bit order from net_id: bit 0 = _00_; bit 1 = _03_.
- h57: 7 bits, bit order from net_id: bit 0 = _03_; bit 1 = _01_; bit 2 = _02_; bit 3 = _04_; bit 4 = _06_; bit 5 = _07_; bit 6 = _08_.
- h58 (unconfirmed): 2 bits, bit order from net_id: bit 0 = _04_; bit 1 = w10.
- h105 (unconfirmed): 2 bits, bit order from wf: bit 0 = w1; bit 1 = w5.
- h106 (unconfirmed): 2 bits, bit order from wf: bit 0 = _17_; bit 1 = w6.
- h107 (unconfirmed): 2 bits, bit order from wf: bit 0 = _09_; bit 1 = _04_.
- h152 (unconfirmed): 2 bits, bit order from wf: bit 0 = _04_; bit 1 = _17_.
- h158 (unconfirmed): 5 bits, bit order from wf: bit 0 = _11_; bit 1 = _12_; bit 2 = w7; bit 3 = _15_; bit 4 = _14_.
- h159 (unconfirmed): 4 bits, bit order from wf: bit 0 = _06_; bit 1 = _07_; bit 2 = _05_; bit 3 = _01_.
- h171 (unconfirmed): 6 bits, bit order from net_id: bit 0 = _03_; bit 1 = _01_; bit 2 = _02_; bit 3 = _06_; bit 4 = _07_; bit 5 = _08_.
- h179 (unconfirmed): 5 bits, bit order from net_id: bit 0 = _06_; bit 1 = _07_; bit 2 = _02_; bit 3 = _03_, _15_; bit 4 = _01_.

State machines: none.

Roles of committed claims: datapath: h15, h16, h17, h45, h46, h48, h50, h51, h54, h57, h139, h146, h153, h154, h155, h161, h164, h165, h166, h167, h168, h170, h177, h178.

## 6. Candidates (not committed, unconfirmed)

- h169 (unconfirmed): 1 cell form a comparison against a constant, `Y = (A == 0)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets _16_, w8. Outputs: Y = nets _08_. Role: datapath.
- h176 (unconfirmed): 1 cell form a comparison against a constant, `Y = (A == 0)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets w3, _15_. Outputs: Y = nets _00_. Role: datapath.
- h35 (unconfirmed): 3 cells form a flip-flop with enable, `ff_en: 1 bits`. No proof recorded. Confidence 0.9901. Inputs: d = nets _08_; en = nets state[4]. Outputs: q = nets err. Role: datapath.
- h22 (unconfirmed): 3 cells form a flip-flop with synchronous reset, `ff_srst: 1 bits`. No proof recorded. Confidence 0.9002. Inputs: d = nets _01_; rst = nets _16_. Outputs: q = nets state[2]. Role: datapath.
- h24 (unconfirmed): 3 cells form a flip-flop with synchronous reset, `ff_srst: 1 bits`. No proof recorded. Confidence 0.9002. Inputs: d = nets _02_; rst = nets _16_. Outputs: q = nets state[3]. Role: datapath.
- h26 (unconfirmed): 2 cells form a flip-flop with synchronous reset, `ff_srst: 1 bits`. No proof recorded. Confidence 0.9002. Inputs: d = nets _03_; rst = nets _16_. Outputs: q = nets state[4]. Role: datapath.
- h27 (unconfirmed): 2 cells form a flip-flop with synchronous reset, `ff_srst: 1 bits`. No proof recorded. Confidence 0.9002. Inputs: d = nets _04_; rst = nets _16_. Outputs: q = nets state[5]. Role: datapath.
- h32 (unconfirmed): 3 cells form a flip-flop with synchronous reset, `ff_srst: 1 bits`. No proof recorded. Confidence 0.9002. Inputs: d = nets _06_; rst = nets _16_. Outputs: q = nets state[7]. Role: datapath.
- h34 (unconfirmed): 3 cells form a flip-flop with synchronous reset, `ff_srst: 1 bits`. No proof recorded. Confidence 0.9002. Inputs: d = nets _07_; rst = nets _16_. Outputs: q = nets state[8]. Role: datapath.
- h36 (unconfirmed): 3 cells form a flip-flop with synchronous reset, `ff_srst: 1 bits`. No proof recorded. Confidence 0.9002. Inputs: d = nets _08_; rst = nets _16_. Outputs: q = nets err. Role: datapath.
- h11 (unconfirmed): 6 cells form a 6-bit bus, `bus: 6 bits`. No proof recorded. Confidence 0.8581. Inputs: slice0 = nets _11_; slice1 = nets _12_; slice2 = nets w7; slice3 = nets _13_; slice4 = nets _15_; slice5 = nets _14_. Role: datapath.
- h13 (unconfirmed): 5 cells form a 5-bit bus, `bus: 5 bits`. No proof recorded. Confidence 0.8581. Inputs: slice0 = nets _06_; slice1 = nets _07_; slice2 = nets _05_; slice3 = nets _02_; slice4 = nets _01_. Role: datapath.
- h158 (unconfirmed): 5 cells form a 5-bit bus, `bus: 5 bits`. No proof recorded. Confidence 0.8581. Inputs: slice0 = nets _11_; slice1 = nets _12_; slice2 = nets w7; slice3 = nets _15_; slice4 = nets _14_. Role: datapath.
- h171 (unconfirmed): 6 cells form a 6-bit bus, `bus: 6 bits`. No proof recorded. Confidence 0.8581. Inputs: ctrl = nets _16_; slice0 = nets _03_; slice1 = nets _01_; slice2 = nets _02_; slice3 = nets _06_; slice4 = nets _07_; slice5 = nets _08_. Role: datapath.
- h182 (unconfirmed): 4 cells form a 3-bit register, `register: 3 bits`. No proof recorded. Confidence 0.8569. Inputs: clk = nets clk; d = nets _00_, _05_, _09_. Outputs: q = nets disc, flag, state[0]. Role: datapath.
- h173 (unconfirmed): 5 cells form a 5-bit register, `register: 5 bits`. No proof recorded. Confidence 0.8006. Inputs: clk = nets clk; d = nets _01_, _02_, _03_, _04_, _07_. Outputs: q = nets state[2], state[3], state[4], state[5], state[8]. Role: datapath.
- h25 (unconfirmed): 2 cells form a flip-flop with synchronous reset, `ff_srst: 1 bits`. No proof recorded. Confidence 0.7503. Inputs: d = nets _03_; rst = nets _15_. Outputs: q = nets state[4]. Role: datapath.
- h30 (unconfirmed): 3 cells form a flip-flop with synchronous reset, `ff_srst: 1 bits`. No proof recorded. Confidence 0.7503. Inputs: d = nets _05_; rst = nets w3. Outputs: q = nets flag. Role: datapath.
- h53 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.7503. Inputs: ctrl = nets w1; slice0 = nets _17_; slice1 = nets w3. Role: datapath.
- h55 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.7503. Inputs: ctrl = nets _15_; slice0 = nets _00_; slice1 = nets _03_. Role: datapath.
- h58 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.7503. Inputs: ctrl = nets w6; slice0 = nets _04_; slice1 = nets w10. Role: datapath.
- h159 (unconfirmed): 4 cells form a 4-bit bus, `bus: 4 bits`. No proof recorded. Confidence 0.7503. Inputs: slice0 = nets _06_; slice1 = nets _07_; slice2 = nets _05_; slice3 = nets _01_. Role: datapath.
- h179 (unconfirmed): 10 cells form a 5-bit bus, `bus: 5 bits`. No proof recorded. Confidence 0.6682. Inputs: ctrl = nets _16_; slice0 = nets _06_; slice1 = nets _07_; slice2 = nets _02_; slice3 = nets _03_, _15_; slice4 = nets _01_. Role: datapath.
- h8 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.6011. Inputs: slice0 = nets w1; slice1 = nets w7. Role: datapath.
- h12 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.6011. Inputs: slice0 = nets _17_; slice1 = nets _05_. Role: datapath.
- h14 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.6011. Inputs: slice0 = nets w4; slice1 = nets w6. Role: datapath.
- h105 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.6011. Inputs: slice0 = nets w1; slice1 = nets w5. Role: datapath.
- h106 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.6011. Inputs: slice0 = nets _17_; slice1 = nets w6. Role: datapath.
- h107 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.6011. Inputs: slice0 = nets _09_; slice1 = nets _04_. Role: datapath.
- h152 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.6011. Inputs: slice0 = nets _04_; slice1 = nets _17_. Role: datapath.
- h1 (unconfirmed): 5 cells form a flip-flop with synchronous reset, `ff_srst: 2 bits`. No proof recorded. Confidence 0.5000. Inputs: d = nets _00_, _05_; rst = nets w3. Outputs: q = nets disc, flag. Role: datapath.
- h3 (unconfirmed): 19 cells form a flip-flop with synchronous reset, `ff_srst: 7 bits`. No proof recorded. Confidence 0.5000. Inputs: d = nets _08_, _01_, _02_, _03_, _04_, _06_, _07_; rst = nets _16_. Outputs: q = nets err, state[2], state[3], state[4], state[5], state[7], state[8]. Role: datapath.
- h101 (unconfirmed): 18 cells form a flip-flop with synchronous reset, `ff_srst: 7 bits`. No proof recorded. Confidence 0.5000. Inputs: d = nets _08_, _01_, _02_, _03_, _04_, _06_, _07_; rst = nets _16_. Outputs: q = nets err, state[2], state[3], state[4], state[5], state[7], state[8]. Role: datapath.
- h145 (unconfirmed): 5 cells form a flip-flop with synchronous reset, `ff_srst: 1 bits`. No proof recorded. Confidence 0.5000. Inputs: rst = nets _17_. Role: datapath.
- h156 (unconfirmed): 16 cells form a flip-flop with synchronous reset, `ff_srst: 6 bits`. No proof recorded. Confidence 0.5000. Inputs: d = nets _08_, _01_, _02_, _03_, _06_, _07_; rst = nets _16_. Outputs: q = nets err, state[2], state[3], state[4], state[7], state[8]. Role: datapath.
- h172 (unconfirmed): 5 cells form a flip-flop with synchronous reset, `ff_srst: 1 bits`. No proof recorded. Confidence 0.5000. Inputs: rst = nets _17_. Role: datapath.
- h181 (unconfirmed): 5 cells form a flip-flop with synchronous reset, `ff_srst: 1 bits`. No proof recorded. Confidence 0.5000. Inputs: rst = nets _17_. Role: datapath.

## 7. Rejected claims

- h151: Loki tested a 2-bit adder with carry-in (`Y = A + B + CI`) on 5 cells and the proof showed it differs (truth_table), counterexample A[0]=0,A[1]=0,B[0]=0,B[1]=0,CI=0.

## 9. What Loki does NOT claim

- Candidates and rejected claims are not statements of fact.
- Module names such as `adder_h1` are Loki's labels built from the kind and the id; they are not the original HDL names, which Loki does not know.

## Helper nets

These nets have no wire of their own in the netlist. Each is defined from netlist wires or other helper nets.

- w1 = NOT(in)
- w2 = NOT(reset)
- w3 = OR(NOT(w2), NOT(w1))
- w4 = AND(NOT(disc), NOT(state[0]))
- w5 = NOT(w4)
- w6 = AND(NOT(w5), NOT(flag))
- w7 = NOT(state[4])
- w8 = AND(NOT(err), NOT(state[4]))
- w9 = AND(NOT(state[8]), NOT(state[5]))
- w10 = OR(NOT(w6), NOT(w9))
- w11 = AND(NOT(err), NOT(state[3]))
- w12 = AND(NOT(state[2]), NOT(reset))
- w13 = OR(NOT(w12), NOT(w11))
- w14 = AND(NOT(w10), NOT(w13))
[LOKI-HINTS-END]
Designer prior: designers write RTL from familiar patterns. If a signal looks like a condition, it
probably is one; if a register group looks like an FSM, it probably is one.
