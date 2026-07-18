"""E3.1 task 2: the D=16384 arm. Regenerates the projection at 16384 (same
seed policy), re-measures: null floor, capacity constants, same-theta
ignorance table, C3 vs load. Expectation from the capacity law: envelope
roughly doubles — confirm or refute.

Usage: python measure_d16384.py [--seed 772]
"""

import argparse
import math
import os
import sys

_R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in (_R, f"{_R}/substrate", f"{_R}/gate", f"{_R}/encoder"):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import numpy as np

import normalisation as nz
from opinion import opinion
from e31_common import Pools, auc, balanced_acc, build_substrate, calibrations, encode
from entities import make_entities

D16 = 16384
NULL_SEED = 550  # same entity sets as encoder/test_null_floor.py


def null_floor(d):
    print(f"{'N':>6} {'pair_sd':>8} {'loo_max_mean':>12} {'floor_analytic':>14}")
    for N in [200, 700, 2000]:
        M = encode(make_entities(N, NULL_SEED + N), d)
        cos = (M.astype(np.float32) @ M.T.astype(np.float32)) / d
        iu = np.triu_indices(N, k=1)
        loo = np.where(np.eye(N, dtype=bool), -np.inf, cos).max(axis=1)
        print(f"{N:>6} {cos[iu].std(ddof=1):>8.4f} {loo.mean():>12.4f} "
              f"{nz.mu_null(N, d):>14.4f}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=772)
    args = ap.parse_args()

    print(f"=== D=16384 arm (seed={args.seed}) ===\n-- null floor --")
    null_floor(D16)

    p = Pools(D16)
    nm, hm = calibrations(p, seed=args.seed)
    scale = hm[0]
    kmax_meas = 2.0 * scale**2 / (np.pi * nm[0] ** 2)
    print(f"\n-- capacity constants --")
    print(f"measured null=({nm[0]:.4f}, {nm[1]:.4f})  hit scale={scale:.4f}  "
          f"hit sd={np.round(hm[2], 4).tolist()}")
    print(f"analytic  k_max={nz.k_max(D16, p.n_obj):.0f} paging={nz.paging_threshold(D16, p.n_obj):.0f}")
    print(f"measured  k_max={kmax_meas:.0f} paging={0.5 * kmax_meas:.0f} "
          f"k_sat={nz.k_sat(D16, p.n_obj, null_moments=nm, hit_moments=hm):.0f}")
    print(f"(D=8192 measured was: k_max=158 paging=79)")

    print(f"\n-- same-theta ignorance, full measured moments --")
    print(f"{'k':>5} {'AUC(u)':>8} {'acc@theta':>10}")
    ss = np.random.SeedSequence(args.seed + 10)
    for k, child in zip([10, 50, 100, 200], ss.spawn(4)):
        trials = max(2, math.ceil(400 / k))
        a_h, m_h, a_m, m_m, k_eff = [], [], [], [], None
        for ts in child.generate_state(trials):
            q = build_substrate(p, k, int(ts))
            a_h.append(q["hit"][0]); m_h.append(q["hit"][1])
            a_m.append(q["miss"][0]); m_m.append(q["miss"][1])
            k_eff = q["k_eff"]
        u_h = opinion(np.concatenate(a_h), np.concatenate(m_h), k_eff, p.n_obj, D16,
                      null_moments=nm, hit_moments=hm).u
        u_m = opinion(np.concatenate(a_m), np.concatenate(m_m), k_eff, p.n_obj, D16,
                      null_moments=nm, hit_moments=hm).u
        print(f"{k:>5} {auc(u_m, u_h):>8.4f} {balanced_acc(u_h, u_m):>10.4f}")

    print(f"\n-- C3 (L1 margin) vs load, full measured moments --")
    print(f"{'k_eff':>6} {'AUC(d)':>8}")
    ss2 = np.random.SeedSequence(args.seed + 20)
    for k_eff_target, child in zip([50, 70, 90, 120, 160], ss2.spawn(5)):
        base = k_eff_target - 20
        a_h, m_h, a_c, m_c, k_eff = [], [], [], [], None
        for ts in child.generate_state(6):
            q = build_substrate(p, base, int(ts), n_coll=10)
            a_h.append(q["hit"][0]); m_h.append(q["hit"][1])
            a_c.append(q["coll"][0]); m_c.append(q["coll"][1])
            k_eff = q["k_eff"]
        oh = opinion(np.concatenate(a_h), np.concatenate(m_h), k_eff, p.n_obj, D16,
                     null_moments=nm, hit_moments=hm)
        oc = opinion(np.concatenate(a_c), np.concatenate(m_c), k_eff, p.n_obj, D16,
                     null_moments=nm, hit_moments=hm)
        print(f"{k_eff:>6} {auc(oc.d, oh.d):>8.4f}")


if __name__ == "__main__":
    main()
