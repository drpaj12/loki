# Loki L2: analysis plugins (design)

Status: decisions approved by Peter, 2026-10-21 (section 2, items 1 to 5), with the graphlet spike result
(`work/controller-scripts/briefs/graphlet-spike.md`) and the controller's two decisions on it folded in:
ORCA as the default graphlet backend, and Peter's global-signal classification before counting (section 8).
Nothing is left open except the questions of section 14, each with a recommendation.

Amended 2026-10-21 (branch `docs/wl-npn`) with two features Peter approved that day, built in Loki III
L1 (`loki.features`, L1 spec 6.7, L1 plan Task 5a) because L1 is built before L2: colour refinement
(1-WL colours) and functional node features (NPN classes). L2 consumes them: the shared signal
classifier (8.1), structural features and GSN-style vectors (4.1), the PyG export (5), the graphlet
features (8.6) and a 1-WL baseline for the GNN (9). New open questions are section 14, items 8 to 11.

## 1. Goal

L2 turns a netlist graph into things L1 (the Bayesian hypothesis flow) and Peter can use: exports for
other tools, partitions of the netlist, graphlet signatures per node, and a baseline graph neural
network that predicts L0's labels. Every analysis is a plugin `loki.analysis.<name>`, runs from the
command line (`loki analyze <kind>`) and as a Wyrd step. There is no LLM step.

Inputs are L0 files only (`graph.json`, optionally `labels.csv` content that `graph.json` already carries,
and `manifest.json` for the split). An analysis never reads `key.json` (original names) and never
reads the BLIF. A `graph.json` without labels is valid input to every analysis except the GNN trainer
(real reverse engineering of an unlabelled netlist is the use case L2 serves, so labels stay optional).

**Done when** (acceptance, section 12): on the L0 micros dataset (floor F2) all four analyses run from
the CLI and as Wyrd steps, every output is deterministic, the partitions load as L1 evidence, the GNN beats
the majority baseline on the test designs, and a 100k-node synthetic graph runs inside the budgets of
section 3.

## 2. Decisions

| # | Decision |
|---|---|
| 1 | Export a whole netlist or a region (cone, cluster, hypothesis) to edge list, GraphML and PyTorch Geometric; node features: cell type, fan-in, fan-out, depth, floor; labels when present. |
| 2 | Clustering: k-means, affinity propagation, spectral (scikit-learn, optional extra `loki[analysis]`), Louvain (networkx). Each partition is stored per run and fed to L1 as evidence. |
| 3 | Graphlets must evaluate a FULL netlist. One interface `GraphletCounter`, two backends: external tool (subprocess; edge list in, per-node orbit counts out) and own implementation (orbits up to 4 nodes). Decided by the spike: default = ORCA (separate process, GPL-3, fetched not vendored); own backend optional and later. Before counting, global signals (clock, reset, constant, global enable) are classified by role, their edges removed and kept as node features (Peter); a degree-threshold hub drop (default 1000) is only the fallback. |
| 4 | GNN: PyG export plus a baseline node classifier (GraphSAGE, GCN) on L0 labels, train and test by L0's design split. Cite GNN4IC and GNN-RE. torch and PyG are an optional extra `loki[gnn]`; tests skip without them. |
| 5 | Each analysis is a plugin `loki.analysis.*`, runnable as a Wyrd step (entry point group `wyrd.steps`) and from `loki analyze <kind>`. |

Agent defaults (Peter may override), all in the sections named: the evidence record is `Partition`
(section 6); features are netlist-visible only (section 4); affinity propagation runs on a sample
(section 5.2); the GNN trains full-batch per design, no neighbour sampler (section 8).

## 3. Scale, budgets, determinism

Target: VTR's largest designs. The spike's graphs (undirected simple projection of the golden k6 BLIFs):
diffeq1 1233 nodes / 2226 edges; or1200 12248 / 24516 (max degree 2584); mcml 286515 / 630712 (max degree
47461); LU64PEEng 819483 / 1611165 (max degree 246427). Graphlets are budgeted on these. The other analyses
are measured on this WSL machine (Python 3.12, scikit-learn 1.9.1, networkx 3.7, scipy 1.18.1,
numpy 2.5.4, torch 2.14.1 cpu, torch_geometric 2.8.1) on a synthetic netlist-like graph of 100k nodes,
306k undirected edges, a 20k-fan-out hub, 246 components:

| Operation | Measured | Budget at 100k nodes (fail the scale test above 2x) |
|---|---|---|
| Louvain (`louvain_communities`) | 35 s, 0.45 GB | 120 s, 2 GB |
| Spectral embedding, 8 vectors (`spectral_embedding`, lobpcg or arpack) | 7 s, 0.45 GB | 60 s, 2 GB |
| k-means on 12-column features (`MiniBatchKMeans` / `KMeans`) | 0.2 s / 1 s | 30 s, 1 GB |
| Affinity propagation | 1.6 s at n=2000, 13.8 s and 1.2 GB at n=5000 (dense n x n) | sample of 3000: 10 s, 1 GB |
| GraphSAGE layer, full graph, 64 hidden | 0.04 s forward | one training epoch 10 s, 3 GB |
| `graph.json` load + featurize | not measured | 30 s, 2 GB |
| Edge list / GraphML / PyG export | not measured | 60 s each, 3 GB |
| Graphlets, ORCA, size 4, `--removal global` (LU64PEEng, 819k nodes, 1.6M edges) | 2 s, 1.06 GB (spike) | 10 s, 2 GB |
| Graphlets, ORCA, size 5, `--removal global` (LU64PEEng) | 18 s, 1.7 GB (spike); mcml 10 s, 0.6 GB | 60 s, 3 GB |
| Graphlets, ORCA, size 4, `--removal none` (mcml 287k nodes / LU64PEEng) | 56 s, 0.56 GB / 12 min 54 s, 1.49 GB (spike) | mcml 3 min; LU64PEEng 30 min, 3 GB |
| Graphlets, ORCA, size 5, `--removal none` | mcml did not finish in 30 min (spike) | refused without `--force` |
| Global-signal classification, 820k nodes | not measured | 60 s, 2 GB |
| Colour refinement, one variant, 4 rounds (`loki.features.wl.refine`, pure Python) | not measured | 30 s, 1 GB (L1 spec 6.7 estimate); 820k nodes 240 s, 8 GB |
| Coarsest equitable partition (`stable_partition`) | not measured | 60 s, 1 GB; 820k nodes 480 s, 8 GB |
| NPN classes of all distinct LUT tables (`npn_class`, cached) | not measured | 60 s, 0.5 GB |

