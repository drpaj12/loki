Loki structural hints for the netlist above. Loki is a netlist analysis program (no language model).
Its output follows between the markers. The worked examples above did not carry hints.
Net names in the hints are wires and ports of the netlist above, except the names w1, w2, ...:
those are helper nets that have no wire of their own; each is defined in the list of helper nets
at the end of the hints, in terms of netlist wires or other helper nets.
[LOKI-HINTS-BEGIN]
# Loki analysis of a gate netlist

## 1. What this is

Loki III analysed the gate-level netlist `netlist.v` (sha256 a99646085625, floor f3).
The list below holds Loki's claims about its higher-level structure.
Each claim has a confidence (a probability) and a proof status.
Trust order: proved or derived claims, then unproven claims with high confidence, then candidates.
Committed claims have confidence of at least 0.9; candidates are listed from 0.5 and are unconfirmed.

## 3. Summary

| kind | committed | candidate | rejected |
| --- | --- | --- | --- |
| bus | 4 | 0 | 0 |
| ff_en | 0 | 64 | 0 |
| ff_srst | 0 | 33 | 0 |
| register | 0 | 1 | 0 |

Input cells (in Loki's re-mapped netlist): 192.

Of the committed cells, 128 (in 4 claims) are marked only by attributes on existing cells (form attrs). Those claims are not modules, so the hierarchy below does not show them.

Recovered module hierarchy (a module contains its children):

(no committed modules)

## 4. Committed claims

- h4: 32 cells form a 32-bit bus, `bus: 32 bits`. No proof recorded. Confidence 0.9234. Inputs: slice0 = nets _032_; slice1 = nets _033_; slice10 = nets _042_; slice11 = nets _043_; slice12 = nets _044_; slice13 = nets _045_; slice14 = nets _046_; slice15 = nets _047_; slice16 = nets _048_; slice17 = nets _049_; slice18 = nets _050_; slice19 = nets _051_; slice2 = nets _034_; slice20 = nets _052_; slice21 = nets _053_; slice22 = nets _054_; slice23 = nets _055_; slice24 = nets _056_; slice25 = nets _057_; slice26 = nets _058_; slice27 = nets _059_; slice28 = nets _060_; slice29 = nets _061_; slice3 = nets _035_; slice30 = nets _062_; slice31 = nets _063_; slice4 = nets _036_; slice5 = nets _037_; slice6 = nets _038_; slice7 = nets _039_; slice8 = nets _040_; slice9 = nets _041_. Role: datapath.
- h6: 32 cells form a 32-bit bus, `bus: 32 bits`. No proof recorded. Confidence 0.9234. Inputs: slice0 = nets _064_; slice1 = nets _066_; slice10 = nets _084_; slice11 = nets _086_; slice12 = nets _088_; slice13 = nets _090_; slice14 = nets _092_; slice15 = nets _094_; slice16 = nets _096_; slice17 = nets _098_; slice18 = nets _100_; slice19 = nets _102_; slice2 = nets _068_; slice20 = nets _104_; slice21 = nets _106_; slice22 = nets _108_; slice23 = nets _110_; slice24 = nets _112_; slice25 = nets _114_; slice26 = nets _116_; slice27 = nets _118_; slice28 = nets _120_; slice29 = nets _122_; slice3 = nets _070_; slice30 = nets _124_; slice31 = nets _126_; slice4 = nets _072_; slice5 = nets _074_; slice6 = nets _076_; slice7 = nets _078_; slice8 = nets _080_; slice9 = nets _082_. Role: datapath.
- h7: 32 cells form a 32-bit bus, `bus: 32 bits`. No proof recorded. Confidence 0.9234. Inputs: slice0 = nets _065_; slice1 = nets _067_; slice10 = nets _085_; slice11 = nets _087_; slice12 = nets _089_; slice13 = nets _091_; slice14 = nets _093_; slice15 = nets _095_; slice16 = nets _097_; slice17 = nets _099_; slice18 = nets _101_; slice19 = nets _103_; slice2 = nets _069_; slice20 = nets _105_; slice21 = nets _107_; slice22 = nets _109_; slice23 = nets _111_; slice24 = nets _113_; slice25 = nets _115_; slice26 = nets _117_; slice27 = nets _119_; slice28 = nets _121_; slice29 = nets _123_; slice3 = nets _071_; slice30 = nets _125_; slice31 = nets _127_; slice4 = nets _073_; slice5 = nets _075_; slice6 = nets _077_; slice7 = nets _079_; slice8 = nets _081_; slice9 = nets _083_. Role: datapath.
- h167: 32 cells form a 32-bit bus, `bus: 32 bits`. No proof recorded. Confidence 0.9954. Inputs: ctrl = nets reset; slice0 = nets _000_; slice1 = nets _001_; slice10 = nets _010_; slice11 = nets _011_; slice12 = nets _012_; slice13 = nets _013_; slice14 = nets _014_; slice15 = nets _015_; slice16 = nets _016_; slice17 = nets _017_; slice18 = nets _018_; slice19 = nets _019_; slice2 = nets _002_; slice20 = nets _020_; slice21 = nets _021_; slice22 = nets _022_; slice23 = nets _023_; slice24 = nets _024_; slice25 = nets _025_; slice26 = nets _026_; slice27 = nets _027_; slice28 = nets _028_; slice29 = nets _029_; slice3 = nets _003_; slice30 = nets _030_; slice31 = nets _031_; slice4 = nets _004_; slice5 = nets _005_; slice6 = nets _006_; slice7 = nets _007_; slice8 = nets _008_; slice9 = nets _009_. Role: datapath.

## 5. Buses, state machines and roles

Buses:
- h4: 32 bits, bit order from wf: bit 0 = _032_; bit 1 = _033_; bit 2 = _034_; bit 3 = _035_; bit 4 = _036_; bit 5 = _037_; bit 6 = _038_; bit 7 = _039_; bit 8 = _040_; bit 9 = _041_; bit 10 = _042_; bit 11 = _043_; bit 12 = _044_; bit 13 = _045_; bit 14 = _046_; bit 15 = _047_; bit 16 = _048_; bit 17 = _049_; bit 18 = _050_; bit 19 = _051_; bit 20 = _052_; bit 21 = _053_; bit 22 = _054_; bit 23 = _055_; bit 24 = _056_; bit 25 = _057_; bit 26 = _058_; bit 27 = _059_; bit 28 = _060_; bit 29 = _061_; bit 30 = _062_; bit 31 = _063_.
- h6: 32 bits, bit order from wf: bit 0 = _064_; bit 1 = _066_; bit 2 = _068_; bit 3 = _070_; bit 4 = _072_; bit 5 = _074_; bit 6 = _076_; bit 7 = _078_; bit 8 = _080_; bit 9 = _082_; bit 10 = _084_; bit 11 = _086_; bit 12 = _088_; bit 13 = _090_; bit 14 = _092_; bit 15 = _094_; bit 16 = _096_; bit 17 = _098_; bit 18 = _100_; bit 19 = _102_; bit 20 = _104_; bit 21 = _106_; bit 22 = _108_; bit 23 = _110_; bit 24 = _112_; bit 25 = _114_; bit 26 = _116_; bit 27 = _118_; bit 28 = _120_; bit 29 = _122_; bit 30 = _124_; bit 31 = _126_.
- h7: 32 bits, bit order from wf: bit 0 = _065_; bit 1 = _067_; bit 2 = _069_; bit 3 = _071_; bit 4 = _073_; bit 5 = _075_; bit 6 = _077_; bit 7 = _079_; bit 8 = _081_; bit 9 = _083_; bit 10 = _085_; bit 11 = _087_; bit 12 = _089_; bit 13 = _091_; bit 14 = _093_; bit 15 = _095_; bit 16 = _097_; bit 17 = _099_; bit 18 = _101_; bit 19 = _103_; bit 20 = _105_; bit 21 = _107_; bit 22 = _109_; bit 23 = _111_; bit 24 = _113_; bit 25 = _115_; bit 26 = _117_; bit 27 = _119_; bit 28 = _121_; bit 29 = _123_; bit 30 = _125_; bit 31 = _127_.
- h167: 32 bits, bit order from net_id: bit 0 = _000_; bit 1 = _001_; bit 2 = _002_; bit 3 = _003_; bit 4 = _004_; bit 5 = _005_; bit 6 = _006_; bit 7 = _007_; bit 8 = _008_; bit 9 = _009_; bit 10 = _010_; bit 11 = _011_; bit 12 = _012_; bit 13 = _013_; bit 14 = _014_; bit 15 = _015_; bit 16 = _016_; bit 17 = _017_; bit 18 = _018_; bit 19 = _019_; bit 20 = _020_; bit 21 = _021_; bit 22 = _022_; bit 23 = _023_; bit 24 = _024_; bit 25 = _025_; bit 26 = _026_; bit 27 = _027_; bit 28 = _028_; bit 29 = _029_; bit 30 = _030_; bit 31 = _031_.

State machines: none.

Roles of committed claims: datapath: h4, h6, h7, h167.

## 6. Candidates (not committed, unconfirmed)

- h39 (unconfirmed): 4 cells form a flip-flop with enable, `ff_en: 1 bits`. No proof recorded. Confidence 0.9901. Inputs: d = nets _000_; en = nets _032_. Outputs: q = nets out[0]. Role: datapath.
- h40 (unconfirmed): 4 cells form a flip-flop with enable, `ff_en: 1 bits`. No proof recorded. Confidence 0.9901. Inputs: d = nets _000_; en = nets in[0]. Outputs: q = nets out[0]. Role: datapath.
- h42 (unconfirmed): 4 cells form a flip-flop with enable, `ff_en: 1 bits`. No proof recorded. Confidence 0.9901. Inputs: d = nets _001_; en = nets _033_. Outputs: q = nets out[1]. Role: datapath.
- h43 (unconfirmed): 4 cells form a flip-flop with enable, `ff_en: 1 bits`. No proof recorded. Confidence 0.9901. Inputs: d = nets _001_; en = nets in[1]. Outputs: q = nets out[1]. Role: datapath.
- h45 (unconfirmed): 4 cells form a flip-flop with enable, `ff_en: 1 bits`. No proof recorded. Confidence 0.9901. Inputs: d = nets _002_; en = nets _034_. Outputs: q = nets out[2]. Role: datapath.
- h46 (unconfirmed): 4 cells form a flip-flop with enable, `ff_en: 1 bits`. No proof recorded. Confidence 0.9901. Inputs: d = nets _002_; en = nets in[2]. Outputs: q = nets out[2]. Role: datapath.
- h48 (unconfirmed): 4 cells form a flip-flop with enable, `ff_en: 1 bits`. No proof recorded. Confidence 0.9901. Inputs: d = nets _003_; en = nets _035_. Outputs: q = nets out[3]. Role: datapath.
- h49 (unconfirmed): 4 cells form a flip-flop with enable, `ff_en: 1 bits`. No proof recorded. Confidence 0.9901. Inputs: d = nets _003_; en = nets in[3]. Outputs: q = nets out[3]. Role: datapath.
- h51 (unconfirmed): 4 cells form a flip-flop with enable, `ff_en: 1 bits`. No proof recorded. Confidence 0.9901. Inputs: d = nets _004_; en = nets _036_. Outputs: q = nets out[4]. Role: datapath.
- h52 (unconfirmed): 4 cells form a flip-flop with enable, `ff_en: 1 bits`. No proof recorded. Confidence 0.9901. Inputs: d = nets _004_; en = nets in[4]. Outputs: q = nets out[4]. Role: datapath.
- h54 (unconfirmed): 4 cells form a flip-flop with enable, `ff_en: 1 bits`. No proof recorded. Confidence 0.9901. Inputs: d = nets _005_; en = nets _037_. Outputs: q = nets out[5]. Role: datapath.
- h55 (unconfirmed): 4 cells form a flip-flop with enable, `ff_en: 1 bits`. No proof recorded. Confidence 0.9901. Inputs: d = nets _005_; en = nets in[5]. Outputs: q = nets out[5]. Role: datapath.
- h57 (unconfirmed): 4 cells form a flip-flop with enable, `ff_en: 1 bits`. No proof recorded. Confidence 0.9901. Inputs: d = nets _006_; en = nets _038_. Outputs: q = nets out[6]. Role: datapath.
- h58 (unconfirmed): 4 cells form a flip-flop with enable, `ff_en: 1 bits`. No proof recorded. Confidence 0.9901. Inputs: d = nets _006_; en = nets in[6]. Outputs: q = nets out[6]. Role: datapath.
- h60 (unconfirmed): 4 cells form a flip-flop with enable, `ff_en: 1 bits`. No proof recorded. Confidence 0.9901. Inputs: d = nets _007_; en = nets in[7]. Outputs: q = nets out[7]. Role: datapath.
- h61 (unconfirmed): 4 cells form a flip-flop with enable, `ff_en: 1 bits`. No proof recorded. Confidence 0.9901. Inputs: d = nets _007_; en = nets _039_. Outputs: q = nets out[7]. Role: datapath.
- h63 (unconfirmed): 4 cells form a flip-flop with enable, `ff_en: 1 bits`. No proof recorded. Confidence 0.9901. Inputs: d = nets _008_; en = nets in[8]. Outputs: q = nets out[8]. Role: datapath.
- h64 (unconfirmed): 4 cells form a flip-flop with enable, `ff_en: 1 bits`. No proof recorded. Confidence 0.9901. Inputs: d = nets _008_; en = nets _040_. Outputs: q = nets out[8]. Role: datapath.
- h66 (unconfirmed): 4 cells form a flip-flop with enable, `ff_en: 1 bits`. No proof recorded. Confidence 0.9901. Inputs: d = nets _009_; en = nets in[9]. Outputs: q = nets out[9]. Role: datapath.
- h67 (unconfirmed): 4 cells form a flip-flop with enable, `ff_en: 1 bits`. No proof recorded. Confidence 0.9901. Inputs: d = nets _009_; en = nets _041_. Outputs: q = nets out[9]. Role: datapath.
- h69 (unconfirmed): 4 cells form a flip-flop with enable, `ff_en: 1 bits`. No proof recorded. Confidence 0.9901. Inputs: d = nets _010_; en = nets in[10]. Outputs: q = nets out[10]. Role: datapath.
- h70 (unconfirmed): 4 cells form a flip-flop with enable, `ff_en: 1 bits`. No proof recorded. Confidence 0.9901. Inputs: d = nets _010_; en = nets _042_. Outputs: q = nets out[10]. Role: datapath.
- h72 (unconfirmed): 4 cells form a flip-flop with enable, `ff_en: 1 bits`. No proof recorded. Confidence 0.9901. Inputs: d = nets _011_; en = nets in[11]. Outputs: q = nets out[11]. Role: datapath.
- h73 (unconfirmed): 4 cells form a flip-flop with enable, `ff_en: 1 bits`. No proof recorded. Confidence 0.9901. Inputs: d = nets _011_; en = nets _043_. Outputs: q = nets out[11]. Role: datapath.
- h75 (unconfirmed): 4 cells form a flip-flop with enable, `ff_en: 1 bits`. No proof recorded. Confidence 0.9901. Inputs: d = nets _012_; en = nets in[12]. Outputs: q = nets out[12]. Role: datapath.
- h76 (unconfirmed): 4 cells form a flip-flop with enable, `ff_en: 1 bits`. No proof recorded. Confidence 0.9901. Inputs: d = nets _012_; en = nets _044_. Outputs: q = nets out[12]. Role: datapath.
- h78 (unconfirmed): 4 cells form a flip-flop with enable, `ff_en: 1 bits`. No proof recorded. Confidence 0.9901. Inputs: d = nets _013_; en = nets in[13]. Outputs: q = nets out[13]. Role: datapath.
- h79 (unconfirmed): 4 cells form a flip-flop with enable, `ff_en: 1 bits`. No proof recorded. Confidence 0.9901. Inputs: d = nets _013_; en = nets _045_. Outputs: q = nets out[13]. Role: datapath.
- h81 (unconfirmed): 4 cells form a flip-flop with enable, `ff_en: 1 bits`. No proof recorded. Confidence 0.9901. Inputs: d = nets _014_; en = nets _046_. Outputs: q = nets out[14]. Role: datapath.
- h82 (unconfirmed): 4 cells form a flip-flop with enable, `ff_en: 1 bits`. No proof recorded. Confidence 0.9901. Inputs: d = nets _014_; en = nets in[14]. Outputs: q = nets out[14]. Role: datapath.
- h84 (unconfirmed): 4 cells form a flip-flop with enable, `ff_en: 1 bits`. No proof recorded. Confidence 0.9901. Inputs: d = nets _015_; en = nets _047_. Outputs: q = nets out[15]. Role: datapath.
- h85 (unconfirmed): 4 cells form a flip-flop with enable, `ff_en: 1 bits`. No proof recorded. Confidence 0.9901. Inputs: d = nets _015_; en = nets in[15]. Outputs: q = nets out[15]. Role: datapath.
- h87 (unconfirmed): 4 cells form a flip-flop with enable, `ff_en: 1 bits`. No proof recorded. Confidence 0.9901. Inputs: d = nets _016_; en = nets _048_. Outputs: q = nets out[16]. Role: datapath.
- h88 (unconfirmed): 4 cells form a flip-flop with enable, `ff_en: 1 bits`. No proof recorded. Confidence 0.9901. Inputs: d = nets _016_; en = nets in[16]. Outputs: q = nets out[16]. Role: datapath.
- h90 (unconfirmed): 4 cells form a flip-flop with enable, `ff_en: 1 bits`. No proof recorded. Confidence 0.9901. Inputs: d = nets _017_; en = nets _049_. Outputs: q = nets out[17]. Role: datapath.
- h91 (unconfirmed): 4 cells form a flip-flop with enable, `ff_en: 1 bits`. No proof recorded. Confidence 0.9901. Inputs: d = nets _017_; en = nets in[17]. Outputs: q = nets out[17]. Role: datapath.
- h93 (unconfirmed): 4 cells form a flip-flop with enable, `ff_en: 1 bits`. No proof recorded. Confidence 0.9901. Inputs: d = nets _018_; en = nets _050_. Outputs: q = nets out[18]. Role: datapath.
- h94 (unconfirmed): 4 cells form a flip-flop with enable, `ff_en: 1 bits`. No proof recorded. Confidence 0.9901. Inputs: d = nets _018_; en = nets in[18]. Outputs: q = nets out[18]. Role: datapath.
- h96 (unconfirmed): 4 cells form a flip-flop with enable, `ff_en: 1 bits`. No proof recorded. Confidence 0.9901. Inputs: d = nets _019_; en = nets _051_. Outputs: q = nets out[19]. Role: datapath.
- h97 (unconfirmed): 4 cells form a flip-flop with enable, `ff_en: 1 bits`. No proof recorded. Confidence 0.9901. Inputs: d = nets _019_; en = nets in[19]. Outputs: q = nets out[19]. Role: datapath.
- h99 (unconfirmed): 4 cells form a flip-flop with enable, `ff_en: 1 bits`. No proof recorded. Confidence 0.9901. Inputs: d = nets _020_; en = nets _052_. Outputs: q = nets out[20]. Role: datapath.
- h100 (unconfirmed): 4 cells form a flip-flop with enable, `ff_en: 1 bits`. No proof recorded. Confidence 0.9901. Inputs: d = nets _020_; en = nets in[20]. Outputs: q = nets out[20]. Role: datapath.
- h102 (unconfirmed): 4 cells form a flip-flop with enable, `ff_en: 1 bits`. No proof recorded. Confidence 0.9901. Inputs: d = nets _021_; en = nets _053_. Outputs: q = nets out[21]. Role: datapath.
- h103 (unconfirmed): 4 cells form a flip-flop with enable, `ff_en: 1 bits`. No proof recorded. Confidence 0.9901. Inputs: d = nets _021_; en = nets in[21]. Outputs: q = nets out[21]. Role: datapath.
- h105 (unconfirmed): 4 cells form a flip-flop with enable, `ff_en: 1 bits`. No proof recorded. Confidence 0.9901. Inputs: d = nets _022_; en = nets _054_. Outputs: q = nets out[22]. Role: datapath.
- h106 (unconfirmed): 4 cells form a flip-flop with enable, `ff_en: 1 bits`. No proof recorded. Confidence 0.9901. Inputs: d = nets _022_; en = nets in[22]. Outputs: q = nets out[22]. Role: datapath.
- h108 (unconfirmed): 4 cells form a flip-flop with enable, `ff_en: 1 bits`. No proof recorded. Confidence 0.9901. Inputs: d = nets _023_; en = nets _055_. Outputs: q = nets out[23]. Role: datapath.
- h109 (unconfirmed): 4 cells form a flip-flop with enable, `ff_en: 1 bits`. No proof recorded. Confidence 0.9901. Inputs: d = nets _023_; en = nets in[23]. Outputs: q = nets out[23]. Role: datapath.
- h111 (unconfirmed): 4 cells form a flip-flop with enable, `ff_en: 1 bits`. No proof recorded. Confidence 0.9901. Inputs: d = nets _024_; en = nets _056_. Outputs: q = nets out[24]. Role: datapath.
- h112 (unconfirmed): 4 cells form a flip-flop with enable, `ff_en: 1 bits`. No proof recorded. Confidence 0.9901. Inputs: d = nets _024_; en = nets in[24]. Outputs: q = nets out[24]. Role: datapath.
- h114 (unconfirmed): 4 cells form a flip-flop with enable, `ff_en: 1 bits`. No proof recorded. Confidence 0.9901. Inputs: d = nets _025_; en = nets _057_. Outputs: q = nets out[25]. Role: datapath.
- h115 (unconfirmed): 4 cells form a flip-flop with enable, `ff_en: 1 bits`. No proof recorded. Confidence 0.9901. Inputs: d = nets _025_; en = nets in[25]. Outputs: q = nets out[25]. Role: datapath.
- h117 (unconfirmed): 4 cells form a flip-flop with enable, `ff_en: 1 bits`. No proof recorded. Confidence 0.9901. Inputs: d = nets _026_; en = nets _058_. Outputs: q = nets out[26]. Role: datapath.
- h118 (unconfirmed): 4 cells form a flip-flop with enable, `ff_en: 1 bits`. No proof recorded. Confidence 0.9901. Inputs: d = nets _026_; en = nets in[26]. Outputs: q = nets out[26]. Role: datapath.
- h120 (unconfirmed): 4 cells form a flip-flop with enable, `ff_en: 1 bits`. No proof recorded. Confidence 0.9901. Inputs: d = nets _027_; en = nets _059_. Outputs: q = nets out[27]. Role: datapath.
- h121 (unconfirmed): 4 cells form a flip-flop with enable, `ff_en: 1 bits`. No proof recorded. Confidence 0.9901. Inputs: d = nets _027_; en = nets in[27]. Outputs: q = nets out[27]. Role: datapath.
- h123 (unconfirmed): 4 cells form a flip-flop with enable, `ff_en: 1 bits`. No proof recorded. Confidence 0.9901. Inputs: d = nets _028_; en = nets _060_. Outputs: q = nets out[28]. Role: datapath.
- h124 (unconfirmed): 4 cells form a flip-flop with enable, `ff_en: 1 bits`. No proof recorded. Confidence 0.9901. Inputs: d = nets _028_; en = nets in[28]. Outputs: q = nets out[28]. Role: datapath.
- h126 (unconfirmed): 4 cells form a flip-flop with enable, `ff_en: 1 bits`. No proof recorded. Confidence 0.9901. Inputs: d = nets _029_; en = nets _061_. Outputs: q = nets out[29]. Role: datapath.
- h127 (unconfirmed): 4 cells form a flip-flop with enable, `ff_en: 1 bits`. No proof recorded. Confidence 0.9901. Inputs: d = nets _029_; en = nets in[29]. Outputs: q = nets out[29]. Role: datapath.
- h129 (unconfirmed): 4 cells form a flip-flop with enable, `ff_en: 1 bits`. No proof recorded. Confidence 0.9901. Inputs: d = nets _030_; en = nets _062_. Outputs: q = nets out[30]. Role: datapath.
- h130 (unconfirmed): 4 cells form a flip-flop with enable, `ff_en: 1 bits`. No proof recorded. Confidence 0.9901. Inputs: d = nets _030_; en = nets in[30]. Outputs: q = nets out[30]. Role: datapath.
- h132 (unconfirmed): 4 cells form a flip-flop with enable, `ff_en: 1 bits`. No proof recorded. Confidence 0.9901. Inputs: d = nets _031_; en = nets _063_. Outputs: q = nets out[31]. Role: datapath.
- h133 (unconfirmed): 4 cells form a flip-flop with enable, `ff_en: 1 bits`. No proof recorded. Confidence 0.9901. Inputs: d = nets _031_; en = nets in[31]. Outputs: q = nets out[31]. Role: datapath.
- h41 (unconfirmed): 4 cells form a flip-flop with synchronous reset, `ff_srst: 1 bits`. No proof recorded. Confidence 0.9526. Inputs: d = nets _000_; rst = nets reset. Outputs: q = nets out[0]. Role: datapath.
- h44 (unconfirmed): 4 cells form a flip-flop with synchronous reset, `ff_srst: 1 bits`. No proof recorded. Confidence 0.9526. Inputs: d = nets _001_; rst = nets reset. Outputs: q = nets out[1]. Role: datapath.
- h47 (unconfirmed): 4 cells form a flip-flop with synchronous reset, `ff_srst: 1 bits`. No proof recorded. Confidence 0.9526. Inputs: d = nets _002_; rst = nets reset. Outputs: q = nets out[2]. Role: datapath.
- h50 (unconfirmed): 4 cells form a flip-flop with synchronous reset, `ff_srst: 1 bits`. No proof recorded. Confidence 0.9526. Inputs: d = nets _003_; rst = nets reset. Outputs: q = nets out[3]. Role: datapath.
- h53 (unconfirmed): 4 cells form a flip-flop with synchronous reset, `ff_srst: 1 bits`. No proof recorded. Confidence 0.9526. Inputs: d = nets _004_; rst = nets reset. Outputs: q = nets out[4]. Role: datapath.
- h56 (unconfirmed): 4 cells form a flip-flop with synchronous reset, `ff_srst: 1 bits`. No proof recorded. Confidence 0.9526. Inputs: d = nets _005_; rst = nets reset. Outputs: q = nets out[5]. Role: datapath.
- h59 (unconfirmed): 4 cells form a flip-flop with synchronous reset, `ff_srst: 1 bits`. No proof recorded. Confidence 0.9526. Inputs: d = nets _006_; rst = nets reset. Outputs: q = nets out[6]. Role: datapath.
- h62 (unconfirmed): 4 cells form a flip-flop with synchronous reset, `ff_srst: 1 bits`. No proof recorded. Confidence 0.9526. Inputs: d = nets _007_; rst = nets reset. Outputs: q = nets out[7]. Role: datapath.
- h65 (unconfirmed): 4 cells form a flip-flop with synchronous reset, `ff_srst: 1 bits`. No proof recorded. Confidence 0.9526. Inputs: d = nets _008_; rst = nets reset. Outputs: q = nets out[8]. Role: datapath.
- h68 (unconfirmed): 4 cells form a flip-flop with synchronous reset, `ff_srst: 1 bits`. No proof recorded. Confidence 0.9526. Inputs: d = nets _009_; rst = nets reset. Outputs: q = nets out[9]. Role: datapath.
- h71 (unconfirmed): 4 cells form a flip-flop with synchronous reset, `ff_srst: 1 bits`. No proof recorded. Confidence 0.9526. Inputs: d = nets _010_; rst = nets reset. Outputs: q = nets out[10]. Role: datapath.
- h74 (unconfirmed): 4 cells form a flip-flop with synchronous reset, `ff_srst: 1 bits`. No proof recorded. Confidence 0.9526. Inputs: d = nets _011_; rst = nets reset. Outputs: q = nets out[11]. Role: datapath.
- h77 (unconfirmed): 4 cells form a flip-flop with synchronous reset, `ff_srst: 1 bits`. No proof recorded. Confidence 0.9526. Inputs: d = nets _012_; rst = nets reset. Outputs: q = nets out[12]. Role: datapath.
- h80 (unconfirmed): 4 cells form a flip-flop with synchronous reset, `ff_srst: 1 bits`. No proof recorded. Confidence 0.9526. Inputs: d = nets _013_; rst = nets reset. Outputs: q = nets out[13]. Role: datapath.
- h83 (unconfirmed): 4 cells form a flip-flop with synchronous reset, `ff_srst: 1 bits`. No proof recorded. Confidence 0.9526. Inputs: d = nets _014_; rst = nets reset. Outputs: q = nets out[14]. Role: datapath.
- h86 (unconfirmed): 4 cells form a flip-flop with synchronous reset, `ff_srst: 1 bits`. No proof recorded. Confidence 0.9526. Inputs: d = nets _015_; rst = nets reset. Outputs: q = nets out[15]. Role: datapath.
- h89 (unconfirmed): 4 cells form a flip-flop with synchronous reset, `ff_srst: 1 bits`. No proof recorded. Confidence 0.9526. Inputs: d = nets _016_; rst = nets reset. Outputs: q = nets out[16]. Role: datapath.
- h92 (unconfirmed): 4 cells form a flip-flop with synchronous reset, `ff_srst: 1 bits`. No proof recorded. Confidence 0.9526. Inputs: d = nets _017_; rst = nets reset. Outputs: q = nets out[17]. Role: datapath.
- h95 (unconfirmed): 4 cells form a flip-flop with synchronous reset, `ff_srst: 1 bits`. No proof recorded. Confidence 0.9526. Inputs: d = nets _018_; rst = nets reset. Outputs: q = nets out[18]. Role: datapath.
- h98 (unconfirmed): 4 cells form a flip-flop with synchronous reset, `ff_srst: 1 bits`. No proof recorded. Confidence 0.9526. Inputs: d = nets _019_; rst = nets reset. Outputs: q = nets out[19]. Role: datapath.
- h101 (unconfirmed): 4 cells form a flip-flop with synchronous reset, `ff_srst: 1 bits`. No proof recorded. Confidence 0.9526. Inputs: d = nets _020_; rst = nets reset. Outputs: q = nets out[20]. Role: datapath.
- h104 (unconfirmed): 4 cells form a flip-flop with synchronous reset, `ff_srst: 1 bits`. No proof recorded. Confidence 0.9526. Inputs: d = nets _021_; rst = nets reset. Outputs: q = nets out[21]. Role: datapath.
- h107 (unconfirmed): 4 cells form a flip-flop with synchronous reset, `ff_srst: 1 bits`. No proof recorded. Confidence 0.9526. Inputs: d = nets _022_; rst = nets reset. Outputs: q = nets out[22]. Role: datapath.
- h110 (unconfirmed): 4 cells form a flip-flop with synchronous reset, `ff_srst: 1 bits`. No proof recorded. Confidence 0.9526. Inputs: d = nets _023_; rst = nets reset. Outputs: q = nets out[23]. Role: datapath.
- h113 (unconfirmed): 4 cells form a flip-flop with synchronous reset, `ff_srst: 1 bits`. No proof recorded. Confidence 0.9526. Inputs: d = nets _024_; rst = nets reset. Outputs: q = nets out[24]. Role: datapath.
- h116 (unconfirmed): 4 cells form a flip-flop with synchronous reset, `ff_srst: 1 bits`. No proof recorded. Confidence 0.9526. Inputs: d = nets _025_; rst = nets reset. Outputs: q = nets out[25]. Role: datapath.
- h119 (unconfirmed): 4 cells form a flip-flop with synchronous reset, `ff_srst: 1 bits`. No proof recorded. Confidence 0.9526. Inputs: d = nets _026_; rst = nets reset. Outputs: q = nets out[26]. Role: datapath.
- h122 (unconfirmed): 4 cells form a flip-flop with synchronous reset, `ff_srst: 1 bits`. No proof recorded. Confidence 0.9526. Inputs: d = nets _027_; rst = nets reset. Outputs: q = nets out[27]. Role: datapath.
- h125 (unconfirmed): 4 cells form a flip-flop with synchronous reset, `ff_srst: 1 bits`. No proof recorded. Confidence 0.9526. Inputs: d = nets _028_; rst = nets reset. Outputs: q = nets out[28]. Role: datapath.
- h128 (unconfirmed): 4 cells form a flip-flop with synchronous reset, `ff_srst: 1 bits`. No proof recorded. Confidence 0.9526. Inputs: d = nets _029_; rst = nets reset. Outputs: q = nets out[29]. Role: datapath.
- h131 (unconfirmed): 4 cells form a flip-flop with synchronous reset, `ff_srst: 1 bits`. No proof recorded. Confidence 0.9526. Inputs: d = nets _030_; rst = nets reset. Outputs: q = nets out[30]. Role: datapath.
- h134 (unconfirmed): 4 cells form a flip-flop with synchronous reset, `ff_srst: 1 bits`. No proof recorded. Confidence 0.9526. Inputs: d = nets _031_; rst = nets reset. Outputs: q = nets out[31]. Role: datapath.
- h3 (unconfirmed): 32 cells form a 32-bit register, `register: 32 bits`. No proof recorded. Confidence 0.8889. Inputs: clk = nets clk; d = nets in[0], in[1], in[2], in[3], in[4], in[5], in[6], in[7], in[8], in[9], in[10], in[11], in[12], in[13], in[14], in[15], in[16], in[17], in[18], in[19], in[20], in[21], in[22], in[23], in[24], in[25], in[26], in[27], in[28], in[29], in[30], in[31]. Outputs: q = nets d_last[0], d_last[1], d_last[2], d_last[3], d_last[4], d_last[5], d_last[6], d_last[7], d_last[8], d_last[9], d_last[10], d_last[11], d_last[12], d_last[13], d_last[14], d_last[15], d_last[16], d_last[17], d_last[18], d_last[19], d_last[20], d_last[21], d_last[22], d_last[23], d_last[24], d_last[25], d_last[26], d_last[27], d_last[28], d_last[29], d_last[30], d_last[31]. Role: datapath.
- h1 (unconfirmed): 128 cells form a flip-flop with synchronous reset, `ff_srst: 32 bits`. No proof recorded. Confidence 0.5000. Inputs: d = nets _000_, _001_, _002_, _003_, _004_, _005_, _006_, _007_, _008_, _009_, _010_, _011_, _012_, _013_, _014_, _015_, _016_, _017_, _018_, _019_, _020_, _021_, _022_, _023_, _024_, _025_, _026_, _027_, _028_, _029_, _030_, _031_; rst = nets reset. Outputs: q = nets out[0], out[1], out[2], out[3], out[4], out[5], out[6], out[7], out[8], out[9], out[10], out[11], out[12], out[13], out[14], out[15], out[16], out[17], out[18], out[19], out[20], out[21], out[22], out[23], out[24], out[25], out[26], out[27], out[28], out[29], out[30], out[31]. Role: datapath.

## 7. Rejected claims

(none)

## 9. What Loki does NOT claim

- Candidates and rejected claims are not statements of fact.
- Module names such as `adder_h1` are Loki's labels built from the kind and the id; they are not the original HDL names, which Loki does not know.
[LOKI-HINTS-END]
Designer prior: designers write RTL from familiar patterns. If a signal looks like a condition, it
probably is one; if a register group looks like an FSM, it probably is one.
