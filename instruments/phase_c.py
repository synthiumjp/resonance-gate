"""THE Phase C invocation — the registered confirmatory analysis. One run,
on the frozen artifact, with the registered seed family. Refuses to run
until docs/registration_final.md carries the OSF URL + filing timestamp.

Registered analysis (docs/registration_final.md):
  H1  : AUROC2(GATE 1-u) > AUROC2(VERBALISED); paired bootstrap CI of the
        difference excludes zero (B=2000, registered seed).
  H2  : AUROC2(FOIL) - AUROC2(GATE 1-u) <= 0.02 (FOIL = frozen trained head
        instruments/h2_foil_head.json over retrieval features).
  H2b : AUROC2(PROBE-on-mouth) 95% CI contains 0.5 (architectural
        prediction: the mouth never holds the facts).
  H3  : referential-d AUC (ref vs clean-ID) >= 0.90 AND stored-d AUC
        (collision vs clean-ID) >= 0.90.
  H4  : ungrounded emitted leak <= 2% by the characterised leak_v2 checker
        (checker precision/recall reported alongside).
Permutation null (1000 perms, registered seed) reported for GATE.
meta-d'/M-ratio reported where eligible (0.55-0.95 window, Guggenmos d'>=0.2).

Usage: python instruments/phase_c.py  (no options: the run is registered)
"""

import hashlib
import json
import os
import re
import sys

_R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in (_R, f"{_R}/substrate", f"{_R}/gate", f"{_R}/encoder", f"{_R}/mouth",
           f"{_R}/instruments"):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import numpy as np

# ---- registered confirmatory seed family (freeze gap 1c; used nowhere else)
SEED_CORPUS = 777000001
SEED_ASSIGN = 777000002
SEED_BOOT = 777000003
SEED_PERM = 777000004

REGISTRATION = os.path.join(_R, "docs", "registration_final.md")
HEAD_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                         "h2_foil_head.json")
HEAD_SHA256 = "b068c096dd6cf9f883138733c5fcecff7a74bfb256dd8cbe5b6a6961fe508b79"
REPORT = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                      "phase_c_report.md")


def guard():
    """Refuse to run before the registration is filed."""
    if not os.path.exists(REGISTRATION):
        sys.exit("REFUSED: docs/registration_final.md missing.")
    text = open(REGISTRATION).read()
    url = re.search(r"^OSF URL: (https://osf\.io/\S+)$", text, re.M)
    ts = re.search(r"^Filed: (20\d\d-\d\d-\d\dT\d\d:\d\d\S*)$", text, re.M)
    if not url or not ts or "PENDING" in (url.group(1) + ts.group(1)):
        sys.exit("REFUSED: registration not filed — add 'OSF URL: https://osf.io/...' "
                 "and 'Filed: <ISO timestamp>' lines to docs/registration_final.md "
                 "after filing on OSF. Phase C runs once, after registration.")
    sha = hashlib.sha256(open(HEAD_PATH, "rb").read()).hexdigest()
    if sha != HEAD_SHA256:
        sys.exit(f"REFUSED: h2_foil_head.json hash mismatch ({sha[:16]}... != "
                 f"{HEAD_SHA256[:16]}...) — frozen artifact violated.")
    return url.group(1), ts.group(1)


