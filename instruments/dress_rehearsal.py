"""E4 dress rehearsal: one command, clean checkout -> full report.

generate corpus -> populate substrate -> run every query through the loop ->
forced answers -> five confidence sources per item (within-item) -> type-2
analysis (AUROC2 + paired-bootstrap CIs, ECE, meta-d' where eligible) ->
leak_v2 + checker characterisation -> markdown report with every number,
CI, and seed. Runs unattended on GPU or with RG_CPU=1 (use --quick for the
CPU arm; sizes documented in the report). Wall-clock reported.

Usage: python instruments/dress_rehearsal.py [--quick] [--seed 20260719]
"""

import argparse
import json
import os
import sys
import time

_R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in (_R, f"{_R}/substrate", f"{_R}/gate", f"{_R}/encoder", f"{_R}/mouth",
           f"{_R}/instruments"):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import numpy as np

from corpus import CorpusConfig, build
from speak import ABSTAIN_TEXT, deliberate_text, gen_leadin, render, verify_leadin
from type2 import auroc2, ece, meta_d_prime, paired_bootstrap
import baselines as bl
import leak_v2

Z975, Z80 = 1.959964, 0.841621


def run(cfg, seed, do_leak=True):
    t0 = time.time()
    corpus = build(cfg)
    mem = corpus.memory
    print(f"[dress] corpus: k={mem.k} N={len(mem.ent)} items={len(corpus.items)} "
          f"seed={cfg.seed}")

    rows = []
    for it in corpus.items:
        q = mem.query(it.subj_term, it.rel)
        subj = mem.ent.resolve(it.subj_term, top=1)[0][0]
        rel = mem.rel.resolve(it.rel, top=1)[0][0]
        a, m_l1, top1 = mem._unbind(subj, rel)   # forced answer (read-only use)
        if it.kind == "id":
            correct = top1 == it.gold
        elif it.kind == "ood":
            correct = False
        elif it.kind == "coll":
            correct = top1 in it.gold
        else:
            correct = top1 in it.gold["objects"]
        rows.append({"item": it, "op": q.op, "action": q.action, "tag": q.tag,
                     "subj": subj, "rel": rel, "answer": top1, "correct": correct})

    n = len(rows)
    correct = np.array([r["correct"] for r in rows])
    print(f"[dress] forced-answer accuracy: {correct.mean():.3f} over {n} items "
          f"({time.time() - t0:.0f}s)")

    # ---- five sources (within-item)
    gate = {k: np.array([bl.gate_scalars(r["op"])[k] for r in rows])
            for k in ("gate_b", "gate_b_over_bd", "gate_1mu")}
    verb = np.array([bl.verbalised(r["subj"], r["rel"],
                                   render((r["subj"], r["rel"], r["answer"])),
                                   seed=seed + i) for i, r in enumerate(rows)])
    judg = np.array([bl.judge(r["subj"], r["rel"],
                              render((r["subj"], r["rel"], r["answer"])),
                              seed=seed + 10_000 + i) for i, r in enumerate(rows)])
    print(f"[dress] verbalised+judge done ({time.time() - t0:.0f}s)")

    X = np.array([bl.probe_features(r["subj"], r["rel"], r["answer"]) for r in rows])
    rng = np.random.default_rng(seed + 5)
    fold = rng.permutation(n) % 2
    probe = np.zeros(n)
    for f in (0, 1):
        tr, te = fold != f, fold == f
        model = bl.LogisticProbe(seed=seed + 6 + f).fit(X[tr], correct[tr])
        probe[te] = model.predict(X[te])
    probe_insample = bl.LogisticProbe(seed=seed + 8).fit(X, correct).predict(X)
    print(f"[dress] probe trained: n_train/fold={int((fold == 0).sum())}, "
          f"features=answer-token logits (adaptation, see baselines.py), "
          f"cross-fit AUROC2={auroc2(probe, correct):.4f}, "
          f"in-sample={auroc2(probe_insample, correct):.4f} ({time.time() - t0:.0f}s)")

    null_strata = bl.null_shuffle(gate["gate_b"], correct, seed=seed + 9)
    null_full = bl.null_shuffle_full(gate["gate_b"], seed=seed + 10)
    sources = {"GATE(b)": gate["gate_b"], "VERBALISED": verb, "PROBE": probe,
               "JUDGE": judg, "NULL(strata)": null_strata, "NULL(full)": null_full}
    secondaries = {"gate_b_over_bd": auroc2(gate["gate_b_over_bd"], correct),
                   "gate_1mu": auroc2(gate["gate_1mu"], correct)}

    # permutation test: the proper "beats the shuffled null" statement —
    # NULL(full) rows are single draws and can sit +-2 null-sd from 0.5
    rngp = np.random.default_rng(seed + 14)
    g = gate["gate_b"]
    perm = np.array([auroc2(g[rngp.permutation(n)], correct) for _ in range(1000)])
    perm_p = float((perm >= auroc2(g, correct)).mean())
    perm_stats = {"mean": float(perm.mean()), "sd": float(perm.std(ddof=1)),
                  "p": perm_p, "n_perm": 1000, "seed": seed + 14}

    boot = paired_bootstrap(sources, correct, B=2000, seed=seed + 11)
    eces = {k: ece(v, correct) for k, v in sources.items()}
    metas = {k: meta_d_prime(v, correct, seed=seed + 12) for k, v in sources.items()}

    # ---- leak_v2 over loop outputs (half with lead-ins)
    leak = None
    checker = None
    if do_leak:
        vocab = set(mem.ent.names) | set(mem.rel.names)
        n_flag = {"grounded": 0, "ungrounded": 0}
        n_tot = {"grounded": 0, "ungrounded": 0}
        for i, r in enumerate(rows[: min(n, 120)]):
            if r["action"] == "answer":
                kind, body = "grounded", render((r["subj"], r["rel"], r["answer"]))
            elif r["action"] == "deliberate":
                continue  # candidates are gate-emitted; counted grounded-adjacent
            else:
                kind, body = "ungrounded", ABSTAIN_TEXT
            if i % 2 == 0:
                lead = verify_leadin(gen_leadin(body, llm_seed=seed + 20_000 + i))
                out = (lead + " " + body).strip()
            else:
                out = body
            flag, _ = leak_v2.check_output(out, [body], mem, vocab)
            n_tot[kind] += 1
            n_flag[kind] += flag
        leak = {k: (n_flag[k], n_tot[k], n_flag[k] / n_tot[k] if n_tot[k] else 0.0)
                for k in n_tot}
        checker = leak_v2.characterise_checker(mem, vocab, seed=seed + 13)
        print(f"[dress] leak_v2 done ({time.time() - t0:.0f}s)")

    wall = time.time() - t0
    return {"n": n, "accuracy": float(correct.mean()), "sources": sources,
            "correct": correct, "boot": boot, "eces": eces, "metas": metas,
            "secondaries": secondaries, "leak": leak, "checker": checker,
            "perm": perm_stats, "wall_s": wall, "corpus": corpus}


