# Loki III

Reverse engineering of structural netlists (LUT, hard-block and gate-level) back to hierarchical, word-level
Verilog, with a Bayesian hypothesis flow over Odin III's provenance IR. It asks how much of a design can be
recovered without a language model, and measures it against an answer key that Odin III provenance supplies.
Four levels, each with a spec in `docs/specs/`:

- **L0**, the ground-truth dataset: provenance is the answer key (`loki bench`, `loki assemble`).
- **L1**, Bayesian hypotheses: detectors, provers and a commit step (`loki re`).
- **L2**, analysis plugins: graph export, structural features, clustering, graphlets and a GNN baseline (`loki analyze`).
- **L3**, design patterns and blocks: a pattern census with a v0 detector, and anchor-grow-join blocks with a kind guess (research code under `experiments/`).

A Gate-Breaker style harness (`experiments/llm-*`) tests whether Loki's hints help a language model that
is given the netlist. Headline result (paper, `docs/paper/loki.tex`): the answer key covers all 54,306 gate nodes of
150 designs and the pipeline is naming-neutral over 105,646 renamed identifiers; hard adders are recovered 67 of 67;
grown and joined blocks are the right block for 0.715 of 1141 held-out constructs against 0.385 for bounded cones, and the
kind guess on them reaches a macro F1 of 0.392 (the weakest part). Clustering does not find the designer's hierarchy, and
Loki's hints did not help a model that already has the netlist. Loki does not detect Trojans (see Leman Russ III for that).
Paper: [`docs/paper/`](docs/paper/README.md). Manual: <https://drpaj12.github.io/loki/>. Hub: <https://github.com/drpaj12/YggdrasilIII>.