Rules:

- **No dense N x N matrix anywhere.** Adjacency is `scipy.sparse.csr_matrix`. Affinity propagation, whose
  similarity matrix is dense (memory grows with n squared), runs only on a sample (section 5.2).
- Spectral clustering uses `sklearn.manifold.spectral_embedding` on the sparse adjacency of the largest
  connected component, then k-means (section 5.3); `SpectralClustering` is not used on full netlists.
- **Determinism.** Every analysis takes `seed: int` (default 0) and records it. Node order is the order
  of `graph.json`; cluster numbers are canonical (clusters ordered by their lowest node index). Same
  input, same library versions, same seed gives byte-identical JSON/CSV outputs. Floats in JSON are
  rounded to 6 decimals. Library versions are written into every output (`versions`). `.pt` and `.npz`
  files are compared by content (tensors, arrays), not bytes. Torch runs on CPU with
  `torch.use_deterministic_algorithms(True)` and `torch_geometric.seed_everything(seed)`; across
  different machines or library versions GNN metrics may differ in the 4th decimal.
- Counts that can exceed 2^31 (a hub of degree d has C(d,3) star triples) are `int64` end to end.

## 4. Graph model, features, regions (`loki.analysis.graphio`, `region`)

`load_graph(path)` reads a `graph.json` (L0 spec 6.4, validated by `loki.schemas.validate_graph`) into a
frozen `Graph`: `node_ids` (`n<k>` strings in file order), `kind`, numeric feature columns, `table` (the
integer `lut_table` of every node, -1 when the node has no table; the JSON file form stays the hex
string), directed edge arrays `src` and `dst` (indices into `node_ids`, driver to sink, one per `edges`
item, parallel edges kept), `pin` and `net` per edge, optional `labels` (column name to array), `floor`,
`design`, and `sha256` of the file bytes.

**Features** (`featurize`), all derived from the netlist, none from provenance labels. Columns, in order:

1. numeric (8): `fan_in`, `fan_out`, `level` (this is the "depth"), `lut_width`, `is_seq`, `is_const`,
   `hard_ports`, `lut_ones` (number of 1 bits of `lut_table`, 0 when empty);
2. kind one-hot (7): `pi, po, lut, ff, const, hard, gate`;
3. floor one-hot (4): `f1-k6, f1-earch, f2, f3`;
4. hard cell type one-hot (T + 1): the vocabulary `hard_types` (sorted names, last column `<unk>`) over the
   `cell_type` label of nodes with kind `hard`; all zero for other kinds and for graphs without labels.
   `cell_type` is the final cell's Odin III type, visible in the netlist; it is not an answer.

The label columns `construct_type`, `construct_types`, `n_construct_cells`, `module_path`, `bus_name`,
`bit_index`, `role`, `hdl_*`, `n_spans` are never features (they are the answer key). A test pins this.
Models transform count columns with `log1p` and standardise (`StandardScaler`) inside the model code; the
exported matrix is raw.

**Regions.** `Region(kind, node_ids)` is a set of node ids; `Graph.induced(region)` returns the induced
subgraph (edges with both ends inside), node order kept, feature values kept as measured on the whole
netlist (fan-in and fan-out are not recomputed). Constructors: `cone(graph, roots, direction, depth)`
(`direction` `in` = transitive fan-in, `out` = fan-out, `both`; `depth` None = unbounded; a flip-flop does
not stop the walk), `from_partition(partition, cluster)`, `from_nodes(graph, ids)` (a hypothesis from
L1 supplies its node ids this way). Unknown ids or an empty region raise `RegionError`. CLI spelling of
`--region`: `cone:<id>[,<id>...]:<in|out|both>:<depth|all>`, `cluster:<partition.json>:<int>`,
`nodes:<file with one id per line>`.

### 4.1 Structural features from `loki.features` (`loki.analysis.structural`)

L1's `loki.features` (L1 spec 6.7) is standard-library code shared by L1 and L2. L2 adapts a `Graph`
with `to_feature_graph(g)` (`loki.analysis.graphio`; node order and ids of `graph.json`, `lut_table` hex
to an integer table, pins and nets as in the file; it equals `loki.features.graph.from_graph_json` on the
same file, a test pins it) and computes:

- **role flags** with `loki.features.roles.classify_nets` (section 8.1);
- **WL colours** with `loki.features.wl.refine`, default variant `npn/both` (`--wl-variant
  table/both` on request), `WL_ROUNDS = 4` rounds: per node the colour of rounds 0 to 4 (16-hex
  SHA-256 strings, comparable across designs), the `stable_round`, and with `--quotient` the coarsest
  equitable partition and its quotient graph;
- **NPN classes** with `loki.features.npn.npn_class` for every node with a LUT table (exact canonical
  form, key `"<support size>:<hex>"`; nodes without a table get the empty key).

