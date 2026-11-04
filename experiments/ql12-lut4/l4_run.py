"""Run a Q-L12 script (ql12-k4k6) at the lut4 endpoint: ``python -B l4_run.py SCRIPT [ARGS]``.

SCRIPT is ``stubcheck``, ``blocks``, ``calls``, ``collect`` or ``astcfg``; the endpoint, output
directory and census are set by ``l4_env`` before the script is imported. ``stubcheck`` and
``blocks`` need libodin3 (``ODIN3_LIB``). No model call.
"""

from __future__ import annotations

import importlib
import sys
from typing import Any

import l4_env  # first: it sets q12_env before the scripts are imported

SCRIPTS = {"stubcheck": ("q12_stubcheck", False), "blocks": ("q12_build", True),
           "calls": ("q12_build", True), "collect": ("q12_collect", True),
           "astcfg": ("q12_astcfg", True)}


def main(argv: list[str]) -> int:
    if not argv or argv[0] not in SCRIPTS:
        print(__doc__)
        return 2
    name, takes_args = SCRIPTS[argv[0]]
    mod: Any = importlib.import_module(name)
    if not l4_env.env.ENDPOINTS == {"lut4": ("O-lut", "f2")}:
        raise SystemExit("endpoint not set")
    if takes_args:
        rest = argv if name == "q12_build" else argv[1:]
        return int(mod.main(rest))
    return int(mod.main())


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