Loki III is part of **Yggdrasil III**, the suite of Odin III (<https://github.com/drpaj12/odin3>, the trunk), Wyrd III (<https://github.com/drpaj12/wyrd>, the canopy, with Bifrost III and Midgard III), Loki III (<https://github.com/drpaj12/loki>), The Norns III (<https://github.com/drpaj12/nornsIII>) and Verdandi III (<https://github.com/drpaj12/verdandiIII>) on side branches, and Mímir III (<https://github.com/drpaj12/mimirIII>, the fruit). Loki III is a side branch, a tool and experiment; it uses Odin III's provenance IR and its L2 clusters seed The Norns III. It depends on the `odin3` Python package and never changes the Odin III core. Version 0.1.0 (`pyproject.toml`). The hub is <https://github.com/drpaj12/YggdrasilIII> (documentation: <https://drpaj12.github.io/YggdrasilIII/>, versions of every piece: <https://drpaj12.github.io/YggdrasilIII/versions.html>) and its picture of the tree is <https://github.com/drpaj12/YggdrasilIII/blob/main/images/yggdrasil-tree.png>.

License: MIT.

## Features

Status: **works** = a command or module on `main` with tests; **experiment** = research code under
`experiments/`, run by script and not a `loki` command; **dismissed** = measured and did not help (kept
as a record, and the options that remain are off by default). Verdicts are in the
[paper](docs/paper/README.md) register.

| Feature | Status | Where |
|---|---|---|
| L0 ground-truth dataset: Odin III provenance as the answer key, three floors (f1, f2, f3), anonymised names, `cell_type` labels in `graph.json` | works | `loki bench`, `loki assemble`, `loki check`; [dataset](docs/user/dataset.md), [formats](docs/user/formats.md) |
| Naming-neutral answer key: names exist only in `key.json`; the renamed-instance re-run over 105,646 identifiers shows nothing recovered is a naming artefact | works | [`experiments/rename-l2/EXPERIMENT.md`](experiments/rename-l2/EXPERIMENT.md) |
| L1 Bayesian flow: detectors, provers, commit with Odin III `raise` and `submod`, `unmap` facts and the `hard` detector for hard blocks | works | `loki re`; [hypotheses](docs/user/hypotheses.md), [runbook](docs/runbook-l1.md) |
| Calibration of the L1 log-odds on the train split | works | `loki calibrate`, `calib/*.json`, `loki re-project`, `loki score`, `loki score-all` |
| Run record for Mimir and the ReverseProvenance output (`reverse-provenance.json`) with a document for a language model | works | `loki rp`; [llm](docs/user/llm.md) |
| L2 analysis: graph export (edge list, GraphML, PyG), structural features (1-WL colours, NPN classes, role flags), clustering (k-means, affinity propagation, spectral, Louvain) | works | `loki analyze export`, `structural`, `cluster`; [hypotheses](docs/user/hypotheses.md) |
| Provenance step files (Odin III 1.4): read the per-step manifests of a silicon or VTR run and resolve any object at any stage (placed cell, extracted cell, LUT) back to the HDL, with the weakest link on the way | works | `loki prov`; [provenance-steps](docs/user/provenance-steps.md) |
| L2 graphlet and orbit counts (ORCA backend, pinned fetch) | works | `loki analyze graphlets`, `loki tools fetch-orca` |
| L2 GNN baseline for gate roles (GNN-RE style) | works | `loki analyze gnn`; baseline, not a re-implementation |
| Loss audit: the pass at which each construct is lost | works | `loki audit`; [`experiments/round6`](experiments/round6) |
| HAL and DANA comparison (`blif2hal`, word scorer) | works (comparison harness; the word-first detector lost to DANA, inconclusive) | `loki/hal/`, [`experiments/hal`](experiments/hal) |
| Word-first detector and word-group detector | dismissed (opt-in, off by default) | [wordfirst](docs/user/wordfirst.md) |
| Calibrated intent claims and linked hints (claims v2, A1 to A6) used as hints for a language model | works as a harness; the hints add nothing to a model that has the netlist (inconclusive and dismissed rows) | `loki/intent/`, [`experiments/llm-hints2`](experiments/llm-hints2) |
| Gate-Breaker LLM replication harness: 137 VerilogEval problems, 3 draws, arm A (netlist), arm B (netlist and Loki hints), arm C (interface only, memorisation control); follow-up arms A2, B1', B2 and W (wrong claims) | experiment | [`experiments/llm-pilot`](experiments/llm-pilot), [`experiments/llm-full`](experiments/llm-full), [`experiments/llm-hints2`](experiments/llm-hints2) |
| L3 design-pattern census and v0 detector (single patterns and composites, catalogue under `loki/l3/catalogue`) | works (v0) | `loki/l3/`, [L3 spec](docs/specs/2026-10-30-l3-patterns-design.md), [`experiments/l3-census`](experiments/l3-census), [`experiments/l3-detector`](experiments/l3-detector) |
| Graphlet signature matching against a pattern library, with fuzzy variants | experiment; no pattern reaches 0.80 on whole designs (inconclusive) | [`experiments/graphlets`](experiments/graphlets), [`experiments/graphlets-fuzzy`](experiments/graphlets-fuzzy) |
| L3 anchor-grow-join blocks: anchors, directed graphlet signatures, a growth order, extra anchors for untouched constructs, a join step; the grown and joined blocks are the right block for 0.715 of 1141 held-out constructs against 0.385 for bounded cones | experiment | [`experiments/ql6-grow`](experiments/ql6-grow), [`ql7-stop`](experiments/ql7-stop), [`ql8a-order`](experiments/ql8a-order), [`ql8b-anchors`](experiments/ql8b-anchors), [`ql9-join`](experiments/ql9-join) |
| M2 kind guess on the grown blocks (finite-state machine, counter, shift register, register file, register, glue); macro F1 0.392 | experiment (weakest part) | [`experiments/ql8c-kind`](experiments/ql8c-kind) |
| Block-by-block decode (Q-L10): Loki's joined blocks go to a language model one per prompt and a script assembles the RTL; arm D (blocks) against Gate-Breaker's whole-netlist arm A, and D+h (with the kind guess); passes 72 of 81 against A's 73 of 81 on 27 multi-block designs (inconclusive), decodes 3 of 4 designs too big for one prompt (useful), the kind-guess hint does not help (inconclusive) | experiment (results; no model call in the repo, replies are the controller's) | [`experiments/ql10-blocks`](experiments/ql10-blocks) |
| State-machine encoding study (one-hot against binary) | experiment; the next-state rule FSM3 was dismissed (precision 0.676) | [`experiments/fsm-encoding`](experiments/fsm-encoding) |
| Bayes-factor stop rule for growing blocks (QL6a), stop rules (QL7e), a split step (QL9-d), clustering as the designer's hierarchy (L2a) | dismissed or inconclusive | paper Table "what did not work", [`experiments/ql6-grow`](experiments/ql6-grow), [`ql7-stop`](experiments/ql7-stop), [`ql9-join`](experiments/ql9-join) |

## Paper and experiments

