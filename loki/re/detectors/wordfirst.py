"""``wordfirst`` and ``wordgroup``: words, control nets and FSMs found first (round 5, L Q2.4).

``wordfirst`` runs before the per-bit detectors and builds words directly from structure:

* register words: flip-flops of one clock grouped by the enable and reset nets of their D cone;
  a control triple shared by more than ``FMAX`` flip-flops, and plain flip-flops (no enable, no
  reset), are split by the signature of the readers of Q and the driver of D;
* ``ff_en`` / ``ff_srst`` words: the register word with its D cones, labelled by the control net;
* mux words: 2:1 mux cells that share one select net (the select labels the word);
* carry chains: the support-based chains of ``arith`` (the carry net joins the bits);
* word-level ``eq_const``: a cone whose support lies inside one register word (or the primary
  inputs) and is a single minterm;
* FSMs: a register word whose D cones all read a Q bit of the word and one of them reads at least
  two distinct bits (a feedback coupling; no decoder is required, the decoders inside the word are
  only counted in the ``decoders`` parameter). The rule over-generates: counters, shift registers
  and LFSRs are coupled too and are proposed as FSMs (see ``_coupled``);
* propagation: readers and drivers of a known word that form isomorphic slices (same cell class
  and pin role) of at least ``max(2, ceil(0.75 k))`` bits become ``bus`` words, depth
  ``GROW_DEPTH``, seeded from registers, mux words and adder words (so growth crosses adders).

``wordgroup`` runs last and links the per-bit hypotheses (``ff_en``, ``ff_srst``, ``mux_bit``) to
the words that contain them, and groups per-bit hypotheses that share an enable or reset net into
words. Both are opt-in: ``loki re --detectors wordfirst,...,wordgroup``.
"""

from __future__ import annotations

import os
from collections import defaultdict
from collections.abc import Hashable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from loki.features.npn import NAMED, npn_class, shrink_support
from loki.re.claims import Claim
from loki.re.detectors import Candidate, RoundContext, k_bin, sorted_candidates
from loki.re.detectors.arith import _chain_candidate, find_chains, support_index
from loki.re.detectors.ff_pattern import _FF_TYPES, _analyse, _Ff
from loki.re.sim import cone, simulate

FMAX = 32
EQ_SUPPORT_MAX = 16
GROW_DEPTH = 2
GROW_TAU = 0.75
MAX_SEEDS = 4000
# Exploratory switch (round 5 review fixes): "round5" is the rule that was evaluated; "stage0" is
# the Stage-0 text (feedback into some D cone plus at least two word-level decoders reading the
# word). Read at import; the default changes no behaviour.
FSM_RULE = os.environ.get("LOKI_WF_FSM_RULE", "round5")

if TYPE_CHECKING:
    from loki.re.overlay import Hypothesis


@dataclass(frozen=True)
class RegWord:
    ffs: tuple[_Ff, ...]
    clock: int
    en: tuple[int, int] | None
    rst: tuple[int, int] | None

    @property
    def q(self) -> tuple[int, ...]:
        return tuple(f.q for f in self.ffs)

    @property
    def d(self) -> tuple[int, ...]:
        return tuple(f.d for f in self.ffs)

    @property
    def cells(self) -> frozenset[int]:
        return frozenset().union(*(f.cells for f in self.ffs))

    @property
    def ff_cells(self) -> frozenset[int]:
        return frozenset(f.cell for f in self.ffs)


def _column(i: int, m: int) -> int:
    block = ((1 << (1 << i)) - 1) << (1 << i)
    out = 0
    for x in range(0, 1 << m, 1 << (i + 1)):
        out |= block << x
    return out


def _ones(table: int, width: int, var: int, value: int) -> int:
    n = 0
    for x in range(1 << width):
        if ((x >> var) & 1) == value and (table >> x) & 1:
            n += 1
    return n


def _role(ctx: RoundContext, cell_id: int, pin: int) -> Hashable:
    """Pin role of a reader: the sorted cofactor ones counts (LUT) or the pin index."""
    c = ctx.graph.cells[cell_id]
    if c.kind != "lut":
        return (c.kind, pin)
    a, b = _ones(c.table, c.width, pin, 0), _ones(c.table, c.width, pin, 1)
    return (c.width, min(a, b), max(a, b))


