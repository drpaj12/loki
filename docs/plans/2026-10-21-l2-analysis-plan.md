# Loki L2 Analysis Plugins Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build Loki L2: analysis plugins (export, clustering, graphlets, GNN baseline) that read L0's `graph.json`, run from `loki analyze <kind>` and as Wyrd steps, and store partitions that L1 consumes as evidence.

**Architecture:** A `Graph` value loaded from `graph.json` (numpy arrays, sparse undirected projection) feeds four plugin modules under `loki/analysis/`. Heavy libraries are optional extras imported lazily. Graphlets sit behind a `GraphletCounter` interface; the spike decided the default: ORCA as a separate process (fetched and built by `loki tools fetch-orca`), after a global-signal classifier removes clock, reset, constant and enable nets from the counting graph and keeps them as node features. An own 4-node C backend is an optional later task. Structural features (1-WL colours, NPN classes, the signal classifier) come from Loki III L1's standard-library package `loki.features` (L1 spec 6.7) and reach the PyG export and the GNN as GSN-style vectors and a 1-WL baseline (Tasks 9, 10a, 11, 12).

**Tech Stack:** Python 3.11+, numpy, scipy, scikit-learn, networkx (extra `analysis`); torch, torch_geometric (extra `gnn`); `g++` to build ORCA (and `cc` for the optional own backend); `unittest`, `ruff`, `mypy --strict`.

**Spec:** `docs/specs/2026-10-21-l2-analysis-design.md` (section numbers below refer to it). Read it first; it fixes features, budgets, partition schema, orbit table and step arguments.

## Global Constraints

- L0 is a prerequisite: its Tasks 1 (skeleton, CI), 2 (`loki.schemas`: `validate_graph`, `dump_json`, `FLOORS`), 10 (`loki.cli.main`) must be merged. Task 1 here checks it.
- L1 Task 5a (`loki.features`) must be merged before Tasks 9 and 10a here (build order L0, L1, L2). L2 never changes `loki.features` semantics; a needed change goes to an L1 PR first.
- Python 3.11+. Base runtime dependency stays `odin3` only; analysis libraries are extras: `analysis` = `numpy`, `scipy`, `scikit-learn`, `networkx`; `gnn` = `analysis` + `torch`, `torch_geometric`. Imports of these happen inside functions via `loki.analysis.require(...)`.
- `ruff check .` and `mypy --strict loki tests` clean; no suppressions without Peter's approval; line length 100. Tests: `python -m unittest discover -s tests -t . -v`; tests needing an extra use `tests.helpers.have("numpy")`-style `skipUnless` (Task 1) and must skip, not fail, without it.
- Never commit to `main`; branch `feat/l2-<task>`, PR, squash merge on green CI; commit and push after each green step.
- Analyses read `graph.json` and `manifest.json` only; never `key.json`, never the BLIF; never write inside the dataset directory (spec 11).
- Label columns are never features (spec 4). Features are exactly the 8 + 7 + 4 + (T+1) columns of spec 4.
- Determinism (spec 3): `seed` everywhere, canonical cluster numbering, JSON floats rounded to 6 decimals (`round(x, 6)`), sorted keys via `loki.schemas.dump_json`, counts `int64`.
- No dense N x N arrays. No subprocess with `shell=True`.
- Verified API names (checked 2026-10-21 on scikit-learn 1.9.1, networkx 3.7, scipy 1.18.1, numpy 2.5.4, torch 2.14.1, torch_geometric 2.8.1): `sklearn.cluster.KMeans/MiniBatchKMeans/AffinityPropagation(damping, max_iter, convergence_iter, preference, random_state; fit, cluster_centers_, labels_)`, `sklearn.manifold.spectral_embedding(adjacency, *, n_components, eigen_solver, random_state, eigen_tol, norm_laplacian, drop_first)`, `sklearn.metrics.normalized_mutual_info_score/adjusted_rand_score/f1_score`, `sklearn.preprocessing.StandardScaler`, `sklearn.linear_model.LogisticRegression`, `networkx.community.louvain_communities(G, weight, resolution, threshold, max_level, seed)`, `networkx.community.modularity(G, communities, weight, resolution)`, `networkx.from_scipy_sparse_array`, `networkx.write_graphml`, `scipy.sparse.csgraph.connected_components`, `torch_geometric.nn.SAGEConv/GCNConv`, ORCA CLI `orca node|edge 4|5 <in> <out>` (built and run 2026-10-21), `torch_geometric.data.Data`, `torch_geometric.utils.to_undirected`, `torch_geometric.seed_everything`, `torch.use_deterministic_algorithms`. `NeighborLoader` needs `pyg-lib` or `torch-sparse` and is not used.

## Review Focus

- A netlist with hundreds of connected components (constants, dead logic) or a single tiny one: spectral clustering uses the largest component and gives each other component one cluster; no crash, every node assigned. Pinned in Task 8 (`test_spectral_many_components`, `test_spectral_tiny`).
- A hub node (clock/reset-like, degree thousands): graphlet counts stay exact in `int64` (star centre orbit 7 equals C(d,3)), exports and clustering do not build anything N x N; the classifier removes global nets first and the degree fallback lists what it still drops. Pinned in Task 10 (`test_star_hub_exact`, `test_hub_fallback_lists_nodes`) and G-ext (`test_real_orca_matches_oracle`).
- A reset or enable the classifier cannot see (merged into data logic, below `min_fanout`, a load mux that is not a hold): must stay `signal`, never be misclassified as a reset. Pinned in Task 9 (`test_data_net_not_reset`, `test_below_min_fanout_is_signal`, the shift-register micro).
- A downloaded `orca.cpp` that does not match the pinned SHA-256, or a missing compiler: refused with a clear message, nothing built, nothing executed. Pinned in Task G-ext (`test_fetch_verifies_sha`).
- Degenerate graphs: zero edges, one node, a constant-only design (all analyses return valid output; `k` clipped to N). Pinned in Tasks 2, 7, 8, 9, 10.
- Affinity propagation that does not converge, or a sample of identical rows: retry once, then a clear `ClusterError` / one cluster. Pinned in Task 7 (`test_affinity_nonconvergence_retry_then_error`, `test_affinity_identical_rows`).
- An unlabelled `graph.json` through cluster and export works (quality keys `null`); through the GNN it is a clear error; a test class never seen in training maps to `__other__`. Pinned in Tasks 5, 6, 11, 12.
- Label leakage: a feature column named after a label column must be impossible. Pinned in Task 2 (`test_features_exclude_labels`).
- WL and NPN ids are categorical hashes: they must never enter `x` or a clustering feature matrix as numbers. Pinned in Task 10a (`test_pyg_structural_keys`: separate keys) and Task 13 (`test_cluster_rejects_wl_features`).
- L1 and L2 must see one signal classification and one colour per node for the same netlist. Pinned in Task 9 (`test_classify_signals_delegates`) and Task 10a (`test_adapter_equals_from_graph_json`).

---

### Task 1: Extras, package skeleton, helpers, fixtures

**Files:**
- Modify: `pyproject.toml`, `loki/cli.py` (only the `analyze` hook is added in Task 13), `.github/workflows/ci.yml`, `CLAUDE.md`
- Create: `loki/analysis/__init__.py`, `tests/analysis_fixtures.py`, `tests/test_analysis_pkg.py`
- Modify: `tests/helpers.py`

**Interfaces:**
- Consumes (L0): `loki.schemas.validate_graph`, `dump_json`, `FLOORS`; `tests.helpers`.
- Produces in `loki/analysis/__init__.py`: `KINDS = ("export", "cluster", "graphlets", "gnn")`; `class MissingExtra(RuntimeError)`; `require(extra: str) -> None` (`"analysis"` imports `numpy, scipy, sklearn, networkx`; `"gnn"` additionally `torch, torch_geometric`; raises `MissingExtra("this needs the 'analysis' extra: pip install 'loki[analysis]'")`, with `gnn` in the message for `gnn`).
- Produces in `tests/helpers.py`: `have(module: str) -> bool` (importable), `skip_without(*modules: str)` decorator (`unittest.skipUnless` with reason).
- Produces in `tests/analysis_fixtures.py`: `make_graph(n_lut: int = 12, floor: str = "f2", design: str = "d", seed: int = 0, labels: bool = True) -> dict` (a valid L0 `graph.json` object with 2 PI, `n_lut` LUTs in two planted blocks of different `lut_width` and `module_path` (`top/u0`, `top/u1`), 2 FFs, 1 PO; `construct_type` is `$eq` for LUTs of width 2 and `$add` for width 3, `role` accordingly; edges form a connected netlist); `write_graph(dir: Path, obj: dict) -> Path` (via `dump_json`); `make_dataset(root: Path, designs: int = 6, floor: str = "f2", seed: int = 0) -> Path` (writes `manifest.json` per L0 spec 6.9 using `split_of`, and `<design>/<floor>/graph.json`; designs named `micro_a0..`; every design contains both planted classes so a model can learn `lut_width -> construct_type`); `star_graph(d: int) -> dict` (hub with d leaves, kind lut); `big_synthetic(n: int, m: int, seed: int) -> tuple[np.ndarray, np.ndarray]` (the section 3 benchmark generator: local edges within +-50 plus a 20000-fan-out hub, as measured; arrays `src`, `dst`, simple undirected, `src < dst`).