The [paper](docs/paper/README.md) (`docs/paper/loki.tex`) reports the L0/L1/L2 recovery statistics under the
Gate-Breaker metrics, with every number traced to the experiment records:

- [`experiments/rename-l2/EXPERIMENT.md`](experiments/rename-l2/EXPERIMENT.md): the renamed-instance re-run
  (L1 with the hard detector, L2 clustering and the GNN against 1-WL).
- [`experiments/f3-recovery/EXPERIMENT.md`](experiments/f3-recovery/EXPERIMENT.md): recovery from the cmos6 gate
  netlist (the L0 provenance ceiling, L1 on the renamed f3 floors, AST and CFG similarity).

## HAL comparison (branch `exp/hal`)

`loki/hal/` converts an L0 floor `netlist.blif` to HAL structural Verilog (`blif2hal`, libraries
`experiments/hal/hgl/{lut6,cmos6}.hgl`), reads DANA's `groups.txt` and scores words (`wordscore`);
plan and rules: `docs/plan/hal-compare-prereg.md` (with Amendments 1 and 2); results (generated):
`docs/results-hal.md`, per-design counts in `experiments/hal/results/`. Tool credit: HAL, the
Hardware Analyzer (Embedded Security Group, MIT licence, https://github.com/emsec/hal, tag v4.5.0)
and its dataflow plugin DANA (Albartus, Hoffmann, Temme, Azriel, Paar, IACR TCHES 2020(4),
309-336, doi 10.46586/tches.v2020.i4.309-336); HAL is built separately and nothing of it is
vendored here. Run: `experiments/hal/run_hal.py` (needs a HAL build with the dataflow plugin and
the vendored pybind11 replaced by a newer one on Python 3.12, see `experiments/hal/README.md`),
then `python -m loki.hal.compare`. Converter notes: a `.latch`
with init 2 or 3 (don't care, unknown) drops the `INIT` parameter, so the flip-flop starts at 0;
a flip-flop without `.cname` makes the conversion fail (the design leaves both arms). The tests
that read datasets need `LOKI_MICRO` (and `LOKI_VEVAL`, `LOKI_R5_DATA` for the scorer comparison)
and skip when they are unset. `python -m loki.hal.sim` runs the function round trip on one BLIF.

## Documentation

Start at the Yggdrasil III hub; every manual links to the others.

- [Yggdrasil III hub](https://drpaj12.github.io/YggdrasilIII/): the suite, how the pieces connect, getting started.
- [Odin III manual](https://drpaj12.github.io/odin3/).
- [Wyrd III manual](https://drpaj12.github.io/wyrd/), with
  [simulation (Bifrost III)](https://drpaj12.github.io/wyrd/simulation.html) and
  [Midgard III (Verilog Town)](https://drpaj12.github.io/wyrd/midgard.html).
- Tutorials (PDF): [command line](https://drpaj12.github.io/wyrd/wyrd-tutorial.pdf) and
  [GUI](https://drpaj12.github.io/wyrd/wyrd-gui-tutorial.pdf).
- [Loki III manual](https://drpaj12.github.io/loki/).
- [Verdandi III manual](https://drpaj12.github.io/verdandiIII/).
- [The Norns III](https://github.com/drpaj12/nornsIII) (repository; plan and paper under `docs/`).
- [Set up the whole suite](https://drpaj12.github.io/YggdrasilIII/getting-started.html) on a clean Linux or
  Windows machine, and [drive it with Claude Code](https://drpaj12.github.io/YggdrasilIII/ai-agent.html).

## Development

    python3 -m venv .venv && .venv/bin/pip install ruff mypy cffi
    .venv/bin/python -m unittest discover -s tests -t . -v
    .venv/bin/ruff check . && .venv/bin/mypy --strict loki tests

See `CLAUDE.md` for the Odin III environment variables.

## L0 dataset

    loki bench init --suite micro --odin3-root $ODIN3_ROOT --out datasets/l0
    wyrd run --project datasets/l0
    loki assemble --project datasets/l0 --out dataset
    loki check dataset

See `docs/runbook-l0.md`.

## L1: `loki re` (Bayesian hypotheses)

    loki re dataset/<design>/f2/netlist.blif --floor f2 --calib calib/f2.json --out out/<design>
    loki calibrate --dataset dataset --floor f2 --split train --out calib/f2.json
    loki re-project --dataset dataset --floors f2 --split test --calib calib --out datasets/l1 [--features none]
    wyrd run --project datasets/l1 --jobs 3 && loki score-all datasets/l1/runs --dataset dataset \
        --out datasets/l1-scores [--compare <runs made with --features none>]
    LOKI_DATASET=$PWD/dataset python -m unittest tests.test_acceptance_l1 -v      # L1 exit test

Every run also writes `reverse-provenance.json` (what Loki claims about each piece of the input netlist, with confidence and proof) and `loki rp doc` turns it into a document for an LLM: see
[Passing Loki results to an LLM](docs/user/llm.md).

`calib/f2.json` (train split) is committed. Details in `docs/runbook-l1.md`, first numbers in
`docs/results-l1.md`.

## L2: `loki analyze` (export, clustering, graphlets, GNN)

Four plugin kinds read one L0 `graph.json` (or one dataset design) and write under `--out`:

    loki analyze export --dataset dataset --design micro_bm_DL_2_1_mux --floor f2 \
        --format edgelist,graphml,pyg --out out [--region cone:<id>:in:2] [--no-structural]
    loki analyze cluster --dataset dataset --design micro_bm_DL_2_1_mux --floor f2 \
        --method all [--k 8|auto] [--features node,graphlet] --out out
    loki tools fetch-orca && loki analyze graphlets --dataset dataset --design micro_bm_DL_2_1_mux \
        --floor f2 --backend ext [--size 4|5] [--removal global|none] --out out [--licence]
    loki analyze gnn --dataset dataset --floor f2 --out out [--features node,graphlet,wl,npn]

`loki analyze structural` computes and caches the structural arrays (1-WL colours, NPN classes,
role flags) for inspection; `export` and `gnn` compute them when needed. `--graph graph.json`
replaces the dataset options for export, structural, cluster and graphlets; `gnn` is
dataset-only (spec 10). Exit codes: 0 ok, 1 analysis failure, 2 usage,
3 missing extra or backend.

Extras: the base install stays `odin3` only. `pip install 'loki[analysis]'` adds numpy, scipy,
scikit-learn and networkx (export, cluster, graphlets, structural); `pip install 'loki[gnn]'`
adds torch and torch_geometric (PyG export, GNN). Tests needing an extra skip without it.

Output tree (`<out>`, spec 11):

    <out>/<design>/<floor>/export/       whole.edges.tsv whole.nodes.tsv whole.graphml whole.pt  region-<h>.*
    <out>/<design>/<floor>/partition/    <method>-<hash8>.json
    <out>/<design>/<floor>/graphlets/    orbits-<backend>-<removal>.npz graphlets-<backend>-<removal>.json
    <out>/<design>/<floor>/structural/   structural-<variant>.npz structural-<variant>.json
    <out>/gnn/                           config.json vocab.json model.pt metrics.json predictions-<design>.csv
    <out>/metrics.json                   numbers for the Wyrd step

The GNN baseline follows GNN-RE (Alrahis et al., "GNN-RE: Graph Neural Networks for Reverse
Engineering of Gate-Level Netlists", IEEE TCAD, doi:10.1109/TCAD.2021.3110807;
github.com/DfX-NYUAD/GNN-RE) and the GNN4IC list (github.com/DfX-NYUAD/GNN4IC; Alrahis,
Knechtel, Sinanoglu, "Graph Neural Networks: A Powerful and Versatile Tool for Advancing Design,
Reliability, and Security of ICs", ASP-DAC 2023, arXiv:2211.16495); it is a baseline for the
same task on L0 labels, not a re-implementation, and its numbers are not compared with theirs.

Graphlet orbit counts use ORCA: Przulj, Bioinformatics 23(2):e177-e183, 2007,
doi:10.1093/bioinformatics/btl301; Hocevar and Demsar, Bioinformatics 30(4):559-565, 2014,
doi:10.1093/bioinformatics/btt717 (`loki analyze graphlets --licence` prints this citation).
ORCA is GPL-3.0 and runs as a separate program, never linked or vendored; fetch and build the
pinned source into `~/.cache/loki/tools/orca-e146a8b/` with `loki tools fetch-orca`.

Acceptance and scale: `python -m unittest tests.test_acceptance_l2 -v` (spec 12; the GNN item
uses `$LOKI_L0_DATASET` when set) and `LOKI_SCALE=1 python -m unittest tests.test_scale_l2 -v`
(spec 3 budgets; run it alone, never beside Odin III sweeps).