def _cell_class(ctx: RoundContext, cell_id: int) -> Hashable:
    c = ctx.graph.cells[cell_id]
    if c.kind != "lut":
        return (c.kind, c.type)
    return ("lut", c.width, npn_class(c.table, c.width).key)


def _reader_sig(ctx: RoundContext, net: int) -> tuple[Hashable, ...]:
    g = ctx.graph
    return tuple(sorted(
        (repr(_cell_class(ctx, r)), repr(_role(ctx, r, p))) for r, p in g.readers.get(net, ())
    ))


def _driver_sig(ctx: RoundContext, net: int) -> Hashable:
    d = ctx.graph.driver.get(net)
    return "in" if d is None else repr(_cell_class(ctx, d))


# -- register words ----------------------------------------------------------------------------
def _analysed_ffs(ctx: RoundContext) -> list[_Ff]:
    g = ctx.graph
    ffs = [_Ff(c, g.cells[c].outs[0], g.cells[c].ins[0], g.cells[c].clock)
           for c in ctx.view.free_cells
           if g.cells[c].kind == "ff" and g.cells[c].type in _FF_TYPES
           and g.cells[c].ins and g.cells[c].outs and g.cells[c].clock]
    for f in ffs:
        _analyse(ctx, f)
    return ffs


def _cands(f: _Ff) -> set[tuple[str, int, int]]:
    return {("e", n, a) for n, a in f.en} | {("r", n, a) for n, a, _ in f.rst}


def _refine(members: list[_Ff]) -> list[list[_Ff]]:
    """Split a group by the control candidates shared by some but not all of its members, only
    when every part keeps at least two flip-flops (agent default)."""
    count: dict[tuple[str, int, int], int] = defaultdict(int)
    for f in members:
        for c in _cands(f):
            count[c] += 1
    parts: dict[tuple[tuple[str, int, int], ...], list[_Ff]] = defaultdict(list)
    for f in members:
        sig = tuple(sorted(c for c in _cands(f) if 2 <= count[c] < len(members)))
        parts[sig].append(f)
    if len(parts) > 1 and all(len(p) >= 2 for p in parts.values()):
        return [parts[k] for k in sorted(parts)]
    return [members]


def register_words(ctx: RoundContext, ffs: list[_Ff]) -> list[RegWord]:
    """Group by (clock, strongest enable, strongest reset), refine, split wide groups and plain
    flip-flops by the signature of the Q readers and the D driver."""
    en_count: dict[tuple[int, int, int], int] = defaultdict(int)
    rst_count: dict[tuple[int, int, int], int] = defaultdict(int)
    for f in ffs:
        for n, a in f.en:
            en_count[(f.clock, n, a)] += 1
        for n, a, _ in f.rst:
            rst_count[(f.clock, n, a)] += 1
    Ctl = tuple[int, tuple[int, int] | None, tuple[int, int] | None]
    shared_groups: dict[Ctl, list[_Ff]] = defaultdict(list)
    plain: dict[tuple[int, str, str], list[_Ff]] = defaultdict(list)
    for f in ffs:
        ens = [t for t in f.en if en_count[(f.clock, t[0], t[1])] >= 2]
        rsts = [(n, a) for n, a, _ in f.rst if rst_count[(f.clock, n, a)] >= 2]
        en = min(ens, key=lambda t: (-en_count[(f.clock, t[0], t[1])], t)) if ens else None
        rst = min(rsts, key=lambda t: (-rst_count[(f.clock, t[0], t[1])], t)) if rsts else None
        if en is None and rst is None:
            plain[(f.clock, repr(_reader_sig(ctx, f.q)), repr(_driver_sig(ctx, f.d)))].append(f)
        else:
            shared_groups[(f.clock, en, rst)].append(f)
    out: list[RegWord] = []
    for ctl in sorted(shared_groups, key=repr):
        members = shared_groups[ctl]
        parts = _refine(members)
        if len(members) > FMAX and len(parts) == 1:
            sub: dict[str, list[_Ff]] = defaultdict(list)
            for f in members:
                sub[repr((_reader_sig(ctx, f.q), _driver_sig(ctx, f.d)))].append(f)
            parts = [sub[k] for k in sorted(sub)]
        out.extend(_words_of(parts, ctl[0], ctl[1], ctl[2]))
    for pk in sorted(plain):
        out.extend(_words_of([plain[pk]], pk[0], None, None))
    return out


