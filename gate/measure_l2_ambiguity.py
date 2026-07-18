"""E3.1 task 3: C3 via L2 top-2 vs L1 margin, at loads above the old cliff.

Hypothesis under test: L2-d is load-invariant because collisions live in the
store, not the bundle. Embedded substrates (D=8192), full measured moments
for u; k_eff in {50, 70, 90, 120}.

Usage: python measure_l2_ambiguity.py [--seed 773]
"""

import argparse
import os
import sys

_R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in (_R, f"{_R}/substrate", f"{_R}/gate", f"{_R}/encoder"):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import numpy as np

from opinion import opinion
from l2_ambiguity import L2Store, l2_opinion_parts
from e31_common import Pools, auc, build_substrate, calibrations

D = 8192


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=773)
    args = ap.parse_args()

    p = Pools(D)
    nm, hm = calibrations(p, seed=771)  # same calibration as task 1
    print(f"seed={args.seed}  null=({nm[0]:.4f}, {nm[1]:.4f}) hit scale={hm[0]:.4f}")
    print(f"{'k_eff':>6} {'AUC(d) L1':>10} {'AUC(d) L2':>10} "
          f"{'m_l2 coll':>10} {'m_l2 clean':>11}")

    ss = np.random.SeedSequence(args.seed)
    for k_eff_target, child in zip([50, 70, 90, 120], ss.spawn(4)):
        base = k_eff_target - 20
        d1_h, d1_c, d2_h, d2_c, ml2_h, ml2_c = [], [], [], [], [], []
        for ts in child.generate_state(6):
            q = build_substrate(p, base, int(ts), n_coll=10)
            k_eff = q["k_eff"]

            store = L2Store(D)
            for s, r, o in q["records"]:
                store.append(p.subj[s], p.rels[r], o)

            for cls, (d1_out, d2_out, ml2_out, rows) in {
                "hit": (d1_h, d2_h, ml2_h, slice(0, base)),
                "coll": (d1_c, d2_c, ml2_c, slice(base, base + 10)),
            }.items():
                a, m = q[cls]
                op = opinion(a, m, k_eff, p.n_obj, D, null_moments=nm, hit_moments=hm)
                d1_out.append(op.d)
                sq = p.subj[q["query_subj_idx"][rows]]
                rq = p.rels[q["query_rel_idx"][rows]]
                c1, c2, _, _ = store.top2_batch(sq, rq)
                m_l2 = c1 - c2
                _, d2 = l2_opinion_parts(op.u, m_l2)
                d2_out.append(d2)
                ml2_out.append(m_l2)

        auc_l1 = auc(np.concatenate(d1_c), np.concatenate(d1_h))
        auc_l2 = auc(np.concatenate(d2_c), np.concatenate(d2_h))
        print(f"{k_eff_target:>6} {auc_l1:>10.4f} {auc_l2:>10.4f} "
              f"{np.mean(np.concatenate(ml2_c)):>10.4f} "
              f"{np.mean(np.concatenate(ml2_h)):>11.4f}")


if __name__ == "__main__":
    main()
