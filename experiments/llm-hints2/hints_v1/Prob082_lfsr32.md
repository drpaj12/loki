Loki structural hints for the netlist above. Loki is a netlist analysis program (no language model).
Its output follows between the markers. The worked examples above did not carry hints.
Net names in the hints are wires and ports of the netlist above, except the names w1, w2, ...:
those are helper nets that have no wire of their own; each is defined in the list of helper nets
at the end of the hints, in terms of netlist wires or other helper nets.
[LOKI-HINTS-BEGIN]
# Loki analysis of a gate netlist

## 1. What this is

Loki III analysed the gate-level netlist `netlist.v` (sha256 0c370e9dcdad, floor f3).
The list below holds Loki's claims about its higher-level structure.
Each claim has a confidence (a probability) and a proof status.
Trust order: proved or derived claims, then unproven claims with high confidence, then candidates.
Committed claims have confidence of at least 0.9; candidates are listed from 0.5 and are unconfirmed.

## 3. Summary

| kind | committed | candidate | rejected |
| --- | --- | --- | --- |
| bus | 2 | 6 | 0 |
| eq_const | 38 | 0 | 0 |
| ff_srst | 0 | 36 | 0 |
| register | 0 | 2 | 0 |
| subtractor | 0 | 0 | 1 |

Input cells (in Loki's re-mapped netlist): 105.

Of the committed cells, 57 (in 2 claims) are marked only by attributes on existing cells (form attrs). Those claims are not modules, so the hierarchy below does not show them.

Recovered module hierarchy (a module contains its children):

- h69 eq_const_h69 (eq_const)
- h70 eq_const_h70 (eq_const)
- h71 eq_const_h71 (eq_const)
- h72 eq_const_h72 (eq_const)
- h73 eq_const_h73 (eq_const)
- h74 eq_const_h74 (eq_const)
- h75 eq_const_h75 (eq_const)
- h76 eq_const_h76 (eq_const)
- h77 eq_const_h77 (eq_const)
- h78 eq_const_h78 (eq_const)
- h79 eq_const_h79 (eq_const)
- h80 eq_const_h80 (eq_const)
- h81 eq_const_h81 (eq_const)
- h82 eq_const_h82 (eq_const)
- h83 eq_const_h83 (eq_const)
- h84 eq_const_h84 (eq_const)
- h85 eq_const_h85 (eq_const)
- h86 eq_const_h86 (eq_const)
- h87 eq_const_h87 (eq_const)
- h88 eq_const_h88 (eq_const)
- h89 eq_const_h89 (eq_const)
- h90 eq_const_h90 (eq_const)
- h91 eq_const_h91 (eq_const)
- h94 eq_const_h94 (eq_const)
- h96 eq_const_h96 (eq_const)
- h97 eq_const_h97 (eq_const)
- h98 eq_const_h98 (eq_const)
- h99 eq_const_h99 (eq_const)
- h100 eq_const_h100 (eq_const)
- h101 eq_const_h101 (eq_const)
- h102 eq_const_h102 (eq_const)
- h103 eq_const_h103 (eq_const)
- h225 eq_const_h225 (eq_const)
- h227 eq_const_h227 (eq_const)
- h228 eq_const_h228 (eq_const)
- h239 eq_const_h239 (eq_const)
  - h238 eq_const_h238 (eq_const)
  - h243 eq_const_h243 (eq_const)

## 4. Committed claims

- h69: 2 cells form a comparison against a constant, `Y = (A == 2)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets reset, q[10]. Outputs: Y = nets _000_. Recovered as module eq_const_h69, instance eq_const_h69_i. Role: datapath.
- h70: 2 cells form a comparison against a constant, `Y = (A == 2)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets reset, q[11]. Outputs: Y = nets _001_. Recovered as module eq_const_h70, instance eq_const_h70_i. Role: datapath.
- h71: 2 cells form a comparison against a constant, `Y = (A == 2)`. Proof derived from h69 (proof transfer). Confidence 0.9999. Inputs: A = nets reset, q[12]. Outputs: Y = nets _002_. Recovered as module eq_const_h71, instance eq_const_h71_i. Role: datapath.
- h72: 2 cells form a comparison against a constant, `Y = (A == 2)`. Proof derived from h69 (proof transfer). Confidence 0.9999. Inputs: A = nets reset, q[13]. Outputs: Y = nets _003_. Recovered as module eq_const_h72, instance eq_const_h72_i. Role: datapath.
- h73: 2 cells form a comparison against a constant, `Y = (A == 2)`. Proof derived from h69 (proof transfer). Confidence 0.9999. Inputs: A = nets reset, q[14]. Outputs: Y = nets _004_. Recovered as module eq_const_h73, instance eq_const_h73_i. Role: datapath.
- h74: 2 cells form a comparison against a constant, `Y = (A == 2)`. Proof derived from h69 (proof transfer). Confidence 0.9999. Inputs: A = nets reset, q[15]. Outputs: Y = nets _005_. Recovered as module eq_const_h74, instance eq_const_h74_i. Role: datapath.
- h75: 2 cells form a comparison against a constant, `Y = (A == 2)`. Proof derived from h69 (proof transfer). Confidence 0.9999. Inputs: A = nets reset, q[16]. Outputs: Y = nets _006_. Recovered as module eq_const_h75, instance eq_const_h75_i. Role: datapath.
- h76: 2 cells form a comparison against a constant, `Y = (A == 2)`. Proof derived from h69 (proof transfer). Confidence 0.9999. Inputs: A = nets reset, q[17]. Outputs: Y = nets _007_. Recovered as module eq_const_h76, instance eq_const_h76_i. Role: datapath.
- h77: 2 cells form a comparison against a constant, `Y = (A == 2)`. Proof derived from h69 (proof transfer). Confidence 0.9999. Inputs: A = nets reset, q[18]. Outputs: Y = nets _008_. Recovered as module eq_const_h77, instance eq_const_h77_i. Role: datapath.
- h78: 2 cells form a comparison against a constant, `Y = (A == 2)`. Proof derived from h69 (proof transfer). Confidence 0.9999. Inputs: A = nets reset, q[19]. Outputs: Y = nets _009_. Recovered as module eq_const_h78, instance eq_const_h78_i. Role: datapath.
- h79: 2 cells form a comparison against a constant, `Y = (A == 2)`. Proof derived from h69 (proof transfer). Confidence 0.9999. Inputs: A = nets reset, q[20]. Outputs: Y = nets _010_. Recovered as module eq_const_h79, instance eq_const_h79_i. Role: datapath.
- h80: 2 cells form a comparison against a constant, `Y = (A == 2)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets reset, q[21]. Outputs: Y = nets _011_. Recovered as module eq_const_h80, instance eq_const_h80_i. Role: datapath.
- h81: 1 cell form a comparison against a constant, `Y = (A != 3)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets q[0], q[22]. Outputs: Y = nets _032_. Recovered as module eq_const_h81, instance eq_const_h81_i. Role: datapath.
- h82: 1 cell form a comparison against a constant, `Y = (A == 0)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets q[0], q[22]. Outputs: Y = nets _033_. Recovered as module eq_const_h82, instance eq_const_h82_i. Role: datapath.
- h83: 2 cells form a comparison against a constant, `Y = (A == 2)`. Proof derived from h69 (proof transfer). Confidence 0.9999. Inputs: A = nets reset, q[23]. Outputs: Y = nets _013_. Recovered as module eq_const_h83, instance eq_const_h83_i. Role: datapath.
- h84: 2 cells form a comparison against a constant, `Y = (A == 2)`. Proof derived from h69 (proof transfer). Confidence 0.9999. Inputs: A = nets reset, q[24]. Outputs: Y = nets _014_. Recovered as module eq_const_h84, instance eq_const_h84_i. Role: datapath.
- h85: 2 cells form a comparison against a constant, `Y = (A == 2)`. Proof derived from h69 (proof transfer). Confidence 0.9999. Inputs: A = nets reset, q[25]. Outputs: Y = nets _015_. Recovered as module eq_const_h85, instance eq_const_h85_i. Role: datapath.
- h86: 2 cells form a comparison against a constant, `Y = (A == 2)`. Proof derived from h69 (proof transfer). Confidence 0.9999. Inputs: A = nets reset, q[26]. Outputs: Y = nets _016_. Recovered as module eq_const_h86, instance eq_const_h86_i. Role: datapath.
- h87: 2 cells form a comparison against a constant, `Y = (A == 2)`. Proof derived from h69 (proof transfer). Confidence 0.9999. Inputs: A = nets reset, q[27]. Outputs: Y = nets _017_. Recovered as module eq_const_h87, instance eq_const_h87_i. Role: datapath.
- h88: 2 cells form a comparison against a constant, `Y = (A == 2)`. Proof derived from h69 (proof transfer). Confidence 0.9999. Inputs: A = nets reset, q[28]. Outputs: Y = nets _018_. Recovered as module eq_const_h88, instance eq_const_h88_i. Role: datapath.
- h89: 2 cells form a comparison against a constant, `Y = (A == 2)`. Proof derived from h69 (proof transfer). Confidence 0.9999. Inputs: A = nets reset, q[29]. Outputs: Y = nets _019_. Recovered as module eq_const_h89, instance eq_const_h89_i. Role: datapath.
- h90: 2 cells form a comparison against a constant, `Y = (A == 2)`. Proof derived from h69 (proof transfer). Confidence 0.9999. Inputs: A = nets reset, q[30]. Outputs: Y = nets _020_. Recovered as module eq_const_h90, instance eq_const_h90_i. Role: datapath.
- h91: 2 cells form a comparison against a constant, `Y = (A == 2)`. Proof derived from h69 (proof transfer). Confidence 0.9999. Inputs: A = nets reset, q[31]. Outputs: Y = nets _021_. Recovered as module eq_const_h91, instance eq_const_h91_i. Role: datapath.
- h94: 2 cells form a comparison against a constant, `Y = (A == 2)`. Proved equivalent by truth table. Confidence 0.9164. Inputs: A = nets reset, q[0]. Outputs: Y = nets _022_. Recovered as module eq_const_h94, instance eq_const_h94_i. Role: datapath. Conflicts with 3 more not listed.
- h96: 1 cell form a comparison against a constant, `Y = (A != 3)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets q[0], q[2]. Outputs: Y = nets _039_. Recovered as module eq_const_h96, instance eq_const_h96_i. Role: datapath.
- h97: 2 cells form a comparison against a constant, `Y = (A == 2)`. Proof derived from h69 (proof transfer). Confidence 0.9999. Inputs: A = nets reset, q[3]. Outputs: Y = nets _025_. Recovered as module eq_const_h97, instance eq_const_h97_i. Role: datapath.
- h98: 2 cells form a comparison against a constant, `Y = (A == 2)`. Proof derived from h69 (proof transfer). Confidence 0.9999. Inputs: A = nets reset, q[4]. Outputs: Y = nets _026_. Recovered as module eq_const_h98, instance eq_const_h98_i. Role: datapath.
- h99: 2 cells form a comparison against a constant, `Y = (A == 2)`. Proof derived from h69 (proof transfer). Confidence 0.9999. Inputs: A = nets reset, q[5]. Outputs: Y = nets _027_. Recovered as module eq_const_h99, instance eq_const_h99_i. Role: datapath.
- h100: 2 cells form a comparison against a constant, `Y = (A == 2)`. Proof derived from h69 (proof transfer). Confidence 0.9999. Inputs: A = nets reset, q[6]. Outputs: Y = nets _028_. Recovered as module eq_const_h100, instance eq_const_h100_i. Role: datapath.
- h101: 2 cells form a comparison against a constant, `Y = (A == 2)`. Proof derived from h69 (proof transfer). Confidence 0.9999. Inputs: A = nets reset, q[7]. Outputs: Y = nets _029_. Recovered as module eq_const_h101, instance eq_const_h101_i. Role: datapath.
- h102: 2 cells form a comparison against a constant, `Y = (A == 2)`. Proof derived from h69 (proof transfer). Confidence 0.9999. Inputs: A = nets reset, q[8]. Outputs: Y = nets _030_. Recovered as module eq_const_h102, instance eq_const_h102_i. Role: datapath.
- h103: 2 cells form a comparison against a constant, `Y = (A == 2)`. Proof derived from h69 (proof transfer). Confidence 0.9999. Inputs: A = nets reset, q[9]. Outputs: Y = nets _031_. Recovered as module eq_const_h103, instance eq_const_h103_i. Role: datapath.
- h225: 3 cells form a comparison against a constant, `Y = (A == 2)`. Proved equivalent by truth table. Confidence 0.9980. Inputs: A = nets reset, _032_, _033_. Outputs: Y = nets _012_. Recovered as module eq_const_h225, instance eq_const_h225_i. Role: datapath. Conflicts with 2 more not listed.
- h227: 1 cell form a comparison against a constant, `Y = (A == 0)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets q[1], _065_. Outputs: Y = nets w3. Recovered as module eq_const_h227, instance eq_const_h227_i. Role: datapath.
- h228: 2 cells form a comparison against a constant, `Y = (A != 2)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets q[2], _065_. Outputs: Y = nets w5. Recovered as module eq_const_h228, instance eq_const_h228_i. Role: datapath.
- h239: 2 cells form a comparison against a constant, `Y = (A == 6)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets reset, w5, _039_. Outputs: Y = nets _024_. Recovered as module eq_const_h239, instance eq_const_h239_i. Role: datapath.
- h238: 1 cell form a comparison against a constant, `Y = (A != 3)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets w5, _039_. Outputs: Y = nets w6. Recovered as module eq_const_h238, instance eq_const_h238_i. Role: datapath.
- h243: 1 cell form a comparison against a constant, `Y = (A == 0)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets reset, w6. Outputs: Y = nets _024_. Recovered as module eq_const_h243, instance eq_const_h243_i. Role: datapath.
- h5: 29 cells form a 29-bit bus, `bus: 29 bits`. No proof recorded. Confidence 0.9234. Inputs: slice0 = nets w1; slice1 = nets w4; slice10 = nets _045_; slice11 = nets _046_; slice12 = nets _047_; slice13 = nets _048_; slice14 = nets _049_; slice15 = nets _050_; slice16 = nets _051_; slice17 = nets _052_; slice18 = nets _053_; slice19 = nets _054_; slice2 = nets _066_; slice20 = nets _056_; slice21 = nets _057_; slice22 = nets _058_; slice23 = nets _059_; slice24 = nets _060_; slice25 = nets _061_; slice26 = nets _062_; slice27 = nets _063_; slice28 = nets _064_; slice3 = nets _067_; slice4 = nets _068_; slice5 = nets _069_; slice6 = nets _070_; slice7 = nets _071_; slice8 = nets _072_; slice9 = nets _043_. Role: datapath.
- h6: 28 cells form a 28-bit bus, `bus: 28 bits`. No proof recorded. Confidence 0.9234. Inputs: slice0 = nets w2; slice1 = nets _025_; slice10 = nets _002_; slice11 = nets _003_; slice12 = nets _004_; slice13 = nets _005_; slice14 = nets _006_; slice15 = nets _007_; slice16 = nets _008_; slice17 = nets _009_; slice18 = nets _010_; slice19 = nets _013_; slice2 = nets _026_; slice20 = nets _014_; slice21 = nets _015_; slice22 = nets _016_; slice23 = nets _017_; slice24 = nets _018_; slice25 = nets _019_; slice26 = nets _020_; slice27 = nets _021_; slice3 = nets _027_; slice4 = nets _028_; slice5 = nets _029_; slice6 = nets _030_; slice7 = nets _031_; slice8 = nets _000_; slice9 = nets _001_. Role: datapath.

## 5. Buses, state machines and roles

Buses:
- h5: 29 bits, bit order from wf: bit 0 = w1; bit 1 = w4; bit 2 = _066_; bit 3 = _067_; bit 4 = _068_; bit 5 = _069_; bit 6 = _070_; bit 7 = _071_; bit 8 = _072_; bit 9 = _043_; bit 10 = _045_; bit 11 = _046_; bit 12 = _047_; bit 13 = _048_; bit 14 = _049_; bit 15 = _050_; bit 16 = _051_; bit 17 = _052_; bit 18 = _053_; bit 19 = _054_; bit 20 = _056_; bit 21 = _057_; bit 22 = _058_; bit 23 = _059_; bit 24 = _060_; bit 25 = _061_; bit 26 = _062_; bit 27 = _063_; bit 28 = _064_.
- h6: 28 bits, bit order from wf: bit 0 = w2; bit 1 = _025_; bit 2 = _026_; bit 3 = _027_; bit 4 = _028_; bit 5 = _029_; bit 6 = _030_; bit 7 = _031_; bit 8 = _000_; bit 9 = _001_; bit 10 = _002_; bit 11 = _003_; bit 12 = _004_; bit 13 = _005_; bit 14 = _006_; bit 15 = _007_; bit 16 = _008_; bit 17 = _009_; bit 18 = _010_; bit 19 = _013_; bit 20 = _014_; bit 21 = _015_; bit 22 = _016_; bit 23 = _017_; bit 24 = _018_; bit 25 = _019_; bit 26 = _020_; bit 27 = _021_.
- h7 (unconfirmed): 2 bits, bit order from wf: bit 0 = _065_; bit 1 = _055_.
- h105 (unconfirmed): 30 bits, bit order from net_id: bit 0 = _000_; bit 1 = _001_; bit 2 = _002_; bit 3 = _003_; bit 4 = _004_; bit 5 = _005_; bit 6 = _006_; bit 7 = _007_; bit 8 = _008_; bit 9 = _009_; bit 10 = _010_; bit 11 = _011_; bit 12 = _013_; bit 13 = _014_; bit 14 = _015_; bit 15 = _016_; bit 16 = _017_; bit 17 = _018_; bit 18 = _019_; bit 19 = _020_; bit 20 = _021_; bit 21 = _022_; bit 22 = _024_; bit 23 = _025_; bit 24 = _026_; bit 25 = _027_; bit 26 = _028_; bit 27 = _029_; bit 28 = _030_; bit 29 = _031_.
- h106 (unconfirmed): 2 bits, bit order from net_id: bit 0 = _034_; bit 1 = _023_.
- h217 (unconfirmed): 2 bits, bit order from wf: bit 0 = w3; bit 1 = w2.
- h218 (unconfirmed): 2 bits, bit order from wf: bit 0 = w3; bit 1 = _024_.
- h229 (unconfirmed): 29 bits, bit order from net_id: bit 0 = _022_, _065_; bit 1 = _025_; bit 2 = _026_; bit 3 = _027_; bit 4 = _028_; bit 5 = _029_; bit 6 = _030_; bit 7 = _031_; bit 8 = _000_; bit 9 = _001_; bit 10 = _002_; bit 11 = _003_; bit 12 = _004_; bit 13 = _005_; bit 14 = _006_; bit 15 = _007_; bit 16 = _008_; bit 17 = _009_; bit 18 = _010_; bit 19 = _011_; bit 20 = _013_; bit 21 = _014_; bit 22 = _015_; bit 23 = _016_; bit 24 = _017_; bit 25 = _018_; bit 26 = _019_; bit 27 = _020_; bit 28 = _021_.

State machines: none.

Roles of committed claims: datapath: h5, h6, h69, h70, h71, h72, h73, h74, h75, h76, h77, h78, h79, h80, h81, h82, h83, h84, h85, h86, h87, h88, h89, h90, h91, h94, h96, h97, h98, h99, h100, h101, h102, h103, h225, h227, h228, h238, h239, h243.

## 6. Candidates (not committed, unconfirmed)

- h9 (unconfirmed): 3 cells form a flip-flop with synchronous reset, `ff_srst: 1 bits`. No proof recorded. Confidence 0.9526. Inputs: d = nets _000_; rst = nets reset. Outputs: q = nets q[9]. Role: datapath.
- h11 (unconfirmed): 3 cells form a flip-flop with synchronous reset, `ff_srst: 1 bits`. No proof recorded. Confidence 0.9526. Inputs: d = nets _001_; rst = nets reset. Outputs: q = nets q[10]. Role: datapath.
- h13 (unconfirmed): 3 cells form a flip-flop with synchronous reset, `ff_srst: 1 bits`. No proof recorded. Confidence 0.9526. Inputs: d = nets _002_; rst = nets reset. Outputs: q = nets q[11]. Role: datapath.
- h15 (unconfirmed): 3 cells form a flip-flop with synchronous reset, `ff_srst: 1 bits`. No proof recorded. Confidence 0.9526. Inputs: d = nets _003_; rst = nets reset. Outputs: q = nets q[12]. Role: datapath.
- h17 (unconfirmed): 3 cells form a flip-flop with synchronous reset, `ff_srst: 1 bits`. No proof recorded. Confidence 0.9526. Inputs: d = nets _004_; rst = nets reset. Outputs: q = nets q[13]. Role: datapath.
- h19 (unconfirmed): 3 cells form a flip-flop with synchronous reset, `ff_srst: 1 bits`. No proof recorded. Confidence 0.9526. Inputs: d = nets _005_; rst = nets reset. Outputs: q = nets q[14]. Role: datapath.
- h21 (unconfirmed): 3 cells form a flip-flop with synchronous reset, `ff_srst: 1 bits`. No proof recorded. Confidence 0.9526. Inputs: d = nets _006_; rst = nets reset. Outputs: q = nets q[15]. Role: datapath.
- h23 (unconfirmed): 3 cells form a flip-flop with synchronous reset, `ff_srst: 1 bits`. No proof recorded. Confidence 0.9526. Inputs: d = nets _007_; rst = nets reset. Outputs: q = nets q[16]. Role: datapath.
- h25 (unconfirmed): 3 cells form a flip-flop with synchronous reset, `ff_srst: 1 bits`. No proof recorded. Confidence 0.9526. Inputs: d = nets _008_; rst = nets reset. Outputs: q = nets q[17]. Role: datapath.
- h27 (unconfirmed): 3 cells form a flip-flop with synchronous reset, `ff_srst: 1 bits`. No proof recorded. Confidence 0.9526. Inputs: d = nets _009_; rst = nets reset. Outputs: q = nets q[18]. Role: datapath.
- h29 (unconfirmed): 3 cells form a flip-flop with synchronous reset, `ff_srst: 1 bits`. No proof recorded. Confidence 0.9526. Inputs: d = nets _010_; rst = nets reset. Outputs: q = nets q[19]. Role: datapath.
- h31 (unconfirmed): 3 cells form a flip-flop with synchronous reset, `ff_srst: 1 bits`. No proof recorded. Confidence 0.9526. Inputs: d = nets _011_; rst = nets reset. Outputs: q = nets q[20]. Role: datapath.
- h34 (unconfirmed): 3 cells form a flip-flop with synchronous reset, `ff_srst: 1 bits`. No proof recorded. Confidence 0.9526. Inputs: d = nets _013_; rst = nets reset. Outputs: q = nets q[22]. Role: datapath.
- h36 (unconfirmed): 3 cells form a flip-flop with synchronous reset, `ff_srst: 1 bits`. No proof recorded. Confidence 0.9526. Inputs: d = nets _014_; rst = nets reset. Outputs: q = nets q[23]. Role: datapath.
- h38 (unconfirmed): 3 cells form a flip-flop with synchronous reset, `ff_srst: 1 bits`. No proof recorded. Confidence 0.9526. Inputs: d = nets _015_; rst = nets reset. Outputs: q = nets q[24]. Role: datapath.
- h40 (unconfirmed): 3 cells form a flip-flop with synchronous reset, `ff_srst: 1 bits`. No proof recorded. Confidence 0.9526. Inputs: d = nets _016_; rst = nets reset. Outputs: q = nets q[25]. Role: datapath.
- h42 (unconfirmed): 3 cells form a flip-flop with synchronous reset, `ff_srst: 1 bits`. No proof recorded. Confidence 0.9526. Inputs: d = nets _017_; rst = nets reset. Outputs: q = nets q[26]. Role: datapath.
- h44 (unconfirmed): 3 cells form a flip-flop with synchronous reset, `ff_srst: 1 bits`. No proof recorded. Confidence 0.9526. Inputs: d = nets _018_; rst = nets reset. Outputs: q = nets q[27]. Role: datapath.
- h46 (unconfirmed): 3 cells form a flip-flop with synchronous reset, `ff_srst: 1 bits`. No proof recorded. Confidence 0.9526. Inputs: d = nets _019_; rst = nets reset. Outputs: q = nets q[28]. Role: datapath.
- h48 (unconfirmed): 3 cells form a flip-flop with synchronous reset, `ff_srst: 1 bits`. No proof recorded. Confidence 0.9526. Inputs: d = nets _020_; rst = nets reset. Outputs: q = nets q[29]. Role: datapath.
- h50 (unconfirmed): 3 cells form a flip-flop with synchronous reset, `ff_srst: 1 bits`. No proof recorded. Confidence 0.9526. Inputs: d = nets _021_; rst = nets reset. Outputs: q = nets q[30]. Role: datapath.
- h51 (unconfirmed): 2 cells form a flip-flop with synchronous reset, `ff_srst: 1 bits`. No proof recorded. Confidence 0.9526. Inputs: d = nets _022_; rst = nets reset. Outputs: q = nets q[31]. Role: datapath.
- h54 (unconfirmed): 5 cells form a flip-flop with synchronous reset, `ff_srst: 1 bits`. No proof recorded. Confidence 0.9526. Inputs: d = nets _024_; rst = nets reset. Outputs: q = nets q[1]. Role: datapath.
- h56 (unconfirmed): 3 cells form a flip-flop with synchronous reset, `ff_srst: 1 bits`. No proof recorded. Confidence 0.9526. Inputs: d = nets _025_; rst = nets reset. Outputs: q = nets q[2]. Role: datapath.
- h58 (unconfirmed): 3 cells form a flip-flop with synchronous reset, `ff_srst: 1 bits`. No proof recorded. Confidence 0.9526. Inputs: d = nets _026_; rst = nets reset. Outputs: q = nets q[3]. Role: datapath.
- h60 (unconfirmed): 3 cells form a flip-flop with synchronous reset, `ff_srst: 1 bits`. No proof recorded. Confidence 0.9526. Inputs: d = nets _027_; rst = nets reset. Outputs: q = nets q[4]. Role: datapath.
- h62 (unconfirmed): 3 cells form a flip-flop with synchronous reset, `ff_srst: 1 bits`. No proof recorded. Confidence 0.9526. Inputs: d = nets _028_; rst = nets reset. Outputs: q = nets q[5]. Role: datapath.
- h64 (unconfirmed): 3 cells form a flip-flop with synchronous reset, `ff_srst: 1 bits`. No proof recorded. Confidence 0.9526. Inputs: d = nets _029_; rst = nets reset. Outputs: q = nets q[6]. Role: datapath.
- h66 (unconfirmed): 3 cells form a flip-flop with synchronous reset, `ff_srst: 1 bits`. No proof recorded. Confidence 0.9526. Inputs: d = nets _030_; rst = nets reset. Outputs: q = nets q[7]. Role: datapath.
- h68 (unconfirmed): 3 cells form a flip-flop with synchronous reset, `ff_srst: 1 bits`. No proof recorded. Confidence 0.9526. Inputs: d = nets _031_; rst = nets reset. Outputs: q = nets q[8]. Role: datapath.
- h213 (unconfirmed): 27 cells form a 27-bit register, `register: 27 bits`. No proof recorded. Confidence 0.8889. Inputs: clk = nets clk; d = nets _026_, _027_, _028_, _029_, _030_, _031_, _000_, _001_, _002_, _003_, _004_, _005_, _006_, _007_, _008_, _009_, _010_, _011_, _014_, _015_, _016_, _017_, _018_, _019_, _020_, _021_, _022_. Outputs: q = nets q[3], q[4], q[5], q[6], q[7], q[8], q[9], q[10], q[11], q[12], q[13], q[14], q[15], q[16], q[17], q[18], q[19], q[20], q[23], q[24], q[25], q[26], q[27], q[28], q[29], q[30], q[31]. Role: datapath.
- h232 (unconfirmed): 28 cells form a 28-bit register, `register: 28 bits`. No proof recorded. Confidence 0.8889. Inputs: clk = nets clk; d = nets _026_, _027_, _028_, _029_, _030_, _031_, _000_, _001_, _002_, _003_, _004_, _005_, _006_, _007_, _008_, _009_, _010_, _011_, _012_, _014_, _015_, _016_, _017_, _018_, _019_, _020_, _021_, _022_. Outputs: q = nets q[3], q[4], q[5], q[6], q[7], q[8], q[9], q[10], q[11], q[12], q[13], q[14], q[15], q[16], q[17], q[18], q[19], q[20], q[21], q[23], q[24], q[25], q[26], q[27], q[28], q[29], q[30], q[31]. Role: datapath.
- h106 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.8191. Inputs: ctrl = nets _044_; slice0 = nets _034_; slice1 = nets _023_. Role: datapath.
- h105 (unconfirmed): 30 cells form a 30-bit bus, `bus: 30 bits`. No proof recorded. Confidence 0.8006. Inputs: ctrl = nets reset; slice0 = nets _000_; slice1 = nets _001_; slice10 = nets _010_; slice11 = nets _011_; slice12 = nets _013_; slice13 = nets _014_; slice14 = nets _015_; slice15 = nets _016_; slice16 = nets _017_; slice17 = nets _018_; slice18 = nets _019_; slice19 = nets _020_; slice2 = nets _002_; slice20 = nets _021_; slice21 = nets _022_; slice22 = nets _024_; slice23 = nets _025_; slice24 = nets _026_; slice25 = nets _027_; slice26 = nets _028_; slice27 = nets _029_; slice28 = nets _030_; slice29 = nets _031_; slice3 = nets _003_; slice4 = nets _004_; slice5 = nets _005_; slice6 = nets _006_; slice7 = nets _007_; slice8 = nets _008_; slice9 = nets _009_. Role: datapath.
- h229 (unconfirmed): 58 cells form a 29-bit bus, `bus: 29 bits`. No proof recorded. Confidence 0.8006. Inputs: ctrl = nets reset; slice0 = nets _022_, _065_; slice1 = nets _025_; slice10 = nets _002_; slice11 = nets _003_; slice12 = nets _004_; slice13 = nets _005_; slice14 = nets _006_; slice15 = nets _007_; slice16 = nets _008_; slice17 = nets _009_; slice18 = nets _010_; slice19 = nets _011_; slice2 = nets _026_; slice20 = nets _013_; slice21 = nets _014_; slice22 = nets _015_; slice23 = nets _016_; slice24 = nets _017_; slice25 = nets _018_; slice26 = nets _019_; slice27 = nets _020_; slice28 = nets _021_; slice3 = nets _027_; slice4 = nets _028_; slice5 = nets _029_; slice6 = nets _030_; slice7 = nets _031_; slice8 = nets _000_; slice9 = nets _001_. Role: datapath.
- h32 (unconfirmed): 5 cells form a flip-flop with synchronous reset, `ff_srst: 1 bits`. No proof recorded. Confidence 0.7503. Inputs: d = nets _012_; rst = nets _044_. Outputs: q = nets q[21]. Role: datapath.
- h53 (unconfirmed): 5 cells form a flip-flop with synchronous reset, `ff_srst: 1 bits`. No proof recorded. Confidence 0.7503. Inputs: d = nets _023_; rst = nets _044_. Outputs: q = nets q[0]. Role: datapath.
- h221 (unconfirmed): 3 cells form a flip-flop with synchronous reset, `ff_srst: 1 bits`. No proof recorded. Confidence 0.7503. Inputs: d = nets _012_; rst = nets _044_. Outputs: q = nets q[21]. Role: datapath.
- h7 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.6011. Inputs: slice0 = nets _065_; slice1 = nets _055_. Role: datapath.
- h217 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.6011. Inputs: slice0 = nets w3; slice1 = nets w2. Role: datapath.
- h218 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.6011. Inputs: slice0 = nets w3; slice1 = nets _024_. Role: datapath.
- h1 (unconfirmed): 91 cells form a flip-flop with synchronous reset, `ff_srst: 30 bits`. No proof recorded. Confidence 0.5000. Inputs: d = nets _024_, _025_, _026_, _027_, _028_, _029_, _030_, _031_, _000_, _001_, _002_, _003_, _004_, _005_, _006_, _007_, _008_, _009_, _010_, _011_, _013_, _014_, _015_, _016_, _017_, _018_, _019_, _020_, _021_, _022_; rst = nets reset. Outputs: q = nets q[1], q[2], q[3], q[4], q[5], q[6], q[7], q[8], q[9], q[10], q[11], q[12], q[13], q[14], q[15], q[16], q[17], q[18], q[19], q[20], q[22], q[23], q[24], q[25], q[26], q[27], q[28], q[29], q[30], q[31]. Role: datapath.
- h3 (unconfirmed): 10 cells form a flip-flop with synchronous reset, `ff_srst: 2 bits`. No proof recorded. Confidence 0.5000. Inputs: d = nets _023_, _012_; rst = nets _044_. Outputs: q = nets q[0], q[21]. Role: datapath.
- h214 (unconfirmed): 8 cells form a flip-flop with synchronous reset, `ff_srst: 2 bits`. No proof recorded. Confidence 0.5000. Inputs: d = nets _023_, _012_; rst = nets _044_. Outputs: q = nets q[0], q[21]. Role: datapath.

## 7. Rejected claims

- h219: Loki tested a 2-bit subtractor (`Y = A - B`) on 4 cells and the proof showed it differs (truth_table), counterexample A[0]=0,A[1]=0,B[0]=0,B[1]=0.

## 9. What Loki does NOT claim

- Candidates and rejected claims are not statements of fact.
- Module names such as `adder_h1` are Loki's labels built from the kind and the id; they are not the original HDL names, which Loki does not know.

## Helper nets

These nets have no wire of their own in the netlist. Each is defined from netlist wires or other helper nets.

- w1 = NOT(q[1])
- w2 = AND(NOT(w1), NOT(q[0]))
- w3 = AND(NOT(q[1]), NOT(_065_))
- w4 = NOT(q[2])
- w5 = OR(NOT(_065_), NOT(w4))
- w6 = OR(NOT(_039_), NOT(w5))
[LOKI-HINTS-END]
Designer prior: designers write RTL from familiar patterns. If a signal looks like a condition, it
probably is one; if a register group looks like an FSM, it probably is one.
