import copy
import csv
import io
import unittest
from typing import Any

from loki import schemas
from loki.schemas import (
    LABEL_COLUMNS,
    dump_json,
    split_of,
    validate_design,
    validate_graph,
    validate_key,
    validate_labels_csv,
    validate_manifest,
    validate_meta,
)

HEADER = (
    "node_id,kind,cell_type,construct_type,construct_types,n_construct_cells,module_path,"
    "bus_name,bit_index,role,hdl_file,hdl_line,hdl_col,hdl_end_line,hdl_end_col,n_spans"
)


def graph_example() -> dict[str, Any]:
    labels = {
        "construct_type": "$eq", "construct_types": "$eq|$gt", "n_construct_cells": 2,
        "module_path": "top", "bus_name": "AeqB", "bit_index": 0, "role": "datapath",
        "hdl_file": "bm.v", "hdl_line": 12, "hdl_col": 6, "hdl_end_line": 12,
        "hdl_end_col": 12, "n_spans": 1,
    }
    feats = {"fan_in": 4, "fan_out": 2, "level": 1, "lut_width": 4, "lut_table": "9009",
             "is_seq": 0, "is_const": 0, "hard_ports": 0}
    return {
        "schema": 1, "design": "micro_x", "floor": "f2",
        "nodes": [
            {"id": "n17", "kind": "lut", "features": feats, "labels": labels},
            {"id": "n40", "kind": "po", "features": dict(feats), "labels": dict(labels)},
        ],
        "edges": [{"src": "n17", "dst": "n40", "net": "n3", "pin": "I0"}],
    }


class SchemasTest(unittest.TestCase):
    def test_label_columns_exact(self) -> None:
        self.assertEqual(",".join(LABEL_COLUMNS), HEADER)

    def test_validate_graph_ok_and_errors(self) -> None:
        self.assertEqual(validate_graph(graph_example()), [])
        g = graph_example()
        g["bogus"] = 1
        self.assertIn("bogus", " ".join(validate_graph(g)))
        g = graph_example()
        g["nodes"][0]["kind"] = "foo"
        self.assertIn("foo", " ".join(validate_graph(g)))
        g = graph_example()
        g["nodes"][0]["labels"]["role"] = "bar"
        self.assertIn("bar", " ".join(validate_graph(g)))
        g = graph_example()
        g["nodes"][1]["id"] = "n17"
        self.assertIn("duplicate node id 'n17'", " ".join(validate_graph(g)))
        g = graph_example()
        g["edges"][0]["dst"] = "n99"
        self.assertIn("n99", " ".join(validate_graph(g)))

    def test_csv_quoting(self) -> None:
        buf = io.StringIO()
        w = csv.writer(buf, lineterminator="\n")
        w.writerow(LABEL_COLUMNS)
        row = dict.fromkeys(LABEL_COLUMNS, "-1")
        row.update(node_id="n1", kind="lut", cell_type="$lut", construct_type="", role="unknown",
                   construct_types="", module_path='top/u 1,"x"', bus_name="", hdl_file="a b.v")
        w.writerow([row[c] for c in LABEL_COLUMNS])
        self.assertEqual(validate_labels_csv(buf.getvalue()), [])
        self.assertTrue(validate_labels_csv("a,b\n"))

    def test_split_is_stable(self) -> None:
        self.assertEqual(split_of("micro_a"), split_of("micro_a"))
        got = [split_of(f"d{i}") for i in range(200)]
        self.assertEqual(set(got), {"train", "test"})
        share = got.count("train") / len(got)
        self.assertTrue(0.7 <= share <= 0.9, share)

    def test_dump_json_deterministic(self) -> None:
        a = dump_json({"b": 1, "a": [1, 2]})
        self.assertEqual(a, dump_json({"a": [1, 2], "b": 1}))
        self.assertTrue(a.endswith("}\n"))
        self.assertLess(a.index('"a"'), a.index('"b"'))

    def test_key_meta_design_manifest(self) -> None:
        key: dict[str, Any] = {"schema": 1, "design": "d", "floor": "f2", "top": "t",
               "nets": {"n0": {"odin_id": 1, "names": ["A[0]"]}},
               "cells": {"n9": {"odin_id": 7, "type": "$lut", "name": "", "word_ids": [6]}},
               "ports": [{"anon": "n20", "orig": "A[0]", "dir": "in", "net": "n0"}]}
        self.assertEqual(validate_key(key), [])
        bad: dict[str, Any] = copy.deepcopy(key)
        bad["nets"]["x1"] = {"odin_id": 1, "names": []}
        self.assertTrue(validate_key(bad))
        meta: dict[str, Any] = {
                "schema": 1, "design": "d", "floor": "f2", "odin3_version": "1", "abi_version": 1,
                "script": ["a"], "loki_version": "0.1.0",
                "counts": {k: 0 for k in schemas._COUNTS}, "unmatched": 0, "loops_cut": 0,
                "equiv": {"writer": {"status": "equivalent", "tool_exit": 0}}}
        self.assertEqual(validate_meta(meta), [])
        meta["extra"] = 1
        self.assertTrue(validate_meta(meta))
        design = {"schema": 1, "design": "d", "benchmark": "micro", "top": None,
                  "files": [{"path": "a.v", "sha256": "00"}],
                  "source": {"url": "u", "commit": "c", "license": "MIT"}}
        self.assertEqual(validate_design(design), [])
        man: dict[str, Any] = {
               "schema": 1, "created_by": "loki 0.1.0", "odin3_version": "1", "split_seed": "s",
               "split_rule": "r", "designs": [
                   {"design": "d", "benchmark": "micro", "split": "train",
                    "floors": {"f2": {"status": "ok", "nodes": 3}}}]}
        self.assertEqual(validate_manifest(man), [])
        man["designs"][0]["floors"]["f9"] = {"status": "ok"}
        self.assertTrue(validate_manifest(man))


if __name__ == "__main__":
    unittest.main()
