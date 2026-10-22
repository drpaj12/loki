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
