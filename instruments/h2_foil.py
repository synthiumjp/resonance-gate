"""Freeze gap 1b: the H2 trained foil — a logistic head over the frozen
gate's retrieval features (a, m_l1, m_l2, m_ref, k, N), trained on DEV items
only and frozen before Phase C. H2 tests whether the untrained analytic
mapping (1-u) comes within 0.02 AUROC2 of this trained readout.

Trains on the E4 dev corpus (seed 20260719, dress mix), reports 2-fold
cross-fit dev AUROC2 (the honest generalisation number) and freezes the
full-fit head to instruments/h2_foil_head.json (weights + normalisation +
provenance; sha256 recorded in the checklist).

Usage: python instruments/h2_foil.py
"""

import hashlib
import json
import os
import sys

_R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in (_R, f"{_R}/substrate", f"{_R}/gate", f"{_R}/encoder", f"{_R}/instruments"):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import numpy as np

from corpus import CorpusConfig, build
from type2 import auroc2
from baselines import LogisticProbe

FEATURES = ["a", "m_l1", "m_l2", "m_ref", "k", "N"]
HEAD_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                         "h2_foil_head.json")
DEV_SEED = 20260719
TRAIN_SEED = 991


def collect(cfg):
    c = build(cfg)
    mem = c.memory
    X, y = [], []
    for it in c.items:
        q = mem.query(it.subj_term, it.rel)
        subj = mem.ent.resolve(it.subj_term, top=1)[0][0]
        rel = mem.rel.resolve(it.rel, top=1)[0][0]
        a, m_l1, top1 = mem._unbind(subj, rel)  # read-only use of the loop
        if it.kind == "id":
            correct = top1 == it.gold
        elif it.kind == "ood":
            correct = False
        elif it.kind == "coll":
            correct = top1 in it.gold
        else:
            correct = top1 in it.gold["objects"]
        X.append([a, m_l1, q.m_l2, q.m_ref, float(mem.k), float(len(mem.ent))])
        y.append(correct)
    return np.array(X), np.array(y)


def main():
    cfg = CorpusConfig(seed=DEV_SEED, n_entities=500, n_facts=160,
                       n_id=150, n_ood=90, n_coll=20, n_ref=20)
    X, y = collect(cfg)
    n = len(y)
    rng = np.random.default_rng(TRAIN_SEED)
    fold = rng.permutation(n) % 2
    pred = np.zeros(n)
    for f in (0, 1):
        tr, te = fold != f, fold == f
        pred[te] = LogisticProbe(seed=TRAIN_SEED + f).fit(X[tr], y[tr]).predict(X[te])
    dev_auc = auroc2(pred, y)

    head = LogisticProbe(seed=TRAIN_SEED + 2).fit(X, y)
    blob = {"features": FEATURES, "l2_reg": 1e-3, "epochs": 3000, "lr": 0.05,
            "train_seed": TRAIN_SEED, "dev_corpus_seed": DEV_SEED,
            "n_train": n, "dev_auroc2_crossfit": float(dev_auc),
            "dev_auroc2_insample": float(auroc2(head.predict(X), y)),
            "w": head.w.tolist(), "mu": head.mu.tolist(), "sd": head.sd.tolist(),
            "keep": head.keep.tolist()}
    with open(HEAD_PATH, "w") as f:
        json.dump(blob, f, indent=1)
    sha = hashlib.sha256(open(HEAD_PATH, "rb").read()).hexdigest()
    print(f"n_train={n} features={FEATURES}")
    print(f"dev AUROC2: cross-fit={dev_auc:.4f} in-sample={blob['dev_auroc2_insample']:.4f}")
    print(f"frozen: {HEAD_PATH} sha256={sha}")


if __name__ == "__main__":
    main()
