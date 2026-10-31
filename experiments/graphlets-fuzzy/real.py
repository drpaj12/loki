"""What a real thing looks like: per pattern x cell x mode orbit statistics from the library."""

from __future__ import annotations

import fzlib as fl
import l3dlib
import numpy as np

NAME = {}
for r in fl.fuzz.catalogue():
    for o, _n in r["orbits"]:
        NAME[o] = f"G{r['g']}[" + " ".join(f"{a}>{b}" for a, b in r["arcs"]) + "]"


def main() -> int:
    rows = []
    lib = fl.Lib()
    for mode in ("undirected", "directed"):
        for cell in fl.CELLS:
            ents = lib.rows[(cell, mode)]
            x = np.array([e["po"]["tot"] / max(1.0, e["po"]["tot"].sum()) for e in ents])
            pat = np.array([e["pattern"] for e in ents])
            wid = np.array([e["width"] for e in ents], dtype=float)
            for p in fl.CLASSES:
                sel = pat == p
                if sel.sum() < 3:
                    continue
                mu, var = x[sel].mean(0), x[sel].var(0)
                for ref, mask in (("glue", pat == "glue"), ("other", (pat != p) & (pat != "glue"))):
                    if p == "glue" and ref == "glue":
                        continue
                    sd = np.sqrt((var + x[mask].var(0)) / 2) + 1e-9
                    z = (mu - x[mask].mean(0)) / sd
                    for o in np.argsort(-np.abs(z))[:3]:
                        slope = np.polyfit(np.log(wid[sel]), np.log1p(
                            np.array([e["po"]["tot"][o] for e, s in zip(ents, sel, strict=True)
                                      if s])), 1)[0]
                        rows.append({"mode": mode, "cell": cell, "pattern": p, "versus": ref,
                                     "orbit": int(o), "arcs": NAME[int(o)] if mode == "directed"
                                     else "", "mean_share": round(float(mu[o]), 4),
                                     "sd_share": round(float(np.sqrt(var[o])), 4),
                                     "std_diff": round(float(z[o]), 2),
                                     "width_slope": round(float(slope), 2),
                                     "instances": int(sel.sum())})
    l3dlib.write_csv(fl.RES / "real_orbits.csv", list(rows[0]), rows)
    print(len(rows), "rows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