Numeric ids: `hash64(s)` = the first 8 bytes of `sha256(s)` as a signed big-endian int64 (0 for the empty
string), so WL colours and NPN keys have ids comparable across designs and exports without a shared
vocabulary. **GSN-style vector** of a node (after Bouritsas, Frasca, Zafeiriou and Bronstein, "Improving
Graph Neural Network Expressivity via Subgraph Isomorphism Counting", IEEE TPAMI 2023, arXiv:2006.09252):
its graphlet orbit counts (8.4, when an orbit file exists), its four role flags (8.2), its NPN class id and
its WL colour ids per round. Counts and flags are numeric columns; NPN and WL ids are categorical and are
never fed to a model as numbers (the GNN embeds them, section 9; clustering does not use them).

Output: `<out>/<design>/<floor>/structural/structural-<variant>.npz` (arrays `wl` int64 (N, 5) of
`hash64` colour ids, `npn` int64 (N,), `roles` int64 (N, 4), `node_ids`; with `--quotient` also
`stable_class` int64 (N,)) and `structural-<variant>.json` (`{"schema": 1, "kind": "structural",
"design", "floor", "variant", "rounds", "stable_round", "classes_per_round", "npn": {"distinct_tables",
"classes", "exact", "worst_enum"}, "npn_keys", "colours", "quotient", "graph_sha256", "seconds",
"versions"}`): `npn_keys` (per node) and `colours` (per round, per node) hold the strings behind the ids;
`quotient` is `{"n_classes", "edges"}` or `null`. `seconds` is excluded from the determinism test.

## 5. Exports (`loki.analysis.export`)

Written for the whole graph or a region into `<out>/<design>/<floor>/export/` (`stem` is `whole` or
`region-<hash8>` of the region spec):

| Format | File | Content |
|---|---|---|
| edge list | `<stem>.edges.tsv` | `src<TAB>dst` per directed edge, ids as in `graph.json`, sorted as in `graph.json`; header-free |
| edge list nodes | `<stem>.nodes.tsv` | `id<TAB>kind<TAB>feature...` with a header row; labels appended when present |
| GraphML | `<stem>.graphml` | `networkx.DiGraph` through `networkx.write_graphml`; node attributes = features and labels (strings and numbers; empty strings kept), edge attributes `pin`, `net`; graph attributes `design`, `floor` |
| PyG | `<stem>.pt` | a plain dict saved with `torch.save`: `x` (float32 N x F), `edge_index` (int64 2 x E, driver to sink), `node_ids` (list of str), `feature_names` (list), `hard_types` (list), `y_construct_type` and `y_role` (int64 N, -1 where unlabelled) when labels exist, `vocab` (the two label vocabularies), `design`, `floor`, `split` (when taken from a dataset); the structural block of 4.1 unless `--no-structural`: `gsn_roles` (int64 N x 4), `gsn_npn` (int64 N), `gsn_wl` (int64 N x 5), `npn_keys` (list of str), `wl_variant`, and `gsn_orbits` (int64 N x 15 or 73) with `gsn_orbits_source` (backend and removal) only when an orbit file for the graph exists (export never runs a graphlet backend). `load_pyg(path) -> torch_geometric.data.Data` builds the `Data` object. |

A plain dict, not a pickled `Data`, is saved because torch 2.6+ defaults to `weights_only=True` loading.
The label vocabularies of an export of one design come from that design alone (class indices are not
comparable across exports); the GNN trainer builds its own from the training designs (section 8).

## 6. Partitions and the L1 evidence interface (`loki.analysis.partition`)

L1's spec was not available when this was written. L2 therefore defines the minimal record and L1 adapts
to it (open question 1):

```
Partition (frozen): design, floor, method, params (dict), seed, graph_sha256, node_ids (tuple[str]),
  assignment (tuple[int], one cluster number per node, 0..K-1, no gaps), quality (dict), versions (dict),
  sampled (dict | None, default None), components (int | None, default None)
  .n_clusters  .members(c) -> tuple[str]  .cluster_of(node_id) -> int  .sizes() -> list[int]
  .key -> str   # "<method>:<hash8>", the evidence identity
load_partition(path) -> Partition      write_partition(partition, dir) -> Path
```

File `<out>/<design>/<floor>/partition/<method>-<hash8>.json` (`hash8` = first 8 hex of sha256 of the
canonical JSON of `{method, params, seed, graph_sha256}`, so one configuration has one file name).
The hash's canonical JSON is compact with sorted keys (`json.dumps(payload, sort_keys=True,
separators=(",", ":"), ensure_ascii=False)`, not `dump_json`'s indented form), and it covers `params`
as stored, floats rounded to 6 decimals:

```json
{"schema": 1, "kind": "partition", "design": "micro_x", "floor": "f2", "method": "louvain",
 "params": {"resolution": 1.0}, "seed": 0, "graph_sha256": "...", "n_nodes": 123, "n_clusters": 7,
 "node_ids": ["n0", "n1", "n2", ...], "assignment": [0, 0, 1, ...],
 "quality": {"modularity": 0.51, "size_min": 3, "size_median": 14, "size_max": 40,
             "nmi_module_path": 0.62, "ari_module_path": 0.4, "nmi_construct_type": 0.2},
 "sampled": null, "components": null,
 "versions": {"numpy": "...", "networkx": "...", "scikit-learn": "..."}}