def _words_of(parts: list[list[_Ff]], clock: int, en: tuple[int, int] | None,
              rst: tuple[int, int] | None) -> list[RegWord]:
    return [RegWord(tuple(sorted(p, key=lambda f: f.q)), clock, en, rst)
            for p in parts if len(p) >= 2]


def _register_cands(ctx: RoundContext, words: list[RegWord]) -> list[Candidate]:
    out: list[Candidate] = []
    for w in words:
        k = len(w.ffs)
        nets: dict[str, tuple[int, ...]] = {"q": w.q, "d": w.d, "clk": (w.clock,)}
        feats = {"width": k_bin(k)}
        if w.en is not None:
            nets["en"] = (w.en[0],)
        if w.rst is not None:
            nets["rst"] = (w.rst[0],)
        if w.en is not None or w.rst is not None:
            feats["shared_ctrl"] = (
                "both" if w.en is not None and w.rst is not None else "en" if w.en else "rst")
        out.append(Candidate("register", w.cells, nets, {"order_source": "net_id"}, feats))
        if w.en is not None and all(w.en in f.en for f in w.ffs):
            out.append(Candidate(
                "ff_en", w.cells, {"q": w.q, "d": w.d, "en": (w.en[0],)},
                {"en": w.en[0], "active": w.en[1], "width": k}, {"en_fn_exact": "yes"}))
        if w.rst is not None:
            val = {f.rst[0][2] for f in w.ffs if f.rst}
            out.append(Candidate(
                "ff_srst", w.cells, {"q": w.q, "d": w.d, "rst": (w.rst[0],)},
                {"rst": w.rst[0], "active": w.rst[1], "width": k, "value": min(val)},
                {"rst_fanout": k_bin(k) if k >= 2 else "1"}))
    return out


# -- mux words ---------------------------------------------------------------------------------
def _mux_triple(table: int, width: int, ins: tuple[int, ...]) -> tuple[int, int, int] | None:
    """(select, a, b) nets with ``table = s ? b : a`` over the support, or ``None``."""
    t, w, kept = shrink_support(table, width)
    if w != 3 or npn_class(t, 3) != NAMED["mux2"]:
        return None
    nets = [ins[p] for p in kept]
    for s in range(3):
        a, b = [i for i in range(3) if i != s]
        ok = True
        for x in range(8):
            sv, av, bv = (x >> s) & 1, (x >> a) & 1, (x >> b) & 1
            if ((t >> x) & 1) != (bv if sv else av):
                ok = False
                break
        if ok:
            return nets[s], nets[a], nets[b]
    return None


def _mux_cands(ctx: RoundContext) -> list[Candidate]:
    g = ctx.graph
    by_sel: dict[int, list[tuple[int, int, int, int]]] = defaultdict(list)
    for cid in ctx.view.free_cells:
        c = g.cells[cid]
        if c.kind != "lut" or not c.outs:
            continue
        tr = _mux_triple(c.table, c.width, c.ins)
        if tr is not None and tr[0] and tr[1] and tr[2]:
            by_sel[tr[0]].append((cid, tr[1], tr[2], c.outs[0]))
    out: list[Candidate] = []
    for sel in sorted(by_sel):
        bits = sorted(by_sel[sel], key=lambda t: t[3])
        if len(bits) < 2:
            continue
        a = tuple(b[1] for b in bits)
        bb = tuple(b[2] for b in bits)
        ys = tuple(b[3] for b in bits)
        claim = Claim("mux2", (("WIDTH", len(bits)),), (("A", a), ("B", bb), ("S", (sel,))),
                      (("Y", ys),))
        feats = {"width": k_bin(len(bits)), "sel_shared": "yes", "wl_depth": "n/a"}
        out.append(Candidate(
            "mux", frozenset(b[0] for b in bits),
            {"A": a, "B": bb, "S": (sel,), "Y": ys}, {"WIDTH": len(bits), "N": 2}, feats, claim))
    return out


# -- word-level eq_const -----------------------------------------------------------------------
@dataclass(frozen=True)
class Decoder:
    net: int
    support: frozenset[int]
    cells: frozenset[int]
    op: str
    const: int


def _minterm(ctx: RoundContext, net: int, srcs: list[int]) -> Decoder | None:
    g = ctx.graph
    cells, side = cone(g, frozenset(srcs), [net], frozenset())
    if side or not cells:
        return None
    m = len(srcs)
    n = 1 << m
    table = simulate(g, cells, {s: _column(i, m) for i, s in enumerate(srcs)}, n)[net]
    ones = table.bit_count()
    if ones == 1:
        return Decoder(net, frozenset(srcs), frozenset(cells), "eq", table.bit_length() - 1)
    if ones == n - 1:
        inv = (~table & (n - 1)).bit_length() - 1
        return Decoder(net, frozenset(srcs), frozenset(cells), "ne", inv)
    return None


