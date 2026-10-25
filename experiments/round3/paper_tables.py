#!/usr/bin/env python3
"""Write docs/paper/round3-tables.tex and round3-log.tex from the round-3 CSVs.

Tables tab:r3-*, the research-log table (tab:r3-log) and a macro for every number the round-3
prose cites (``\\rtt...``); statuses come from ``decide.py`` (the rules of EXPERIMENT.md). No
timestamps: a rerun reproduces the files byte for byte.

Usage: paper_tables.py [--out PATH]
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

import decide

HERE = Path(__file__).resolve().parent
DEFAULT_OUT = HERE.parents[1] / "docs" / "paper" / "round3-tables.tex"
MACROS: dict[str, str] = {}
ALL_SETS = ("M2N", "M2C", "V2N", "V2C", "V3N", "V3C", "M3N", "M3C", "M1N")
DECISIVE = decide.DECISIVE


def rows(name: str) -> list[dict[str, str]]:
    with (HERE / name).open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def f3(x: float | str, digits: int = 3) -> str:
    return f"{float(x):.{digits}f}".replace("-", "$-$")


def fi(x: float | int | str) -> str:
    return f"{int(float(x)):,}".replace(",", "{,}")


def macro(name: str, value: str) -> None:
    MACROS[name] = value


def tex(text: str) -> str:
    return text.replace("_", r"\_")


def table(caption: str, label: str, head: list[str], body: list[list[str]], spec: str) -> str:
    lines = [r"\begin{table}[t]", rf"\caption{{{caption}}}", rf"\label{{{label}}}",
             r"\centering", r"\footnotesize", r"\resizebox{\columnwidth}{!}{%",
             rf"\begin{{tabular}}{{@{{}}{spec}@{{}}}}",
             r"\toprule", " & ".join(head) + r" \\", r"\midrule"]
    lines += [" & ".join(r) + r" \\" for r in body]
    lines += [r"\bottomrule", r"\end{tabular}}", r"\end{table}"]
    return "\n".join(lines)


def verdict(status: str) -> str:
    return {"S": "supported", "N": "not supported", "I": "inconclusive"}[status]


def sget(d: dict[str, object], k: str) -> float:
    return float(str(d[k]))


# ------------------------------------------------------------------------------------- RQ-L9
def l9_block() -> tuple[str, str, str]:
    a, b = decide.h9a(), decide.h9b()
    macro("rttNinePoolFalse", fi(sget(a, "pool_false")))
    macro("rttNinePoolFrag", f3(sget(a, "pool_frag")))
    macro("rttNinePoolNoise", f3(sget(a, "pool_noise")))
    macro("rttNineKindsOk", str(a["kinds_ok"]))
    macro("rttNineKindsOkB", str(b["kinds_ok"]))
    lo = decide.h9a_without_top()
    macro("rttNineTopFalse", fi(sget(lo, "false")))
    macro("rttNineTopFrag", f3(sget(lo, "fragment_related")))
    macro("rttNineTopOther", f3(sget(lo, "fragment_other")))
    macro("rttNineTopDesign", tex(str(lo["design"])))
    macro("rttNineTopFfenFrag", f3(sget(lo, "ff_en_frag")))
    macro("rttNineTopRegisterFrag", f3(sget(lo, "register_frag")))
    for tag, d in (("NoFfen", decide.h9a_without_kind()),
                   ("NoFfenTop", decide.h9a_without_kind(drop_top=True))):
        macro(f"rttNine{tag}False", fi(sget(d, "false")))
        macro(f"rttNine{tag}Frag", f3(sget(d, "frag")))
        macro(f"rttNine{tag}KindsOk", str(d["kinds_ok"]))
    ex = decide.expl_false()
    macro("rttNineNoisePrime", f3(sget(ex, "pool_noise_prime")))
    macro("rttNineNoisePrimeN", fi(sget(ex, "pool_noise_prime_n")))
    macro("rttNineCellFrag", f3(sget(ex, "pool_cell_frag")))
    macro("rttNineCells", fi(sget(ex, "pool_cells")))
    for k in DECISIVE:
        kk = k.replace("_", "").title()
        macro(f"rttNine{kk}NoisePrime", f3(sget(ex, f"{k}_noise_prime")))
        macro(f"rttNine{kk}NoisePrimeN", fi(sget(ex, f"{k}_noise_prime_n")))
        macro(f"rttNine{kk}CellFrag", f3(sget(ex, f"{k}_cell_frag")))
    xb = decide.expl_h9b()
    macro("rttNinePoolQTouched", f3(sget(xb, "pool_qtouched")))
    macro("rttNinePoolTouched", fi(sget(xb, "pool_touched")))
    for k in DECISIVE:
        kk = k.replace("_", "").title()
        macro(f"rttNine{kk}QTouched", f3(sget(xb, f"{k}_qtouched")))
        macro(f"rttNine{kk}Touched", fi(sget(xb, f"{k}_touched")))
    frag_n = {k: int(round(sget(a, f"{k}_fragment_related") * sget(a, f"{k}_false")))
              for k in DECISIVE}
    macro("rttNinePoolFragN", fi(sum(frag_n.values())))
    macro("rttNineFfenFragN", fi(frag_n["ff_en"]))
    macro("rttNinePoolQ", f3(sget(b, "pool_q")))
    macro("rttNineGtN", fi(sget(b, "pool_n")))
    body = []
    for k in DECISIVE:
        macro(f"rttNine{k.replace('_', '').title()}Frag", f3(sget(a, f"{k}_fragment_related")))
        macro(f"rttNine{k.replace('_', '').title()}Q", f3(sget(b, f"{k}_q")))
        macro(f"rttNine{k.replace('_', '').title()}Other", f3(sget(a, f"{k}_fragment_other")))
        macro(f"rttNine{k.replace('_', '').title()}Cov", f3(sget(b, f"{k}_meancov")))
        macro(f"rttNine{k.replace('_', '').title()}Any", f3(sget(b, f"{k}_qany")))
        body.append([tex(k), fi(sget(a, f"{k}_cand")), fi(sget(a, f"{k}_false")),
                     *(f3(sget(a, f"{k}_{c}"), 2) for c in decide.CLASSES)])
    t1 = table(
        r"RQ-L9, primary set P (M2N+V2N, f2, uncalibrated): counted candidates, false ones, and "
        r"the share of the false ones per class (rules of \code{EXPERIMENT.md}).",
        "tab:r3-false",
        ["kind", "cand.", "false", "same ext.", "frag. rel.", "frag. other", "straddle",
         "partial", "noise"], body, "lrrrrrrrr")
    body = []
    for k in DECISIVE:
        body.append([tex(k), fi(sget(b, f"{k}_n")), fi(sget(b, f"{k}_matched")),
                     f3(sget(b, f"{k}_q")), f3(sget(b, f"{k}_qany")),
                     f3(sget(b, f"{k}_meancov"))])
    t2 = table(
        r"RQ-L9 (H9b), set P: ground-truth instances with at least two cells, the share whose "
        r"fragment union covers at least 0.8 of them ($q$), the same with candidates of any "
        r"kind, and the mean fragment coverage.",
        "tab:r3-frag", ["kind", "GT", "matched", "$q$ frag.", "$q$ any", "mean cov."], body,
        "lrrrrr")
    allrows = rows("l9_false.csv")
    body = []
    for s in ALL_SETS:
        sel = [r for r in allrows if r["set"] == s and r["kind"] in DECISIVE]
        if not sel:
            body.append([s, "not run", "", "", "", "", ""])
            continue
        nf = sum(int(r["n_false"]) for r in sel)
        sh = {c: decide.share(sum(int(r[c]) for r in sel), nf) for c in decide.CLASSES}
        body.append([s, sel[0]["runs"], fi(sum(int(r["n_cand"]) for r in sel)), fi(nf),
                     f3(sh["fragment_related"], 2), f3(sh["fragment_other"], 2),
                     f3(sh["noise"], 2)])
    t3 = table(
        r"RQ-L9 for every run set (four decisive kinds pooled): runs, candidates, false "
        r"candidates and the share that are related fragments, other-type fragments, noise.",
        "tab:r3-sets", ["set", "runs", "cand.", "false", "frag. rel.", "frag. other", "noise"],
        body, "lrrrrrr")
    body = [[tex(k), f3(sget(a, f"{k}_fragment_related"), 2),
             f3(sget(ex, f"{k}_cell_frag"), 2), f3(sget(ex, f"{k}_noise_prime"), 2),
             f3(sget(b, f"{k}_q"), 3), f3(sget(xb, f"{k}_qtouched"), 3)] for k in DECISIVE]
    body.append(["pooled", f3(sget(a, "pool_frag"), 2), f3(sget(ex, "pool_cell_frag"), 2),
                 f3(sget(ex, "pool_noise_prime"), 2), f3(sget(b, "pool_q"), 3),
                 f3(sget(xb, "pool_qtouched"), 3)])
    t4 = table(
        r"Exploratory, non-deciding additions (2026-10-24, after the data), set P: share of "
        r"false candidates that are related fragments (by candidate, by distinct cell), the "
        r"noise$'$ share (cells only in plain-gate ground-truth words), $q$ over all words and "
        r"over the words touched by a candidate.",
        "tab:r3-expl", ["kind", "frag. rel.", "frag. rel. (cells)", "noise$'$", "$q$",
                        "$q$ touched"], body, "lccccc")
    return "\n\n".join([t1, t2, t3, t4]), a["status"] if isinstance(a["status"], str) else "I", \
        str(b["status"])


# ------------------------------------------------------------------------------------ RQ-L10
def l10_block() -> tuple[str, str, str]:
    r, sa, sb = decide.h10()
    macro("rttTenDatapath", f3(sget(r, "datapath_share")))
    macro("rttTenControl", f3(sget(r, "control_share")))
    macro("rttTenDatapathN", fi(sget(r, "datapath_n")))
    macro("rttTenControlN", fi(sget(r, "control_n")))
    mac = decide.design_macro()
    macro("rttTenDatapathMacro", f3(mac["datapath_macro"]))
    macro("rttTenControlMacro", f3(mac["control_macro"]))
    macro("rttTenDatapathDesigns", fi(mac["datapath_designs"]))
    macro("rttTenControlDesigns", fi(mac["control_designs"]))
    for var, tag in (("no_relconst", "NoRel"), ("dedup_footprint", "Dedup"),
                     ("no_relconst_dedup", "NoRelDedup")):
        xv = decide.expl_l10(var)
        macro(f"rttTen{tag}Datapath", f3(xv["datapath_share"], 4))
        macro(f"rttTen{tag}DatapathN", fi(xv["datapath_n"]))
    macro("rttTenDecidingFour", f3(decide.expl_l10("deciding")["datapath_share"], 4))
    macro("rttTenRelConstN", fi(decide.expl_l10_count("relconst_count")))
    macro("rttTenSubsumedN", fi(decide.expl_l10_count("subsumed_count")))
    macro("rttTenIoCells", fi(decide.expl_l10_count("footprint_io_cells")))
    full = [r for r in rows("l10_reach.csv")
            if r["floor"] == "f2" and r["rule"] == "relaxed"]
    for cls, tag in (("datapath", "Datapath"), ("control", "Control")):
        sel = [r for r in full if r["class"] == cls]
        n = sum(int(r["n_gt"]) for r in sel)
        macro(f"rttTenFullHone{tag}", f3(decide.share(sum(int(r["full_h1"]) for r in sel), n)))
    for ds in ("micro", "veval"):
        x = decide.reach(dataset=ds)
        macro(f"rttTen{ds.title()}Datapath", f3(sget(x, "datapath_share")))
        macro(f"rttTen{ds.title()}Control", f3(sget(x, "control_share")))
    xs = decide.reach(rule="strict")
    macro("rttTenStrictDatapath", f3(sget(xs, "datapath_share")))
    macro("rttTenStrictControl", f3(sget(xs, "control_share")))
    x3 = decide.reach(floor="f3")
    macro("rttTenFthreeDatapath", f3(sget(x3, "datapath_share")))
    macro("rttTenFthreeControl", f3(sget(x3, "control_share")))
    macro("rttTenAdderN", fi(sget(r, "adder_n")))
    macro("rttTenRegHone", f3(sget(r, "register_h1")))
    macro("rttTenRegHtwo", f3(sget(r, "register_h2")))
    macro("rttTenEqHtwo", f3(sget(r, "eq_const_h2")))
    body = []
    for k in (*decide.DATAPATH, *decide.CONTROL):
        body.append([tex(k), "datapath" if k in decide.DATAPATH else "control",
                     fi(sget(r, f"{k}_n")), *(f3(sget(r, f"{k}_h{h}"), 2) for h in (1, 2, 3, 4)),
                     f3(sget(r, f"{k}_never"), 2)])
    t1 = table(
        r"RQ-L10, f2 floor, micro and VerilogEval pooled, relaxed rule ($\tau=0.75$): the "
        r"share of ground-truth word constructs seeded by a propagated group within $h$ hops of "
        r"an I/O port word, and the share never reached.",
        "tab:r3-reach", ["kind", "class", "GT", "$h\\le1$", "$h\\le2$", "$h\\le3$", "$h\\le4$",
                         "never"], body, "llrrrrrr")
    ports = rows("l10_ports.csv")
    body = []
    for p in ports:
        if p["rule"] != "relaxed":
            continue
        xx = decide.reach(floor=p["floor"], dataset=p["dataset"])
        body.append([p["dataset"], p["floor"], p["designs"], p["designs_with_port_word"],
                     p["input_words"], p["output_words"], f3(sget(xx, "datapath_share"), 2),
                     f3(sget(xx, "control_share"), 2)])
    t2 = table(
        r"RQ-L10 by dataset and floor: designs, designs with a port word, input and output "
        r"port words, and the datapath and control shares reached within two hops.",
        "tab:r3-ports", ["dataset", "floor", "designs", "with port word", "in words",
                         "out words", "datapath $h\\le2$", "control $h\\le2$"], body, "llrrrrrr")
    return "\n\n".join([t1, t2]), sa, sb


# ------------------------------------------------------------------------------------ RQ-L11
def l11_block() -> str:
    gt = {(r["dataset"], r["floor"]): r for r in rows("l11_gt.csv")}
    v, m = gt[("veval", "f2")], gt[("micro", "f2")]
    for tag, r in (("Ve", v), ("Mi", m)):
        macro(f"rttEleven{tag}Sinks", fi(r["sinks"]))
        macro(f"rttEleven{tag}Fb", fi(r["fb_registers"]))
        macro(f"rttEleven{tag}Dec", fi(r["decoders"]))
        macro(f"rttEleven{tag}Chains", fi(r["chains"]))
        macro(f"rttEleven{tag}MuxS", fi(r["muxes_s"]))
        macro(f"rttEleven{tag}MuxChain", fi(r["muxes_s_chain"]))
        macro(f"rttEleven{tag}MuxAny", fi(r["muxes_s_any_decoder"]))
        macro(f"rttEleven{tag}Designs", fi(r["designs"]))
        macro(f"rttEleven{tag}DesignsChain", fi(r["designs_with_chain"]))
        macro(f"rttEleven{tag}Fsm", fi(r["fb_fsm_flagged"]))
        macro(f"rttEleven{tag}En", fi(r["enabled_words"]))
        macro(f"rttEleven{tag}EnChain", fi(r["enabled_chain"]))
    tot_mux = int(v["muxes_s"]) + int(m["muxes_s"])
    tot_chain = int(v["muxes_s_chain"]) + int(m["muxes_s_chain"])
    macro("rttElevenMuxShare", f3(decide.share(tot_chain, tot_mux)))
    body = [[r["dataset"], r["floor"], r["designs"], r["designs_with_fb"],
             r["designs_with_chain"], r["fb_registers"], r["fb_fsm_flagged"], r["decoders"],
             r["sinks"], r["chains"], f"{r['muxes_s_chain']}/{r['muxes_s']}",
             f"{r['enabled_chain']}/{r['enabled_words']}"]
            for r in gt.values()]
    t1 = table(
        r"RQ-L11, ground truth: feedback registers, constant-compare decoders on them, sinks "
        r"(mux selects and enables) and chains, and the muxes with a select (enabled words) "
        r"whose select (enable) is a chain sink.",
        "tab:r3-chain",
        ["dataset", "floor", "designs", "with fb.", "with chain", "fb. reg.", "fsm flag",
         "decoders", "sinks", "chains", "mux S chain/all", "enable chain/all"], body,
        "llrrrrrrrrrr")
    det = rows("l11_detect.csv")
    body = []
    for s in ALL_SETS:
        sel = {r["element"]: r for r in det if r["set"] == s}
        if not sel:
            continue
        cells: list[str] = [s]
        for el in ("fb_register", "decoder", "sink"):
            r = sel[el]
            cells.append(f"{r['proposed_j05']}/{r['n']} ({r['kind_correct']})")
        c = sel["chain"]
        cells.append(f"{c['proposed_j05']}/{c['n']} ({c['kind_correct']})")
        f = sel["fsm_instance"]
        cells.append(f"{f['proposed_j05']}/{f['n']}")
        body.append(cells)
    for s, tag in (("V2N", "VtwoN"), ("M2N", "MtwoN")):
        sel = {r["element"]: r for r in det if r["set"] == s}
        macro(f"rttEleven{tag}Chain", f"{sel['chain']['proposed_j05']}/{sel['chain']['n']}")
        macro(f"rttEleven{tag}Dec", f"{sel['decoder']['proposed_j05']}/{sel['decoder']['n']}")
        macro(f"rttEleven{tag}Fb",
              f"{sel['fb_register']['proposed_j05']}/{sel['fb_register']['n']}")
        macro(f"rttEleven{tag}Sink", f"{sel['sink']['proposed_j05']}/{sel['sink']['n']}")
        macro(f"rttEleven{tag}Fsm",
              f"{sel['fsm_instance']['proposed_j05']}/{sel['fsm_instance']['n']}")
        macro(f"rttEleven{tag}FbKc", sel["fb_register"]["kind_correct"])
        macro(f"rttEleven{tag}FbCom", sel["fb_register"]["committed"])
    t2 = table(
        r"RQ-L11, detectors: chain elements proposed by a counted candidate with Jaccard at "
        r"least 0.5 of any kind (in brackets: of the right scored type), chains with all three "
        r"elements proposed, and ground-truth FSM instances matched by an \code{fsm} "
        r"candidate.",
        "tab:r3-detect",
        ["set", "fb. register", "decoder", "sink", "complete chains", "fsm"], body, "lccccc")
    return "\n\n".join([t1, t2])


def log_table(st: dict[str, str]) -> str:
    m = MACROS
    body = [
        ["L9a", "wrong candidates are fragments of GT words", "3",
         st["L9a"] + " by the letter of the rule; not robust",
         f"related-fragment share {m['rttNinePoolFrag']} of {m['rttNinePoolFalse']} false; "
         f"noise 0 by construction (every cell is in a GT word); without the largest design "
         f"{m['rttNineTopFrag']}, without \\code{{ff\\_en}} {m['rttNineNoFfenFrag']} "
         f"(exploratory)"],
        ["L9b", "fragments of a word cover it", "3", st["L9b"],
         f"share with coverage $\\geq0.8$: {m['rttNinePoolQ']} "
         f"(touched words only, exploratory: {m['rttNinePoolQTouched']})"],
        ["L10a", "datapath words reached from I/O within 2 hops", "3", st["L10a"],
         f"share reached {m['rttTenDatapath']} (per-design mean {m['rttTenDatapathMacro']}, "
         f"exploratory)"],
        ["L10b", "control words are not", "3", st["L10b"] + " (uninformative by construction)",
         f"share reached {m['rttTenControl']} (per-design mean {m['rttTenControlMacro']}, "
         f"exploratory)"],
        ["L11", "FSM chain: feedback, decode, select", "3", "measurement only",
         f"{m['rttElevenMuxShare']} of muxes with a select are chain sinks"],
    ]
    return table(
        r"Research log: the round-3 questions, their status and the deciding number "
        r"(all generated from \code{experiments/round3}).",
        "tab:r3-log", ["RQ", "Hypothesis", "Round", "Status", "Deciding number"], body,
        "lp{3.0cm}lp{2.6cm}p{3.2cm}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = ap.parse_args()
    t9, s9a, s9b = l9_block()
    t10, s10a, s10b = l10_block()
    t11 = l11_block()
    status = {"L9a": verdict(s9a), "L9b": verdict(s9b), "L10a": verdict(s10a),
              "L10b": verdict(s10b), "L11": "measurement only"}
    names = {"L9a": "LNinea", "L9b": "LNineb", "L10a": "LTena", "L10b": "LTenb",
             "L11": "LEleven"}
    for k, v in status.items():
        macro(f"rtt{names[k]}Status", v)
    head = ["% Generated by experiments/round3/paper_tables.py; do not edit."]
    macros = [rf"\newcommand{{\{k}}}{{{v}}}" for k, v in sorted(MACROS.items())]
    args.out.write_text("\n".join(head + macros) + "\n\n" + "\n\n".join([t9, t10, t11]) + "\n",
                        encoding="utf-8")
    log = args.out.with_name("round3-log.tex")
    log.write_text("\n".join(head) + "\n\n" + log_table(status) + "\n", encoding="utf-8")
    print(f"wrote {args.out} and {log}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