```

`node_ids` holds the ids in `graph.json` order, so the record names its own nodes and
`members(c)`/`cluster_of(id)` need no graph. `sampled` records a node sample the method worked on
(affinity propagation) and `components` the connected component count spectral clustering measured;
both are `null` when the method did not look. `assignment` is aligned to `graph.json` node order.
`modularity` is computed on the undirected simple
projection (`networkx.community.modularity`; for 100k nodes this takes a few seconds). The `nmi_*` and
`ari_*` keys (`sklearn.metrics.normalized_mutual_info_score`, `adjusted_rand_score`) compare the partition
with the ground truth `module_path` and `construct_type` over nodes of kind `lut`, `ff`, `hard`, `gate`;
each is `null` per column: when the graph has no labels, when that label column is absent, or when fewer
than two nodes of kind `lut`, `ff`, `hard` or `gate` carry a label in it. They are a quality report for Peter and tests, never an
input to a method. Pre-existing hierarchy (`module_path`) is exactly what L1 climbs, so these numbers
are the L2 acceptance signal for "clusters recover modules".

A partition is a **set of candidate blocks**: L1 treats `members(c)` as a node set that a hypothesis may
adopt (via `Region.from_partition`). L1 chooses which methods and parameters to run; `loki analyze cluster
--method all` runs all four with defaults.

## 7. Clustering methods (`loki.analysis.cluster`)

Common: input `Graph`, `seed`, output `Partition`. Undirected simple projection `A` (symmetric 0/1 CSR,
no self-loops, parallel edges merged) is built once by `undirected_adjacency(graph)`.
`k` is an int or `"auto"`; `auto` = `clip(round(sqrt(N / 2)), 2, 200)`, then `min(k, N)`. N below 2 gives
one cluster. All methods number clusters canonically.

### 7.1 k-means (feature space)

`sklearn.cluster.KMeans` when N <= 20000, else `MiniBatchKMeans`; `n_init=3`, `random_state=seed`.
Space (section 4 minus the floor block, the hard-type one-hot and `is_seq`/`is_const`), in column
order: the six numeric features `fan_in`, `fan_out`, `level`, `lut_width`, `hard_ports`, `lut_ones`,
`log1p`-scaled and standardised with `StandardScaler` (a constant column stays, as zeros); the kind
one-hot block; then optional extra columns (graphlet signatures, section 8.6, passed in as an
array). `is_seq` and `is_const` are covered by the `ff` and `const` kind one-hot columns and are
intentionally excluded (plan Task 7 pins the six-feature space). Params recorded: `k`, `features`
(one name per space column, in order: the six numeric names, `kind:<kind>` per one-hot column,
`extra:<i>` per extra column), `algorithm` (`"kmeans"`, `"minibatch"`, or `"none"` when fewer than
two clusters were asked for or are possible) and `convergence_warning` (whether sklearn raised a
`ConvergenceWarning`; always false for `"none"`).

### 7.2 Affinity propagation (feature space, on a sample)

`sklearn.cluster.AffinityPropagation` builds a dense n x n similarity matrix, so it never sees the full
netlist (measured: 1.2 GB at n=5000). Decision: take a sample of `min(N, max_points)` nodes
(`max_points` default 3000, a seeded `numpy.random.default_rng(seed).choice(N, size, replace=False)`,
sorted), run AP on the sample's feature rows (same space as k-means), then assign every other node to
the nearest exemplar by Euclidean distance (`cluster_centers_`, computed in chunks of 10000 rows so memory
stays at chunk x exemplars). Sampled nodes keep their own AP cluster. The partition records
`"sampled": {"points": n}`. `damping=0.5`, `max_iter=200`, `convergence_iter=15`, `preference=None`
(library default: median similarity), `random_state=seed`. If AP does not converge (sklearn then sets all
labels to -1 and warns) the method retries once with `damping=0.95, max_iter=400`; if that fails too it
raises `ClusterError("affinity propagation did not converge")` and the step exits 1. When the sample
is all identical rows AP gives one cluster; that is returned as is.

### 7.3 Spectral (graph structure)

1. `scipy.sparse.csgraph.connected_components(A)`. Let L be the largest component (ties: lowest node).
2. If |L| < 3 or k < 2: every component is one cluster.
3. Else `sklearn.manifold.spectral_embedding(A_L, n_components=min(k, |L|-1), eigen_solver="lobpcg"
   if |L| > 5000 else "arpack", random_state=seed, drop_first=False)`, rows scaled to unit L2 norm
   (zero rows stay zero), then k-means (`n_init=3`, `random_state=seed`, `MiniBatchKMeans` above 20000 rows)
   with `n_clusters=min(k, |L|)`.
4. Every other connected component becomes one cluster of its own, numbered after L's by its lowest node.
   That order is provisional: `make_partition` relabels every number canonically 0..K-1 by lowest node
   index (section 3), and that stored order is the final one. Hundreds of tiny components are normal in a
   netlist (constants, unused logic); the partition records `"components": C`.
Params recorded: `k`, `n_components`. (`sklearn.cluster.SpectralClustering` is not used: its sparse path
is not tested at this scale and it hides the component handling.)

### 7.4 Louvain (graph structure)

`networkx.community.louvain_communities(G, weight=None, resolution=resolution, seed=seed)` on the
`networkx.Graph` built from `A` (`networkx.from_scipy_sparse_array`); `resolution` default 1.0. Result
sets are numbered canonically. No `k`. Params recorded: `resolution`.

## 8. Graphlets (`loki.analysis.graphlets`)

A graphlet degree vector (GDV) of a node counts, per automorphism orbit, how many induced connected
subgraphs touch the node in that orbit (Przulj 2007). Peter requires the FULL netlist: every node gets a
signature, nothing is sampled. The spike (2026-10-21, `briefs/graphlet-spike.md`) decided the tool and
showed what makes it feasible: ORCA's cost is driven by hubs (clock, reset, constant nets), not by size.

### 8.1 Global-signal classifier (`loki.analysis.graphlets.signals`)

Before counting, nets that carry a global signal are classified by role from `graph.json` alone; their
edges are removed from the counting graph and kept as node features (Peter, 2026-10-21: a node with a
clock is a specialised node type). `classify_signals(g, cfg) -> SignalInfo` groups edges by `net` (the
driver, the sink pins). `SignalConfig(min_fanout=16, dominance=0.8)`; clock and constant detection need no
fan-out threshold. The rules below are implemented once, in `loki.features.roles` (L1 spec 6.7, L1 plan
Task 5a; L1 needs them first, for its start colours); `classify_signals` adapts the `Graph` with
`to_feature_graph` (4.1), calls `classify_nets` and builds the arrays of `SignalInfo` (open question 10).

| Class | Rule |
|---|---|
| `const` | the net's driver has kind `const` (any fan-out). |
| `clock` | at least one sink pin is a clock pin: pin name `CLK` on a node of kind `ff` (L0 spec 6.4), or on a `hard` node a pin whose lower-case name starts with `clk` or `clock`. Latch enables (`EN`) are not clocks. Clock domains are numbered 1..D by the lowest driver node index of the clock nets; every sink node of a clock net gets that domain id. |
| `reset` | not clock or const; fan-out >= `min_fanout`; at least `dominance` of its sinks are *D-LUTs* (a LUT whose output net feeds only flip-flop `D` pins) in which the net is a *forcing input*: for some value v of that input the LUT output is constant whatever the other inputs are. A `hard` sink pin whose lower-case name starts with `rst`, `reset`, `clr` or `clear` also counts as a reset sink. |
| `enable` | not clock, const or reset; fan-out >= `min_fanout`; at least `dominance` of its sinks are D-LUTs in which, for some value v of the net, the LUT output equals the D-LUT's own flip-flop output (the hold path of a clock-enable mux). A `hard` sink pin named `en`/`enable`/`ce` (lower case, prefix) also counts. |
| `signal` | everything else. |

LUT semantics use `lut_table` (hex, MSB first) with address bit k = input `I<k>` (L0 spec 6.4); the helper
`lut_restrict(table, width, pin_index, value)` returns the restricted table and a test pins the
convention against the L0 fixture (L0 Task 4 Step 6 fixes the bit order; this helper follows
`loki.blifout.LUT_ROW_ORDER`). `SignalInfo` holds a per-edge class array, one entry per `Graph` edge in
`graph.json` order (an edge's class is the class of its `net`), and the per-node features of 8.2.
A reset deasserted by a LUT that merges several resets, or a reset hidden in the data logic of a LUT of
more than the D-LUT shape, is not found; those nets stay `signal` and the hub fallback (8.3) catches them
if their fan-out is high. This is stated in the output (`classified`: counts per class).

### 8.2 Role features per node

Kept for every node of the original graph, whatever the removal: `clock_domain` (int, 0 = none),
`has_reset` (0/1: the node is a sink of a `reset` net, or is a flip-flop whose `D` driver has it),
`const_inputs` (count of in-edges from `const` drivers), `enable` (0/1, defined like `has_reset` for
`enable` nets). A node's graphlet signature is its orbit vector plus these four numbers
(`graphlet_features` returns both blocks). Typed (coloured) graphlets, where the role is part of the
subgraph, are a later option; ORCA has no node colours (section 13).

### 8.3 Counting graph and variants

The counting graph is the undirected simple projection of the original graph (one node per graph node, an
edge per connected driver-sink pair, direction dropped, self-loops and duplicates removed; PI/PO
pseudo-cells are nodes). Two variants, selected by `--removal`:

- `global` (default): remove every edge whose net class is not `signal` (8.1), then the **hub fallback**:
  every node whose degree in what remains exceeds `hub_threshold` (default 1000) loses all its edges.
  Removed nodes stay in the graph with all-zero orbits, so rows align with `node_ids`. The output lists
  the removed hub nodes with their degrees (`dropped_hubs`), the number of removed edges per class, and
  `classified`.
- `none`: no removal. Allowed for size 4 (LU64PEEng 13 min, section 3); for size 5 it is refused with
  exit 3 unless `--force` is given (measured: full 5-node mcml did not finish in 30 min).

Sizes: 4 (15 orbits, default) and 5 (73 orbits; ORCA only).

### 8.4 Orbits (size 4, 15 orbits)

Orbit numbers follow the standard 2- to 4-node numbering (graphlets G0 to G8, orbits 0 to 14), the
numbering ORCA prints (checked: ORCA on a 4-cycle gives `2 2 1 0 0 0 0 0 1 0 0 0 0 0 0` per node). An orbit
is a node's role in a connected induced subgraph:

| Orbit | Subgraph (nodes) | Role |
|---|---|---|
| 0 | edge (2) | either end (= node degree) |
| 1, 2 | path P3 (3) | end node, middle node |
| 3 | triangle (3) | any node |
| 4, 5 | path P4 (4) | end node, inner node |
| 6, 7 | star K1,3 (4) | leaf, centre |
| 8 | cycle C4 (4) | any node |
| 9, 10, 11 | tailed triangle (4) | pendant node (degree 1), degree-2 triangle node, degree-3 triangle node |
| 12, 13 | diamond (4) | degree-2 node, degree-3 node |
| 14 | clique K4 (4) | any node |

Output: `int64` array `orbits` of shape (N, 15) or (N, 73).

### 8.5 Interface and backends

```
class GraphletCounter(Protocol):
    name: str                     # "ext" (ORCA) or "own"
    max_size: int                 # ext: 5, own: 4
    def available(self) -> tuple[bool, str]       # (ok, reason when not)
    def count(self, n: int, src: ndarray, dst: ndarray, size: int = 4) -> ndarray  # int64 (n, orbits(size))
