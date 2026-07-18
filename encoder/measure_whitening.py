"""E3.1 task 4: the whitening frontier. Shrinkage-ZCA blend at lambda in
{0, .25, .5, .75, 1}; at each lambda: pairwise null sd, same-theta ignorance
AUC at k in {50, 100}, C3 AUC(d) (L1 margin, k_eff=70, comparable with the
E3 number 0.8374), and query generalization top1/top2. One CSV out. This is
a frontier, not a pass/fail.

Usage: python measure_whitening.py [--seed 774]
"""

import argparse
import csv
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
from e31_common import (HERE, Pools, auc, balanced_acc, build_substrate,
                        calibrations, get_embeddings)
from entities import make_entities
from test_generalization import score_generalization
from whitening import blend_transform, load_or_fit_zca

D = 8192


def ignorance_auc(p, nm, hm, k, seed):
    trials = max(3, math.ceil(300 / k))
    ss = np.random.SeedSequence(seed)
    a_h, m_h, a_m, m_m, k_eff = [], [], [], [], None
    for ts in ss.generate_state(trials):
        q = build_substrate(p, k, int(ts))
        a_h.append(q["hit"][0]); m_h.append(q["hit"][1])
        a_m.append(q["miss"][0]); m_m.append(q["miss"][1])
        k_eff = q["k_eff"]
    u_h = opinion(np.concatenate(a_h), np.concatenate(m_h), k_eff, p.n_obj, D,
                  null_moments=nm, hit_moments=hm).u
    u_m = opinion(np.concatenate(a_m), np.concatenate(m_m), k_eff, p.n_obj, D,
                  null_moments=nm, hit_moments=hm).u
    return auc(u_m, u_h)


def c3_auc(p, nm, hm, seed):
    ss = np.random.SeedSequence(seed)
    a_h, m_h, a_c, m_c, k_eff = [], [], [], [], None
    for ts in ss.generate_state(5):
        q = build_substrate(p, 50, int(ts), n_coll=10)
        a_h.append(q["hit"][0]); m_h.append(q["hit"][1])
        a_c.append(q["coll"][0]); m_c.append(q["coll"][1])
        k_eff = q["k_eff"]
    oh = opinion(np.concatenate(a_h), np.concatenate(m_h), k_eff, p.n_obj, D,
                 null_moments=nm, hit_moments=hm)
    oc = opinion(np.concatenate(a_c), np.concatenate(m_c), k_eff, p.n_obj, D,
                 null_moments=nm, hit_moments=hm)
    return auc(oc.d, oh.d)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=774)
    args = ap.parse_args()

    # ZCA fit once on the codebook embedding distribution (subjects + objects)
    fit_names = make_entities(1600, 660) + make_entities(500, 661)
    mu, W = load_or_fit_zca(get_embeddings(list(dict.fromkeys(fit_names))))
    null_names = make_entities(700, 550 + 700)

    rows = []
    print(f"seed={args.seed}  ZCA fit on {len(set(fit_names))} pool embeddings")
    print(f"{'lambda':>7} {'null_sd':>8} {'ign@50':>8} {'ign@100':>8} {'C3@70':>7} "
          f"{'gen_top1':>9} {'gen_top2':>9}")
    for lam in [0.0, 0.25, 0.5, 0.75, 1.0]:
        t = blend_transform(mu, W, lam)
        M = None
        from e31_common import encode
        M = encode(null_names, D, t)
        cosm = (M.astype(np.float32) @ M.T.astype(np.float32)) / D
        pair_sd = cosm[np.triu_indices(len(M), k=1)].std(ddof=1)

        p = Pools(D, transform=t)
        nm, hm = calibrations(p, seed=args.seed)
        g = score_generalization(transform=t)
        r = {
            "lambda": lam,
            "null_sd": pair_sd,
            "ign_auc_k50": ignorance_auc(p, nm, hm, 50, args.seed + 10),
            "ign_auc_k100": ignorance_auc(p, nm, hm, 100, args.seed + 11),
            "c3_auc_k70": c3_auc(p, nm, hm, args.seed + 12),
            "gen_top1": g["overall"]["top1"],
            "gen_top2": g["overall"]["top2"],
            "null_mu_substrate": nm[0],
        }
        rows.append(r)
        print(f"{lam:>7.2f} {r['null_sd']:>8.4f} {r['ign_auc_k50']:>8.4f} "
              f"{r['ign_auc_k100']:>8.4f} {r['c3_auc_k70']:>7.4f} "
              f"{r['gen_top1']:>9.3f} {r['gen_top2']:>9.3f}")

    out = os.path.join(HERE, "whitening_frontier.csv")
    with open(out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows([{k: f"{v:.6f}" for k, v in r.items()} for r in rows])
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