- [ ] **Step 1: Failing tests** `tests/test_analysis_pkg.py`: `test_require_missing_extra_message` (monkeypatch `importlib.import_module` to raise for `sklearn`; expect `MissingExtra` whose text contains `loki[analysis]`); `test_extras_declared` (read `pyproject.toml`: `optional-dependencies["analysis"]` contains `scikit-learn`, `networkx`, `scipy`, `numpy`; `["gnn"]` contains `torch` and `torch_geometric`; `["dev"]` contains both sets so CI mypy sees them); `test_fixture_graph_valid` (`validate_graph(make_graph()) == []`, also with `labels=False`); `test_fixture_dataset_manifest_split` (each design's `split` equals `split_of(design)`).
- [ ] **Step 2: Run** `python -m unittest tests.test_analysis_pkg -v`. Expected: FAIL (module missing).
- [ ] **Step 3: Implement.** `pyproject.toml`: add `[project.optional-dependencies]` `analysis = ["numpy>=1.26", "scipy>=1.11", "scikit-learn>=1.5", "networkx>=3.3"]`, `gnn = ["loki[analysis]", "torch>=2.3", "torch_geometric>=2.5"]`, extend `dev` with the same; no entry points yet (Task 14). CI: install `.[dev]` with the CPU torch wheel index (`pip install torch --index-url https://download.pytorch.org/whl/cpu` first), add `pip install ruff mypy` unchanged. `CLAUDE.md`: one paragraph for L2 (spec/plan paths, extras). Fixture `make_graph` is deterministic and hand-structured (no randomness except `seed` shuffling of nothing: keep it purely arithmetic).
- [ ] **Step 4: Run** unittest, `ruff check .`, `mypy --strict loki tests`. Expected: PASS, clean. Also confirm L0 prerequisites: `python -c "import loki.schemas, loki.cli"` succeeds, else stop and report.
- [ ] **Step 5: Commit** (`feat/l2-skeleton`), PR, merge.

### Task 2: Graph loading, features, adjacency, dataset iteration

**Files:**
- Create: `loki/analysis/graphio.py`, `tests/test_graphio.py`

**Interfaces:**
- Consumes: `make_graph`, `write_graph`, `make_dataset`, `star_graph` (Task 1); `loki.schemas.validate_graph`.
- Produces: `@dataclass(frozen=True) Graph(design: str, floor: str, node_ids: tuple[str, ...], kind: tuple[str, ...], num: dict[str, np.ndarray], table: tuple[int, ...], src: np.ndarray, dst: np.ndarray, pin: tuple[str, ...], net: tuple[str, ...], labels: dict[str, np.ndarray] | None, sha256: str)` (`table` is the integer `lut_table` per node, -1 when absent; the JSON file form stays hex) with `n_nodes`, `n_edges`, `index() -> dict[str, int]`, `induced(node_ids: Sequence[str]) -> Graph` (spec 4);
  `load_graph(path: Path) -> Graph` (validates, raises `ValueError` listing validator errors);
  `@dataclass(frozen=True) FeatureMatrix(names: tuple[str, ...], x: np.ndarray, hard_types: tuple[str, ...])`;
  `featurize(g: Graph, hard_types: Sequence[str] | None = None) -> FeatureMatrix` (spec 4: 8 numeric, 7 kind, 4 floor, T+1 hard type; `hard_types=None` derives sorted types from `g.labels["cell_type"]` of kind `hard` nodes; x is float32);
  `NUMERIC_FEATURES: tuple[str, ...]`; `LABEL_COLUMNS_FORBIDDEN: frozenset[str]` (`LABEL_COLUMNS` minus `node_id`, `kind` and `cell_type`: the answer-key columns of spec 4);
  `undirected_adjacency(g: Graph) -> scipy.sparse.csr_matrix` (symmetric float32 0/1, no self-loops, parallel edges merged);
  `undirected_edges(g: Graph) -> tuple[np.ndarray, np.ndarray]` (int32 `src < dst`, unique, sorted);
  `@dataclass(frozen=True) DatasetEntry(design: str, floor: str, split: str, graph_path: Path)`; `iter_dataset(root: Path, floor: str) -> Iterator[DatasetEntry]` (reads `manifest.json`, yields designs whose `floors[floor].status == "ok"`, sorted by design);
  `canonical_numbers(raw: np.ndarray) -> np.ndarray` (renumber cluster labels 0..K-1 by lowest node index; used by Tasks 7, 8).

- [ ] **Step 1: Failing tests:** `test_load_roundtrip` (counts, `sha256` equals `hashlib.sha256` of the file bytes, `node_ids` in file order); `test_load_invalid_raises` (an unknown kind gives `ValueError` containing the validator message); `test_features_columns_exact` (`featurize(load_graph(...)).names` equals the 8 numeric names, `kind:pi`..`kind:gate`, `floor:f1-k6`..`floor:f3`, `hard:<type>`..., `hard:<unk>` in that order; `x.shape == (n, len(names))`; the `level` column equals the JSON `level`; `lut_ones` for `lut_table "9009"` is 4); `test_features_exclude_labels` (no name in `names` contains any entry of `LABEL_COLUMNS_FORBIDDEN`; `construct_type` values do not appear anywhere in `names`); `test_unlabelled_graph` (`labels is None`, `featurize` still works, all hard-type columns 0); `test_undirected_adjacency_merges_parallel` (graph with two edges between the same pair and a self-loop: `adj.nnz == 2`, diagonal 0); `test_induced_keeps_features` (fan_in values unchanged after `induced`); `test_iter_dataset_skips_non_ok` (a floor entry `skipped` is not yielded); `test_zero_edge_graph` (n nodes, no edges: adjacency `nnz == 0`, `undirected_edges` empty arrays of dtype int32); `test_canonical_numbers` (`[5,5,2,9,2]` becomes `[0,0,1,2,1]`).
- [ ] **Step 2: Run** `python -m unittest tests.test_graphio -v`. Expected: FAIL.
- [ ] **Step 3: Implement.** Parse with `json.load`; build arrays with `numpy`; `lut_ones = int(table, 16).bit_count()`. Edge endpoint ids map through a dict built once. Memory note in a docstring: peak is about 2 GB at 100k nodes and 500k edges (spec 3).
- [ ] **Step 4: Run** tests, ruff, mypy. Expected: PASS.
- [ ] **Step 5: Commit** (`feat/l2-graphio`), PR, merge.

### Task 3: Regions

**Files:**
- Create: `loki/analysis/region.py`, `tests/test_region.py`

**Interfaces:**
- Consumes: `Graph`, `Graph.induced` (Task 2); `Partition` (Task 6, imported lazily inside `from_partition` to avoid a cycle: use `TYPE_CHECKING`).
- Produces: `class RegionError(ValueError)`; `@dataclass(frozen=True) Region(spec: str, node_ids: tuple[str, ...])` (ids sorted by graph order); `cone(g: Graph, roots: Sequence[str], direction: str, depth: int | None) -> Region`; `from_partition(p: Partition, cluster: int) -> Region`; `from_nodes(g: Graph, ids: Sequence[str]) -> Region`; `parse_region(g: Graph, spec: str) -> Region` (spec 4 spellings); `region_hash(spec: str) -> str` (first 8 hex of sha256).

- [ ] **Step 1: Failing tests** on `make_graph` / a hand-built chain `a -> b -> c -> d` with a flip-flop in it: `test_cone_in_depth` (depth 1 from `d` gives `{c, d}`), `test_cone_out_all`, `test_cone_both`, `test_cone_crosses_flipflop`, `test_unknown_root_raises` (`RegionError` naming the id), `test_empty_region_raises`, `test_parse_cone_and_nodes_file` (`nodes:<tmpfile>`), `test_parse_bad_spec`, `test_region_hash_stable`.
- [ ] **Step 2: Run** `python -m unittest tests.test_region -v`. Expected: FAIL.
- [ ] **Step 3: Implement** with a breadth-first walk over CSR in/out adjacency built from `g.src`, `g.dst` (`scipy.sparse.csr_matrix`); `parse_region` for `cluster:` loads via `load_partition` (Task 6) lazily, so its test lives in Task 6.
- [ ] **Step 4: Run** tests, ruff, mypy. Expected: PASS.
- [ ] **Step 5: Commit** (`feat/l2-region`), PR, merge.

### Task 4: Export: edge list and GraphML

**Files:**
- Create: `loki/analysis/export.py`, `tests/test_export.py`

**Interfaces:**
- Consumes: `Graph`, `featurize` (Task 2); `Region`, `Graph.induced` (Tasks 2, 3).
- Produces: `export_graph(g: Graph, region: Region | None, formats: Sequence[str], out: Path) -> list[Path]` (`formats` subset of `edgelist, graphml, pyg`; writes into `out` with `stem` per spec 5, returns paths sorted; raises `ValueError` on unknown format; `pyg` is implemented in Task 5 and raises `NotImplementedError` here); `write_edgelist(g: Graph, stem: Path) -> list[Path]`; `write_graphml(g: Graph, path: Path) -> Path`.

- [ ] **Step 1: Failing tests:** `test_edgelist_content` (lines equal `src\tdst` ids in `graph.json` edge order; no header; nodes file header `id\tkind\tfan_in...` and one row per node; label columns appended when labels exist, absent otherwise); `test_graphml_roundtrip` (`networkx.read_graphml` of the output: node count, edge count, node attribute `fan_in` equals the JSON, edge attribute `pin`, graph attribute `floor`); `test_region_export_is_induced` (cone region: only inside edges; fan_in kept from the whole netlist); `test_export_deterministic` (two exports byte-identical); `test_unknown_format`; `test_zero_edge_graph_exports` (empty edges file, valid GraphML).
- [ ] **Step 2: Run** `python -m unittest tests.test_export -v`. Expected: FAIL.
- [ ] **Step 3: Implement** edge list by direct text writing (no networkx); GraphML through `networkx.DiGraph` and `networkx.write_graphml` (attributes must be `str`/`int`/`float`; convert numpy scalars with `.item()`); node insertion order = graph order for determinism.
- [ ] **Step 4: Run** tests, ruff, mypy. Expected: PASS.
- [ ] **Step 5: Commit** (`feat/l2-export`), PR, merge.

### Task 5: Export: PyTorch Geometric

**Files:**
- Modify: `loki/analysis/export.py`
- Create: `tests/test_export_pyg.py`

**Interfaces:**
- Consumes: Task 4's `export_graph`; `featurize`.
- Produces: `build_vocab_for_graph(g: Graph) -> dict[str, list[str]]` (`{"construct_type": [...], "role": [...]}`, sorted unique non-empty values of that graph; empty dict entries when unlabelled); `pyg_dict(g: Graph, split: str | None = None) -> dict[str, object]` (spec 5 keys; `y_*` int64 with -1 for empty targets, absent when unlabelled); `write_pyg(g: Graph, path: Path, split: str | None = None) -> Path` (`torch.save`); `load_pyg(path: Path) -> "torch_geometric.data.Data"` (`torch.load(path, weights_only=True)`, then `Data(x=..., edge_index=..., y_construct_type=..., y_role=...)` plus attributes `node_ids`, `feature_names`).

- [ ] **Step 1: Failing tests** (`@skip_without("torch", "torch_geometric")`): `test_pyg_dict_shapes` (`x.shape == (n, len(feature_names))`, `edge_index.shape == (2, e)`, dtype int64, driver row first); `test_pyg_label_vocab_and_minus_one` (nodes with empty `construct_type` get -1; PI/PO nodes carry `$port_in`/`$port_out` ids); `test_pyg_unlabelled_has_no_y`; `test_load_pyg_weights_only` (round trip through `write_pyg`/`load_pyg`, tensors equal, `isinstance(..., Data)`); `test_pyg_region` (cone region: `edge_index` indices within the region size); `test_export_graph_pyg_format_listed`.
- [ ] **Step 2: Run** `python -m unittest tests.test_export_pyg -v`. Expected: FAIL or SKIP-all (skip must not be the only outcome in CI: CI installs the extras, so FAIL).
- [ ] **Step 3: Implement**; replace the Task 4 `NotImplementedError` by a call to `write_pyg`; `require("gnn")` inside.
- [ ] **Step 4: Run** tests, ruff, mypy. Expected: PASS.
- [ ] **Step 5: Commit** (`feat/l2-export-pyg`), PR, merge.

### Task 6: Partition record, storage, quality, evidence loading

**Files:**
- Create: `loki/analysis/partition.py`, `tests/test_partition.py`

**Interfaces:**
- Consumes: `Graph`, `undirected_adjacency`, `canonical_numbers` (Task 2); `loki.schemas.dump_json`.
- Produces: `@dataclass(frozen=True) Partition(design, floor, method, params: dict[str, object], seed: int, graph_sha256: str, node_ids: tuple[str, ...], assignment: tuple[int, ...], quality: dict[str, object], versions: dict[str, str], sampled: dict[str, int] | None = None, components: int | None = None)` with `n_clusters`, `members(c) -> tuple[str, ...]`, `cluster_of(node_id) -> int`, `sizes() -> list[int]`, `key -> str`;
  `partition_hash(method: str, params: dict[str, object], seed: int, graph_sha256: str) -> str` (spec 6, 8 hex);
  `compute_quality(g: Graph, assignment: np.ndarray) -> dict[str, object]` (modularity, size_min/median/max, and `nmi_module_path`, `ari_module_path`, `nmi_construct_type` over kinds lut/ff/hard/gate, `None` when unlabelled or fewer than 2 nodes);
  `make_partition(g: Graph, method: str, params: dict[str, object], seed: int, assignment: np.ndarray, sampled=None, components=None) -> Partition` (canonicalises numbers, fills quality and versions);
  `write_partition(p: Partition, out_dir: Path) -> Path` (`<out_dir>/<method>-<hash8>.json`, schema 1, `dump_json`); `load_partition(path: Path) -> Partition` (validates keys, `assignment` length equals `n_nodes`, numbers 0..K-1 without gaps; `ValueError` otherwise); `version_info() -> dict[str, str]`.
  Also wires `parse_region("cluster:<partition.json>:<c>")` in Task 3.

- [ ] **Step 1: Failing tests:** `test_roundtrip_and_key` (`load_partition(write_partition(p))` equals `p`; `p.key == f"{method}:{hash8}"`); `test_hash_depends_on_params_and_seed`; `test_quality_planted_blocks` (on `make_graph`, the planted assignment by `module_path` gives `nmi_module_path == 1.0`, a one-cluster assignment gives modularity 0.0 within 1e-9); `test_quality_unlabelled_is_null`; `test_members_and_cluster_of`; `test_load_rejects_gaps_and_length`; `test_parse_region_cluster` (region from a written partition, cluster 1 members); `test_write_deterministic` (two writes byte-identical, floats rounded to 6 decimals); `test_single_node_graph` (quality computed without error, modularity 0.0).
- [ ] **Step 2: Run** `python -m unittest tests.test_partition -v`. Expected: FAIL.
- [ ] **Step 3: Implement.** `modularity` via `networkx.community.modularity(G, communities)` with `G` from `networkx.from_scipy_sparse_array(adj)`; for a graph with zero edges return `0.0` without calling it (networkx raises on no edges).
- [ ] **Step 4: Run** tests, ruff, mypy. Expected: PASS.
- [ ] **Step 5: Commit** (`feat/l2-partition`), PR, merge.

### Task 7: Clustering: k-means and affinity propagation

**Files:**
- Create: `loki/analysis/cluster.py`, `tests/test_cluster_features.py`

**Interfaces:**
- Consumes: Tasks 2 and 6.
- Produces: `class ClusterError(RuntimeError)`; `resolve_k(k: int | str, n: int) -> int` (spec 7: `"auto"`, clip, `min(k, n)`; n < 2 gives 1); `cluster_space(g: Graph, extra: np.ndarray | None = None) -> np.ndarray` (float64: `log1p` on `fan_in, fan_out, level, lut_width, hard_ports, lut_ones`, standardised with `StandardScaler`; kind one-hot appended; `extra` columns appended; constant columns kept as zeros); `cluster_kmeans(g: Graph, *, k: int | str = "auto", seed: int = 0, extra: np.ndarray | None = None) -> Partition`; `cluster_affinity(g: Graph, *, seed: int = 0, max_points: int = 3000, extra: np.ndarray | None = None) -> Partition`; `assign_nearest(x: np.ndarray, centers: np.ndarray, chunk: int = 10000) -> np.ndarray`.

- [ ] **Step 1: Failing tests:** `test_resolve_k` (`resolve_k("auto", 200) == 10`, `resolve_k("auto", 4) == 2`, `resolve_k(50, 10) == 10`, `resolve_k("auto", 1) == 1`); `test_kmeans_separates_planted_blocks` (on `make_graph(40)` with `k=2`: assignment constant within each `lut_width` class); `test_kmeans_deterministic` (same seed same assignment; Partition JSON byte-identical); `test_kmeans_uses_minibatch_over_20000` (monkeypatch threshold constant `KMEANS_FULL_MAX = 20000` to 10 and assert `MiniBatchKMeans` used via recorded `params["algorithm"] == "minibatch"`); `test_affinity_sampled_and_assigned` (graph of 120 nodes, `max_points=50`: `sampled == {"points": 50}`, assignment covers all 120 nodes, K at least 1); `test_assign_nearest_chunked_matches_unchunked` (chunk 7 vs 10000); `test_affinity_identical_rows` (all-identical feature rows: one cluster); `test_affinity_nonconvergence_retry_then_error` (monkeypatch `AffinityPropagation.fit` to return labels all -1 twice: `ClusterError` with the message of spec 7.2; once only: success with `params["retried"] is True`); `test_single_node_and_zero_edge` (n=1 gives one cluster; constant-only design with zero edges clusters fine); `test_extra_columns_change_space` (`cluster_space` width grows by `extra.shape[1]`).
- [ ] **Step 2: Run** `python -m unittest tests.test_cluster_features -v`. Expected: FAIL.
- [ ] **Step 3: Implement** per spec 7.1 and 7.2. `KMEANS_FULL_MAX = 20000` module constant. Params recorded as in spec 7. Any sklearn `ConvergenceWarning` is converted via `warnings.catch_warnings(record=True)` to the non-convergence check (labels all -1 is the signal).
- [ ] **Step 4: Run** tests, ruff, mypy. Expected: PASS.
- [ ] **Step 5: Commit** (`feat/l2-cluster-features`), PR, merge.

### Task 8: Clustering: spectral and Louvain; `run_cluster`

**Files:**
- Modify: `loki/analysis/cluster.py`
- Create: `tests/test_cluster_graph.py`

**Interfaces:**
- Consumes: Task 7's `resolve_k`, `cluster_space`; Task 2's `undirected_adjacency`.
- Produces: `cluster_spectral(g: Graph, *, k: int | str = "auto", seed: int = 0) -> Partition` (spec 7.3; `components` recorded); `cluster_louvain(g: Graph, *, resolution: float = 1.0, seed: int = 0) -> Partition` (spec 7.4); `METHODS = ("kmeans", "affinity", "spectral", "louvain")`; `run_cluster(g: Graph, methods: Sequence[str], out_dir: Path, *, k, seed, resolution, max_points, extra) -> list[Path]` (runs the methods in the order of `METHODS`, writes each partition, returns paths; unknown method `ValueError`).

- [ ] **Step 1: Failing tests:** `test_louvain_recovers_planted_blocks` (two dense blocks joined by one edge: two clusters, `nmi_module_path > 0.9`); `test_louvain_deterministic_with_seed`; `test_spectral_recovers_blocks` (same graph, `k=2`, `nmi_module_path > 0.9`); `test_spectral_many_components` (graph with 50 isolated two-node components plus one connected block of 30 nodes: every node assigned, `components == 51`, each small component is a single cluster, no exception); `test_spectral_tiny` (a 2-node graph and a 1-node graph: valid partitions); `test_spectral_zero_edges` (N isolated nodes: N clusters); `test_run_cluster_all_writes_four_files` (names `kmeans-*.json` ... `louvain-*.json`, each loadable); `test_run_cluster_byte_identical_twice`; `test_unknown_method`.
- [ ] **Step 2: Run** `python -m unittest tests.test_cluster_graph -v`. Expected: FAIL.
- [ ] **Step 3: Implement.** Spectral solver rule: `"arpack"` when the component has at most 5000 nodes else `"lobpcg"`; `n_components=min(k, n_L-1)`; row L2 normalisation guarded against zero rows; follow spec 7.3 steps exactly. Louvain: build `networkx.Graph` from the adjacency; sort result sets canonically through `canonical_numbers`.
- [ ] **Step 4: Run** tests, ruff, mypy. Expected: PASS.
- [ ] **Step 5: Commit** (`feat/l2-cluster-graph`), PR, merge.

### Task 9: Global-signal classifier

Runs before the ORCA task (Peter, 2026-10-21): clock, reset, constant and global-enable nets are found by role, removed from the counting graph in Task 10, and kept as node features.

**Files:**
- Create: `loki/analysis/graphlets/__init__.py` (package marker only here), `loki/analysis/graphlets/signals.py`, `tests/test_signals.py`
- Modify: `tests/analysis_fixtures.py`, `loki/analysis/graphio.py` (`to_feature_graph`)

**Interfaces:**
- Consumes: `Graph` (Task 2) with per-edge `pin`, `net`, and node `kind`, `lut_table`, `lut_width`; `loki.features.graph.FeatureGraph`, `loki.features.roles` (`SignalConfig`, `NetRoles`, `classify_nets`, `restrict`, `is_forcing`, `is_hold`; L1 Task 5a).
- Produces in `graphio.py`: `to_feature_graph(g: Graph) -> FeatureGraph` (spec 4.1; equal to `from_graph_json` of the same file).
- Produces in `signals.py` (spec 8.1, 8.2): `CLASS_NAMES` and `SignalConfig` re-exported from `loki.features.roles` (same values: `("signal", "clock", "reset", "enable", "const")`, `SignalConfig(min_fanout: int = 16, dominance: float = 0.8)`); `@dataclass(frozen=True) SignalInfo(edge_class: np.ndarray, roles: np.ndarray, classified: dict[str, int], clock_domains: int)` (`edge_class` int8 `(E,)` indices into `CLASS_NAMES`; `roles` int64 `(N, 4)` columns `clock_domain, has_reset, const_inputs, enable`; `classified` = number of nets per class name);
  `lut_bits(table_hex: str, width: int) -> np.ndarray` (uint8 length `2**width`, index = address, address bit k = input `I<k>`, `table_hex` MSB first as in L0 spec 6.4; follows `loki.blifout.LUT_ROW_ORDER`);
  `lut_restrict(bits: np.ndarray, width: int, k: int, value: int) -> np.ndarray` (the table over the remaining inputs, order kept);
  `is_forcing(bits, width, k) -> bool` (for some value of input k the output is constant); `is_hold(bits, width, k, q: int) -> bool` (for some value of input k the output equals input q);
  `classify_signals(g: Graph, cfg: SignalConfig = SignalConfig()) -> SignalInfo`.
- Produces in `tests/analysis_fixtures.py`: `make_sync_design(n_ff: int = 20, reset: bool = False, enable: bool = False, clocks: int = 1, consts: bool = False) -> dict` (a valid `graph.json` object: PI `clk0..`, PI `rst`, PI `en`, PI data, per FF a D-LUT feeding an FF `D`; with `reset` the D-LUT is `!rst & d` (width 2), with `enable` it is `en ? d : q` (width 3, `q` = the FF's own output net), otherwise a width-2 XOR of two data PIs; FFs are split across `clocks` clock PIs; `consts` adds a `const` node feeding every D-LUT of an extra input).

- [ ] **Step 1: Failing tests** `tests/test_signals.py`: `test_lut_convention` (AND table `"8"`, width 2: `lut_bits` is `[0,0,0,1]`; restricting `I0=0` gives `[0,0]` and `I0=1` gives `[0,1]`); `test_is_forcing_and_hold` (AND: forcing on both inputs; mux `en ? d : q` table: `is_hold(.., en_index, q_index)` true, `is_forcing` false); `test_clock_nets_and_domains` (`clocks=2`: classified clock = 2, `roles[:,0]` of FFs are 1 and 2 by lowest driver index, `clock_domains == 2`, every non-clocked node 0); `test_latch_enable_is_not_clock` (a `ff` sink on pin `EN` leaves the net `signal`); `test_hard_clock_pin` (hard node with pin `clk` makes the net a clock; pin `data[0]` does not); `test_reset_found` (`reset=True, n_ff=20`: net class `reset`, D-LUTs and FFs have `has_reset == 1`, the PI `rst` itself 0); `test_enable_found` (`enable=True`); `test_below_min_fanout_is_signal` (`n_ff=5` default config: `signal`; `SignalConfig(min_fanout=2)`: reset); `test_data_net_not_reset` (the `xor` design: a PI with fan-out 20 that is not forcing stays `signal`); `test_hard_reset_pin` (hard sink pin `rst` counts as a reset sink); `test_const_nets` (`consts=True`: class `const`, `const_inputs` equals the count of const in-edges for each D-LUT, even below `min_fanout`); `test_edge_class_aligned` (`edge_class.shape == (n_edges,)`; every edge of a classified net carries that class); `test_no_edges` (graph without edges: `roles` zeros, `clock_domains == 0`); `test_to_feature_graph_equals_from_graph_json`; `test_classify_signals_delegates` (on `make_sync_design(reset=True, enable=True, clocks=2)`: every net class and node role equals `loki.features.roles.classify_nets(to_feature_graph(g))`).
- [ ] **Step 2: Run** `python -m unittest tests.test_signals -v`. Expected: FAIL.
- [ ] **Step 3: Implement.** The rules are L1's (`loki.features.roles.classify_nets`, spec 8.1, L1 spec 6.7): `classify_signals` calls it on `to_feature_graph(g)` and builds `edge_class` and `roles` with numpy; `lut_restrict`, `is_forcing` and `is_hold` convert `lut_bits` to the integer table and call `restrict`, `is_forcing`, `is_hold`; `lut_bits` stays the numpy view. Budget 60 s on 820k nodes (spec 3), checked in Task 15; if it fails, group edges by `net` with `np.unique`/argsort here and call only the per-net rule functions of `loki.features.roles` (spec 14 item 10), with `test_classify_signals_delegates` kept.
- [ ] **Step 4: Run** tests, ruff, mypy. Expected: PASS.
- [ ] **Step 5: Known micros** (`tests/test_signals_micros.py`, skips without Odin III; builds F2 graphs for the micros through L0's `build_floor` into a temp dir): `bm_DL_Dff_w_synch_reset` (1 FF): exactly one clock net, `clock_domain == 1` on the FF, with `SignalConfig(min_fanout=1)` the `Resetn` net is `reset` and the FF has `has_reset == 1`; `bm_DL_4_bit_shift_register` (4 FFs): one clock net, 4 clocked FFs, and with `min_fanout=1` the select `L` is `signal` (a load mux is neither a reset nor a hold); `bm_if_reset` (read the Verilog first to name its FFs): one clock net and `reset_n` classified `reset` with `min_fanout=1`. Where a result differs from this expectation, inspect the graph and fix the rule or the expectation in the spec 8.1 table, not the test alone; report it.
- [ ] **Step 6: Commit** (`feat/l2-signals`), PR, merge.

### Task 10: Graphlet core: counting graph, interface, features, orbit files, oracle

**Files:**
- Modify: `loki/analysis/graphlets/__init__.py`
- Create: `tests/graphlet_oracle.py`, `tests/test_graphlets_core.py`

**Interfaces:**
- Consumes: `Graph`, `undirected_edges` (Task 2); `version_info` (Task 6); `classify_signals`, `SignalConfig`, `SignalInfo` (Task 9).
- Produces: `N_ORBITS = {4: 15, 5: 73}`; `class GraphletCounter(Protocol)` (spec 8.5); `BACKENDS: dict[str, GraphletCounter]`; `DEFAULT_BACKEND = "ext"`; `class BackendUnavailable(RuntimeError)`; `get_backend(name: str) -> GraphletCounter` (`"default"` resolves to `DEFAULT_BACKEND`; unknown `ValueError`; unavailable `BackendUnavailable` with the reason);
  `@dataclass(frozen=True) CountingGraph(n: int, src: np.ndarray, dst: np.ndarray, removed_edges: dict[str, int], dropped_hubs: list[tuple[str, int]], info: SignalInfo | None)`;
  `counting_graph(g: Graph, removal: str = "global", cfg: SignalConfig = SignalConfig(), hub_threshold: int = 1000) -> CountingGraph` (spec 8.3: `global` drops every edge whose class is not `signal`, then every edge of nodes whose remaining degree exceeds `hub_threshold`, listing `(node_id, degree)`; `none` keeps everything and `info` is still computed for the role features; both undirected, simple, `src < dst`, node count unchanged);
  `write_edge_file(path: Path, n: int, src, dst) -> None`; `read_orbit_file(path: Path, n: int, n_orbits: int) -> np.ndarray` (spec 8.5 protocol; `ValueError` on wrong row count or width);
  `graphlet_features(orbits: np.ndarray, roles: np.ndarray) -> np.ndarray` (spec 8.6);
  `run_graphlets(g: Graph, backend: str, out_dir: Path, *, size: int = 4, removal: str = "global", cfg: SignalConfig = SignalConfig(), hub_threshold: int = 1000, force: bool = False) -> Path` (refuses `size == 5` with `removal == "none"` unless `force`, raising `BackendUnavailable("5-node orbits on the full graph did not finish in 30 min; use --removal global or --force")`; writes the npz and JSON of spec 8.6; returns the JSON path);
  `load_orbits(g: Graph, backend: str, removal: str, out_dir: Path) -> tuple[np.ndarray, np.ndarray]` (orbits, roles).
- Produces in `tests/graphlet_oracle.py`: `brute_orbits(n: int, src: np.ndarray, dst: np.ndarray) -> np.ndarray` (int64 `(n, 15)`; enumerates all connected induced subgraphs of 2, 3 and 4 nodes, classifies by edge count and degree sequence (3 edges: path (1,2,2,1) or star (3,1,1,1); 4: cycle (2,2,2,2) or tailed triangle (3,2,2,1); 5: diamond; 6: K4; a disconnected 3-edge set with a triangle plus an isolated node is skipped), adds 1 to the orbit of each member; for n up to 200).

- [ ] **Step 1: Failing tests** with a `FakeCounter` (registered in the test; returns `brute_orbits`): oracle self-tests first, with hand-computed values from spec 8.4: `test_oracle_path4` (nodes 0-1-2-3: orbit 4 of 0 and 3 is 1, orbit 5 of 1 and 2 is 1, orbit 1 of 0 is 1, orbit 2 of 1 is 1, orbit 0 = degree), `test_oracle_star4` (hub orbit 7 = 1, leaves orbit 6 = 1, hub orbit 2 = 3), `test_oracle_triangle`, `test_oracle_c4_matches_orca` (every node `2 2 1 0 0 0 0 0 1 0 0 0 0 0 0`, the line ORCA printed), `test_oracle_tailed_triangle` (pendant 9, degree-2 nodes 10, degree-3 node 11), `test_oracle_diamond` (12 and 13), `test_oracle_k4` (orbit 14 = 1, orbit 3 = 3), `test_star_hub_exact` (star with 60 leaves: hub orbit 7 = 34220, orbit 2 = 1770), `test_oracle_identities` (random graph: sum of orbit 3 = 3 x triangles from `networkx.triangles`; sum of orbit 0 = 2m). Then core tests: `test_counting_graph_global_removes_non_signal` (`make_sync_design(reset=True, clocks=2)`: no remaining edge from clock or reset nets, `removed_edges["clock"]` and `["reset"]` equal the edge counts, all nodes kept); `test_hub_fallback_lists_nodes` (star with 10 leaves and `hub_threshold=5`: no edges left, `dropped_hubs == [(hub, 10)]`); `test_removal_none_keeps_everything`; `test_simple_undirected` (parallel edges, self-loops, direction merged; `src < dst`); `test_edge_file_roundtrip`; `test_run_graphlets_outputs` (npz arrays `orbits` int64 `(n, 15)`, `roles` int64 `(n, 4)`, `node_ids`; JSON keys of spec 8.6 including `classified`, `removed_edges`, `dropped_hubs`, `tool`; file names contain backend and removal); `test_size5_none_refused_without_force`; `test_features_roles_appended` (columns = non-constant orbit columns + 4); `test_default_backend_is_ext` (`DEFAULT_BACKEND == "ext"`); `test_unavailable_backend_message`; `test_zero_edge_graph`; `test_int64_survives_npz` (a counter returning `2**40`).
- [ ] **Step 2: Run** `python -m unittest tests.test_graphlets_core -v`. Expected: FAIL.
- [ ] **Step 3: Implement.** The orbit-file reader splits the whole text once and reshapes (no per-line Python loop); `counting_graph` uses the edge-class array to mask edges, then `np.bincount` degrees for the fallback.
- [ ] **Step 4: Run** tests, ruff, mypy. Expected: PASS.
- [ ] **Step 5: Commit** (`feat/l2-graphlets-core`), PR, merge.

### Task 10a: Structural features: WL colours, NPN classes, GSN vectors (spec 4.1)

Approved by Peter, 2026-10-21. The algorithms live in Loki III L1's `loki.features` (L1 plan Task 5a); this task adapts them to `Graph`, stores them, and feeds the PyG export and the GNN.

**Gate:** L1 Task 5a merged (`loki.features`).

**Files:**
- Create: `loki/analysis/structural.py`, `tests/test_structural.py`
- Modify: `loki/analysis/__init__.py` (`KINDS` gains `"structural"`), `loki/analysis/export.py` (structural block in `pyg_dict`), `loki/analysis/graphlets/__init__.py` (`gsn_features`), `tests/test_export_pyg.py`, `tests/test_analysis_pkg.py`

**Interfaces:**
- Consumes: `Graph`, `load_graph` (Task 2); `to_feature_graph` (Task 9); `load_orbits` (Task 10); from `loki.features` (L1 Task 5a): `classify_nets`, `WL_ROUNDS`, `WLConfig`, `refine`, `stable_partition`, `quotient`, `Quotient`, `npn_class`, `from_graph_json` (the adapter test only). `stats` is not consumed: its counters are process-global, so the spec-4.1 `npn` block (`distinct_tables`, `classes`, `exact`, `worst_enum`) is computed per graph for determinism.
- Produces in `structural.py`: `hash64(s: str) -> int` (spec 4.1: first 8 bytes of SHA-256, signed big-endian; 0 for `""`); `@dataclass(frozen=True) StructuralArrays(variant: str, wl: np.ndarray, npn: np.ndarray, roles: np.ndarray, npn_keys: tuple[str, ...], colours: tuple[tuple[str, ...], ...], stable_round: int | None, stable_class: np.ndarray | None, quotient: Quotient | None)` (`wl` int64 `(N, rounds + 1)`, `npn` int64 `(N,)`, `roles` int64 `(N, 4)`); `compute_structural(g: Graph, variant: str = "npn/both", rounds: int = WL_ROUNDS, with_quotient: bool = False) -> StructuralArrays`; `run_structural(g: Graph, out_dir: Path, variant: str = "npn/both", rounds: int = WL_ROUNDS, with_quotient: bool = False) -> Path` (npz and JSON of spec 4.1, returns the JSON path; reuses existing files with the same `graph_sha256` and options); `load_structural(g: Graph, variant: str, out_dir: Path) -> StructuralArrays`.
- Produces in `graphlets/__init__.py`: `gsn_features(orbits: np.ndarray | None, roles: np.ndarray, s: StructuralArrays) -> tuple[np.ndarray, np.ndarray]` (the numeric block of spec 8.6, roles only when `orbits` is `None`; the categorical int64 block `[npn, wl[:, 0], ..., wl[:, rounds]]`).
- `pyg_dict(g, split, include_structural: bool = True)` gains the spec 5 keys `gsn_roles`, `gsn_npn`, `gsn_wl`, `npn_keys`, `wl_variant`, and `gsn_orbits`/`gsn_orbits_source` only when `load_orbits` finds a file.

- [ ] **Step 1: Failing tests** (`tests/test_structural.py`, `@skip_without("numpy")`): `test_hash64` (`hash64("") == 0`; the value for `"4:6996"` equals the test's own `int.from_bytes(hashlib.sha256(b"4:6996").digest()[:8], "big", signed=True)`); `test_adapter_equals_from_graph_json` (fixture graph: `to_feature_graph(load_graph(p)) == from_graph_json(json.load(open(p)))`); `test_wl_ids_match_colours` (`wl[v, r] == hash64(colours[r][v])` for every node and round); `test_npn_keys_luts_only` (non-LUT nodes have key `""` and id 0); `test_structural_files_deterministic` (two runs: JSON byte-identical except `seconds`, arrays equal); `test_quotient_optional` (`stable_class` and `quotient` only with `with_quotient=True`); `test_cross_design_ids` (two fixture designs that share one identical sub-circuit: equal WL ids on its nodes at round 1); `test_gsn_features_blocks` (with and without orbits; categorical block int64 with `1 + rounds + 1` columns). In `tests/test_export_pyg.py`: `test_pyg_structural_keys` (`gsn_wl.shape == (n, 5)`, `gsn_npn.shape == (n,)`, `gsn_roles.shape == (n, 4)`, `len(npn_keys) == n`; no `gsn_orbits` without an orbit file, present after `run_graphlets` with a FakeCounter); `test_pyg_no_structural` (`include_structural=False`: none of the keys). In `tests/test_analysis_pkg.py`: `"structural" in KINDS`.
- [ ] **Step 2: Run** `python -m unittest tests.test_structural tests.test_export_pyg tests.test_analysis_pkg -v`. Expected: FAIL.
- [ ] **Step 3: Implement.** `compute_structural`: `to_feature_graph`, `loki.features.roles.classify_nets` on that `FeatureGraph` (the one implementation Task 9's `classify_signals` also calls), `refine` with `WLConfig(start, direction, rounds)` parsed from `variant`, `npn_class` per LUT node, arrays by `np.fromiter`; `hash64` with `int.from_bytes(hashlib.sha256(s.encode()).digest()[:8], "big", signed=True)`.
- [ ] **Step 4: Run** tests, ruff, mypy. Expected: PASS.
- [ ] **Step 5: Commit** (`feat/l2-structural`), PR, merge.

### Task G-ext: ORCA backend and `loki tools fetch-orca` (the default backend, decided by the spike)

**Files:**
- Create: `loki/analysis/graphlets/ext.py`, `loki/tools.py`, `tests/test_graphlets_ext.py`, `tests/data/fake_orca.py`
- Modify: `loki/analysis/graphlets/__init__.py` (register `"ext"`), `loki/cli.py` (subcommand `tools fetch-orca`); `tests/test_cli.py` is untouched (the usage test `test_cli_tools_fetch_orca_usage` lives in `tests/test_graphlets_ext.py`)

**Interfaces:**
- Consumes: Task 10 (`write_edge_file`, `read_orbit_file`, `BACKENDS`, `BackendUnavailable`).
- Produces in `ext.py`: constants `ORCA_COMMIT = "e146a8b1a99a90f5e3096b7bcc2ab0ea246c3ca7"`, `ORCA_SHA256 = "01c580febfd3653a632a04d6b466f7c6f2bf2f9baf3a75a2e553be30ac7ee778"`, `ORCA_URL = "https://raw.githubusercontent.com/thocevar/orca/" + ORCA_COMMIT + "/orca.cpp"`, `ORCA_LICENCE = "GPL-3.0 (https://github.com/thocevar/orca/blob/master/LICENSE); run as a separate program, never linked or vendored"`, `ORCA_CITATION` (Hocevar and Demsar, Bioinformatics 30(4):559-565, 2014, doi:10.1093/bioinformatics/btt717; Przulj, Bioinformatics 23(2):e177-e183, 2007, doi:10.1093/bioinformatics/btl301);
  `cache_dir() -> Path` (`~/.cache/loki/tools/orca-e146a8b`, `$XDG_CACHE_HOME` honoured); `find_orca(explicit: Path | None = None) -> Path | None` (order: argument, `$LOKI_GRAPHLET_TOOL`, `cache_dir()/orca`); `class OrcaCounter` (`name = "ext"`, `max_size = 5`, `__init__(self, tool: Path | None = None, argv_prefix: Sequence[str] | None = None, timeout: float = 7200.0)`, `available()`, `count(n, src, dst, size=4)` running `[tool, "node", str(size), in, out]` with `subprocess.run(..., capture_output=True, text=True, timeout=timeout, check=False)` in a `tempfile.TemporaryDirectory`, stdout/stderr discarded on success, a non-zero exit raises `RuntimeError` containing the last 5 stderr lines);
  in `loki/tools.py`: `fetch_orca(dest: Path | None = None, *, downloader: Callable[[str], bytes] = _http_get, compiler: str = "g++") -> Path` (downloads `ORCA_URL`, verifies `ORCA_SHA256` else `ValueError("orca.cpp sha256 mismatch")` and deletes nothing it did not create, writes `orca.cpp` into `cache_dir()`, builds `[compiler, "-O2", "-std=c++11", "-o", "orca", "orca.cpp"]` with an argv list, returns the binary; a second call with an existing binary returns at once).

- [ ] **Step 1: Failing tests:** `test_count_with_fake_tool` (`tests/data/fake_orca.py` implements `<node> <size> <in> <out>` using `brute_orbits`; `OrcaCounter(argv_prefix=[sys.executable, fake])` returns the oracle's array for 5 random graphs); `test_argv_is_list_no_shell` (monkeypatch `subprocess.run`: first arg a list of `str`, `shell` falsy, args end with `node 4 <in> <out>`); `test_tool_failure_message` (fake exits 1 writing to stderr: `RuntimeError` with the stderr text); `test_timeout`; `test_size5_width_73` (fake with size 5 returns 73 columns); `test_find_tool_order` (argument, env, cache); `test_available_false_with_reason` (`"run: loki tools fetch-orca"`); `test_fetch_verifies_sha` (injected downloader returning wrong bytes: `ValueError`; right bytes: `orca.cpp` written; compile step monkeypatched to record argv `["g++","-O2","-std=c++11","-o","orca","orca.cpp"]`); `test_constants_pinned` (`len(ORCA_COMMIT) == 40`, `len(ORCA_SHA256) == 64`, URL contains the commit); `test_cli_tools_fetch_orca_usage` (`loki tools` without subcommand exits 2); `test_real_orca_matches_oracle` (runs only when `find_orca()` finds a binary: 10 random graphs of 5 to 60 nodes, sizes 4 and 5 first 15 columns, equal to `brute_orbits`); `test_run_graphlets_with_fake_orca_end_to_end` (via `run_graphlets(..., backend="ext")` with the fake registered as the tool: files written, `tool.commit == ORCA_COMMIT`).
- [ ] **Step 2: Run** `python -m unittest tests.test_graphlets_ext -v`. Expected: FAIL.
- [ ] **Step 3: Implement** `OrcaCounter` and `fetch_orca`; register `BACKENDS["ext"] = OrcaCounter()`; `loki tools fetch-orca` prints the binary path and the licence line; `loki analyze graphlets --licence` (Task 13) prints `ORCA_LICENCE` and `ORCA_CITATION`. `_http_get` uses `urllib.request.urlopen(url, timeout=60)`; no redirects to other hosts are followed beyond what urllib does by default; only the pinned URL is requested.
- [ ] **Step 4: Run** tests, ruff, mypy. Then run once for real: `loki tools fetch-orca` and `test_real_orca_matches_oracle`. Expected: PASS. Record the ORCA times on `or1200` and `mcml` `graph.json` (if available) in the PR description and compare with the spike's numbers.
- [ ] **Step 5: Commit** (`feat/l2-graphlets-ext`), PR, merge.

### Task G-own-1: OPTIONAL, LATER. Promote the oracle to `count_reference`

Not needed for L2 to be done; the controller schedules it only if the own backend is wanted (spec 8.5). Skip both G-own tasks otherwise.

**Files:**
- Create: `loki/analysis/graphlets/own.py`, `tests/test_graphlets_own_ref.py`
- Modify: `tests/graphlet_oracle.py` (re-export from `own.py`)

**Interfaces:**
- Produces: `ORBIT_TABLE: dict[int, tuple[str, str]]` (the spec 8.4 table, 15 entries); `classify4(edges: set[tuple[int, int]], nodes: tuple[int, int, int, int]) -> tuple[str, tuple[int, int, int, int]]`; `count_reference(n, src, dst) -> np.ndarray` (the oracle's code moved here unchanged, documented O(n * d^3), n up to 2000).

- [ ] **Step 1: Failing tests:** `test_orbit_table_matches_spec` (keys 0..14, names as in spec 8.4); `test_classify4_cases` (path, star, cycle, tailed triangle, diamond, K4, each with its per-node orbit tuple); `test_reference_equals_oracle`.
- [ ] **Step 2: Run** `python -m unittest tests.test_graphlets_own_ref -v`. Expected: FAIL.
- [ ] **Step 3: Move** the code from `tests/graphlet_oracle.py` into `own.py`; the test helper re-exports `count_reference as brute_orbits`.
- [ ] **Step 4: Run** the full suite, ruff, mypy. Expected: PASS.
- [ ] **Step 5: Commit** (`feat/l2-graphlets-own-ref`), PR, merge.

### Task G-own-2: OPTIONAL, LATER. Own 4-node C counter

**Files:**
- Create: `loki/analysis/graphlets/native/orbits4.c`, `tests/test_graphlets_own_c.py`
- Modify: `loki/analysis/graphlets/own.py`, `loki/analysis/graphlets/__init__.py`, `pyproject.toml` (package data for the `.c` file)

**Interfaces:**
- Consumes: G-own-1, Task 10's file protocol; ORCA (Task G-ext) as the second oracle.
- Produces: C program `orbits4 <in> <out>` (file protocol of spec 8.5; exit 0, 2 on bad input; `int64_t` counts); `build_native(cache: Path | None = None) -> Path` (`cc -O2 -o <cache>/orbits4 orbits4.c` via argv list into `~/.cache/loki/graphlets/`, skipped when the binary is newer than the source); `class OwnCounter` (`name = "own"`, `max_size = 4`); `BACKENDS["own"]`. `DEFAULT_BACKEND` stays `"ext"`.

- [ ] **Step 1: Failing tests** (skip without `cc`): `test_c_equals_reference_random` (20 seeded graphs, n 5 to 60, sparse to dense); `test_c_equals_reference_netlist_like` (n = 400 with a hub of degree 300); `test_c_star_hub_exact_int64` (star d = 5000: hub orbit 7 = 5000*4999*4998//6 > 2**31); `test_c_zero_edges`; `test_c_rejects_bad_input` (self-loop, node out of range, wrong edge count: exit 2, `RuntimeError` with stderr); `test_build_is_cached`; `test_c_equals_orca` (skips without ORCA: 10 graphs); `test_size5_rejected`.
- [ ] **Step 2: Run** `python -m unittest tests.test_graphlets_own_c -v`. Expected: FAIL.
- [ ] **Step 3: Implement `orbits4.c`:** CSR with sorted neighbour lists; degrees; triangles per edge by degree-ordered orientation (O(sum min(du, dv))); per-pair common-neighbour counts for 4-cycles with the same ordering so hubs cost O(m * arboricity); the 4-node orbit identities of Hocevar and Demsar 2014 derived and verified against `count_reference`, not copied from memory; `calloc` with checks; peak memory O(n + m).
- [ ] **Step 4: Run** tests, ruff, mypy. Expected: PASS. Time it on mcml and LU64PEEng against ORCA's numbers in spec 3 (estimate 1 to 5 s, under 200 MB) and put the result in the PR.
- [ ] **Step 5: Commit** (`feat/l2-graphlets-own-c`), PR, merge.

### Task 11: GNN data: vocabulary, tensors, baselines

**Files:**
- Create: `loki/analysis/gnn.py`, `tests/test_gnn_data.py`

**Interfaces:**
- Consumes: `iter_dataset`, `load_graph`, `featurize` (Task 2); `graphlet_features` (Task 10) optionally; `compute_structural`, `gsn_features` (Task 10a).
- Produces: `TARGETS = ("construct_type", "role")`; `TRAIN_KINDS = ("lut", "ff", "hard", "gate")`; `build_vocab(graphs: Iterable[Graph], target: str, min_count: int = 5) -> list[str]` (class names sorted; `__other__` appended last, so index C = `len(names) - 1`); `encode(g: Graph, target: str, vocab: Sequence[str]) -> np.ndarray` (int64; -1 for empty target or kinds outside `TRAIN_KINDS`; unseen value maps to `__other__`); `@dataclass(frozen=True) Prepared(design, split, x: np.ndarray, edge_index: np.ndarray, y: np.ndarray, node_ids: tuple[str, ...])`; `prepare(entries, target, vocab, hard_types, scaler) -> list[Prepared]`; `fit_scaler(x_train_list) -> dict[str, np.ndarray]` (mean, std over `TRAIN_KINDS` nodes of train designs, `std == 0` replaced by 1; `log1p` applied to the count columns first); `baseline_majority(y_train, y_test) -> dict`; `baseline_logreg(xtr, ytr, xte, yte, seed) -> dict`; `metrics(y_true, y_pred) -> dict[str, float]` (`accuracy`, `macro_f1`, `n_nodes`, over nodes with `y >= 0`; zeros and `n_nodes 0` when none); `baseline_wl(wl_train: np.ndarray, y_train: np.ndarray, wl_test: np.ndarray, y_test: np.ndarray, min_count: int = 5) -> dict[str, float]` (spec 9: majority train class per WL id, backoff from the last round to round 0, then the majority class; `wl_*` int64 `(n, rounds + 1)`); `build_id_vocab(ids: Iterable[np.ndarray], min_count: int = 5) -> dict[int, int]` (id to index over train nodes, `__other__` last); `Prepared` gains `cat: np.ndarray | None` (the categorical block of `gsn_features`, mapped through the vocabularies).

- [ ] **Step 1: Failing tests:** `test_vocab_train_only_and_other` (a class with 3 train nodes and `min_count=5` lands in `__other__`; a class present only in test encodes to `__other__`); `test_encode_masks_pi_po_const` (PI/PO/const nodes are -1); `test_unlabelled_graph_raises` (`ValueError("graph has no labels: the GNN needs L0 labels")`; detect unlabelled explicitly as "no node of `TRAIN_KINDS` carries a non-empty `construct_type`", not as `g.labels is None`, which Task 2 documents as "every label object is empty": a from-blif graph labels its ports only, so it is refused while cluster and export accept it); `test_scaler_fit_on_train_only` (changing test data does not change mean/std); `test_majority_baseline_value`; `test_logreg_baseline_learns_planted_signal` (on `make_dataset` data accuracy above majority); `test_metrics_empty`; `test_split_respected` (`iter_dataset` entries partition into train/test exactly as `split_of`; designs of status skipped absent); `test_wl_baseline_backoff` (a round-4 id seen 6 times predicts its majority; a test id unseen at round 4 but seen at round 2 uses round 2; nothing seen gives the majority class); `test_wl_baseline_planted_colour` (labels fixed by the round-1 colour: accuracy 1.0); `test_id_vocab_min_count`.
- [ ] **Step 2: Run** `python -m unittest tests.test_gnn_data -v`. Expected: FAIL.
- [ ] **Step 3: Implement** with numpy and sklearn only (this task needs `analysis`, not torch; the torch import is added in Task 12). The count columns for `log1p` are the same set as Task 7.
- [ ] **Step 4: Run** tests, ruff, mypy. Expected: PASS.
- [ ] **Step 5: Commit** (`feat/l2-gnn-data`), PR, merge.

### Task 12: GNN model: train, evaluate, outputs

**Files:**
- Modify: `loki/analysis/gnn.py`
- Create: `tests/test_gnn_train.py`

**Interfaces:**
- Consumes: Task 11.
- Produces: `class Net(torch.nn.Module)` (`__init__(self, in_dim: int, n_classes: int, kind: str = "sage", hidden: int = 64, dropout: float = 0.2)`; two `SAGEConv` or `GCNConv` layers, ReLU, dropout, linear head); `train_eval(dataset: Path, floor: str, out: Path, *, model: str = "sage", target: str = "construct_type", epochs: int = 100, hidden: int = 64, lr: float = 0.01, weight_decay: float = 5e-4, min_count: int = 5, seed: int = 0, features: Sequence[str] = ("node",)) -> dict[str, object]` (spec 9 structural inputs: `graphlet` appends the numeric block, `wl`/`npn` add size-8 `torch.nn.Embedding`s over the Task 11 vocabularies; `Net.__init__` gains `cat_sizes: Sequence[int] = ()`; `metrics.json` gains `baselines.wl` and `beats_wl`) (spec 9: vocabulary from train designs, scaler, undirected edges via `to_undirected`, class weights `1/sqrt(count)` normalised to mean 1, full-batch per design with summed gradients, fixed epochs, then evaluation on train and test designs, baselines, writes `config.json`, `vocab.json`, `model.pt`, `metrics.json`, `predictions-<design>.csv` for test designs, returns the metrics dict); `run_gnn(args) -> int` is added in Task 13.

- [ ] **Step 1: Failing tests** (`@skip_without("torch", "torch_geometric", "sklearn")`) on `make_dataset(root, designs=8)`: `test_trains_above_majority` (test `accuracy` greater than `baselines.majority.accuracy`, train `accuracy >= 0.9` for both `sage` and `gcn`); `test_deterministic_metrics` (two runs with the same seed give equal `metrics.json` bytes; `config.json` identical); `test_outputs_complete` (the five file kinds exist; `predictions-*.csv` header `node_id,true,pred`, one file per test design; `metrics.json` has `train`, `test`, `baselines.majority`, `baselines.logreg`, `note`); `test_target_role`; `test_other_class_for_unseen` (planted extra class only in a test design is predicted/encoded as `__other__`); `test_no_label_columns_in_input_dim` (`config.json["in_dim"] == len(feature names)` of Task 2, i.e. 8 + 7 + 4 + T + 1); `test_unlabelled_dataset_raises`; `test_no_test_designs_ok` (all designs train: `metrics["test"]["n_nodes"] == 0`, no crash); `test_missing_extra_message` (monkeypatch `require` to raise: `MissingExtra`); `test_metrics_wl_baseline_and_beats_wl` (`baselines.wl` has `accuracy` and `macro_f1`; `beats_wl` is a bool equal to `test.macro_f1 > baselines.wl.macro_f1`); `test_features_wl_npn_embeddings` (`features=("node","wl","npn")`: trains, `config.json` lists the features and embedding sizes); `test_default_features_node_only` (`config.json["features"] == ["node"]`).
- [ ] **Step 2: Run** `python -m unittest tests.test_gnn_train -v`. Expected: FAIL.
- [ ] **Step 3: Implement** `train_eval` with `seed_everything(seed)` and `torch.use_deterministic_algorithms(True)` set at entry (and restored in `finally`); `model.pt` is `torch.save({"state_dict": ..., "scaler": {...lists}, "vocab": [...], "config": {...}}, ...)` using only tensors and builtins so `weights_only=True` loads it. The `note` text is the "honest limit" sentence of spec 9. Metrics rounding via `round(x, 4)`.
- [ ] **Step 4: Run** tests, ruff, mypy. Expected: PASS.
- [ ] **Step 5: Commit** (`feat/l2-gnn-train`), PR, merge.

### Task 13: Runner and `loki analyze` CLI

**Files:**
- Create: `loki/analysis/run.py`, `tests/test_analysis_cli.py`
- Modify: `loki/cli.py` (add subcommand `analyze` delegating to `loki.analysis.run.main`), `tests/test_cli.py` (usage test for `analyze` with no kind exits 2)

**Interfaces:**
- Consumes: Tasks 2 to 12, Task 9 and 10 and G-ext through `get_backend`; `loki.tools.fetch_orca` (G-ext).
- Produces: `main(argv: Sequence[str] | None = None) -> int` implementing spec 10's CLI and exit codes (0 ok, 1 analysis failure, 2 usage, 3 missing extra or backend unavailable); `resolve_input(args) -> tuple[Graph, str]` (`--graph` file, or `--dataset/--design/--floor` -> `<dataset>/<design>/<floor>/graph.json`; the design must be `ok` in the manifest, else exit 1 with the reason); output tree of spec 11 under `--out`; `write_metrics(out: Path, metrics: dict[str, float]) -> None` (`<out>/metrics.json`, numbers only, sorted keys); `parse_features(s: str) -> list[str]` (`node`, `graphlet`, `wl`, `npn`; others `ValueError`; `wl` and `npn` only for `gnn`, the `cluster` kind exits 2 with "wl and npn are categorical ids; only gnn uses them"); the `structural` kind (`--wl-variant`, `--rounds`, `--quotient`; `metrics.json`: `stable_round` (-1 for none), `classes_last_round`, `npn_classes`, `seconds`) and export `--no-structural` (spec 10); for `--features node,graphlet` the runner calls `load_orbits` (backend and removal from the options) and computes with `run_graphlets` first when missing, then passes `graphlet_features(orbits, roles)` as `extra`; the `graphlets` kind takes `--backend --size --removal --hub-threshold --min-fanout --force --graphlet-tool --licence` of spec 10 and prints `ORCA_LICENCE` and `ORCA_CITATION` for `--licence`; `metrics.json` of `graphlets` has the keys of spec 10.

- [ ] **Step 1: Failing tests** (call `main([...])` in process, tmp dirs, fixture dataset): `test_export_all_formats` (exit 0, files exist per spec 11); `test_export_region_cone` (`--region cone:<id>:in:2`); `test_cluster_all_four_files_and_metrics_json` (`metrics.json` keys `n_clusters_kmeans`, `modularity_louvain`, ... numbers only); `test_cluster_with_graphlet_features` (registers a FakeCounter as default via monkeypatch; orbit file is created then reused); `test_graphlets_ext_missing_exit_3` (ORCA not installed: exit 3 with `run: loki tools fetch-orca`); `test_graphlets_removal_none_size5_exit_3`; `test_graphlets_metrics_keys` (FakeCounter as default: `removed_edges_total`, `dropped_hubs`, `clock_domains`, `nodes`, `edges`, `seconds`); `test_licence_flag_prints_gpl_notice`; `test_gnn_metrics_json_keys` (`test_accuracy`, `test_macro_f1`, `baseline_majority_accuracy`); `test_missing_extra_exit_3` (monkeypatch `require`); `test_bad_args_exit_2` (unknown kind, `--method` bad value, both `--graph` and `--dataset`); `test_failure_exit_1` (affinity non-convergence monkeypatched; invalid graph.json); `test_deterministic_rerun_byte_identical` (cluster outputs); `test_unlabelled_graph_json_cluster_and_export_ok` (graph.json without labels: exit 0, partition `nmi_*` null); `test_never_writes_in_dataset_dir` (dataset tree hash before and after equal); `test_structural_kind_outputs` (npz and JSON of spec 4.1, `metrics.json` keys); `test_cluster_rejects_wl_features` (exit 2); `test_export_no_structural_flag`; `test_gnn_features_wl` (`--features node,wl,npn` accepted).
- [ ] **Step 2: Run** `python -m unittest tests.test_analysis_cli tests.test_cli -v`. Expected: FAIL.
- [ ] **Step 3: Implement** with `argparse` (sub-subparsers per kind); `--seed` default 0; catch `MissingExtra`/`BackendUnavailable` -> 3, `ClusterError`/`RegionError`/`ValueError` from inputs -> 1 with a one-line message on stderr.
- [ ] **Step 4: Run** tests, ruff, mypy. Expected: PASS.
- [ ] **Step 5: Commit** (`feat/l2-cli`), PR, merge.

### Task 14: Wyrd step plugins

**Files:**
- Create: `loki/analysis/steps.py`, `tests/test_analysis_steps.py`
- Modify: `pyproject.toml` (the four entry points of spec 10)

**Interfaces:**
- Consumes: Wyrd's `RunSpec`, `StepSpec`, `Metric`, `Settings` as in L0 Task 8 (`~/odin3-ws/wyrd/tests/helpers.py` shows how to build them); the CLI of Task 13.
- Produces: `class _AnalysisStep` base (`tools = ()`, `is_vpr = False`, `collect` reading `<step_dir>/analysis/metrics.json`, falling back to the older-layout `<step_dir>/metrics.json`, into `Metric(name, float(value))`, missing file gives `[]`); `ExportStep` (`name = "loki-export"`), `ClusterStep` (`"loki-cluster"`), `GraphletStep` (`"loki-graphlets"`), `GnnStep` (`"loki-gnn"`), each `__init__(self, spec: StepSpec)` validating its args (`dataset` required, `floor` default `"f2"`, `seed` default 0, kind options as in spec 10, unknown key `ValueError("step 'loki-cluster': unknown argument 'x'")`) and `command(run, step_dir, settings) -> tuple[list[str], dict[str, str]]` building `[sys.executable, "-m", "loki.analysis.run", <kind>, "--dataset", <dataset>, "--design", run.design.name, "--floor", <floor>, "--out", str(step_dir / "analysis"), "--seed", str(seed), ...]` and env `{}` plus `LOKI_GRAPHLET_TOOL` copied from `os.environ` when set (`GnnStep` omits `--design`). List-valued args (`format = ["edgelist", "pyg"]`) become one comma-joined option.

- [ ] **Step 1: Failing tests** (module skipped with `unittest.SkipTest` when `wyrd` is not importable): `test_cluster_command_argv`; `test_export_format_list_joined`; `test_gnn_has_no_design_flag`; `test_missing_dataset_rejected`; `test_unknown_arg_rejected`; `test_collect_reads_metrics_json` (two metrics); `test_collect_missing_file_empty`; `test_entry_points_load` (installed package: `importlib.metadata.entry_points(group="wyrd.steps")` has the four names; `wyrd.steps.get_step(StepSpec("loki-cluster", {"dataset": "/d"}))` returns a `ClusterStep`; skip if not installed); `test_command_runs_end_to_end` (execute the returned argv with `subprocess.run` against the fixture dataset, exit 0, `metrics.json` exists; `collect` returns metrics).
- [ ] **Step 2: Run** `python -m unittest tests.test_analysis_steps -v`. Expected: FAIL.
- [ ] **Step 3: Implement** the four classes over one base; the entry points go in `pyproject.toml`.
- [ ] **Step 4: Run** tests, ruff, mypy (mypy needs Wyrd importable, as in L0 Task 8). Expected: PASS.
- [ ] **Step 5: Commit** (`feat/l2-steps`), PR, merge.

### Task 15: Scale test, acceptance test, documentation

**Files:**
- Create: `tests/test_scale_l2.py`, `tests/test_acceptance_l2.py`
- Modify: `README.md`, `CLAUDE.md`

**Interfaces:**
- Consumes: everything above; `big_synthetic` (Task 1).
- Produces: nothing new in code; the budgets of spec 3 as test constants `BUDGETS: dict[str, tuple[float, float]]` (seconds, MB) in `tests/test_scale_l2.py`.

- [ ] **Step 1: Write the tests.** `test_scale_l2.py` (runs only when `LOKI_SCALE=1`, `@skip_without` analysis): build the 100k-node, 300k-edge graph with `big_synthetic`, wrap it in a `Graph` (helper in the test), then for Louvain, spectral, k-means, affinity (sample 3000), `classify_signals`, `loki analyze structural` (4 rounds, then again with `--quotient`; the JSON records one combined `seconds` for colour refinement plus NPN classes, so the test composes the spec-3 rows: refinement 30 s plus NPN 60 s, and with `--quotient` plus the coarsest equitable partition 60 s), the ORCA backend when installed (size 4 and 5 with `--removal global`; size 4 `--removal none` only under `LOKI_SCALE=2`), the own C backend if it exists, and PyG export, record `time.monotonic()` and `resource.getrusage(resource.RUSAGE_SELF).ru_maxrss`; assert each is under 2x the budget of spec 3 (each analysis in a fresh subprocess so RSS is per analysis, via `subprocess.run([sys.executable, "-m", "loki.analysis.run", ...])` on a graph.json written from the synthetic arrays by a fixture writer; the graphlet run only when its backend is available). Under `LOKI_SCALE=2` use the 820k-node, 1.6M-edge graph (and the golden LU64PEEng `graph.json` when `$LOKI_BIG_GRAPH` is set) and the 820k budgets of spec 3, including `graph.json` load (8 GB, 120 s) and Louvain (the 15 minute rule of spec 14 item 7). `test_acceptance_l2.py`: the five items of spec 12 on `make_dataset(designs=8)` (and on a real L0 micros dataset when `$LOKI_L0_DATASET` points to one), including the structural keys of item 1 and `baselines.wl`/`beats_wl` of item 4; `beats_wl` is asserted only on the real micros dataset (spec 14 item 8), and a failure there is reported to the controller as a finding with the rerun on `--features node,graphlet,wl,npn`.
- [ ] **Step 2: Run** `python -m unittest tests.test_acceptance_l2 -v`. Expected: PASS (fix anything it exposes in the owning module, never in the test).
- [ ] **Step 3: Run the scale test once locally:** `LOKI_SCALE=1 python -m unittest tests.test_scale_l2 -v`. Expected: PASS; if a budget fails, the failing analysis's numbers go into the PR description and the controller decides between a spec change and a fix. Do not run the graphlet part while Odin III sweeps are running (memory limit of the WSL VM; run it alone).
- [ ] **Step 4: Docs.** `README.md`: an "Analysis" section with the four commands and a one-line example each, the extras, the output tree, and the citations of spec 9 (GNN-RE, GNN4IC) and of the graphlet method (Przulj 2007, Bioinformatics 23(2):e177-e183; Hocevar and Demsar 2014, Bioinformatics 30(4):559-565; `ORCA_CITATION`, the ORCA GPL-3 statement and `loki tools fetch-orca`). `CLAUDE.md`: how to run the scale test.
- [ ] **Step 5: Commit** (`feat/l2-acceptance`), PR, merge.

## Self-review

- Spec coverage of the 2026-10-21 features: shared classifier (Task 9), structural arrays, GSN vectors and PyG keys (Task 10a), 1-WL baseline and structural GNN inputs (Tasks 11, 12), CLI kind and options (Task 13), budgets and acceptance (Task 15); spec 14 items 8 to 11 (Tasks 15, 10a/11, 9, 10a).
- Spec coverage: decision 1 (Tasks 3 to 5), decision 2 (Tasks 6 to 8; partition storage and evidence Task 6), decision 3 (global-signal classifier Task 9, counting graph and interface Task 10, ORCA Task G-ext, optional own backend G-own-1 and G-own-2), decision 4 (Tasks 11, 12), decision 5 (Tasks 13, 14); scale and determinism (Task 15 plus determinism tests in Tasks 4, 6, 8, 12, 13); features without leakage (Task 2); extras and skip behaviour (Task 1, tests everywhere); L1 evidence (Task 6, spec 14 item 1); acceptance (Task 15).
- Type consistency: `Graph`, `Partition`, `Region`, `FeatureMatrix`, `SignalInfo`, `CountingGraph`, `GraphletCounter`, `Prepared` are defined once (Tasks 2, 6, 3, 2, 9, 10, 10, 11) and used with those names; `StructuralArrays`, `hash64`, `gsn_features` (Task 10a) and `to_feature_graph` (Task 9) likewise; `FeatureGraph`, `SignalConfig`, `NetRoles`, `WLConfig`, `Quotient`, `npn_class` come from L1 Task 5a unchanged; `canonical_numbers` (Task 2) is used by Tasks 6, 7, 8; `resolve_k` and `cluster_space` (Task 7) by Task 8; `brute_orbits` (Task 10) by G-ext and G-own.
- Order and conditionals: the classifier (Task 9) precedes the counting core (Task 10) and the ORCA task. Tasks 10 and later work with a `FakeCounter` and reach backends only through `get_backend`; G-own-1 and G-own-2 are optional and later and nothing else depends on them.
- Proportion: tasks give signatures, test names and assertions; bodies appear only for the stated algorithms.
