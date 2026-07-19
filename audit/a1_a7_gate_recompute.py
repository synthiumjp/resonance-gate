"""A1 + A7 + parts of A3/A6: regenerate the registered corpus (seed
999000021), recompute every LLM-free quantity in phase_c_report.md with an
INDEPENDENT implementation (sklearn), and decompose the headline AUROC2 by
item subset. Read-only; writes only to audit/.

Outputs: audit/a1_a7_output.txt, audit/per_item.csv
"""

import json
import os

import numpy as np
from sklearn.metrics import roc_auc_score

import _common
_common.patch_cache()

from type2 import auroc2, ece, meta_d_prime  # committed implementation
import baselines as bl

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "a1_a7_output.txt")
CSV = os.path.join(os.path.dirname(os.path.abspath(__file__)), "per_item.csv")
SEED_CORPUS, SEED_ASSIGN, SEED_BOOT, SEED_PERM = (999000021, 999000022,
                                                  999000023, 999000024)
L = []


def say(s=""):
    print(s)
    L.append(s)


def sk_auc(conf, correct):
    correct = np.asarray(correct, dtype=int)
    if correct.min() == correct.max():
        return float("nan")
    return roc_auc_score(correct, conf)


def indep_bootstrap_ci(conf, correct, B=2000, seed=SEED_BOOT):
    """Independent bootstrap (sklearn AUC), same seed/B as registered."""
    rng = np.random.default_rng(seed)
    n = len(correct)
    vals = []
    for _ in range(B):
        idx = rng.integers(n, size=n)
        c = correct[idx]
        if c.all() or not c.any():
            continue
        vals.append(sk_auc(conf[idx], c))
    v = np.array(vals)
    return float(np.quantile(v, 0.025)), float(np.quantile(v, 0.975))