```
`src`, `dst`: int32 arrays of a simple undirected graph, each edge once, `src < dst`. File protocol
shared by both backends: input text file, first line `N M`, then M lines `u v` (0-based, no self-loops,
no duplicates; ORCA rejects them); output N lines of space-separated orbit counts. Backends are in
`BACKENDS`; **`DEFAULT_BACKEND = "ext"`** (decided by the spike). Selection: `--backend ext|own|default`.

- **External backend = ORCA** (`ext.py`): `thocevar/orca`, single file `orca.cpp`, GPL-3.0 (repository
  `LICENSE`; `orca.cpp` has no per-file header; the CRAN `orca` package says LGPL-3 in `DESCRIPTION` but GPL
  v3 or later in its source header, so Loki treats ORCA as GPL-3). It runs as a **separate process**
  (`orca node <4|5> <in> <out>`, via `subprocess.run` with an argv list), never linked, included or
  vendored, so the MIT repository stays MIT. ORCA prints progress to stdout; Loki captures and discards it.
  `loki tools fetch-orca` downloads `orca.cpp` at the pinned commit
  `e146a8b1a99a90f5e3096b7bcc2ab0ea246c3ca7` (master, 2016-11-15) from
  `https://raw.githubusercontent.com/thocevar/orca/<commit>/orca.cpp`, checks its SHA-256
  `01c580febfd3653a632a04d6b466f7c6f2bf2f9baf3a75a2e553be30ac7ee778` (both checked 2026-10-21; 1478
  lines), builds `g++ -O2 -std=c++11 -o orca orca.cpp` into `~/.cache/loki/tools/orca-e146a8b/` (verified:
  builds clean, no extra includes), and `loki analyze graphlets --licence` prints the GPL-3 notice and
  the citations. The tool path is `--graphlet-tool`, else `$LOKI_GRAPHLET_TOOL`, else that cache.
  ORCA allocates an edge-orbit table (68 x 8 bytes per edge) even in node mode: 1 to 1.7 GB RSS on the
  largest graphs.
- **Own backend** (`own.py`, `native/orbits4.c`), **optional, later** (plan Tasks G-own-1, G-own-2): a
  4-node C99 counter with ORCA as the oracle. Estimated 1 to 5 s and under 200 MB on LU64PEEng without any
  removal (degree-ordered triangle counting, O(m * arboricity)), against ORCA's 13 minutes. It is not the
  default and not needed for L2 to be done.

Integer results of the two backends must be identical on every test graph (cross-check test, when both exist).

### 8.6 Output

