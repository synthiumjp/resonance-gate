"""Audit plumbing. READ-ONLY discipline: the embedding disk cache normally
lives inside encoder/ (a frozen dir) and get_embeddings() rewrites it when a
new string is embedded. Every audit script must call patch_cache() BEFORE
building any Registry so all cache reads/writes go to a scratch copy and the
frozen tree stays byte-identical."""

import os
import shutil
import sys

R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in (R, f"{R}/substrate", f"{R}/gate", f"{R}/encoder", f"{R}/mouth",
           f"{R}/instruments"):
    if _p not in sys.path:
        sys.path.insert(0, _p)

SCRATCH = os.environ.get(
    "AUDIT_SCRATCH",
    "/tmp/claude-1000/-home-jp-rg/e5325534-3661-4d1c-8b33-e17d6c23795a/scratchpad")


def patch_cache():
    import e31_common
    os.makedirs(SCRATCH, exist_ok=True)
    audit_cache = os.path.join(SCRATCH, "emb_cache_audit.npz")
    if not os.path.exists(audit_cache):
        shutil.copy(e31_common.CACHE_PATH, audit_cache)
    e31_common.CACHE_PATH = audit_cache
    return audit_cache


def build_registered_corpus(seed=999000021):
    """The registered Phase C corpus, regenerated deterministically."""
    from corpus import CorpusConfig, build
    cfg = CorpusConfig(seed=seed, n_entities=500, n_facts=160,
                       n_id=150, n_ood=90, n_coll=20, n_ref=20)
    return build(cfg)


def phase_c_rows(c):
    """Reproduce phase_c.py's per-item loop exactly (read-only)."""
    import numpy as np
    mem = c.memory
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
                     "subj": subj, "rel": rel, "answer": top1, "correct": correct,
                     "a": a, "m_l1": m_l1, "action": q.action, "tag": q.tag})
        X.append([a, m_l1, q.m_l2, q.m_ref, float(mem.k), float(len(mem.ent))])
    return rows, np.array(X)
