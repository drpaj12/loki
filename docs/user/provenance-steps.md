# Reading Odin III provenance at every stage

Odin III 1.4 writes a provenance manifest for every step of a flow (`<out>/prov/`): the HDL, the IR,
the mapped gates or LUTs, and, in the silicon flow, the placed, routed, GDS, extracted and recovered
layout. Loki reads them with `loki/prov_steps.py`, so an object at any stage resolves back to the HDL
text it came from. The file format and the JSON Schemas are in the Odin III manual
(`docs/user/provenance-files.md`, `docs/schemas/`); this page is the reader's side.

## Contract

Loki reads: `index.json` (`schema`, `flow`, `design`, `top`, `steps[].id/stage/file/objects/sha256/
objects_sha256/count/needs/tool`, `tools`), each step header (`stage`, `links`, `census`, `check`, `map`)
and each object line (`id`, `stage`, `kind`, `name`, `type`, `origin`, `links[].to/kind/confidence`,
`attrs`, `src`, `recs`). Unknown fields are ignored. A `schema` other than 1, a sha256 that differs from the
index, a missing `index.json` (a partial run) and a link to an object that does not exist are all
`ProvError`.

## Python

```python
from pathlib import Path
from loki.prov_steps import read_run, resolve

run = read_run(Path("out/prov"))
for obj in run.stage_objects("recovered"):
    res = resolve(run, obj)
    if obj.origin == "hdl" and not res.reached_hdl:
        ...                       # a broken chain
print(res.path, res.weakest, res.sources)
```

`resolve` walks `links` from the object to the first object of stage `hdl` or `ir` by the shortest path
(ties go to the stronger link). `weakest` is the lowest confidence on that path (`exact` > `high` >
`medium` > `low` > `ambiguous`); `sources` are the file and span of every terminal object reached. An
object with a `physical:KIND` origin (a tap, clock buffer, fill, tie with no HDL constant) has no HDL
parent: `reached_hdl` is False and `origin` says which step inserted it. That is the answer key for
"which cells of a layout come from the HDL".

## Command line

```text
loki prov OUT/prov                       one line per step: stage, objects, how many have an HDL chain, checks
loki prov OUT/prov --resolve recovered:o3__c9
```

## Tests and fixtures

`tests/test_prov_steps.py` reads two runs written by Odin III 1.4 (`tests/data/prov_steps/silicon`:
the 4-bit comparator through GDS and back, 17 cells; `tests/data/prov_steps/vtr`: the same design through
`odin3-flow --prov`). They are copies of Odin III `tests/silicon/comparator*/prov`; regenerate them with
`python3 tools/silicon/silicon_flow.py ...` (silicon) and `odin3-flow --prov --no-vpr` (VTR) from the
Odin III checkout.

## Limits

Device-level (transistor) objects are not in v1.4 files (the `extracted` stage holds cells). The reader
does not follow the name map chains named by `recs`; `odin3.read_name_map` does. Mímir III's schema has no provenance stages
(its HDL graph keeps the atom to span relationships of the name map, which 1.4 does not change), so Mímir needs no change.
