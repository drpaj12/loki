"""HAL script: truth table of every LUT gate as HAL evaluates it (lut6.hgl bit_order check).

Environment: HAL_V (Verilog), HAL_L (.hgl), HAL_OUT (existing directory). Writes
``HAL_OUT/lut_tt.txt``, one line ``<gate name> <k> <table>`` per LUT gate, the table an integer
whose bit ``i`` is the output for the assignment with pin ``I<j>`` = ``(i >> j) & 1``.
"""

import os

from hal_py import BooleanFunction, NetlistFactory

nl = NetlistFactory.load_netlist(os.environ["HAL_V"], os.environ["HAL_L"])
lines = []
for gate in nl.get_gates():
    if not gate.type.name.startswith("LUT"):
        continue
    k = int(gate.type.name[3:])
    func = gate.get_boolean_function()
    table = 0
    for i in range(1 << k):
        env = {f"I{j}": (BooleanFunction.Value.ONE if (i >> j) & 1 else BooleanFunction.Value.ZERO)
               for j in range(k)}
        if func.evaluate(env) == BooleanFunction.Value.ONE:
            table |= 1 << i
    lines.append(f"{gate.name} {k} {table}")
with open(os.environ["HAL_OUT"] + "/lut_tt.txt", "w", encoding="utf-8") as fh:
    fh.write("\n".join(sorted(lines)) + "\n")
