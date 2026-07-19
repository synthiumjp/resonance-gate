"""A8 supplement: show that the shipped (gitignored, unversioned)
instruments/dress_report_cpu.md was generated with the PRE-freeze
C_L2/S_L2 placeholders (0.15/0.08), not the frozen constants
(0.4528/0.0342). Recomputes the quick-arm gate-side numbers under both
constant sets; no LLM needed. Expected:
  frozen : b/(b+d) 0.7857, ECE(b) 0.3297, NULL(full) 0.4018  == audit rerun
  E4-era : b/(b+d) 0.6652, ECE(b) 0.3132, NULL(full) 0.4464  == shipped file
"""

import numpy as np

import _common
_common.patch_cache()

import l2_ambiguity
from corpus import CorpusConfig, build
from type2 import auroc2, ece
from baselines import null_shuffle_full

for c_l2, s_l2, tag in [(0.4528, 0.0342, "frozen"), (0.15, 0.08, "E4-era")]:
    l2_ambiguity.C_L2, l2_ambiguity.S_L2 = c_l2, s_l2
    cfg = CorpusConfig(seed=20260719, n_entities=150, n_facts=40,
                       n_id=8, n_ood=8, n_coll=3, n_ref=3)
    c = build(cfg)
    mem = c.memory
    b, d, corr = [], [], []
    for it in c.items:
        q = mem.query(it.subj_term, it.rel)
        subj = mem.ent.resolve(it.subj_term, top=1)[0][0]
        rel = mem.rel.resolve(it.rel, top=1)[0][0]
        _, _, top1 = mem._unbind(subj, rel)
        if it.kind == "id":
            cc = top1 == it.gold
        elif it.kind == "ood":
            cc = False
        elif it.kind == "coll":
            cc = top1 in it.gold
        else:
            cc = top1 in it.gold["objects"]
        b.append(q.op.b)
        d.append(q.op.d)
        corr.append(cc)
    b, d, corr = np.array(b), np.array(d), np.array(corr)
    bbd = np.where(b + d > 1e-12, b / (b + d), 0.5)
    nf = null_shuffle_full(b, seed=20260719 + 10)
    print(f"{tag}: AUROC2(b/(b+d))={auroc2(bbd, corr):.4f} "
          f"ECE(b)={ece(b, corr):.4f} AUROC2(NULL_full)={auroc2(nf, corr):.4f}")
