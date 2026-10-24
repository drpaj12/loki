# Dataset files

```
dataset/
  manifest.json
  <design>/
    design.json
    <floor>/
      netlist.blif   netlist.v   graph.json   labels.csv   key.json   meta.json
```

| File | Content |
|---|---|
| `manifest.json` | The designs, their floors and status, and the train/test split. |
| `design.json` | Per-design facts. |
| `netlist.blif`, `netlist.v` | The anonymised netlist; every name is `n<k>`. |
| `graph.json` | Nodes and edges of the netlist graph. |
| `labels.csv` | One row per graph node: the answer key. |
| `key.json` | Maps the anonymous names back to the original names. |
| `meta.json` | Build facts, including the equivalence result. |

All files are UTF-8 with `\n` line ends and are written deterministically, so two builds of one
input are byte-identical. Every JSON file has `"schema": 1`; a reader refuses another value.

## labels.csv

The header is exactly:

```
node_id,kind,cell_type,construct_type,construct_types,n_construct_cells,module_path,bus_name,bit_index,role,hdl_file,hdl_line,hdl_col,hdl_end_line,hdl_end_col,n_spans
```

`role` is one of `datapath`, `control`, `mixed`, `io`, `const`, `unknown`. Missing text is an empty
string and missing integers are `-1`. The `hdl_*` columns hold the first source span.

## What `loki check` verifies

- every file validates against its schema, and unknown keys are errors;
- node IDs in `graph.json` equal the `node_id` column of `labels.csv`, row for row;
- every edge endpoint is a node;
- every BLIF name is `n<k>`, and `key.json` covers every name;
- every node has a labels row;
- every `meta.json` equivalence status is `equivalent` or a warning-level status;
- `manifest.json` lists exactly the design directories present.

The exact rules are section 10 of the
[L0 spec](https://github.com/drpaj12/loki/blob/main/docs/specs/2026-10-21-l0-dataset-design.md).

## reverse-provenance.json (`loki re` output)

Odin III's forward provenance says where each netlist element came from in the HDL. Reverse
provenance is the inverse claim of Loki: for each piece of recovered structure, which cells and nets
of the input netlist it covers, what Loki says it is, how sure Loki is and why. Every `loki re` run
writes `reverse-provenance.json` next to `design.v`. It is a curated, stable view of
`overlay.json`; it does not change `overlay.json`, `report.json` or the inline `loki_*` attributes
of `design.v`. The file is deterministic (sorted keys, floats at 6 decimals), so two runs of one
input give identical bytes. Element ids (`h12`) are the `loki_hid` values of `design.v`, so the
inline attribute points into this file.

| Key | Content |
|---|---|
| `schema` | `1`. |
| `header` | `loki` and `odin3` versions, `input` (`path`, `sha256`), `floor`, `calib` (`path`, `sha256`), `seed`, `commit_threshold` (0.9) and `candidate_threshold` (`--rp-min-p`, default 0.5). |
| `netlist` | `cells`, `inputs`, `outputs`: the names of the input netlist (used to join an L2 partition). |
| `elements` | One per claim, ordered by id; see below. |
| `buses` | `id`, `width`, `order_source` (what fixed the bit order), `bits` (the nets of each bit, bit 0 first). |
| `fsms` | `id`, `state_nets`, `control_nets`, `reset_net`, `states`, `reset_state`, `encoding`, `transitions` (`[state, control value, next state]` integers), `transitions_total`. |
| `hierarchy` | The committed module tree: `id`, `module`, `instance`, `children`. |
| `coverage` | `cells_total`; `committed`, `candidate`, `uncovered` (`cells`, `fraction`); `uncovered_cells`; `uncovered_nets` (nets driven by uncovered cells). |
| `l2` | Optional. Added by `loki rp add-l2`: `method`, `partition`, `clusters` (members and overlap with committed modules). |

An element is a hypothesis that is committed, or a candidate with `p_comp` at or above the
candidate threshold, or rejected after a proof or a failed commit (negative evidence). Hypotheses of
kind `role` are not elements; they set the `role` of the elements they lie in.

| Element key | Content |
|---|---|
| `id`, `kind`, `stage` | The id, the kind (`adder`, `fsm`, `bus`, ...) and `"L1"`. |
| `status` | `committed`, `candidate` or `rejected`. |
| `fn`, `width`, `params` | The function text (as in `loki_fn`), the width and the detector parameters. |
| `proof` | `label` (`equivalent`, `derived`, `unproven`, `none`), `engine`, `verdict`, `from` (the source of a transferred proof). |
| `p_comp`, `prior_log_odds`, `log_odds` | Final probability and log-odds (`"inf"`/`"-inf"` as text). |
| `evidence` | At most 5 items (`name`, `source`, `value`, `llr`), highest absolute `llr` first. |
| `cells`, `nets`, `ports` | Input-netlist cell names; nets by role; claim inputs and outputs (nets least-significant bit first). |
| `recovered` | `module`, `instance`, `form` in `design.v`; `null` unless committed. |
| `parents`, `children`, `conflicts` | Ids of other elements. |
| `role` | `control`, `datapath`, `mixed` or empty when unknown (as in `loki_role`). |
| `reason` | Why a rejected element was rejected; empty otherwise. |

`loki.schemas.validate_reverse_provenance` checks a file against this schema.