def main():
    c = _common.build_registered_corpus(SEED_CORPUS)
    mem = c.memory
    rows, X = _common.phase_c_rows(c)
    n = len(rows)
    correct = np.array([r["correct"] for r in rows])
    kinds = np.array([r["it"].kind for r in rows])
    gate_1mu = np.array([1.0 - r["op"].u for r in rows])

    say(f"corpus regenerated: k={mem.k} N={len(mem.ent)} items={n} "
        f"accuracy={correct.mean():.4f}")
    say("committed report:   k=233 N=500 items=280 accuracy=0.6357")
    say()

    # ---------------- A7: independent recompute of the LLM-free numbers
    say("== A7: independent statistics (sklearn) vs committed ==")
    au_own = auroc2(gate_1mu, correct)
    au_sk = sk_auc(gate_1mu, correct)
    say(f"GATE(1-u) AUROC2: committed 0.9790 | type2.py {au_own:.4f} | "
        f"sklearn {au_sk:.4f} | delta(own-sk) {au_own - au_sk:+.2e}")

    head = json.load(open(os.path.join(_common.R, "instruments",
                                       "h2_foil_head.json")))
    hp = bl.LogisticProbe()
    hp.w, hp.mu, hp.sd, hp.keep = (np.array(head["w"]), np.array(head["mu"]),
                                   np.array(head["sd"]),
                                   np.array(head["keep"], dtype=bool))
    foil = hp.predict(X)
    say(f"FOIL AUROC2:      committed 0.9920 | type2.py {auroc2(foil, correct):.4f} | "
        f"sklearn {sk_auc(foil, correct):.4f}")
    gb = np.array([r["op"].b for r in rows])
    gbbd = np.array([r["op"].b / (r["op"].b + r["op"].d)
                     if (r["op"].b + r["op"].d) > 1e-12 else 0.5 for r in rows])
    say(f"GATE(b):          committed 0.9359 | sklearn {sk_auc(gb, correct):.4f}")
    say(f"GATE(b/(b+d)):    committed 0.8570 | sklearn {sk_auc(gbbd, correct):.4f}")

    lo, hi = indep_bootstrap_ci(gate_1mu, correct)
    say(f"GATE CI: committed (0.9645, 0.9907) | independent boot ({lo:.4f}, {hi:.4f})")

    rngp = np.random.default_rng(SEED_PERM)
    perm = np.array([sk_auc(gate_1mu[rngp.permutation(n)], correct)
                     for _ in range(1000)])
    p = float((perm >= au_sk).mean())
    say(f"perm null: committed mean=0.4992 sd=0.0363 | independent "
        f"mean={perm.mean():.4f} sd={perm.std(ddof=1):.4f} p={p:.4f} "
        f"(add-one p={(1 + (perm >= au_sk).sum()) / 1001:.4f})")

    # H3 from committed constants
    from opinion import C_REF, S_REF, sigmoid
    from l2_ambiguity import C_L2, S_L2
    m_ref = np.array([r["m_ref"] for r in rows])
    m_l2 = np.array([r["m_l2"] for r in rows])
    p_ref = 1.0 - sigmoid((m_ref - C_REF) / S_REF)
    p_sto = 1.0 - sigmoid((m_l2 - C_L2) / S_L2)
    clean = (kinds == "id") & correct
    lab_ref = np.concatenate([np.ones((kinds == "ref").sum()), np.zeros(clean.sum())])
    lab_sto = np.concatenate([np.ones((kinds == "coll").sum()), np.zeros(clean.sum())])
    say(f"H3 referential AUC: committed 1.0000 | sklearn "
        f"{roc_auc_score(lab_ref, np.concatenate([p_ref[kinds == 'ref'], p_ref[clean]])):.4f}")
    say(f"H3 stored AUC:      committed 1.0000 | sklearn "
        f"{roc_auc_score(lab_sto, np.concatenate([p_sto[kinds == 'coll'], p_sto[clean]])):.4f}")
    # H3 is a monotone transform of the raw margin -> same AUC on raw feature?
    say(f"H3 referential AUC on RAW m_ref (no constants): "
        f"{roc_auc_score(lab_ref, np.concatenate([-m_ref[kinds == 'ref'], -m_ref[clean]])):.4f}")
    say(f"H3 stored AUC on RAW m_l2 (no constants): "
        f"{roc_auc_score(lab_sto, np.concatenate([-m_l2[kinds == 'coll'], -m_l2[clean]])):.4f}")
    say(f"margin gap, referential: max ref m_ref="
        f"{m_ref[kinds == 'ref'].max():.4f} vs min clean-ID m_ref="
        f"{m_ref[clean].min():.4f}")
    say(f"margin gap, stored: min coll m_l2={m_l2[kinds == 'coll'].min():.4f} "
        f"max coll={m_l2[kinds == 'coll'].max():.4f} vs min clean-ID m_l2="
        f"{m_l2[clean].min():.4f}")

    # ECE recheck + meta-d'
    say(f"ECE GATE(1-u): committed 0.1593 | recomputed {ece(gate_1mu, correct):.4f}")
    meta = meta_d_prime(gate_1mu, correct, seed=SEED_ASSIGN + 40_000)
    say(f"meta-d': committed d'=0.694 meta-d'=5.466 M=7.876 | recomputed "
        f"d'={meta['d_prime']:.3f} meta-d'={meta['meta_d']:.3f} M={meta['m_ratio']:.3f}")
    say()

    # ---------------- A1: what drives the headline AUROC2?
    say("== A1: OOD composition and AUROC2 decomposition ==")
    ood = kinds == "ood"
    in_reg = np.array([r["it"].subj_term in mem.ent for r in rows])
    say(f"OOD items: {ood.sum()}; OOD subjects present in entity registry: "
        f"{in_reg[ood].sum()}/{ood.sum()}")
    say(f"OOD subjects resolving at cosine 1.0 (exact string): "
        f"{sum(1 for r in np.array(rows, dtype=object)[ood] if mem.ent.resolve(r['it'].subj_term, top=1)[0][1] > 0.999)}"
        f"/{ood.sum()}")
    say(f"ALL query subject terms present verbatim in registry: "
        f"{in_reg.sum()}/{n}")

    say(f"incorrect items by kind: "
        f"{ {k: int(((kinds == k) & ~correct).sum()) for k in ('id', 'ood', 'coll', 'ref')} }")
    say(f"correct items by kind:   "
        f"{ {k: int(((kinds == k) & correct).sum()) for k in ('id', 'ood', 'coll', 'ref')} }")

    def subset_auc(mask, label):
        cc, gg = correct[mask], gate_1mu[mask]
        if cc.all() or not cc.any():
            say(f"  {label}: degenerate (all one class, n={mask.sum()})")
            return
        say(f"  {label}: AUROC2={sk_auc(gg, cc):.4f}  n={mask.sum()} "
            f"(n_correct={cc.sum()}, n_incorrect={(~cc).sum()})")

    say("GATE(1-u) AUROC2 by subset:")
    subset_auc(np.ones(n, bool), "ALL (headline)")
    subset_auc(~ood, "OOD removed (ID+coll+ref)")
    subset_auc(kinds == "id", "ID only (written facts: does confidence track "
                              "correctness among knowns?)")
    subset_auc(ood | clean, "OOD vs clean-correct-ID only (written vs unwritten)")
    say(f"gate 1-u means: OOD {gate_1mu[ood].mean():.4f} | "
        f"ID-correct {gate_1mu[(kinds == 'id') & correct].mean():.4f} | "
        f"ID-incorrect {gate_1mu[(kinds == 'id') & ~correct].mean():.4f} | "
        f"coll {gate_1mu[kinds == 'coll'].mean():.4f} | "
        f"ref {gate_1mu[kinds == 'ref'].mean():.4f}")
    say("FOIL by subset:")
    for mask, label in [(np.ones(n, bool), "ALL"), (kinds == "id", "ID only")]:
        cc = correct[mask]
        if 0 < cc.sum() < len(cc):
            say(f"  {label}: AUROC2={sk_auc(foil[mask], cc):.4f} n={mask.sum()}")
    say()

    # controller routing per kind (context for what 'forced answer' overrides)
    say("controller action by kind:")
    for k in ("id", "ood", "coll", "ref"):
        acts = {}
        for r in np.array(rows, dtype=object)[kinds == k]:
            key = (r["action"], r["tag"])
            acts[key] = acts.get(key, 0) + 1
        say(f"  {k}: {acts}")

    # dump per-item csv
    import csv as csvmod
    with open(CSV, "w", newline="") as f:
        w = csvmod.writer(f)
        w.writerow(["kind", "subj_term", "rel", "correct", "gate_1mu", "gate_b",
                    "foil", "a", "m_l1", "m_l2", "m_ref", "action", "tag"])
        for i, r in enumerate(rows):
            w.writerow([r["it"].kind, r["it"].subj_term, r["it"].rel,
                        int(r["correct"]), f"{gate_1mu[i]:.6f}", f"{gb[i]:.6f}",
                        f"{foil[i]:.6f}", f"{r['a']:.6f}", f"{r['m_l1']:.6f}",
                        f"{r['m_l2']:.6f}", f"{r['m_ref']:.6f}", r["action"],
                        str(r["tag"])])
    say(f"wrote {CSV}")

    with open(OUT, "w") as f:
        f.write("\n".join(L) + "\n")


if __name__ == "__main__":
    main()
