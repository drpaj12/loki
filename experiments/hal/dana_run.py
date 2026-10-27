"""Script run INSIDE HAL (``hal --python-script dana_run.py``): DANA on one netlist.

HAL v4.5.0's own ``--dataflow`` command line route does not run (its handler sets no gate types
and no control pin types, and writes no result file), so the comparison drives the dataflow
plugin through its documented Python API, with the documented default configuration
``Configuration.with_flip_flops()`` (all flip-flop gate types; clock, enable, set and reset pins
as control pins) and nothing else changed except ``min_group_size`` (pre-registration,
Amendment 1 A4 and Amendment 2 B1). Arguments come from the environment because HAL's
embedded interpreter has no argv:

    HAL_V    structural Verilog netlist        HAL_L    gate library (.hgl)
    HAL_OUT  output directory (exists)         HAL_MIN  min_group_size

Writes ``HAL_OUT/groups.txt`` (the plugin's ``Result.write_txt``) and ``HAL_OUT/done.txt``.
"""

import os
import sys

from hal_plugins import dataflow
from hal_py import NetlistFactory

out = os.environ["HAL_OUT"]
nl = NetlistFactory.load_netlist(os.environ["HAL_V"], os.environ["HAL_L"])
if nl is None:
    sys.exit("load failed")
cfg = dataflow.Configuration(nl).with_flip_flops().with_min_group_size(int(os.environ["HAL_MIN"]))
res = dataflow.analyze(cfg)
if res is None:
    sys.exit("analysis failed")
res.write_txt(out + "/groups.txt")
with open(out + "/done.txt", "w", encoding="utf-8") as fh:
    fh.write(f"{len(res.get_groups())} groups, {len(res.get_gates())} gates\n")
