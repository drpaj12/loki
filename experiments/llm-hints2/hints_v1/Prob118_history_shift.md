Loki structural hints for the netlist above. Loki is a netlist analysis program (no language model).
Its output follows between the markers. The worked examples above did not carry hints.
Net names in the hints are wires and ports of the netlist above, except the names w1, w2, ...:
those are helper nets that have no wire of their own; each is defined in the list of helper nets
at the end of the hints, in terms of netlist wires or other helper nets.
[LOKI-HINTS-BEGIN]
# Loki analysis of a gate netlist

## 1. What this is

Loki III analysed the gate-level netlist `netlist.v` (sha256 f6487a512ae3, floor f3).
The list below holds Loki's claims about its higher-level structure.
Each claim has a confidence (a probability) and a proof status.
Trust order: proved or derived claims, then unproven claims with high confidence, then candidates.
Committed claims have confidence of at least 0.9; candidates are listed from 0.5 and are unconfirmed.

## 3. Summary

| kind | committed | candidate | rejected |
| --- | --- | --- | --- |
| adder_cin | 0 | 0 | 1 |
| bus | 31 | 69 | 0 |
| datapath_unit | 0 | 0 | 1 |
| eq_const | 29 | 0 | 6 |

Input cells (in Loki's re-mapped netlist): 235.

Of the committed cells, 64 (in 31 claims) are marked only by attributes on existing cells (form attrs). Those claims are not modules, so the hierarchy below does not show them.

Recovered module hierarchy (a module contains its children):

- h71 eq_const_h71 (eq_const)
  - h135 eq_const_h135 (eq_const)
  - h522 eq_const_h522 (eq_const)
- h73 eq_const_h73 (eq_const)
- h74 eq_const_h74 (eq_const)
- h76 eq_const_h76 (eq_const)
- h77 eq_const_h77 (eq_const)
- h78 eq_const_h78 (eq_const)
- h79 eq_const_h79 (eq_const)
- h80 eq_const_h80 (eq_const)
- h81 eq_const_h81 (eq_const)
- h82 eq_const_h82 (eq_const)
- h83 eq_const_h83 (eq_const)
- h85 eq_const_h85 (eq_const)
- h86 eq_const_h86 (eq_const)
- h87 eq_const_h87 (eq_const)
- h88 eq_const_h88 (eq_const)
- h89 eq_const_h89 (eq_const)
- h90 eq_const_h90 (eq_const)
- h91 eq_const_h91 (eq_const)
- h92 eq_const_h92 (eq_const)
- h93 eq_const_h93 (eq_const)
- h94 eq_const_h94 (eq_const)
- h95 eq_const_h95 (eq_const)
- h96 eq_const_h96 (eq_const)
- h97 eq_const_h97 (eq_const)
- h99 eq_const_h99 (eq_const)
- h100 eq_const_h100 (eq_const)
- h101 eq_const_h101 (eq_const)

## 4. Committed claims

- h71: 3 cells form a comparison against a constant, `Y = (A != 3)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets predict_valid, predict_taken, train_mispredicted. Outputs: Y = nets w7. Recovered as module eq_const_h71, instance eq_const_h71_i. Role: datapath.
- h135: 2 cells form a comparison against a constant, `Y = (A == 1)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets predict_valid, train_mispredicted. Outputs: Y = nets w6. Recovered as module eq_const_h135, instance eq_const_h135_i. Role: datapath.
- h522: 1 cell form a comparison against a constant, `Y = (A != 3)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets predict_taken, w6. Outputs: Y = nets w7. Recovered as module eq_const_h522, instance eq_const_h522_i. Role: datapath.
- h73: 1 cell form a comparison against a constant, `Y = (A != 3)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets train_mispredicted, train_history[0]. Outputs: Y = nets _074_. Recovered as module eq_const_h73, instance eq_const_h73_i. Role: datapath.
- h74: 1 cell form a comparison against a constant, `Y = (A != 3)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets train_mispredicted, train_history[1]. Outputs: Y = nets _078_. Recovered as module eq_const_h74, instance eq_const_h74_i. Role: datapath.
- h76: 1 cell form a comparison against a constant, `Y = (A != 3)`. Proof derived from h73 (proof transfer). Confidence 0.9999. Inputs: A = nets train_mispredicted, train_history[2]. Outputs: Y = nets _082_. Recovered as module eq_const_h76, instance eq_const_h76_i. Role: datapath.
- h77: 1 cell form a comparison against a constant, `Y = (A != 3)`. Proof derived from h73 (proof transfer). Confidence 0.9999. Inputs: A = nets train_mispredicted, train_history[5]. Outputs: Y = nets _094_. Recovered as module eq_const_h77, instance eq_const_h77_i. Role: datapath.
- h78: 1 cell form a comparison against a constant, `Y = (A != 3)`. Proof derived from h73 (proof transfer). Confidence 0.9999. Inputs: A = nets train_mispredicted, train_history[6]. Outputs: Y = nets _098_. Recovered as module eq_const_h78, instance eq_const_h78_i. Role: datapath.
- h79: 1 cell form a comparison against a constant, `Y = (A != 3)`. Proof derived from h73 (proof transfer). Confidence 0.9999. Inputs: A = nets train_mispredicted, train_history[7]. Outputs: Y = nets _102_. Recovered as module eq_const_h79, instance eq_const_h79_i. Role: datapath.
- h80: 1 cell form a comparison against a constant, `Y = (A != 3)`. Proof derived from h73 (proof transfer). Confidence 0.9999. Inputs: A = nets train_mispredicted, train_history[8]. Outputs: Y = nets _106_. Recovered as module eq_const_h80, instance eq_const_h80_i. Role: datapath.
- h81: 1 cell form a comparison against a constant, `Y = (A != 3)`. Proof derived from h73 (proof transfer). Confidence 0.9999. Inputs: A = nets train_mispredicted, train_history[9]. Outputs: Y = nets _110_. Recovered as module eq_const_h81, instance eq_const_h81_i. Role: datapath.
- h82: 1 cell form a comparison against a constant, `Y = (A != 3)`. Proof derived from h73 (proof transfer). Confidence 0.9999. Inputs: A = nets train_mispredicted, train_history[10]. Outputs: Y = nets _114_. Recovered as module eq_const_h82, instance eq_const_h82_i. Role: datapath.
- h83: 1 cell form a comparison against a constant, `Y = (A != 3)`. Proof derived from h73 (proof transfer). Confidence 0.9999. Inputs: A = nets train_mispredicted, train_history[11]. Outputs: Y = nets _118_. Recovered as module eq_const_h83, instance eq_const_h83_i. Role: datapath.
- h85: 1 cell form a comparison against a constant, `Y = (A != 3)`. Proof derived from h73 (proof transfer). Confidence 0.9999. Inputs: A = nets train_mispredicted, train_history[12]. Outputs: Y = nets _122_. Recovered as module eq_const_h85, instance eq_const_h85_i. Role: datapath.
- h86: 1 cell form a comparison against a constant, `Y = (A != 3)`. Proof derived from h73 (proof transfer). Confidence 0.9999. Inputs: A = nets train_mispredicted, train_history[15]. Outputs: Y = nets _134_. Recovered as module eq_const_h86, instance eq_const_h86_i. Role: datapath.
- h87: 1 cell form a comparison against a constant, `Y = (A != 3)`. Proof derived from h73 (proof transfer). Confidence 0.9999. Inputs: A = nets train_mispredicted, train_history[16]. Outputs: Y = nets _138_. Recovered as module eq_const_h87, instance eq_const_h87_i. Role: datapath.
- h88: 1 cell form a comparison against a constant, `Y = (A != 3)`. Proof derived from h73 (proof transfer). Confidence 0.9999. Inputs: A = nets train_mispredicted, train_history[17]. Outputs: Y = nets _142_. Recovered as module eq_const_h88, instance eq_const_h88_i. Role: datapath.
- h89: 1 cell form a comparison against a constant, `Y = (A != 3)`. Proof derived from h73 (proof transfer). Confidence 0.9999. Inputs: A = nets train_mispredicted, train_history[18]. Outputs: Y = nets _146_. Recovered as module eq_const_h89, instance eq_const_h89_i. Role: datapath.
- h90: 1 cell form a comparison against a constant, `Y = (A != 3)`. Proof derived from h73 (proof transfer). Confidence 0.9999. Inputs: A = nets train_mispredicted, train_history[19]. Outputs: Y = nets _150_. Recovered as module eq_const_h90, instance eq_const_h90_i. Role: datapath.
- h91: 1 cell form a comparison against a constant, `Y = (A != 3)`. Proof derived from h73 (proof transfer). Confidence 0.9999. Inputs: A = nets train_mispredicted, train_history[20]. Outputs: Y = nets _154_. Recovered as module eq_const_h91, instance eq_const_h91_i. Role: datapath.
- h92: 1 cell form a comparison against a constant, `Y = (A != 3)`. Proof derived from h73 (proof transfer). Confidence 0.9999. Inputs: A = nets train_mispredicted, train_history[21]. Outputs: Y = nets _158_. Recovered as module eq_const_h92, instance eq_const_h92_i. Role: datapath.
- h93: 1 cell form a comparison against a constant, `Y = (A != 3)`. Proof derived from h73 (proof transfer). Confidence 0.9999. Inputs: A = nets train_mispredicted, train_history[22]. Outputs: Y = nets _162_. Recovered as module eq_const_h93, instance eq_const_h93_i. Role: datapath.
- h94: 1 cell form a comparison against a constant, `Y = (A != 3)`. Proof derived from h73 (proof transfer). Confidence 0.9999. Inputs: A = nets train_mispredicted, train_history[23]. Outputs: Y = nets _166_. Recovered as module eq_const_h94, instance eq_const_h94_i. Role: datapath.
- h95: 1 cell form a comparison against a constant, `Y = (A != 3)`. Proof derived from h73 (proof transfer). Confidence 0.9999. Inputs: A = nets train_mispredicted, train_history[24]. Outputs: Y = nets _170_. Recovered as module eq_const_h95, instance eq_const_h95_i. Role: datapath.
- h96: 1 cell form a comparison against a constant, `Y = (A != 3)`. Proof derived from h73 (proof transfer). Confidence 0.9999. Inputs: A = nets train_mispredicted, train_history[25]. Outputs: Y = nets _174_. Recovered as module eq_const_h96, instance eq_const_h96_i. Role: datapath.
- h97: 1 cell form a comparison against a constant, `Y = (A != 3)`. Proof derived from h73 (proof transfer). Confidence 0.9999. Inputs: A = nets train_mispredicted, train_history[26]. Outputs: Y = nets _178_. Recovered as module eq_const_h97, instance eq_const_h97_i. Role: datapath.
- h99: 1 cell form a comparison against a constant, `Y = (A != 3)`. Proof derived from h73 (proof transfer). Confidence 0.9999. Inputs: A = nets train_mispredicted, train_history[27]. Outputs: Y = nets _182_. Recovered as module eq_const_h99, instance eq_const_h99_i. Role: datapath.
- h100: 1 cell form a comparison against a constant, `Y = (A != 3)`. Proof derived from h73 (proof transfer). Confidence 0.9999. Inputs: A = nets train_mispredicted, train_history[30]. Outputs: Y = nets _194_. Recovered as module eq_const_h100, instance eq_const_h100_i. Role: datapath.
- h101: 1 cell form a comparison against a constant, `Y = (A == 0)`. Proved equivalent by truth table. Confidence 0.9999. Inputs: A = nets predict_valid, train_mispredicted. Outputs: Y = nets w1. Recovered as module eq_const_h101, instance eq_const_h101_i. Role: datapath.
- h179: 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.9474. Inputs: ctrl = nets w2; slice0 = nets w3; slice1 = nets w10. Role: datapath.
- h180: 29 cells form a 29-bit bus, `bus: 29 bits`. No proof recorded. Confidence 0.9954. Inputs: ctrl = nets _070_; slice0 = nets w3; slice1 = nets w9; slice10 = nets w43; slice11 = nets w46; slice12 = nets w49; slice13 = nets w55; slice14 = nets w61; slice15 = nets w64; slice16 = nets w67; slice17 = nets w70; slice18 = nets w73; slice19 = nets w76; slice2 = nets w12; slice20 = nets w79; slice21 = nets w82; slice22 = nets w85; slice23 = nets w88; slice24 = nets w91; slice25 = nets w94; slice26 = nets w97; slice27 = nets w103; slice28 = nets w108; slice3 = nets w16; slice4 = nets w22; slice5 = nets w28; slice6 = nets w31; slice7 = nets w34; slice8 = nets w37; slice9 = nets w40. Role: datapath.
- h181: 7 cells form a 7-bit bus, `bus: 7 bits`. No proof recorded. Confidence 0.9731. Inputs: ctrl = nets _065_; slice0 = nets w5; slice1 = nets w19; slice2 = nets w24; slice3 = nets w52; slice4 = nets w57; slice5 = nets w100; slice6 = nets w105. Role: datapath.
- h183: 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.9474. Inputs: ctrl = nets w8; slice0 = nets w9; slice1 = nets w13. Role: datapath.
- h184: 28 cells form a 28-bit bus, `bus: 28 bits`. No proof recorded. Confidence 0.9954. Inputs: ctrl = nets _067_; slice0 = nets w10; slice1 = nets w13; slice10 = nets w44; slice11 = nets w47; slice12 = nets w50; slice13 = nets w59; slice14 = nets w62; slice15 = nets w65; slice16 = nets w68; slice17 = nets w71; slice18 = nets w74; slice19 = nets w77; slice2 = nets w14; slice20 = nets w80; slice21 = nets w83; slice22 = nets w86; slice23 = nets w89; slice24 = nets w92; slice25 = nets w95; slice26 = nets w98; slice27 = nets w109; slice3 = nets w17; slice4 = nets w26; slice5 = nets w29; slice6 = nets w32; slice7 = nets w35; slice8 = nets w38; slice9 = nets w41. Role: datapath.
- h185: 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.9474. Inputs: ctrl = nets w11; slice0 = nets w12; slice1 = nets w14. Role: datapath.
- h186: 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.9474. Inputs: ctrl = nets w15; slice0 = nets w16; slice1 = nets w17. Role: datapath.
- h189: 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.9474. Inputs: ctrl = nets w21; slice0 = nets w22; slice1 = nets w26. Role: datapath.
- h190: 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.9474. Inputs: ctrl = nets w27; slice0 = nets w28; slice1 = nets w29. Role: datapath.
- h191: 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.9474. Inputs: ctrl = nets w30; slice0 = nets w31; slice1 = nets w32. Role: datapath.
- h192: 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.9474. Inputs: ctrl = nets w33; slice0 = nets w34; slice1 = nets w35. Role: datapath.
- h193: 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.9474. Inputs: ctrl = nets w36; slice0 = nets w37; slice1 = nets w38. Role: datapath.
- h194: 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.9474. Inputs: ctrl = nets w39; slice0 = nets w40; slice1 = nets w41. Role: datapath.
- h195: 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.9474. Inputs: ctrl = nets w42; slice0 = nets w43; slice1 = nets w44. Role: datapath.
- h196: 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.9474. Inputs: ctrl = nets w45; slice0 = nets w46; slice1 = nets w47. Role: datapath.
- h197: 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.9474. Inputs: ctrl = nets w48; slice0 = nets w49; slice1 = nets w50. Role: datapath.
- h199: 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.9474. Inputs: ctrl = nets w54; slice0 = nets w55; slice1 = nets w59. Role: datapath.
- h200: 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.9474. Inputs: ctrl = nets w60; slice0 = nets w61; slice1 = nets w62. Role: datapath.
- h201: 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.9474. Inputs: ctrl = nets w63; slice0 = nets w64; slice1 = nets w65. Role: datapath.
- h202: 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.9474. Inputs: ctrl = nets w66; slice0 = nets w67; slice1 = nets w68. Role: datapath.
- h203: 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.9474. Inputs: ctrl = nets w69; slice0 = nets w70; slice1 = nets w71. Role: datapath.
- h204: 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.9474. Inputs: ctrl = nets w72; slice0 = nets w73; slice1 = nets w74. Role: datapath.
- h205: 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.9474. Inputs: ctrl = nets w75; slice0 = nets w76; slice1 = nets w77. Role: datapath.
- h206: 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.9474. Inputs: ctrl = nets w78; slice0 = nets w79; slice1 = nets w80. Role: datapath.
- h207: 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.9474. Inputs: ctrl = nets w81; slice0 = nets w82; slice1 = nets w83. Role: datapath.
- h208: 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.9474. Inputs: ctrl = nets w84; slice0 = nets w85; slice1 = nets w86. Role: datapath.
- h209: 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.9474. Inputs: ctrl = nets w87; slice0 = nets w88; slice1 = nets w89. Role: datapath.
- h210: 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.9474. Inputs: ctrl = nets w90; slice0 = nets w91; slice1 = nets w92. Role: datapath.
- h211: 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.9474. Inputs: ctrl = nets w93; slice0 = nets w94; slice1 = nets w95. Role: datapath.
- h212: 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.9474. Inputs: ctrl = nets w96; slice0 = nets w97; slice1 = nets w98. Role: datapath.
- h214: 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.9474. Inputs: ctrl = nets w102; slice0 = nets w103; slice1 = nets w109. Role: datapath.

## 5. Buses, state machines and roles

Buses:
- h34 (unconfirmed): 2 bits, bit order from wf: bit 0 = _064_; bit 1 = w2.
- h42 (unconfirmed): 2 bits, bit order from wf: bit 0 = _064_; bit 1 = w8.
- h43 (unconfirmed): 2 bits, bit order from wf: bit 0 = _064_; bit 1 = w11.
- h44 (unconfirmed): 2 bits, bit order from wf: bit 0 = _064_; bit 1 = w15.
- h45 (unconfirmed): 2 bits, bit order from wf: bit 0 = _064_; bit 1 = w21.
- h46 (unconfirmed): 2 bits, bit order from wf: bit 0 = _064_; bit 1 = w27.
- h47 (unconfirmed): 2 bits, bit order from wf: bit 0 = _064_; bit 1 = w30.
- h48 (unconfirmed): 2 bits, bit order from wf: bit 0 = _064_; bit 1 = w33.
- h49 (unconfirmed): 2 bits, bit order from wf: bit 0 = _064_; bit 1 = w36.
- h50 (unconfirmed): 2 bits, bit order from wf: bit 0 = _064_; bit 1 = w39.
- h51 (unconfirmed): 2 bits, bit order from wf: bit 0 = _064_; bit 1 = w42.
- h52 (unconfirmed): 2 bits, bit order from wf: bit 0 = _064_; bit 1 = w45.
- h53 (unconfirmed): 2 bits, bit order from wf: bit 0 = _064_; bit 1 = w48.
- h54 (unconfirmed): 2 bits, bit order from wf: bit 0 = _064_; bit 1 = w54.
- h55 (unconfirmed): 2 bits, bit order from wf: bit 0 = _064_; bit 1 = w60.
- h56 (unconfirmed): 2 bits, bit order from wf: bit 0 = _064_; bit 1 = w63.
- h57 (unconfirmed): 2 bits, bit order from wf: bit 0 = _064_; bit 1 = w66.
- h58 (unconfirmed): 2 bits, bit order from wf: bit 0 = _064_; bit 1 = w69.
- h59 (unconfirmed): 2 bits, bit order from wf: bit 0 = _064_; bit 1 = w72.
- h60 (unconfirmed): 2 bits, bit order from wf: bit 0 = _064_; bit 1 = w75.
- h61 (unconfirmed): 2 bits, bit order from wf: bit 0 = _064_; bit 1 = w78.
- h62 (unconfirmed): 2 bits, bit order from wf: bit 0 = _064_; bit 1 = w81.
- h63 (unconfirmed): 2 bits, bit order from wf: bit 0 = _064_; bit 1 = w84.
- h64 (unconfirmed): 2 bits, bit order from wf: bit 0 = _064_; bit 1 = w87.
- h65 (unconfirmed): 2 bits, bit order from wf: bit 0 = _064_; bit 1 = w90.
- h66 (unconfirmed): 2 bits, bit order from wf: bit 0 = _064_; bit 1 = w93.
- h67 (unconfirmed): 2 bits, bit order from wf: bit 0 = _064_; bit 1 = w96.
- h68 (unconfirmed): 2 bits, bit order from wf: bit 0 = _064_; bit 1 = w102.
- h69 (unconfirmed): 2 bits, bit order from wf: bit 0 = _064_; bit 1 = w107.
- h72 (unconfirmed): 2 bits, bit order from wf: bit 0 = w6; bit 1 = w108.
- h75 (unconfirmed): 2 bits, bit order from wf: bit 0 = w15; bit 1 = w18.
- h84 (unconfirmed): 2 bits, bit order from wf: bit 0 = w48; bit 1 = w51.
- h98 (unconfirmed): 2 bits, bit order from wf: bit 0 = w96; bit 1 = w99.
- h178 (unconfirmed): 27 bits, bit order from net_id: bit 0 = w1; bit 1 = _074_; bit 2 = _078_; bit 3 = _082_; bit 4 = _094_; bit 5 = _098_; bit 6 = _102_; bit 7 = _106_; bit 8 = _110_; bit 9 = _114_; bit 10 = _118_; bit 11 = _122_; bit 12 = _134_; bit 13 = _138_; bit 14 = _142_; bit 15 = _146_; bit 16 = _150_; bit 17 = _154_; bit 18 = _158_; bit 19 = _162_; bit 20 = _166_; bit 21 = _170_; bit 22 = _174_; bit 23 = _178_; bit 24 = _182_; bit 25 = _194_; bit 26 = w6.
- h179: 2 bits, bit order from net_id: bit 0 = w3; bit 1 = w10.
- h180: 29 bits, bit order from net_id: bit 0 = w3; bit 1 = w9; bit 2 = w12; bit 3 = w16; bit 4 = w22; bit 5 = w28; bit 6 = w31; bit 7 = w34; bit 8 = w37; bit 9 = w40; bit 10 = w43; bit 11 = w46; bit 12 = w49; bit 13 = w55; bit 14 = w61; bit 15 = w64; bit 16 = w67; bit 17 = w70; bit 18 = w73; bit 19 = w76; bit 20 = w79; bit 21 = w82; bit 22 = w85; bit 23 = w88; bit 24 = w91; bit 25 = w94; bit 26 = w97; bit 27 = w103; bit 28 = w108.
- h181: 7 bits, bit order from net_id: bit 0 = w5; bit 1 = w19; bit 2 = w24; bit 3 = w52; bit 4 = w57; bit 5 = w100; bit 6 = w105.
- h182 (unconfirmed): 4 bits, bit order from net_id: bit 0 = w7; bit 1 = w25; bit 2 = w58; bit 3 = w106.
- h183: 2 bits, bit order from net_id: bit 0 = w9; bit 1 = w13.
- h184: 28 bits, bit order from net_id: bit 0 = w10; bit 1 = w13; bit 2 = w14; bit 3 = w17; bit 4 = w26; bit 5 = w29; bit 6 = w32; bit 7 = w35; bit 8 = w38; bit 9 = w41; bit 10 = w44; bit 11 = w47; bit 12 = w50; bit 13 = w59; bit 14 = w62; bit 15 = w65; bit 16 = w68; bit 17 = w71; bit 18 = w74; bit 19 = w77; bit 20 = w80; bit 21 = w83; bit 22 = w86; bit 23 = w89; bit 24 = w92; bit 25 = w95; bit 26 = w98; bit 27 = w109.
- h185: 2 bits, bit order from net_id: bit 0 = w12; bit 1 = w14.
- h186: 2 bits, bit order from net_id: bit 0 = w16; bit 1 = w17.
- h187 (unconfirmed): 2 bits, bit order from net_id: bit 0 = w20; bit 1 = w25.
- h188 (unconfirmed): 3 bits, bit order from net_id: bit 0 = w20; bit 1 = w53; bit 2 = w101.
- h189: 2 bits, bit order from net_id: bit 0 = w22; bit 1 = w26.
- h190: 2 bits, bit order from net_id: bit 0 = w28; bit 1 = w29.
- h191: 2 bits, bit order from net_id: bit 0 = w31; bit 1 = w32.
- h192: 2 bits, bit order from net_id: bit 0 = w34; bit 1 = w35.
- h193: 2 bits, bit order from net_id: bit 0 = w37; bit 1 = w38.
- h194: 2 bits, bit order from net_id: bit 0 = w40; bit 1 = w41.
- h195: 2 bits, bit order from net_id: bit 0 = w43; bit 1 = w44.
- h196: 2 bits, bit order from net_id: bit 0 = w46; bit 1 = w47.
- h197: 2 bits, bit order from net_id: bit 0 = w49; bit 1 = w50.
- h198 (unconfirmed): 2 bits, bit order from net_id: bit 0 = w53; bit 1 = w58.
- h199: 2 bits, bit order from net_id: bit 0 = w55; bit 1 = w59.
- h200: 2 bits, bit order from net_id: bit 0 = w61; bit 1 = w62.
- h201: 2 bits, bit order from net_id: bit 0 = w64; bit 1 = w65.
- h202: 2 bits, bit order from net_id: bit 0 = w67; bit 1 = w68.
- h203: 2 bits, bit order from net_id: bit 0 = w70; bit 1 = w71.
- h204: 2 bits, bit order from net_id: bit 0 = w73; bit 1 = w74.
- h205: 2 bits, bit order from net_id: bit 0 = w76; bit 1 = w77.
- h206: 2 bits, bit order from net_id: bit 0 = w79; bit 1 = w80.
- h207: 2 bits, bit order from net_id: bit 0 = w82; bit 1 = w83.
- h208: 2 bits, bit order from net_id: bit 0 = w85; bit 1 = w86.
- h209: 2 bits, bit order from net_id: bit 0 = w88; bit 1 = w89.
- h210: 2 bits, bit order from net_id: bit 0 = w91; bit 1 = w92.
- h211: 2 bits, bit order from net_id: bit 0 = w94; bit 1 = w95.
- h212: 2 bits, bit order from net_id: bit 0 = w97; bit 1 = w98.
- h213 (unconfirmed): 2 bits, bit order from net_id: bit 0 = w101; bit 1 = w106.
- h214: 2 bits, bit order from net_id: bit 0 = w103; bit 1 = w109.
- h417 (unconfirmed): 2 bits, bit order from wf: bit 0 = _070_; bit 1 = _067_.
- h467 (unconfirmed): 2 bits, bit order from wf: bit 0 = w8; bit 1 = w2.
- h468 (unconfirmed): 2 bits, bit order from wf: bit 0 = w11; bit 1 = w8.
- h469 (unconfirmed): 2 bits, bit order from wf: bit 0 = w15; bit 1 = w11.
- h470 (unconfirmed): 2 bits, bit order from wf: bit 0 = w27; bit 1 = w21.
- h471 (unconfirmed): 2 bits, bit order from wf: bit 0 = w30; bit 1 = w27.
- h472 (unconfirmed): 2 bits, bit order from wf: bit 0 = w33; bit 1 = w30.
- h473 (unconfirmed): 2 bits, bit order from wf: bit 0 = w36; bit 1 = w33.
- h474 (unconfirmed): 2 bits, bit order from wf: bit 0 = w39; bit 1 = w36.
- h475 (unconfirmed): 2 bits, bit order from wf: bit 0 = w42; bit 1 = w39.
- h476 (unconfirmed): 2 bits, bit order from wf: bit 0 = w45; bit 1 = w42.
- h477 (unconfirmed): 2 bits, bit order from wf: bit 0 = w48; bit 1 = w45.
- h478 (unconfirmed): 2 bits, bit order from wf: bit 0 = w60; bit 1 = w54.
- h479 (unconfirmed): 2 bits, bit order from wf: bit 0 = w63; bit 1 = w60.
- h480 (unconfirmed): 2 bits, bit order from wf: bit 0 = w66; bit 1 = w63.
- h481 (unconfirmed): 2 bits, bit order from wf: bit 0 = w69; bit 1 = w66.
- h482 (unconfirmed): 2 bits, bit order from wf: bit 0 = w72; bit 1 = w69.
- h483 (unconfirmed): 2 bits, bit order from wf: bit 0 = w75; bit 1 = w72.
- h484 (unconfirmed): 2 bits, bit order from wf: bit 0 = w78; bit 1 = w75.
- h485 (unconfirmed): 2 bits, bit order from wf: bit 0 = w81; bit 1 = w78.
- h486 (unconfirmed): 2 bits, bit order from wf: bit 0 = w84; bit 1 = w81.
- h487 (unconfirmed): 2 bits, bit order from wf: bit 0 = w87; bit 1 = w84.
- h488 (unconfirmed): 2 bits, bit order from wf: bit 0 = w90; bit 1 = w87.
- h489 (unconfirmed): 2 bits, bit order from wf: bit 0 = w93; bit 1 = w90.
- h490 (unconfirmed): 2 bits, bit order from wf: bit 0 = w96; bit 1 = w93.
- h491 (unconfirmed): 2 bits, bit order from wf: bit 0 = w107; bit 1 = w102.
- h1156 (unconfirmed): 25 bits, bit order from net_id: bit 0 = _074_; bit 1 = _078_; bit 2 = _082_; bit 3 = _094_; bit 4 = _098_; bit 5 = _102_; bit 6 = _106_; bit 7 = _110_; bit 8 = _114_; bit 9 = _118_; bit 10 = _122_; bit 11 = _134_; bit 12 = _138_; bit 13 = _142_; bit 14 = _146_; bit 15 = _150_; bit 16 = _154_; bit 17 = _158_; bit 18 = _162_; bit 19 = _166_; bit 20 = _170_; bit 21 = _174_; bit 22 = _178_; bit 23 = _182_; bit 24 = _194_.
- h1158 (unconfirmed): 2 bits, bit order from wf: bit 0 = _070_; bit 1 = w4.
- h1160 (unconfirmed): 2 bits, bit order from wf: bit 0 = w2; bit 1 = _065_.
- h1173 (unconfirmed): 3 bits, bit order from net_id: bit 0 = w25; bit 1 = w58; bit 2 = w106.

State machines: none.

Roles of committed claims: datapath: h71, h73, h74, h76, h77, h78, h79, h80, h81, h82, h83, h85, h86, h87, h88, h89, h90, h91, h92, h93, h94, h95, h96, h97, h99, h100, h101, h135, h179, h180, h181, h183, h184, h185, h186, h189, h190, h191, h192, h193, h194, h195, h196, h197, h199, h200, h201, h202, h203, h204, h205, h206, h207, h208, h209, h210, h211, h212, h214, h522.

## 6. Candidates (not committed, unconfirmed)

- h178 (unconfirmed): 27 cells form a 27-bit bus, `bus: 27 bits`. No proof recorded. Confidence 0.8006. Inputs: ctrl = nets train_mispredicted; slice0 = nets w1; slice1 = nets _074_; slice10 = nets _118_; slice11 = nets _122_; slice12 = nets _134_; slice13 = nets _138_; slice14 = nets _142_; slice15 = nets _146_; slice16 = nets _150_; slice17 = nets _154_; slice18 = nets _158_; slice19 = nets _162_; slice2 = nets _078_; slice20 = nets _166_; slice21 = nets _170_; slice22 = nets _174_; slice23 = nets _178_; slice24 = nets _182_; slice25 = nets _194_; slice26 = nets w6; slice3 = nets _082_; slice4 = nets _094_; slice5 = nets _098_; slice6 = nets _102_; slice7 = nets _106_; slice8 = nets _110_; slice9 = nets _114_. Role: datapath.
- h1156 (unconfirmed): 25 cells form a 25-bit bus, `bus: 25 bits`. No proof recorded. Confidence 0.8006. Inputs: ctrl = nets train_mispredicted; slice0 = nets _074_; slice1 = nets _078_; slice10 = nets _122_; slice11 = nets _134_; slice12 = nets _138_; slice13 = nets _142_; slice14 = nets _146_; slice15 = nets _150_; slice16 = nets _154_; slice17 = nets _158_; slice18 = nets _162_; slice19 = nets _166_; slice2 = nets _082_; slice20 = nets _170_; slice21 = nets _174_; slice22 = nets _178_; slice23 = nets _182_; slice24 = nets _194_; slice3 = nets _094_; slice4 = nets _098_; slice5 = nets _102_; slice6 = nets _106_; slice7 = nets _110_; slice8 = nets _114_; slice9 = nets _118_. Role: datapath.
- h188 (unconfirmed): 3 cells form a 3-bit bus, `bus: 3 bits`. No proof recorded. Confidence 0.7503. Inputs: ctrl = nets w1; slice0 = nets w20; slice1 = nets w53; slice2 = nets w101. Role: datapath.
- h1173 (unconfirmed): 3 cells form a 3-bit bus, `bus: 3 bits`. No proof recorded. Confidence 0.7503. Inputs: ctrl = nets w6; slice0 = nets w25; slice1 = nets w58; slice2 = nets w106. Role: datapath.
- h187 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.6942. Inputs: ctrl = nets predict_history[4]; slice0 = nets w20; slice1 = nets w25. Role: datapath.
- h198 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.6942. Inputs: ctrl = nets predict_history[14]; slice0 = nets w53; slice1 = nets w58. Role: datapath.
- h213 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.6942. Inputs: ctrl = nets predict_history[29]; slice0 = nets w101; slice1 = nets w106. Role: datapath.
- h34 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.6011. Inputs: slice0 = nets _064_; slice1 = nets w2. Role: datapath.
- h42 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.6011. Inputs: slice0 = nets _064_; slice1 = nets w8. Role: datapath.
- h43 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.6011. Inputs: slice0 = nets _064_; slice1 = nets w11. Role: datapath.
- h44 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.6011. Inputs: slice0 = nets _064_; slice1 = nets w15. Role: datapath.
- h45 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.6011. Inputs: slice0 = nets _064_; slice1 = nets w21. Role: datapath.
- h46 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.6011. Inputs: slice0 = nets _064_; slice1 = nets w27. Role: datapath.
- h47 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.6011. Inputs: slice0 = nets _064_; slice1 = nets w30. Role: datapath.
- h48 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.6011. Inputs: slice0 = nets _064_; slice1 = nets w33. Role: datapath.
- h49 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.6011. Inputs: slice0 = nets _064_; slice1 = nets w36. Role: datapath.
- h50 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.6011. Inputs: slice0 = nets _064_; slice1 = nets w39. Role: datapath.
- h51 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.6011. Inputs: slice0 = nets _064_; slice1 = nets w42. Role: datapath.
- h52 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.6011. Inputs: slice0 = nets _064_; slice1 = nets w45. Role: datapath.
- h53 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.6011. Inputs: slice0 = nets _064_; slice1 = nets w48. Role: datapath.
- h54 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.6011. Inputs: slice0 = nets _064_; slice1 = nets w54. Role: datapath.
- h55 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.6011. Inputs: slice0 = nets _064_; slice1 = nets w60. Role: datapath.
- h56 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.6011. Inputs: slice0 = nets _064_; slice1 = nets w63. Role: datapath.
- h57 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.6011. Inputs: slice0 = nets _064_; slice1 = nets w66. Role: datapath.
- h58 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.6011. Inputs: slice0 = nets _064_; slice1 = nets w69. Role: datapath.
- h59 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.6011. Inputs: slice0 = nets _064_; slice1 = nets w72. Role: datapath.
- h60 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.6011. Inputs: slice0 = nets _064_; slice1 = nets w75. Role: datapath.
- h61 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.6011. Inputs: slice0 = nets _064_; slice1 = nets w78. Role: datapath.
- h62 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.6011. Inputs: slice0 = nets _064_; slice1 = nets w81. Role: datapath.
- h63 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.6011. Inputs: slice0 = nets _064_; slice1 = nets w84. Role: datapath.
- h64 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.6011. Inputs: slice0 = nets _064_; slice1 = nets w87. Role: datapath.
- h65 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.6011. Inputs: slice0 = nets _064_; slice1 = nets w90. Role: datapath.
- h66 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.6011. Inputs: slice0 = nets _064_; slice1 = nets w93. Role: datapath.
- h67 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.6011. Inputs: slice0 = nets _064_; slice1 = nets w96. Role: datapath.
- h68 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.6011. Inputs: slice0 = nets _064_; slice1 = nets w102. Role: datapath.
- h69 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.6011. Inputs: slice0 = nets _064_; slice1 = nets w107. Role: datapath.
- h72 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.6011. Inputs: slice0 = nets w6; slice1 = nets w108. Role: datapath.
- h75 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.6011. Inputs: slice0 = nets w15; slice1 = nets w18. Role: datapath.
- h84 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.6011. Inputs: slice0 = nets w48; slice1 = nets w51. Role: datapath.
- h98 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.6011. Inputs: slice0 = nets w96; slice1 = nets w99. Role: datapath.
- h417 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.6011. Inputs: slice0 = nets _070_; slice1 = nets _067_. Role: datapath.
- h467 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.6011. Inputs: slice0 = nets w8; slice1 = nets w2. Role: datapath.
- h468 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.6011. Inputs: slice0 = nets w11; slice1 = nets w8. Role: datapath.
- h469 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.6011. Inputs: slice0 = nets w15; slice1 = nets w11. Role: datapath.
- h470 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.6011. Inputs: slice0 = nets w27; slice1 = nets w21. Role: datapath.
- h471 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.6011. Inputs: slice0 = nets w30; slice1 = nets w27. Role: datapath.
- h472 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.6011. Inputs: slice0 = nets w33; slice1 = nets w30. Role: datapath.
- h473 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.6011. Inputs: slice0 = nets w36; slice1 = nets w33. Role: datapath.
- h474 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.6011. Inputs: slice0 = nets w39; slice1 = nets w36. Role: datapath.
- h475 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.6011. Inputs: slice0 = nets w42; slice1 = nets w39. Role: datapath.
- h476 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.6011. Inputs: slice0 = nets w45; slice1 = nets w42. Role: datapath.
- h477 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.6011. Inputs: slice0 = nets w48; slice1 = nets w45. Role: datapath.
- h478 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.6011. Inputs: slice0 = nets w60; slice1 = nets w54. Role: datapath.
- h479 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.6011. Inputs: slice0 = nets w63; slice1 = nets w60. Role: datapath.
- h480 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.6011. Inputs: slice0 = nets w66; slice1 = nets w63. Role: datapath.
- h481 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.6011. Inputs: slice0 = nets w69; slice1 = nets w66. Role: datapath.
- h482 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.6011. Inputs: slice0 = nets w72; slice1 = nets w69. Role: datapath.
- h483 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.6011. Inputs: slice0 = nets w75; slice1 = nets w72. Role: datapath.
- h484 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.6011. Inputs: slice0 = nets w78; slice1 = nets w75. Role: datapath.
- h485 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.6011. Inputs: slice0 = nets w81; slice1 = nets w78. Role: datapath.
- h486 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.6011. Inputs: slice0 = nets w84; slice1 = nets w81. Role: datapath.
- h487 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.6011. Inputs: slice0 = nets w87; slice1 = nets w84. Role: datapath.
- h488 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.6011. Inputs: slice0 = nets w90; slice1 = nets w87. Role: datapath.
- h489 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.6011. Inputs: slice0 = nets w93; slice1 = nets w90. Role: datapath.
- h490 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.6011. Inputs: slice0 = nets w96; slice1 = nets w93. Role: datapath.
- h491 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.6011. Inputs: slice0 = nets w107; slice1 = nets w102. Role: datapath.
- h1158 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.6011. Inputs: slice0 = nets _070_; slice1 = nets w4. Role: datapath.
- h1160 (unconfirmed): 2 cells form a 2-bit bus, `bus: 2 bits`. No proof recorded. Confidence 0.6011. Inputs: slice0 = nets w2; slice1 = nets _065_. Role: datapath.
- h182 (unconfirmed): 4 cells form a 4-bit bus, `bus: 4 bits`. No proof recorded. Confidence 0.5000. Inputs: ctrl = nets w6; slice0 = nets w7; slice1 = nets w25; slice2 = nets w58; slice3 = nets w106. Role: datapath.

## 7. Rejected claims

- h2: Loki tested a 2-bit adder with carry-in (`Y = A + B + CI`) on 12 cells and the proof showed it differs (truth_table), counterexample A[0]=0,A[1]=0,B[0]=0,B[1]=0,CI=0.
- h622: Loki proposed a comparison against a constant (`Y = (A != 3)`) on 1 cell; rejected: commit failed: ODIN3_ERR_INVALID_ARG.
- h623: Loki proposed a comparison against a constant (`Y = (A != 3)`) on 1 cell; rejected: commit failed: ODIN3_ERR_INVALID_ARG.
- h816: Loki proposed a comparison against a constant (`Y = (A != 3)`) on 1 cell; rejected: commit failed: ODIN3_ERR_INVALID_ARG.
- h817: Loki proposed a comparison against a constant (`Y = (A != 3)`) on 1 cell; rejected: commit failed: ODIN3_ERR_INVALID_ARG.
- h1130: Loki proposed a comparison against a constant (`Y = (A != 3)`) on 1 cell; rejected: commit failed: ODIN3_ERR_INVALID_ARG.
- h1131: Loki proposed a comparison against a constant (`Y = (A != 3)`) on 1 cell; rejected: commit failed: ODIN3_ERR_INVALID_ARG.
- h1174: Loki proposed a datapath unit (`datapath_unit: 67 bits`) on 194 cells; rejected: commit failed: ODIN3_ERR_INVALID_ARG.

## 9. What Loki does NOT claim

- Candidates and rejected claims are not statements of fact.
- Module names such as `adder_h1` are Loki's labels built from the kind and the id; they are not the original HDL names, which Loki does not know.

## Helper nets

These nets have no wire of their own in the netlist. Each is defined from netlist wires or other helper nets.

- w1 = AND(NOT(train_mispredicted), NOT(predict_valid))
- w2 = NOT(predict_history[0])
- w3 = AND(NOT(_070_), NOT(w2))
- w4 = NOT(train_taken)
- w5 = AND(NOT(w4), NOT(_065_))
- w6 = AND(NOT(train_mispredicted), NOT(_064_))
- w7 = OR(NOT(predict_taken), NOT(w6))
- w8 = NOT(predict_history[1])
- w9 = AND(NOT(_070_), NOT(w8))
- w10 = AND(NOT(_067_), NOT(w2))
- w11 = NOT(predict_history[2])
- w12 = AND(NOT(_070_), NOT(w11))
- w13 = AND(NOT(_067_), NOT(w8))
- w14 = AND(NOT(_067_), NOT(w11))
- w15 = NOT(predict_history[3])
- w16 = AND(NOT(_070_), NOT(w15))
- w17 = AND(NOT(_067_), NOT(w15))
- w18 = NOT(train_history[3])
- w19 = AND(NOT(w18), NOT(_065_))
- w20 = OR(NOT(predict_history[4]), NOT(w1))
- w21 = NOT(predict_history[5])
- w22 = AND(NOT(_070_), NOT(w21))
- w23 = NOT(train_history[4])
- w24 = AND(NOT(w23), NOT(_065_))
- w25 = OR(NOT(predict_history[4]), NOT(w6))
- w26 = AND(NOT(_067_), NOT(w21))
- w27 = NOT(predict_history[6])
- w28 = AND(NOT(_070_), NOT(w27))
- w29 = AND(NOT(_067_), NOT(w27))
- w30 = NOT(predict_history[7])
- w31 = AND(NOT(_070_), NOT(w30))
- w32 = AND(NOT(_067_), NOT(w30))
- w33 = NOT(predict_history[8])
- w34 = AND(NOT(_070_), NOT(w33))
- w35 = AND(NOT(_067_), NOT(w33))
- w36 = NOT(predict_history[9])
- w37 = AND(NOT(_070_), NOT(w36))
- w38 = AND(NOT(_067_), NOT(w36))
- w39 = NOT(predict_history[10])
- w40 = AND(NOT(_070_), NOT(w39))
- w41 = AND(NOT(_067_), NOT(w39))
- w42 = NOT(predict_history[11])
- w43 = AND(NOT(_070_), NOT(w42))
- w44 = AND(NOT(_067_), NOT(w42))
- w45 = NOT(predict_history[12])
- w46 = AND(NOT(_070_), NOT(w45))
- w47 = AND(NOT(_067_), NOT(w45))
- w48 = NOT(predict_history[13])
- w49 = AND(NOT(_070_), NOT(w48))
- w50 = AND(NOT(_067_), NOT(w48))
- w51 = NOT(train_history[13])
- w52 = AND(NOT(w51), NOT(_065_))
- w53 = OR(NOT(predict_history[14]), NOT(w1))
- w54 = NOT(predict_history[15])
- w55 = AND(NOT(_070_), NOT(w54))
- w56 = NOT(train_history[14])
- w57 = AND(NOT(w56), NOT(_065_))
- w58 = OR(NOT(predict_history[14]), NOT(w6))
- w59 = AND(NOT(_067_), NOT(w54))
- w60 = NOT(predict_history[16])
- w61 = AND(NOT(_070_), NOT(w60))
- w62 = AND(NOT(_067_), NOT(w60))
- w63 = NOT(predict_history[17])
- w64 = AND(NOT(_070_), NOT(w63))
- w65 = AND(NOT(_067_), NOT(w63))
- w66 = NOT(predict_history[18])
- w67 = AND(NOT(_070_), NOT(w66))
- w68 = AND(NOT(_067_), NOT(w66))
- w69 = NOT(predict_history[19])
- w70 = AND(NOT(_070_), NOT(w69))
- w71 = AND(NOT(_067_), NOT(w69))
- w72 = NOT(predict_history[20])
- w73 = AND(NOT(_070_), NOT(w72))
- w74 = AND(NOT(_067_), NOT(w72))
- w75 = NOT(predict_history[21])
- w76 = AND(NOT(_070_), NOT(w75))
- w77 = AND(NOT(_067_), NOT(w75))
- w78 = NOT(predict_history[22])
- w79 = AND(NOT(_070_), NOT(w78))
- w80 = AND(NOT(_067_), NOT(w78))
- w81 = NOT(predict_history[23])
- w82 = AND(NOT(_070_), NOT(w81))
- w83 = AND(NOT(_067_), NOT(w81))
- w84 = NOT(predict_history[24])
- w85 = AND(NOT(_070_), NOT(w84))
- w86 = AND(NOT(_067_), NOT(w84))
- w87 = NOT(predict_history[25])
- w88 = AND(NOT(_070_), NOT(w87))
- w89 = AND(NOT(_067_), NOT(w87))
- w90 = NOT(predict_history[26])
- w91 = AND(NOT(_070_), NOT(w90))
- w92 = AND(NOT(_067_), NOT(w90))
- w93 = NOT(predict_history[27])
- w94 = AND(NOT(_070_), NOT(w93))
- w95 = AND(NOT(_067_), NOT(w93))
- w96 = NOT(predict_history[28])
- w97 = AND(NOT(_070_), NOT(w96))
- w98 = AND(NOT(_067_), NOT(w96))
- w99 = NOT(train_history[28])
- w100 = AND(NOT(w99), NOT(_065_))
- w101 = OR(NOT(predict_history[29]), NOT(w1))
- w102 = NOT(predict_history[30])
- w103 = AND(NOT(_070_), NOT(w102))
- w104 = NOT(train_history[29])
- w105 = AND(NOT(w104), NOT(_065_))
- w106 = OR(NOT(predict_history[29]), NOT(w6))
- w107 = NOT(predict_history[31])
- w108 = AND(NOT(_070_), NOT(w107))
- w109 = AND(NOT(_067_), NOT(w102))
[LOKI-HINTS-END]
Designer prior: designers write RTL from familiar patterns. If a signal looks like a condition, it
probably is one; if a register group looks like an FSM, it probably is one.
