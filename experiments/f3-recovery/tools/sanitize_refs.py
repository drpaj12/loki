"""Write pyverilog-parseable copies of the micro reference RTL (mechanical syntax fixes only).

pyverilog 1.3 rejects a handful of the micro sources that Odin III accepts. The fixes are
syntactic and structure-preserving:

  * drop a trailing comma before ``)`` in a module port list (Verilog-2005 forbids it);
  * drop ``defparam`` statements (parameter overrides; no structural effect);
  * drop an empty ``#()`` parameter list on a module header;
  * wrap module-scope ``for``/``if`` generate constructs in ``generate``/``endgenerate``
    (the micro sources use the implied-generate style Odin III accepts; pyverilog does not).

Only files that the original parse rejects are sanitized; originals are used otherwise.
Usage: sanitize_refs.py REF_DIR OUT_DIR [NAME ...]
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

from pyverilog.vparser.parser import parse


def sanitize(text: str) -> str:
    text = re.sub(r",(\s*)\)", r"\1)", text)
    text = re.sub(r"^[ \t]*defparam[^;\n]*;[^\n]*\n", "", text, flags=re.M)
    text = re.sub(r"module\s+(\w+)\s*#\s*\(\s*\)\s*\(", r"module \1 (", text)
    text = re.sub(r"module\s+(\w+)\s*#\s*\(\s*\)\s*", r"module \1 ", text)
    if "genvar" in text and not re.search(r"^[ \t]*(end)?generate\b", text, flags=re.M):
        text = re.sub(r"((?:[ \t]*genvar [^;]+;\n)+)", r"\1    generate\n", text, count=1)
        text = re.sub(r"(    end\n)\n(endmodule)", r"\1    endgenerate\n\n\2", text, count=1)
    return text


def wrap_module_scope_generates(text: str) -> str:
    """Wrap a bare module-scope ``if`` or ``case`` that is not inside an always block."""
    text = re.sub(r"(    parameter [^;]+;\n\s*)(    if \()", r"\1    generate\n\2", text)
    text = re.sub(r"(        end\n)(\s+endmodule)", r"\1    endgenerate\n\n\2", text)
    text = re.sub(r"(    parameter [^;]+;\n\s*)(    case \()", r"\1    generate\n\2", text)
    text = re.sub(r"(    endcase\n)(\s+endmodule)", r"\1    endgenerate\n\n\2", text)
    return text


def parses(path: Path) -> bool:
    try:
        parse([str(path)], preprocess_include=[], preprocess_define=[])
        return True
    except Exception:
        return False


def main() -> int:
    ref_dir, out_dir = Path(sys.argv[1]), Path(sys.argv[2])
    names = sys.argv[3:] or sorted(p.stem for p in ref_dir.glob("*.v"))
    out_dir.mkdir(parents=True, exist_ok=True)
    written = 0
    for name in names:
        source = ref_dir / f"{name}.v"
        if parses(source):
            continue
        fixed = wrap_module_scope_generates(sanitize(source.read_text(encoding="utf-8")))
        target = out_dir / f"{name}.v"
        target.write_text(fixed, encoding="utf-8")
        if not parses(target):
            print(f"still fails: {name}", file=sys.stderr)
            continue
        written += 1
        print(f"sanitized {name}")
    print(f"{written} sanitized")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