def word_decoders(ctx: RoundContext, words: list[RegWord]) -> list[Decoder]:
    """Cones whose support is inside one register word (or all primary inputs)."""
    g = ctx.graph
    member: dict[int, int] = {q: i for i, w in enumerate(words) for q in w.q}
    pis = set(g.pis)
    free = set(ctx.view.free_cells)
    found: dict[tuple[frozenset[int], str, int], Decoder] = {}
    for net in sorted(g.driver):
        cid = g.driver[net]
        if cid not in free or g.cells[cid].kind != "lut":
            continue
        sup = ctx.view.support.of(net)
        if sup is None or not 2 <= len(sup) <= EQ_SUPPORT_MAX:
            continue
        in_word = len({member.get(s, -1) for s in sup}) == 1 and -1 not in {
            member.get(s, -1) for s in sup}
        if not (in_word or sup <= pis):
            continue
        dec = _minterm(ctx, net, sorted(sup))
        if dec is None:
            continue
        key = (dec.support, dec.op, dec.const)
        if key not in found or len(dec.cells) > len(found[key].cells):
            found[key] = dec
    decs = sorted(found.values(), key=lambda d: (sorted(d.support), d.op, d.const))
    return [d for d in decs if not any(
        o is not d and d.cells < o.cells and d.support <= o.support for o in decs)]


def _eq_cands(ctx: RoundContext, decs: list[Decoder]) -> list[Candidate]:
    out: list[Candidate] = []
    pos = set(ctx.graph.pos)
    for d in decs:
        srcs = tuple(sorted(d.support))
        m = len(srcs)
        claim = Claim("eq_const" if d.op == "eq" else "ne_const", (("A_WIDTH", m), ("C", d.const)),
                      (("A", srcs),), (("Y", (d.net,)),))
        reads = "yes" if d.net in pos or any(
            ctx.graph.cells[r].kind in ("ff", "latch") for r, _ in ctx.graph.readers.get(d.net, ())
        ) else "no"
        out.append(Candidate(
            "eq_const", d.cells, {"A": srcs, "Y": (d.net,)},
            {"op": d.op, "C": d.const, "width": m},
            {"width": k_bin(m), "out_reads": reads}, claim))
    return out


# -- FSMs ---------------------------------------------------------------------------------------
def _next_state_cone(ctx: RoundContext, w: RegWord) -> frozenset[int]:
    """Cells of the fan-in of the D nets that feed only the cone and the word's flip-flops."""
    g = ctx.graph
    cells, _ = cone(g, frozenset(), list(w.d), frozenset())
    ffc = set(w.ff_cells)
    pos = set(g.pos)
    inside = set(cells) | ffc
    changed = True
    while changed:
        changed = False
        for c in sorted(inside - ffc):
            outs = g.cells[c].outs
            if any(r not in inside for n in outs for r, _ in g.readers.get(n, ())) or any(
                    n in pos for n in outs):
                inside.discard(c)
                changed = True
    return frozenset(inside)


def _coupled(ctx: RoundContext, w: RegWord) -> bool:
    """Feedback coupling of a register word: every D cone reads a Q bit of the word and some cone
    reads at least two distinct bits.

    This is a necessary condition for an FSM, not a sufficient one. It over-generates: counters
    (the carry chain makes bit i read the lower bits), LFSRs (the XOR taps read several bits) and
    any other word whose bits feed each other pass it and are proposed as ``fsm``. A plain shift
    register does not pass (each D cone reads one Q bit, so ``widest`` stays 1) unless some stage
    also reads another bit (a tap, a load mux with a second state input). Nothing here tells an FSM
    from those: no decoder is required and no state encoding is tested. The share of ``fsm``
    candidates that are counters or shift registers by ground-truth kind is measured in
    ``experiments/round5/l16_explore.py`` (exploratory)."""
    qs = set(w.q)
    widest = 0
    for d in w.d:
        sup = ctx.view.support.of(d)
        if sup is None or not qs & sup:
            return False
        widest = max(widest, len(qs & sup))
    return widest >= 2