`<out>/<design>/<floor>/graphlets/orbits-<backend>-<removal>.npz` (arrays `orbits` int64 (N, K),
`roles` int64 (N, 4) with columns `clock_domain, has_reset, const_inputs, enable`, `node_ids` unicode (N,))
and `graphlets-<backend>-<removal>.json`: `{"schema":1, "kind":"graphlets", "design", "floor", "backend",
"tool": {"name","commit","sha256","licence"}, "size", "n_orbits", "removal", "hub_threshold",
"signal_config", "classified": {"clock": nets, "reset": nets, "enable": nets, "const": nets},
"removed_edges": {"clock": e, "reset": e, "enable": e, "const": e, "hub": e}, "dropped_hubs": [{"id",
"degree"}], "clock_domains": D, "n_nodes", "n_edges", "graph_sha256", "seconds", "versions"}`. `seconds` is
the only non-deterministic key and is excluded from the determinism test. The feature block
(`graphlet_features(orbits, roles)`): `log1p` of the orbits then per-column standardisation, constant
columns dropped, then `roles` appended as is (`clock_domain` as the domain id; clustering treats it as a
number, models may one-hot it). `gsn_features(orbits, roles, structural)` returns that numeric block plus
the categorical block (NPN id and WL ids per round, section 4.1) for the GNN. Clustering and the GNN accept it with `--features node,graphlet`; if
the orbit file for that graph, backend and removal is missing the runner computes it first.

## 9. GNN baseline (`loki.analysis.gnn`, extra `loki[gnn]`)

Citations (verified 2026-10-21): GNN-RE is Alrahis, Sengupta, Knechtel, Patnaik, Saleh, Mohammad,
Al-Qutayri, Sinanoglu, "GNN-RE: Graph Neural Networks for Reverse Engineering of Gate-Level Netlists",
IEEE Transactions on Computer-Aided Design of Integrated Circuits and Systems, DOI
10.1109/TCAD.2021.3110807 (IEEE early access September 2021, article 9530566; the volume and issue of the
print version were not confirmed, the year in print is 2022 per Peter; code: github.com/DfX-NYUAD/GNN-RE,
no licence stated on the page). GNN4IC is the paper list at github.com/DfX-NYUAD/GNN4IC and its companion
paper Alrahis, Knechtel, Sinanoglu, "Graph Neural Networks: A Powerful and Versatile Tool for Advancing
Design, Reliability, and Security of ICs", ASP-DAC 2023 (arXiv:2211.16495). GNN-RE maps each gate of a flat
gate-level netlist to the module (arithmetic block type) it belongs to; Loki's L0 labels are the analogue
for LUT and gate netlists. Loki's model is a baseline for the same task, not a re-implementation of
GNN-RE; numbers are not compared with the paper's (different cells, labels and benchmarks).

**Task.** Node classification on one floor (default `f2`). Target `construct_type` (default) or `role`.
Loss and metrics only over nodes of kind `lut`, `ff`, `hard`, `gate` with a known target (PI, PO and
constants are trivially labelled and would inflate accuracy).

**Split.** Exactly L0's: designs whose `manifest.json` split is `train` train, the rest are test; designs
whose floor entry is not `ok` are skipped. No validation set and no early stopping: the epoch count is
fixed, so nothing is tuned on the test designs. (Hyperparameter tuning, if wanted later, must carve a
validation set out of the train designs by a new seeded rule; that is out of scope.)

**Vocabulary.** From the train designs only: target values with at least `min_count` (default 5) train
nodes get indices 0..C-1 sorted by name, everything else (including values first seen in the test designs)
maps to the class `__other__` (index C). Saved as `vocab.json`.

**Model.** `torch_geometric.nn.SAGEConv` (default, mean aggregation) or `GCNConv`, 2 layers, hidden 64,
ReLU, dropout 0.2, then a linear layer to C+1 logits. Input: the section 4 feature matrix with `log1p` on
count columns and standardisation fitted on the train nodes. Edges: the directed edge list plus its
reverse (`torch_geometric.utils.to_undirected`). Adam, lr 0.01, weight decay 5e-4, 100 epochs, cross
entropy with class weights `1/sqrt(count)` normalised to mean 1. Training is **full-batch per design**,
gradients summed over the train designs of an epoch; no neighbour sampler, because `NeighborLoader`
needs `pyg-lib` or `torch-sparse`, which are not in the extra (verified: `ImportError` without them).
Full-batch SAGE on 100k nodes is 0.04 s forward on this machine.

**Outputs** in `<out>/gnn/`: `config.json`, `vocab.json`, `model.pt` (`state_dict` plus scaler arrays),
`metrics.json`, `predictions-<design>.csv` for each test design (`node_id,true,pred`, `true` and `pred`
as class names). `metrics.json`: per split (`train`, `test`) `accuracy`, `macro_f1`
(`sklearn.metrics.f1_score(average="macro")`), `n_nodes`, `n_designs`, and the same for two baselines
computed on the same nodes: `majority` (most common train class) and `logreg` (features only, no graph:
`sklearn.linear_model.LogisticRegression(max_iter=1000, random_state=seed)`), so the graph's value is
visible. Floats rounded to 4 decimals.

