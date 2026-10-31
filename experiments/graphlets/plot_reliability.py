"""Reliability diagram (SVG, no plotting library): ``python -B plot_reliability.py``.

x = posterior bin midpoint, y = observed share of same-pattern pairs, point area ~ pairs; the
diagonal is perfect calibration. Reads results/part_reliability.csv, writes results/reliability.svg.
"""

from __future__ import annotations

import csv
from pathlib import Path

RES = Path(__file__).resolve().parent / "results"
COL = {"undirected/all": "#1b6ca8", "undirected/ff": "#7fb3d5", "directed/all": "#c0392b",
       "directed/ff": "#e6a09a"}


def main() -> int:
    rows = list(csv.DictReader((RES / "part_reliability.csv").open(encoding="utf-8")))
    w = h = 360
    m = 50
    s = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{w + 190}" height="{h + 70}" '
         'font-family="sans-serif" font-size="11">',
         f'<rect x="{m}" y="10" width="{w - m - 10}" height="{h - m - 10}" fill="none" '
         'stroke="#444"/>']

    def px(v: float) -> float:
        return m + v * (w - m - 10)

    def py(v: float) -> float:
        return 10 + (1 - v) * (h - m - 10)

    s.append(f'<line x1="{px(0)}" y1="{py(0)}" x2="{px(1)}" y2="{py(1)}" stroke="#999" '
             'stroke-dasharray="4"/>')
    for t in (0, 0.2, 0.4, 0.6, 0.8, 1.0):
        s.append(f'<text x="{px(t) - 8}" y="{h - m + 8}">{t:.1f}</text>')
        s.append(f'<text x="{m - 28}" y="{py(t) + 4}">{t:.1f}</text>')
    s.append(f'<text x="{m + 40}" y="{h - 12}">posterior (bin midpoint)</text>')
    s.append(f'<text x="4" y="{h / 2 - 20}" transform="rotate(-90 14 {h / 2})">observed same share'
             '</text>')
    for r in rows:
        lo = float(r["posterior_bin"].split("-")[0])
        key = f'{r["mode"]}/{r["restrict"]}'
        rad = 2 + min(10, int(r["pairs"]) ** 0.5 / 5)
        s.append(f'<circle cx="{px(lo + 0.05):.1f}" cy="{py(float(r["observed_same"])):.1f}" '
                 f'r="{rad:.1f}" fill="{COL[key]}" fill-opacity="0.7">'
                 f'<title>{key} {r["posterior_bin"]} n={r["pairs"]}</title></circle>')
    for i, (k, c) in enumerate(COL.items()):
        s.append(f'<rect x="{w + 10}" y="{20 + 18 * i}" width="10" height="10" fill="{c}"/>'
                 f'<text x="{w + 26}" y="{29 + 18 * i}">{k}</text>')
    s.append("</svg>")
    (RES / "reliability.svg").write_text("\n".join(s) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
