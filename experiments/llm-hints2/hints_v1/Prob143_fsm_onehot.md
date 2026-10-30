Loki structural hints for the netlist above. Loki is a netlist analysis program (no language model).
Its output follows between the markers. The worked examples above did not carry hints.
Net names in the hints are wires and ports of the netlist above, except the names w1, w2, ...:
those are helper nets that have no wire of their own; each is defined in the list of helper nets
at the end of the hints, in terms of netlist wires or other helper nets.
[LOKI-HINTS-BEGIN]
# Loki analysis of a gate netlist

## 1. What this is

Loki III analysed the gate-level netlist `netlist.v` (sha256 e6586f94ff3f, floor f3).
The list below holds Loki's claims about its higher-level structure.
Each claim has a confidence (a probability) and a proof status.
Trust order: proved or derived claims, then unproven claims with high confidence, then candidates.
Committed claims have confidence of at least 0.9; candidates are listed from 0.5 and are unconfirmed.

## 3. Summary

| kind | committed | candidate | rejected |
| --- | --- | --- | --- |
| bus | 2 | 4 | 0 |
| eq_const | 15 | 0 | 0 |

Input cells (in Loki's re-mapped netlist): 30.

Of the committed cells, 9 (in 2 claims) are marked only by attributes on existing cells (form attrs). Those claims are not modules, so the hierarchy below does not show them.

Recovered module hierarchy (a module contains its children):

- h4 eq_const_h4 (eq_const)
  - h20 eq_const_h20 (eq_const)
  - h59 eq_const_h59 (eq_const)
- h11 eq_const_h11 (eq_const)
- h12 eq_const_h12 (eq_const)
- h13 eq_const_h13 (eq_const)
- h14 eq_const_h14 (eq_const)
- h16 eq_const_h16 (eq_const)
- h18 eq_const_h18 (eq_const)
  - h17 eq_const_h17 (eq_const)
  - h19 eq_const_h19 (eq_const)
  - h58 eq_const_h58 (eq_const)
- h57 eq_const_h57 (eq_const)
- h65 eq_const_h65 (eq_const)
- h69 eq_const_h69 (eq_const)

## 4. Committed claims

- h4: 4 cells form a comparison against a constant, `Y = (A == 0)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets state[0], state[8], state[9]. Outputs: Y = nets _12_. Recovered as module eq_const_h4, instance eq_const_h4_i. Role: datapath.
- h20: 3 cells form a comparison against a constant, `Y = (A != 0)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets state[8], state[9]. Outputs: Y = nets out1. Recovered as module eq_const_h20, instance eq_const_h20_i. Role: datapath.
- h59: 1 cell form a comparison against a constant, `Y = (A == 0)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets state[0], out1. Outputs: Y = nets _12_. Recovered as module eq_const_h59, instance eq_const_h59_i. Role: datapath.
- h11: 2 cells form a comparison against a constant, `Y = (A == 2)`. Proved equivalent by truth table. Confidence 0.9971. Inputs: A = nets in, state[5]. Outputs: Y = nets next_state[8]. Recovered as module eq_const_h11, instance eq_const_h11_i. Role: datapath. Conflicts with 1 more not listed.
- h12: 1 cell form a comparison against a constant, `Y = (A == 0)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets state[6], state[7]. Outputs: Y = nets _18_. Recovered as module eq_const_h12, instance eq_const_h12_i. Role: datapath.
- h13: 2 cells form a comparison against a constant, `Y = (A == 2)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets in, state[6]. Outputs: Y = nets next_state[9]. Recovered as module eq_const_h13, instance eq_const_h13_i. Role: datapath.
- h14: 1 cell form a comparison against a constant, `Y = (A == 0)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets state[0], state[1]. Outputs: Y = nets _09_. Recovered as module eq_const_h14, instance eq_const_h14_i. Role: datapath.
- h16: 1 cell form a comparison against a constant, `Y = (A == 0)`. Proof derived from h12 (proof transfer). Confidence 0.9999. Inputs: A = nets state[7], state[9]. Outputs: Y = nets _08_. Recovered as module eq_const_h16, instance eq_const_h16_i. Role: datapath.
- h18: 3 cells form a comparison against a constant, `Y = (A != 0)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets state[2], state[3], state[4], state[8]. Outputs: Y = nets _07_. Recovered as module eq_const_h18, instance eq_const_h18_i. Role: datapath.
- h17: 1 cell form a comparison against a constant, `Y = (A == 0)`. Proof derived from h12 (proof transfer). Confidence 0.9999. Inputs: A = nets state[4], state[8]. Outputs: Y = nets _06_. Recovered as module eq_const_h17, instance eq_const_h17_i. Role: datapath.
- h19: 1 cell form a comparison against a constant, `Y = (A == 0)`. Proof derived from h12 (proof transfer). Confidence 0.9999. Inputs: A = nets state[2], state[3]. Outputs: Y = nets _05_. Recovered as module eq_const_h19, instance eq_const_h19_i. Role: datapath.
- h58: 1 cell form a comparison against a constant, `Y = (A != 3)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets _06_, _05_. Outputs: Y = nets _07_. Recovered as module eq_const_h58, instance eq_const_h58_i. Role: datapath.
- h57: 1 cell form a comparison against a constant, `Y = (A != 3)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets _09_, _08_. Outputs: Y = nets _10_. Recovered as module eq_const_h57, instance eq_const_h57_i. Role: datapath.
- h65: 1 cell form a comparison against a constant, `Y = (A == 0)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets _10_, _07_. Outputs: Y = nets _11_. Recovered as module eq_const_h65, instance eq_const_h65_i. Role: datapath.
- h69: 1 cell form a comparison against a constant, `Y = (A == 0)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets in, _11_. Outputs: Y = nets next_state[0]. Recovered as module eq_const_h69, instance eq_const_h69_i. Role: datapath.
- h22: 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.9002. Inputs: ctrl = nets state[7]; slice0 = nets _18_; slice1 = nets _08_. Role: datapath.
- h24: 7 cells form a 7-bit bus, `bus: 7 bits`. No proof recorded. Confidence 0.9234. Inputs: ctrl = nets _00_; slice0 = nets next_state[1]; slice1 = nets next_state[2]; slice2 = nets next_state[3]; slice3 = nets next_state[4]; slice4 = nets next_state[5]; slice5 = nets next_state[6]; slice6 = nets next_state[7]. Role: datapath.

## 5. Buses, state machines and roles

Buses:
- h5 (unconfirmed): 2 bits, bit order from wf: bit 0 = _03_; bit 1 = _00_.
- h21 (unconfirmed): 2 bits, bit order from net_id: bit 0 = _09_; bit 1 = _12_.
- h22: 2 bits, bit order from net_id: bit 0 = _18_; bit 1 = _08_.
- h23 (unconfirmed): 3 bits, bit order from net_id: bit 0 = next_state[0]; bit 1 = next_state[8]; bit 2 = next_state[9].
- h24: 7 bits, bit order from net_id: bit 0 = next_state[1]; bit 1 = next_state[2]; bit 2 = next_state[3]; bit 3 = next_state[4]; bit 4 = next_state[5]; bit 5 = next_state[6]; bit 6 = next_state[7].
- h25 (unconfirmed): 2 bits, bit order from net_id: bit 0 = next_state[8]; bit 1 = next_state[6].

State machines: none.

Roles of committed claims: datapath: h4, h11, h12, h13, h14, h16, h17, h18, h19, h20, h22, h24, h57, h58, h59, h65, h69.

## 6. Candidates (not committed, unconfirmed)

- h21 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.7503. Inputs: ctrl = nets state[0]; slice0 = nets _09_; slice1 = nets _12_. Role: datapath.
- h25 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.7503. Inputs: ctrl = nets _01_; slice0 = nets next_state[8]; slice1 = nets next_state[6]. Role: datapath.
- h5 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.6011. Inputs: slice0 = nets _03_; slice1 = nets _00_. Role: datapath.
- h23 (unconfirmed): 3 cells form a 3-bit bus, `bus: 3 bits`. No proof recorded. Confidence 0.5000. Inputs: ctrl = nets in; slice0 = nets next_state[0]; slice1 = nets next_state[8]; slice2 = nets next_state[9]. Role: datapath.

## 7. Rejected claims

(none)

## 9. What Loki does NOT claim

- Candidates and rejected claims are not statements of fact.
- Module names such as `adder_h1` are Loki's labels built from the kind and the id; they are not the original HDL names, which Loki does not know.
[LOKI-HINTS-END]
Designer prior: designers write RTL from familiar patterns. If a signal looks like a condition, it
probably is one; if a register group looks like an FSM, it probably is one.