**1-WL baseline** (Peter, 2026-10-21: the GNN must beat WL-colour classification on L0 labels). Baseline
`wl` predicts, for each node, the majority train class of its WL colour (variant `npn/both`), backing off
from round 4 to round 0 when a colour has fewer than `min_count` train nodes, and to the `majority` class
when no round qualifies. It is computed on the same nodes and written as `baselines.wl` next to the others;
`metrics.json` adds `beats_wl` (test `macro_f1` of the GNN greater than that of `wl`). Message-passing GNNs
of this kind are at most as discriminating as 1-WL (Xu, Hu, Leskovec and Jegelka, "How Powerful are Graph
Neural Networks?", ICLR 2019; Morris et al., AAAI 2019), so the GNN can only win by generalising better
than a colour lookup; on small datasets the lookup may win, which is a finding (open question 8).

**Structural inputs** (optional, `--features node,graphlet,wl,npn`): `graphlet` appends the numeric block
of 8.6; `wl` and `npn` add embeddings (size 8) of the NPN id and the round-2 WL id over a train vocabulary
(ids with at least `min_count` train nodes, the rest `__other__`), concatenated to the input of the first
layer. The default stays `node` so the baseline numbers do not move.

Honest limit stated in every `metrics.json` (`"note"`): a LUT merges the logic of several constructs; its
label is the primary construct (L0 spec 5.3), so accuracy has a ceiling below 1.

## 10. Plugin surface

**Modules.**

```
loki/analysis/
  __init__.py     KINDS = ("export","cluster","graphlets","gnn","structural"); MissingExtra; require(extra)
  graphio.py      Graph, load_graph, featurize, undirected_adjacency, iter_dataset, DatasetEntry
  region.py       Region, RegionError, cone, from_partition, from_nodes, parse_region
  partition.py    Partition, load_partition, write_partition, quality
  structural.py   hash64, StructuralArrays, run_structural, load_structural   (4.1; plan Task 10a)
  export.py       export_graph(graph, region, formats, out) -> list[Path]; load_pyg
  cluster.py      cluster_kmeans, cluster_affinity, cluster_spectral, cluster_louvain, run_cluster
  graphlets/
    __init__.py   GraphletCounter, BACKENDS, DEFAULT_BACKEND = "ext", counting_graph, graphlet_features, gsn_features, run_graphlets
    signals.py    SignalConfig, SignalInfo, classify_signals, lut_restrict   (plan Task 9)
    ext.py        OrcaCounter, fetch_orca, find_orca   (plan Task G-ext)
    own.py        OwnCounter, count_reference   (optional, later: plan Tasks G-own-1, G-own-2)
    native/orbits4.c
  gnn.py          build_vocab, train_eval, run_gnn
  run.py          main(argv) -> int  (python -m loki.analysis.run <kind> ...)
  steps.py        ExportStep, ClusterStep, GraphletStep, GnnStep (Wyrd)
```

**Extras** (`pyproject.toml`): `analysis` = `numpy`, `scipy`, `scikit-learn`, `networkx`; `gnn` = the
`analysis` set plus `torch`, `torch_geometric`. Base `loki` keeps `odin3` as its only runtime dependency
(L0 spec 8). Every `loki.analysis` module imports its heavy dependencies lazily, inside functions, through
`require("analysis")` or `require("gnn")`, which raises `MissingExtra("pip install 'loki[gnn]'")`; the CLI
turns it into exit code 3. mypy `--strict` needs these libraries installed in CI (they are in the `dev` set).

**CLI.** `loki analyze <kind>` (added to `loki.cli.main`, which delegates to `loki.analysis.run.main`):

```
common:   (--graph graph.json | --dataset DIR --design ID --floor F) --out DIR --seed N
export:   --format edgelist,graphml,pyg   [--region SPEC] [--no-structural]
structural: [--wl-variant npn/both|table/both] [--rounds N] [--quotient]   (no Wyrd step: export and gnn
          compute it when needed; the kind exists to inspect and cache it)
cluster:  --method kmeans|affinity|spectral|louvain|all  [--k N|auto] [--resolution X] [--max-points N]
          [--features node[,graphlet]] [--backend B]
graphlets:--backend ext|own|default  [--size 4|5] [--removal global|none] [--hub-threshold N]
          [--min-fanout N] [--force] [--graphlet-tool PATH] [--licence]
tools:    loki tools fetch-orca        (download, verify, build ORCA into the cache; not an analyze kind)
gnn:      --dataset DIR --floor F [--model sage|gcn] [--target construct_type|role] [--epochs N]
          [--hidden N] [--min-count N] [--features node[,graphlet][,wl][,npn]]   (no --design: whole dataset)
```
Exit codes: 0 ok; 1 analysis failure (`ClusterError`, backend failure, invalid input); 2 usage; 3 missing
extra or backend unavailable.

**Wyrd steps.** Same pattern as L0's `DatasetStep` (L0 spec 8.1): classes with `name`, `tools = ()`,
`is_vpr = False`, `command(run, step_dir, settings) -> (argv, env)`, `collect(step_dir) -> list[Metric]`.
Registered in `pyproject.toml`:

```
[project.entry-points."wyrd.steps"]
loki-export    = "loki.analysis.steps:ExportStep"
loki-cluster   = "loki.analysis.steps:ClusterStep"
loki-graphlets = "loki.analysis.steps:GraphletStep"
loki-gnn       = "loki.analysis.steps:GnnStep"
```
Step args (from the project file): `dataset` (path, required), `floor` (default `"f2"`), `seed` (default 0),
plus the kind's CLI options with underscores (`method`, `k`, `format`, `region`, `backend`, `removal`, `hub_threshold`, `size`,
`model`, `epochs`, ...). `command` returns `[sys.executable, "-m", "loki.analysis.run", <kind>, "--dataset",
<dataset>, "--design", run.design.name, "--floor", <floor>, "--out", <step_dir>/analysis, ...]`, env
`{"LOKI_GRAPHLET_TOOL": <value from the environment>}` when that variable is set, else `{}`.
`loki-gnn` ignores `run.design` and trains on the whole dataset (use it in a project with one design
entry). `collect` reads `<step_dir>/analysis/metrics.json` (numbers only, e.g. cluster: `n_clusters_<method>`,
`modularity_<method>`, `nmi_module_path_<method>`; graphlets: `nodes`, `edges`, `seconds`, `removed_edges_total`, `dropped_hubs`, `clock_domains`; gnn:
`test_accuracy`, `test_macro_f1`, `baseline_majority_accuracy`; export: `files`), falling back to the
older-layout `<step_dir>/metrics.json` when that file is absent. Exit 0 on success.

## 11. Output tree