def _feedback(ctx: RoundContext, w: RegWord) -> bool:
    """Stage-0 feedback test (exploratory ``LOKI_WF_FSM_RULE=stage0``): some D cone reads a Q bit
    of the word."""
    qs = set(w.q)
    for d in w.d:
        sup = ctx.view.support.of(d)
        if sup is not None and qs & sup:
            return True
    return False


def _fsm_cands(ctx: RoundContext, words: list[RegWord], decs: list[Decoder]) -> list[Candidate]:
    """A register word that passes ``_coupled`` becomes an ``fsm`` candidate over its next-state
    cone; no decoder is needed. ``decoders`` (the word-level ``eq_const`` decoders inside the word)
    and the ``decoder_readers`` feature only record whether there is one. With
    ``FSM_RULE == "stage0"`` the Stage-0 text applies instead: some D cone reads the word and at
    least two decoders read it."""
    out: list[Candidate] = []
    for w in words:
        qs = set(w.q)
        mine = [d for d in decs if d.support <= qs]
        if FSM_RULE == "stage0":
            if len(mine) < 2 or not _feedback(ctx, w):
                continue
        elif not _coupled(ctx, w):
            continue
        cells = _next_state_cone(ctx, w)
        out.append(Candidate(
            "fsm", cells, {"q": w.q, "d": w.d}, {"width": len(w.ffs), "decoders": len(mine)},
            {"decoder_readers": ">=0.5" if mine else "<0.5", "ctrl_inputs": "1-4"}))
    return out