def power_analysis(boot, n, pair, delta=None):
    """n for >=80% power at alpha=.05 (two-sided), paired bootstrap sd."""
    sd_item = boot["diff_sd"][pair] * np.sqrt(n)
    gap = boot["point"][pair[0]] - boot["point"][pair[1]]
    target = delta if delta is not None else gap
    if target <= 0:
        return {"gap": gap, "n_required": None, "sd_item": sd_item}
    n_req = int(np.ceil(((Z975 + Z80) * sd_item / target) ** 2))
    return {"gap": gap, "sd_item": float(sd_item), "n_required": n_req}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true",
                    help="reduced n (the RG_CPU=1 arm); sizes in the report")
    ap.add_argument("--seed", type=int, default=20260719)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    if args.quick:
        cfg = CorpusConfig(seed=args.seed, n_entities=150, n_facts=40,
                           n_id=8, n_ood=8, n_coll=3, n_ref=3)
    else:
        # 150/90 ID/OOD keeps forced accuracy inside the 0.55-0.95 meta-d'
        # window (120/120 measured 0.539 — excluded; entry 10). The
        # confirmatory mix is registered at freeze.
        cfg = CorpusConfig(seed=args.seed, n_entities=500, n_facts=160,
                           n_id=150, n_ood=90, n_coll=20, n_ref=20)

    res = run(cfg, args.seed, do_leak=True)
    boot = res["boot"]

    lines = ["# E4 dress rehearsal report", "",
             f"seed={args.seed} quick={args.quick} backend="
             f"{'CPU (RG_CPU=1)' if os.environ.get('RG_CPU') == '1' else 'GPU'} "
             f"wall={res['wall_s']:.0f}s",
             f"corpus: k={res['corpus'].memory.k} N={len(res['corpus'].memory.ent)} "
             f"items={res['n']} forced-answer accuracy={res['accuracy']:.3f}",
             "", "## AUROC2 (paired bootstrap "
             f"B={boot['B']} seed={boot['seed']})", "",
             "| source | AUROC2 | 95% CI | ECE | meta-d' | M-ratio |",
             "|---|---|---|---|---|---|"]
    for k in res["sources"]:
        lo, hi = boot["ci"][k]
        mt = res["metas"][k]
        md = f"{mt['meta_d']:.3f}" if mt.get("eligible") else "excl."
        mr = f"{mt['m_ratio']:.3f}" if mt.get("eligible") else mt.get("reason", "")[:24]
        lines.append(f"| {k} | {boot['point'][k]:.4f} | ({lo:.4f}, {hi:.4f}) | "
                     f"{res['eces'][k]:.4f} | {md} | {mr} |")
    p = res["perm"]
    lines += ["", f"permutation test (GATE vs full shuffle, n_perm={p['n_perm']} "
              f"seed={p['seed']}): null mean={p['mean']:.4f} sd={p['sd']:.4f} "
              f"p={'<0.001' if p['p'] == 0 else f'{p['p']:.4f}'}",
              f"gate secondaries: {res['secondaries']}", ""]
    for pair in boot["diff_ci"]:
        lo, hi = boot["diff_ci"][pair]
        lines.append(f"diff {pair[0]} - {pair[1]}: "
                     f"{boot['point'][pair[0]] - boot['point'][pair[1]]:+.4f} "
                     f"CI ({lo:+.4f}, {hi:+.4f})")
    if res["leak"]:
        lines += ["", "## leak_v2",
                  f"grounded: {res['leak']['grounded'][0]}/{res['leak']['grounded'][1]}"
                  f" = {res['leak']['grounded'][2]:.3f}",
                  f"ungrounded: {res['leak']['ungrounded'][0]}/{res['leak']['ungrounded'][1]}"
                  f" = {res['leak']['ungrounded'][2]:.3f}",
                  f"checker: precision={res['checker']['precision']:.3f} "
                  f"recall={res['checker']['recall']:.3f} "
                  f"(tp={res['checker']['tp']} fp={res['checker']['fp']} "
                  f"fn={res['checker']['fn']} tn={res['checker']['tn']}, "
                  f"seed={res['checker']['seed']})"]
        lines += ["", "### checker sample for review (real outputs, flags)"]
        for po in res["checker"]["per_output"]:
            if po["kind"] == "real":
                lines.append(f"- flag={po['flag']} {po['output']!r}")

    h1 = power_analysis(boot, res["n"], ("GATE(b)", "VERBALISED"))
    h2gap = boot["point"]["GATE(b)"] - boot["point"]["PROBE"]
    lines += ["", "## power / freeze parameters",
              f"H1 (GATE vs VERBALISED): dev gap={h1['gap']:+.4f}, per-item "
              f"sd={h1.get('sd_item', float('nan')):.3f}, "
              f"n for 80% power at alpha=.05: {h1['n_required']}",
              f"H2 (GATE vs PROBE): dev gap={h2gap:+.4f} "
              f"(margin question: is |gap| <= 0.02 realistic?)"]

    out_path = args.out or os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                        "dress_report.md")
    with open(out_path, "w") as f:
        f.write("\n".join(lines) + "\n")
    print("\n".join(lines[:40]))
    print(f"\n[dress] wrote {out_path}  wall={res['wall_s']:.0f}s")


if __name__ == "__main__":
    main()
