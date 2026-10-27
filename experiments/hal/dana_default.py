"""Script run INSIDE HAL: DANA with the library defaults only (no ``min_group_size`` call).

Check of the headline setting (pre-registration Amendment 1 A4, fix 2 L6): the group file of this
script must equal the one of ``dana_run.py`` with ``HAL_MIN=8``. Environment as in ``dana_run.py``
(HAL_V, HAL_L, HAL_OUT); writes ``HAL_OUT/groups.txt``.
"""

import os
import sys

from hal_plugins import dataflow
from hal_py import NetlistFactory

nl = NetlistFactory.load_netlist(os.environ["HAL_V"], os.environ["HAL_L"])
if nl is None:
    sys.exit("load failed")
res = dataflow.analyze(dataflow.Configuration(nl).with_flip_flops())
if res is None:
    sys.exit("analysis failed")
res.write_txt(os.environ["HAL_OUT"] + "/groups.txt")