# -- propagation -------------------------------------------------------------------------------
def _step(ctx: RoundContext, nets: tuple[int, ...], forward: bool) -> list[tuple[int, ...]]:
    """Groups of cells (as output-net tuples) one slice step away from the ordered ``nets``."""
    g = ctx.graph
    free = set(ctx.view.free_cells)
    classes: dict[Hashable, dict[int, int]] = defaultdict(dict)
    for i, net in enumerate(nets):
        if forward:
            found = [(r, p) for r, p in g.readers.get(net, ())
                     if r in free and g.cells[r].kind == "lut"]
            sigs = [(repr(_cell_class(ctx, r)), repr(_role(ctx, r, p)), r) for r, p in found]
        else:
            d = g.driver.get(net)
            sigs = [(repr(_cell_class(ctx, d)), "out", d)] if (
                d is not None and d in free and g.cells[d].kind == "lut") else []
        by_sig: dict[Hashable, list[int]] = defaultdict(list)
        for cls, role, cell in sigs:
            by_sig[(cls, role)].append(cell)
        for sig, cells in by_sig.items():
            if len(cells) == 1:
                classes[sig][i] = cells[0]
    need = max(2, -(-int(GROW_TAU * 100) * len(nets) // 100))
    out: list[tuple[int, ...]] = []
    for sig in sorted(classes, key=repr):
        members = classes[sig]
        cells = list(members.values())
        if len(set(cells)) == len(cells) and len(cells) >= need:
            out.append(tuple(g.cells[members[i]].outs[0] for i in sorted(members)
                             if g.cells[members[i]].outs))
    return out


def _grow(ctx: RoundContext, seeds: list[tuple[int, ...]]) -> list[tuple[int, ...]]:
    seen: set[frozenset[int]] = {frozenset(s) for s in seeds}
    frontier = seeds[:MAX_SEEDS]
    found: list[tuple[int, ...]] = []
    for _ in range(GROW_DEPTH):
        nxt: list[tuple[int, ...]] = []
        for nets in frontier:
            for fwd in (True, False):
                for grp in _step(ctx, nets, fwd):
                    key = frozenset(grp)
                    if len(grp) >= 2 and key not in seen:
                        seen.add(key)
                        nxt.append(grp)
        found.extend(nxt)
        frontier = nxt[:MAX_SEEDS]
    return found


def _bus_cands(ctx: RoundContext, groups: list[tuple[int, ...]]) -> list[Candidate]:
    g = ctx.graph
    out: list[Candidate] = []
    for grp in groups:
        cells = frozenset(g.driver[n] for n in grp if n in g.driver)
        nets = {f"slice{i}": (n,) for i, n in enumerate(grp)}
        out.append(Candidate(
            "bus", cells, nets, {"k": len(grp), "order_source": "wf"},
            {"k": k_bin(len(grp)), "ctrl_fanout_exact": "no", "data_from_bus": "all",
             "wl_depth": "n/a"}))
    return out


def _seeds(words: list[RegWord], cands: list[Candidate]) -> list[tuple[int, ...]]:
    seeds: list[tuple[int, ...]] = []
    for w in words:
        seeds.append(w.q)
        seeds.append(w.d)
    for c in cands:
        if c.kind == "mux" or c.kind in ("adder", "subtractor", "adder_cin"):
            for role in ("Y", "A", "B"):
                if len(c.nets.get(role, ())) >= 2:
                    seeds.append(tuple(c.nets[role]))
    return seeds


class WordFirstDetector:
    name = "wordfirst"
    kinds = ("register", "ff_en", "ff_srst", "mux", "eq_const", "fsm", "adder", "subtractor",
             "adder_cin", "bus")

    def propose(self, ctx: RoundContext) -> list[Candidate]:
        ffs = _analysed_ffs(ctx)
        words = register_words(ctx, ffs)
        out = _register_cands(ctx, words)
        out.extend(_mux_cands(ctx))
        index = support_index(ctx.view)
        for chain in find_chains(ctx.view, ctx.graph, index, ctx.rng):
            cand = _chain_candidate(ctx, chain, index)
            if cand is not None:
                out.append(cand)
        decs = word_decoders(ctx, words)
        out.extend(_eq_cands(ctx, decs))
        out.extend(_fsm_cands(ctx, words, decs))
        out.extend(_bus_cands(ctx, _grow(ctx, _seeds(words, out))))
        return sorted_candidates(out)


class WordGroupDetector:
    """Links per-bit hypotheses to the words that contain them; groups the leftovers."""

    name = "wordgroup"
    kinds = ("ff_en", "ff_srst", "mux")

    def propose(self, ctx: RoundContext) -> list[Candidate]:
        out: list[Candidate] = []
        for kind, bit_kind in (("ff_en", "ff_en"), ("ff_srst", "ff_srst"), ("mux", "mux_bit")):
            bits = [h for h in ctx.overlay.by_kind(bit_kind)
                    if h.status != "rejected" and h.detector not in ("wordfirst", "wordgroup")]
            words = [h for h in ctx.overlay.by_kind(kind)
                     if h.detector == "wordfirst" and h.status != "rejected"]
            out.extend(self._link(kind, words, bits))
            if kind != "mux":
                out.extend(self._leftover(kind, words, bits))
        return sorted_candidates(out)

    @staticmethod
    def _same_control(kind: str, word_params: dict[str, int | str],
                      bit_params: dict[str, int | str]) -> bool:
        if kind == "ff_en":
            return word_params.get("en") == bit_params.get("en")
        if kind == "ff_srst":
            return word_params.get("rst") == bit_params.get("rst")
        return True

    def _link(self, kind: str, words: list[Hypothesis], bits: list[Hypothesis]) -> list[Candidate]:
        out: list[Candidate] = []
        for w in words:
            kids = tuple(sorted(
                (b.id for b in bits
                 if b.cells <= w.cells and self._same_control(kind, w.params, b.params)),
                key=lambda s: int(s[1:])))
            if kids:
                out.append(Candidate(kind, w.cells, dict(w.nets), dict(w.params),
                                     dict(w.features), w.claim, kids))
        return out

    @staticmethod
    def _leftover(kind: str, words: list[Hypothesis], bits: list[Hypothesis]) -> list[Candidate]:
        taken = set().union(*(w.cells for w in words)) if words else set()
        name = "en" if kind == "ff_en" else "rst"
        groups: dict[tuple[int | str, int | str], list[Hypothesis]] = defaultdict(list)
        for b in bits:
            if not b.cells & taken:
                groups[(b.params.get(name, 0), b.params.get("active", 0))].append(b)
        out: list[Candidate] = []
        for (net, active), hs in sorted(groups.items(), key=repr):
            if len(hs) < 2:
                continue
            cells = frozenset().union(*(h.cells for h in hs))
            params: dict[str, int | str] = {name: net, "active": active, "width": len(hs)}
            if kind == "ff_srst":
                params["value"] = min(int(h.params.get("value", 0)) for h in hs)
            feats = {"en_fn_exact": "yes"} if kind == "ff_en" else {"rst_fanout": k_bin(len(hs))}
            out.append(Candidate(kind, cells, {name: (int(net),)}, params, feats,
                                 children=tuple(h.id for h in hs)))
        return out