```
<out>/<design>/<floor>/export/       whole.edges.tsv whole.nodes.tsv whole.graphml whole.pt  region-<h>.*
<out>/<design>/<floor>/partition/    <method>-<hash8>.json
<out>/<design>/<floor>/graphlets/    orbits-<backend>-<removal>.npz graphlets-<backend>-<removal>.json
<out>/<design>/<floor>/structural/   structural-<variant>.npz structural-<variant>.json
<out>/gnn/                           config.json vocab.json model.pt metrics.json predictions-<design>.csv
<out>/metrics.json                   numbers for the Wyrd step
```
Analyses never write into the L0 dataset directory (L0's `loki check` stays valid).

## 12. Acceptance (`tests/test_acceptance_l2.py`, local, skips without extras)

Using an L0 dataset built from the micros for F2 when Odin III is present, else the synthetic fixture
dataset (tests/analysis_fixtures.py): (1) `loki analyze export --format edgelist,graphml,pyg` on a design
and on a cone region; the PyG dict loads and `x.shape[1] == len(feature_names)`, and `gsn_wl`, `gsn_npn`,
`gsn_roles` have N rows; `loki analyze structural` twice gives byte-identical JSON; (2) `cluster --method
all` writes four partitions that `load_partition` reads, `assignment` covers every node, a second run is
byte-identical; (3) `graphlets` (ORCA; skips when `loki tools fetch-orca` has not been run) on the small designs gives
orbits equal to the brute-force oracle of plan Task 9 (the test helper `brute_orbits`), with clock domains
and reset flags matching the known micros of section 8.1; (4) `gnn` on the dataset: test accuracy greater than the majority baseline on
the fixture dataset (planted signal) and `metrics.json` complete, with `baselines.wl` and `beats_wl`; on a
real L0 micros dataset (`$LOKI_L0_DATASET`) `beats_wl` is asserted (open question 8); (5) each of the four runs as a Wyrd step
through `get_step` and `command` (skips without Wyrd). The scale test (`LOKI_SCALE=1`) builds the synthetic
100k-node graph and checks the section 3 budgets (time and `resource.getrusage` peak RSS); with
`LOKI_SCALE=2` it uses an 820k-node, 1.6M-edge graph and the golden LU64PEEng `graph.json` when
`$LOKI_BIG_GRAPH` points to one.

## 13. Not in L2

Hypothesis scoring (L1); directed graphlets and typed (coloured) graphlets where a node's role is part of the
subgraph (ORCA has no colours; later option, for which WL or NPN classes would be the natural colours); 5-node orbits in the own backend; graphlet-based distance between
designs (GDV similarity, graph comparison); other GNN architectures, hyperparameter search, GPU; the
neighbour sampler; reading a BLIF directly (L2 reads `graph.json`; open question 2); the F3 gate floor
before gate mapping lands (the code is floor-generic); the P1 placement experiment.

## 14. Open questions (Peter accepted every recommendation below, including items 8-11, 2026-10-21)

1. **L1 evidence interface.** L1's spec was absent. Recommendation: L1 consumes `Partition` as defined in
   section 6 (key `"<method>:<hash8>"`, `members(c)` as candidate blocks). If L1 needs another shape, add an
   adapter function in `loki.analysis.partition`, not a change to the stored file.
2. **Analyse a BLIF that did not come from L0.** Real reverse engineering of an unlabelled netlist needs a
   BLIF-to-`graph.json` path without Odin III. Recommendation: a small `loki graph from-blif` command in a
   later L0 follow-up (it needs L0's numbering and level computation); until then such a netlist goes through
   L0's `build` with the Odin III binding.
3. **Graphlet backend.** Decided: ORCA default (separate process, fetched and built by `loki tools
   fetch-orca`), own 4-node C backend optional and later. Remaining check: the pinned ORCA commit has no
   per-file licence header; the GPL-3 repository `LICENSE` governs. Recommendation: keep the "separate
   process, never vendored" rule and ask the ORCA authors for a permissive grant only if Loki ever needs
   to ship the binary.
4. **Dependency pins.** The extras are unpinned lower bounds (`scikit-learn>=1.5`, `networkx>=3.3`,
   `scipy>=1.11`, `numpy>=1.26`, `torch>=2.3`, `torch_geometric>=2.5`); the API names used here were verified
   on the newest versions above. Recommendation: CI pins the versions of section 3 for the determinism test.
5. **Role classifier limits and LUT bit order.** The reset/enable rules (section 8.1) need the `lut_table`
   address-bit convention of L0 (decided in L0 Task 4 Step 6) and find only resets and enables that appear as
   a forcing or hold input of a D-LUT; a flip-flop with a native reset pin (hard blocks only) is found by
   pin name. Recommendation: accept this, report `classified` counts, and let the degree fallback catch the
   rest; check the rule against the micros with known resets (plan Task 9) and review the counts on mcml
   and LU64PEEng once.
6. **Loading very large `graph.json`.** An 820k-node, 1.6M-edge `graph.json` in plain `json` may need more than
   5 GB at load (not measured). The budget is 8 GB and 120 s, checked by `LOKI_SCALE=2`. Recommendation: if
   the budget fails, add a cache of the arrays (`<out>/cache/graph-<sha8>.npz`) written on first load,
   before adding any streaming parser.
7. **Clustering at LU64PEEng size.** Section 3 budgets are measured at 100k nodes and extrapolated linearly
   to 820k (Louvain about 5 min); `LOKI_SCALE=2` checks them. Recommendation: if Louvain exceeds
   15 minutes there, run it on the graph with the global signals removed (section 8.3), which is cheaper and
   closer to the logical structure.

New with the features of 2026-10-21 (not yet accepted; recommendations given):

8. **"GNN must beat 1-WL" as a gate.** A message-passing GNN is at most as discriminating as 1-WL, so a colour
   lookup can beat it on small datasets such as the micros. Recommendation: `beats_wl` is computed and reported
   always; the acceptance test asserts it on the real micros dataset only; if it fails there, the result is a
   finding for Peter (with the GNN rerun on `--features node,graphlet,wl,npn`), not a silent pass and not a
   change to the baseline.
9. **Categorical ids.** WL and NPN ids are `hash64` values, comparable across designs; the GNN maps them to a
   train vocabulary. Recommendation: as section 9; clustering never uses them.
10. **One classifier for L1 and L2.** The 8.1 rules live in `loki.features.roles` (pure Python). Recommendation:
    `classify_signals` delegates; if the 820k-node budget of section 3 fails, L2 keeps its numpy grouping of
    edges by net and calls only the per-net rule functions from `loki.features.roles`.
11. **Which WL variant to export.** Recommendation: `npn/both` by default (it generalises across designs, since
    permuted LUT inputs give one colour); `table/both` on request for exact-structure work.
