# Passing Loki results to an LLM

`loki re` writes `reverse-provenance.json` (see [Dataset files](formats.md)). Two commands turn it
into something to hand to a language model next to the netlist. Loki makes no LLM call itself; this
page only prepares the material.

```
loki re netlist.blif --floor f2 --calib calib/f2.json --out out/x [--rp-min-p 0.5]
loki rp add-l2 out/x partition/kmeans-0c78bea4.json        # optional: add graph-analysis groups
loki rp doc out/x -o out/x/rp.md [--max-chars 24000] [--no-candidates]
```

`loki rp add-l2` joins an L2 partition (from `loki analyze cluster`) to the cells of the `loki re`
input by name and adds an `l2` block. It stops with exit code 2 when the partition node ids cannot
be joined to the input names; it never guesses. `loki rp doc` reads `reverse-provenance.json` only
and writes Markdown. The same text is available in Python as `loki.rp.doc.render(path)`.

The document has these parts: what the claims are and the trust order (proved, then high-confidence
unproven, then candidate); how the `loki_*` attributes of `design.v` point into the claims; a summary
with counts, coverage and the module tree; one statement per committed claim; buses, state machines
and roles; candidates, flagged unconfirmed; rejected claims; the L2 groups when present; and what
Loki does not claim (uncovered cells and nets, and that module names are Loki's labels, not HDL
names). The output is deterministic. When it exceeds `--max-chars` the rejected claims go first, then
the candidates, then the per-cell lists; the document names what it dropped.

## Sample

```
## 4. Committed claims

- h1: cells n10..n12 (3 cells) form a 2-bit adder, `Y = A + B`. Proved equivalent by cone check.
  Confidence 0.9999. Inputs: A = nets a0, a1; B = nets b0, b1. Outputs: Y = nets y0, y1.
  Recovered as module adder_h1, instance adder_h1_i. Role: datapath.
```
