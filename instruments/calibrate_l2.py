"""Freeze gap 1a: measure C_L2 / S_L2 from a dedicated dev calibration pass.

Embedded lambda=0.75 substrates; per trial: singleton records + planted
collisions; L2 top-2 key margins collected per class. C_L2 = variance-
weighted crossing between the collision and singleton margin distributions
(house style, matching the z_resolution zero-point); S_L2 = pooled sd.

Usage: python instruments/calibrate_l2.py [--seed 880]
"""

import argparse
import os
import sys

_R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in (_R, f"{_R}/substrate", f"{_R}/gate", f"{_R}/encoder", f"{_R}/instruments"):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import numpy as np

from corpus import CorpusConfig, build
from l2_ambiguity import L2Store


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=880)
    ap.add_argument("--trials", type=int, default=4)
    args = ap.parse_args()

    m_single, m_coll = [], []
    for t in range(args.trials):
        cfg = CorpusConfig(seed=args.seed + t, n_entities=300, n_facts=80,
                           n_id=60, n_ood=10, n_coll=15, n_ref=5)
        c = build(cfg)
        mem = c.memory
        for it in c.items:
            if it.kind not in ("id", "coll"):
                continue
            subj = mem.ent.resolve(it.subj_term, top=1)[0][0]
            rel = mem.rel.resolve(it.rel, top=1)[0][0]
            c1, c2, _, _ = mem.store.top2_batch(mem.ent.vector(subj)[None, :],
                                                mem.rel.vector(rel)[None, :])
            (m_single if it.kind == "id" else m_coll).append(float(c1[0] - c2[0]))

    m_single, m_coll = np.array(m_single), np.array(m_coll)
    mu_s, sd_s = m_single.mean(), m_single.std(ddof=1)
    mu_c, sd_c = m_coll.mean(), m_coll.std(ddof=1)
    c_l2 = (mu_s * sd_c + mu_c * sd_s) / (sd_s + sd_c)
    s_l2 = 0.5 * (sd_s + sd_c)
    print(f"seed={args.seed} trials={args.trials} "
          f"n_single={len(m_single)} n_coll={len(m_coll)}")
    print(f"singleton m_l2: mean={mu_s:.4f} sd={sd_s:.4f}")
    print(f"collision m_l2: mean={mu_c:.4f} sd={sd_c:.4f}")
    print(f"C_L2 = {c_l2:.4f}  S_L2 = {s_l2:.4f}")


if __name__ == "__main__":
    main()
