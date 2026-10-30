# Example: a Q4 problem (Prob136_m2014_q6), arm B2

Hint block (what the model reads after the question):

```
## Claims

h73 (p=0.95, proved by exhaustive simulation of the next-state logic): state[5:0] holds a 6-state machine (one-hot: a state is the flip-flop that is high); states state[0], state[1], state[2], state[3], state[4], state[5]; synchronous reset when reset is high enters state state[0]; inputs w.
    state[0] -> state[0] when w
    state[0] -> state[3] when ~w
    state[1] -> state[1] when ~w
    state[1] -> state[5] when w
    state[2] -> state[1] when ~w
    state[2] -> state[5] when w
    state[3] -> state[2] when ~w
    state[3] -> state[5] when w
    state[4] -> state[2] when ~w
    state[4] -> state[5] when w
    state[5] -> state[0] when w
    state[5] -> state[4] when ~w
h4 (p=0.99, proved by truth table): comparison against a constant `Y = (A != 0)` (A = state[1], state[4]; Y = z).
h14 (p=0.99, proved by truth table): comparison against a constant `Y = (A != 0)` (A = state[0], state[5]; Y = _09_).

## Buses

- b1 (p=0.95): state[5:0] is the state of the state machine h73; bit 0 = state[0]

## Control and data nets

- control: _09_, reset (p=0.95), state[0] (p=0.95), state[2] (p=0.95), state[3] (p=0.95), state[5] (p=0.95), w (p=0.95)
- datapath: z
- mixed: state[1] (p=0.95), state[4] (p=0.95)
```

Linked netlist, lines that carry a `// loki` comment (excerpt):

```
module RefModule(clk, reset, w, z);
  input reset;  // loki h73 reset of fsm, p=0.95
  input w;  // loki h73 input of fsm, p=0.95
  NOR _18_ (  // loki h73 fsm logic, p=0.95
  NOT _19_ (  // loki h73 fsm logic, p=0.95
  NOT _21_ (  // loki h14 eq_const logic, p=0.99; h73 fsm logic, p=0.95
  NOR _22_ (  // loki h73 fsm logic, p=0.95
  NOR _23_ (  // loki h73 next-state of fsm bit 0, p=0.95
  NOT _25_ (  // loki h4 eq_const logic, p=0.99
  NOR _26_ (  // loki h73 fsm logic, p=0.95
  NOR _27_ (  // loki h73 next-state of fsm bit 1, p=0.95
  NOT _29_ (  // loki h73 next-state of fsm bit 4, p=0.95
  NOT _31_ (  // loki h73 next-state of fsm bit 3, p=0.95
  NOR _32_ (  // loki h73 fsm logic, p=0.95
  NOR _33_ (  // loki h73 next-state of fsm bit 2, p=0.95
  NAND _34_ (  // loki h73 fsm logic, p=0.95
  NAND _35_ (  // loki h73 fsm logic, p=0.95
  NOR _36_ (  // loki h73 next-state of fsm bit 5, p=0.95
```
