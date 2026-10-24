# Build the L0 dataset

L0 turns Verilog designs into labelled, anonymised netlists. Odin III's provenance is the answer
key: every LUT, flip-flop, hard block and gate carries the HDL file and line it came from, the
construct it implements, its module path, the bus and bit it drives, and a datapath or control role.
The anonymised netlist hides all of that; the labels are kept apart.

## Commands

`loki` has three subcommands. `wyrd run` does the heavy work between the first and the second.

```
loki bench init --suite micro --odin3-root $ODIN3_ROOT --out datasets/l0
wyrd run --project datasets/l0 --jobs 3 --mem-budget 8G --progress
loki assemble --project datasets/l0 --out dataset
loki check dataset
```

| Command | Does |
|---|---|
| `loki bench init --suite S --odin3-root DIR --out DIR [--cache DIR]` | Writes a Wyrd project (`wyrd.toml`) for suite `S`: `micro`, `verilog-eval` or `all`. |
| `loki assemble --project DIR --out DIR` | Merges the finished Wyrd runs into one dataset directory and writes `manifest.json`. |
| `loki check DATASET` | Validates a dataset directory against the invariants; exit code 1 on any error. Warnings are listed but do not fail. |

`--suite verilog-eval` clones the pinned VerilogEval commit into `~/.cache/loki/verilog-eval`
(`--cache DIR` changes it). The download is treated as data and never executed.

## Floors

The same design is built to several netlist forms, called floors, each with its own labels.

| Floor | Directory | Netlist |
|---|---|---|
| F1 | `f1-k6`, `f1-earch` | LUT6 plus hard blocks (adders, multipliers, RAMs stay hard cells and are labelled), for the `k6_frac_N10_frac_chain_mem32K_40nm` and `EArch` architectures |
| F2 | `f2` | LUT6 only, soft arithmetic |
| F3 | `f3` | six-cell gate netlist |

## What one build does

1. Read the Verilog with Odin III and run the common front end.
2. Snapshot the word-level cells before mapping.
3. Map to the floor's form.
4. Read the final netlist back out of Odin III.
5. Join final cells to the snapshot by source spans and compute labels and roles.
6. Anonymise (names become `n<k>`) and write the files.
7. Write Verilog from the BLIF and check that it, and the anonymised netlist, are equivalent to the
   original.

A design that Odin III cannot read, or that keeps unsupported structure, is recorded as `skipped`
with the reason; it does not stop the run. The full pipeline is section 4 of the
[L0 spec](https://github.com/drpaj12/loki/blob/main/docs/specs/2026-10-21-l0-dataset-design.md).