def main():
    url, ts = guard()
    from corpus import CorpusConfig, build
    from speak import ABSTAIN_TEXT, gen_leadin, render, verify_leadin
    from type2 import auroc2, ece, meta_d_prime, paired_bootstrap
    from opinion import C_REF, S_REF, sigmoid
    from l2_ambiguity import C_L2, S_L2
    import baselines as bl
    import leak_v2

    print(f"[phase-c] registration: {url} filed {ts}")
    cfg = CorpusConfig(seed=SEED_CORPUS, n_entities=500, n_facts=160,
                       n_id=150, n_ood=90, n_coll=20, n_ref=20)
    c = build(cfg)
    mem = c.memory
    print(f"[phase-c] corpus: k={mem.k} N={len(mem.ent)} items={len(c.items)}")

    rows, X = [], []
    for it in c.items:
        q = mem.query(it.subj_term, it.rel)
        subj = mem.ent.resolve(it.subj_term, top=1)[0][0]
        rel = mem.rel.resolve(it.rel, top=1)[0][0]
        a, m_l1, top1 = mem._unbind(subj, rel)
        if it.kind == "id":
            correct = top1 == it.gold
        elif it.kind == "ood":
            correct = False
        elif it.kind == "coll":
            correct = top1 in it.gold
        else:
            correct = top1 in it.gold["objects"]
        rows.append({"it": it, "op": q.op, "m_ref": q.m_ref, "m_l2": q.m_l2,
                     "subj": subj, "rel": rel, "answer": top1, "correct": correct})
        X.append([a, m_l1, q.m_l2, q.m_ref, float(mem.k), float(len(mem.ent))])
    X = np.array(X)
    correct = np.array([r["correct"] for r in rows])
    kinds = np.array([r["it"].kind for r in rows])
    n = len(rows)

    gate_1mu = np.array([1.0 - r["op"].u for r in rows])
    gate_b = np.array([r["op"].b for r in rows])
    gate_bbd = np.array([r["op"].b / (r["op"].b + r["op"].d)
                         if (r["op"].b + r["op"].d) > 1e-12 else 0.5 for r in rows])
    verb = np.array([bl.verbalised(r["subj"], r["rel"],
                                   render((r["subj"], r["rel"], r["answer"])),
                                   seed=SEED_ASSIGN + i) for i, r in enumerate(rows)])
    judg = np.array([bl.judge(r["subj"], r["rel"],
                              render((r["subj"], r["rel"], r["answer"])),
                              seed=SEED_ASSIGN + 10_000 + i) for i, r in enumerate(rows)])
    probe_feats = np.array([bl.probe_features(r["subj"], r["rel"], r["answer"])
                            for r in rows])
    # PROBE head is refit on confirmatory items via registered 2-fold cross-fit
    rng = np.random.default_rng(SEED_ASSIGN)
    fold = rng.permutation(n) % 2
    probe = np.zeros(n)
    for f in (0, 1):
        tr, te = fold != f, fold == f
        probe[te] = bl.LogisticProbe(seed=SEED_ASSIGN + f).fit(
            probe_feats[tr], correct[tr]).predict(probe_feats[te])
    head = json.load(open(HEAD_PATH))
    hp = bl.LogisticProbe()
    hp.w, hp.mu, hp.sd = (np.array(head["w"]), np.array(head["mu"]),
                          np.array(head["sd"]))
    foil = hp.predict(X)

    sources = {"GATE(1-u)": gate_1mu, "FOIL": foil, "VERBALISED": verb,
               "JUDGE": judg, "PROBE": probe,
               "GATE(b)": gate_b, "GATE(b/(b+d))": gate_bbd}
    boot = paired_bootstrap(sources, correct, B=2000, seed=SEED_BOOT)
    rngp = np.random.default_rng(SEED_PERM)
    perm = np.array([auroc2(gate_1mu[rngp.permutation(n)], correct)
                     for _ in range(1000)])
    perm_p = float((perm >= auroc2(gate_1mu, correct)).mean())

    # H3: two-source d separations against clean correct ID items
    p_ref = 1.0 - sigmoid((np.array([r["m_ref"] for r in rows]) - C_REF) / S_REF)
    p_sto = 1.0 - sigmoid((np.array([r["m_l2"] for r in rows]) - C_L2) / S_L2)
    clean = (kinds == "id") & correct
    h3_ref = auroc2(np.concatenate([p_ref[kinds == "ref"], p_ref[clean]]),
                    np.concatenate([np.ones((kinds == "ref").sum(), bool),
                                    np.zeros(clean.sum(), bool)]))
    h3_sto = auroc2(np.concatenate([p_sto[kinds == "coll"], p_sto[clean]]),
                    np.concatenate([np.ones((kinds == "coll").sum(), bool),
                                    np.zeros(clean.sum(), bool)]))

    # H4 leak
    vocab = set(mem.ent.names) | set(mem.rel.names)
    n_flag = {"grounded": 0, "ungrounded": 0}
    n_tot = {"grounded": 0, "ungrounded": 0}
    for i, r in enumerate(rows[:120]):
        q_action = "answer" if (kinds[i] == "id" and r["correct"]) else "abstain"
        body = (render((r["subj"], r["rel"], r["answer"]))
                if q_action == "answer" else ABSTAIN_TEXT)
        kind = "grounded" if q_action == "answer" else "ungrounded"
        if i % 2 == 0:
            lead = verify_leadin(gen_leadin(body, llm_seed=SEED_ASSIGN + 20_000 + i))
            out = (lead + " " + body).strip()
        else:
            out = body
        flag, _ = leak_v2.check_output(out, [body], mem, vocab)
        n_tot[kind] += 1
        n_flag[kind] += flag
    checker = leak_v2.characterise_checker(mem, vocab, seed=SEED_ASSIGN + 30_000)

    # ---- verdicts
    lo_h1, hi_h1 = boot["diff_ci"][("GATE(1-u)", "VERBALISED")]
    h1_pass = lo_h1 > 0
    h2_gap = boot["point"]["FOIL"] - boot["point"]["GATE(1-u)"]
    h2_pass = h2_gap <= 0.02
    p_lo, p_hi = boot["ci"]["PROBE"]
    h2b_pass = p_lo <= 0.5 <= p_hi
    h3_pass = h3_ref >= 0.90 and h3_sto >= 0.90
    u_rate = n_flag["ungrounded"] / max(n_tot["ungrounded"], 1)
    h4_pass = u_rate <= 0.02
    meta = meta_d_prime(gate_1mu, correct, seed=SEED_ASSIGN + 40_000)

    lines = ["# Phase C confirmatory report (single registered run)", "",
             f"registration: {url} filed {ts}",
             f"seeds: corpus={SEED_CORPUS} assign={SEED_ASSIGN} boot={SEED_BOOT} "
             f"perm={SEED_PERM}",
             f"corpus: k={mem.k} N={len(mem.ent)} items={n} "
             f"forced accuracy={correct.mean():.4f}", "",
             "| source | AUROC2 | 95% CI |", "|---|---|---|"]
    for k in sources:
        lo, hi = boot["ci"][k]
        lines.append(f"| {k} | {boot['point'][k]:.4f} | ({lo:.4f}, {hi:.4f}) |")
    lines += ["",
              f"H1 : diff GATE(1-u)-VERBALISED CI ({lo_h1:+.4f}, {hi_h1:+.4f}) -> "
              f"{'PASS' if h1_pass else 'FAIL'}",
              f"H2 : FOIL-GATE gap {h2_gap:+.4f} (margin 0.02) -> "
              f"{'PASS' if h2_pass else 'FAIL'}",
              f"H2b: PROBE CI ({p_lo:.4f}, {p_hi:.4f}) contains 0.5 -> "
              f"{'PASS' if h2b_pass else 'FAIL'}",
              f"H3 : referential AUC {h3_ref:.4f}, stored AUC {h3_sto:.4f} "
              f"(floors 0.90) -> {'PASS' if h3_pass else 'FAIL'}",
              f"H4 : ungrounded leak {n_flag['ungrounded']}/{n_tot['ungrounded']} = "
              f"{u_rate:.4f} (<= 0.02) -> {'PASS' if h4_pass else 'FAIL'}; "
              f"grounded {n_flag['grounded']}/{n_tot['grounded']}; checker "
              f"precision={checker['precision']:.3f} recall={checker['recall']:.3f}",
              f"permutation null: mean={perm.mean():.4f} sd={perm.std(ddof=1):.4f} "
              f"p={'<0.001' if perm_p == 0 else f'{perm_p:.4f}'}",
              f"meta-d': " + (f"d'={meta['d_prime']:.3f} meta-d'={meta['meta_d']:.3f} "
                              f"M={meta['m_ratio']:.3f}" if meta.get("eligible")
                              else f"excluded ({meta.get('reason')})"),
              f"ECE (descriptive, no calibration fit): "
              f"{ {k: round(ece(v, correct), 4) for k, v in sources.items()} }"]
    with open(REPORT, "w") as f:
        f.write("\n".join(lines) + "\n")
    print("\n".join(lines))
    print(f"\n[phase-c] wrote {REPORT}")


if __name__ == "__main__":
    main()
