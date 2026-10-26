"""Word recovery scores against the L0 ground truth; one code path for Loki and for HAL/DANA.

A predicted word is a set of flip-flop node ids (L0 ``.cname`` ids). The ground truth words are
the L0 storage words whose footprint holds at least two flip-flops (footprint intersected with
the ``ff`` nodes of ``graph.json``). Definitions: ``docs/plan/hal-compare-prereg.md``
(Amendment 1 lists the four deliberate differences from the round-5 scorer). The ``round5``
switches below reproduce the round-5 choices (duplicates counted, Loki cells not cut to FFs,
full footprints with WIDTH >= 2) so the differences can be measured.

    python -m loki.hal.wordscore --floor-dir <ds>/<design>/f2 --dana groups.txt
    python -m loki.hal.wordscore --floor-dir <ds>/<design>/f2 --loki-re <run>/re
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, fields
from pathlib import Path

from loki.hal.dana import hal_words, parse_groups_txt
from loki.score.gt import REGISTER, STORAGE, derive_instances, load_netmap
from loki.score.match import match_greedy
from loki.score.metrics import construct_scores, load_preds

MATCH_J = 0.5
LOKI_KINDS = ("register",)


def _width(params: dict[str, object]) -> int:
    w = params.get("WIDTH", 1)
    return w if isinstance(w, int) and not isinstance(w, bool) else 1


@dataclass(frozen=True)
class GtWord:
    """``scored`` is False for a width-1 word: a label carrier for purity, never a GT word."""

    wid: str
    ffs: frozenset[str]
    scored: bool = True


def gt_words(floor_dir: Path, *, round5: bool = False) -> tuple[list[GtWord], frozenset[str]]:
    """(all storage words that hold at least one FF, the FF node ids) of an L0 floor directory.

    A word is scored when its ``WIDTH`` is at least 2 and its footprint holds at least 2 FFs.
    Width-1 words are kept as purity labels only (two width-1 words can share one footprint).

    ``round5=True``: the round-5 ground truth instead, the full footprint of every storage word
    with ``WIDTH >= 2`` (``loki.score.gt.derive_instances``, kind register)."""
    kinds = load_netmap(floor_dir).kinds
    ffs = frozenset(n for n, k in kinds.items() if k == "ff")
    obj = json.loads((floor_dir / "words.json").read_text(encoding="utf-8"))
    if round5:
        return [GtWord(i.gid, i.footprint) for i in derive_instances(obj)
                if i.type == REGISTER], ffs
    out = []
    for w in obj.get("words", []):
        if w["type"] in STORAGE:
            bits = frozenset(w["footprint"]) & ffs
            if bits:
                scored = _width(w.get("params", {})) >= 2 and len(bits) >= 2
                out.append(GtWord(f"w{w['id']}", bits, scored))
    return out, ffs


@dataclass(frozen=True)
class WordScore:
    """Counts of one design (or a sum over designs); ratios are derived."""

    n_pred: int = 0
    n_gt: int = 0
    exact_pred: int = 0
    exact_gt: int = 0
    matched: int = 0
    pur_num: int = 0
    pur_den: int = 0
    comp_num: int = 0
    comp_den: int = 0
    cov_num: int = 0
    cov_den: int = 0

    def __add__(self, other: WordScore) -> WordScore:
        return WordScore(*(getattr(self, f.name) + getattr(other, f.name) for f in fields(self)))

    @staticmethod
    def _ratio(num: int, den: int) -> float | None:
        return round(num / den, 6) if den else None

    def ratios(self) -> dict[str, float | None]:
        f1 = self._ratio(2 * self.matched, self.n_pred + self.n_gt)
        return {
            "precision_exact": self._ratio(self.exact_pred, self.n_pred),
            "recall_exact": self._ratio(self.exact_gt, self.n_gt),
            "precision_j": self._ratio(self.matched, self.n_pred),
            "recall_j": self._ratio(self.matched, self.n_gt),
            "f1_j": f1,
            "purity": self._ratio(self.pur_num, self.pur_den),
            "completeness": self._ratio(self.comp_num, self.comp_den),
            "ff_coverage": self._ratio(self.cov_num, self.cov_den),
        }

    def as_dict(self) -> dict[str, object]:
        out: dict[str, object] = {f.name: getattr(self, f.name) for f in fields(self)}
        out.update(self.ratios())
        return out


def _best_overlap(group: frozenset[str], words: Iterable[frozenset[str]]) -> int:
    return max((len(group & w) for w in words), default=0)


def score_words(
    pred: Iterable[Iterable[str]], gt: Sequence[GtWord], *, dedup: bool = True
) -> WordScore:
    """Score predicted words (FF id sets; groups of fewer than 2 FFs are dropped).

    ``dedup=True`` scores each distinct set once; ``dedup=False`` counts a repeated set as a
    further prediction (round 5: a duplicate is a false positive)."""
    sets = [frozenset(g) for g in pred if len(set(g)) >= 2]
    groups = sorted(set(sets) if dedup else sets, key=sorted)
    labels = [w.ffs for w in gt]
    words = [w for w in gt if w.scored and len(w.ffs) >= 2]
    wsets = {w.ffs for w in words}
    gsets = set(groups)
    pairs = match_greedy(
        [(f"p{i}", g) for i, g in enumerate(groups)], [(w.wid, w.ffs) for w in words], MATCH_J)
    in_pred = frozenset().union(*groups) if groups else frozenset()
    gt_bits = frozenset().union(*(w.ffs for w in words)) if words else frozenset()
    return WordScore(
        n_pred=len(groups), n_gt=len(words),
        exact_pred=sum(g in wsets for g in groups), exact_gt=sum(w.ffs in gsets for w in words),
        matched=len(pairs),
        pur_num=sum(_best_overlap(g, labels) for g in groups), pur_den=sum(map(len, groups)),
        comp_num=sum(_best_overlap(w.ffs, groups) for w in words),
        comp_den=sum(len(w.ffs) for w in words),
        cov_num=len(gt_bits & in_pred), cov_den=len(gt_bits),
    )


def loki_words(re_dir: Path, ffs: frozenset[str], kinds: Sequence[str] = LOKI_KINDS,
               score_p: float = 0.5, *, cut: bool = True) -> list[frozenset[str]]:
    """Counted candidates of the given kinds of a ``loki re`` run; ``cut=True`` intersects the
    cells with the flip-flops, ``cut=False`` keeps the full cell sets (round 5)."""
    overlay = json.loads((re_dir / "overlay.json").read_text(encoding="utf-8"))
    return [p.cells & ffs if cut else p.cells
            for p in load_preds(overlay) if p.kind in kinds and p.counted(score_p)]


def round5_register(re_dir: Path, floor_dir: Path, score_p: float = 0.5) -> dict[str, int]:
    """Loki's numbers under the round-5 scorer (``construct_scores``, kind register): counted,
    matched, gt. Duplicates count, cells are not cut, GT is the full footprint with WIDTH >= 2."""
    overlay = json.loads((re_dir / "overlay.json").read_text(encoding="utf-8"))
    words = json.loads((floor_dir / "words.json").read_text(encoding="utf-8"))
    row = construct_scores(load_preds(overlay), derive_instances(words), score_p).get("register")
    if row is None:
        return {"counted": 0, "matched": 0, "gt": 0}
    return {k: int(row[k]) for k in ("counted", "matched", "gt")}


def dana_words(groups_txt: Path, ffs: frozenset[str]) -> list[frozenset[str]]:
    return hal_words(parse_groups_txt(groups_txt.read_text(encoding="utf-8")), ffs)


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="loki.hal.wordscore", description=__doc__)
    ap.add_argument("--floor-dir", type=Path, required=True)
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--dana", type=Path, help="HAL dataflow groups.txt")
    src.add_argument("--loki-re", type=Path, help="a loki re output directory")
    ap.add_argument("--round5", action="store_true",
                    help="with --loki-re: print the round-5 scorer's counts instead")
    args = ap.parse_args(argv)
    if args.round5:
        if not args.loki_re:
            ap.error("--round5 needs --loki-re")
        sys.stdout.write(json.dumps(round5_register(args.loki_re, args.floor_dir), sort_keys=True)
                         + "\n")
        return 0
    gt, ffs = gt_words(args.floor_dir)
    pred = dana_words(args.dana, ffs) if args.dana else loki_words(args.loki_re, ffs)
    sys.stdout.write(json.dumps(score_words(pred, gt).as_dict(), indent=1, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
