"""E3.1 task 1: the E3 Part-1 embedded table under FULL measured moments
(hit + null calibrated on the actual codebook) vs the null-only calibration
used in E3. Same pools, same substrate seeds as encoder/test_embedded_gate.py
so every number is directly comparable.

Usage: python measure_measured_moments.py [--seed 771]
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
from e31_common import Pools, auc, balanced_acc, build_substrate, calibrations

D = 8192
E3_SEED = 660  # substrate seed base from test_embedded_gate.py


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=771)
    args = ap.parse_args()

    p = Pools(D)
    nm, hm = calibrations(p, seed=args.seed)
    scale, k_refs, sd_refs = hm
    print(f"calibration seed={args.seed}  null=({nm[0]:.4f}, {nm[1]:.4f})")
    print(f"hit: scale={scale:.4f} (mu = {scale:.3f}*sqrt(2/pi k)); "
          f"sd at k={k_refs.astype(int).tolist()}: {np.round(sd_refs, 4).tolist()} "
          f"(E1 synthetic ~0.011)")
    km = nz.k_sat(D, p.n_obj, null_moments=nm, hit_moments=hm)
    kmax = 2.0 * scale**2 / (np.pi * nm[0] ** 2)
    print(f"capacity w/ full measured moments: k_max={kmax:.0f} paging={0.5 * kmax:.0f} "
          f"k_sat={km:.0f}\n")

    print(f"{'k':>5} {'AUC(u)':>8} {'acc null-only':>13} {'acc full-meas':>13}")
    ss = np.random.SeedSequence(E3_SEED + 3)
    for k, child in zip([10, 50, 100, 200], ss.spawn(4)):
        trials = max(2, math.ceil(400 / k))
        a_h, m_h, a_m, m_m, k_eff = [], [], [], [], None
        for ts in child.generate_state(trials):
            q = build_substrate(p, k, int(ts))
            a_h.append(q["hit"][0]); m_h.append(q["hit"][1])
            a_m.append(q["miss"][0]); m_m.append(q["miss"][1])
            k_eff = q["k_eff"]
        a_h, m_h = np.concatenate(a_h), np.concatenate(m_h)
        a_m, m_m = np.concatenate(a_m), np.concatenate(m_m)

        u_h0 = opinion(a_h, m_h, k_eff, p.n_obj, D, null_moments=nm).u
        u_m0 = opinion(a_m, m_m, k_eff, p.n_obj, D, null_moments=nm).u
        u_h1 = opinion(a_h, m_h, k_eff, p.n_obj, D, null_moments=nm, hit_moments=hm).u
        u_m1 = opinion(a_m, m_m, k_eff, p.n_obj, D, null_moments=nm, hit_moments=hm).u
        print(f"{k:>5} {auc(u_m1, u_h1):>8.4f} {balanced_acc(u_h0, u_m0):>13.4f} "
              f"{balanced_acc(u_h1, u_m1):>13.4f}")
    print("\nNote: AUC(u) is invariant to the moment choice at fixed (k, N) — the\n"
          "normalisation is monotone in a (notebook entry 4). Moments move the\n"
          "same-theta operating point (acc), the flag boundaries, and k_max.")


if __name__ == "__main__":
    main()
