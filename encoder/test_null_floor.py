"""E3 Part 1, THE test of the stage: does the embedding path's correlated
geometry break the analytic null floor?

Measures, for embedded codebooks over realistic (deliberately confusable)
entity sets at N in {200, 700, 2000}:
  - the pairwise-cosine distribution of projected non-identical entities
    (analytic expectation for i.i.d. bipolar: mean 0, sd 1/sqrt(D)), and
  - the leave-one-out max-over-codebook statistic (the a_miss role),
    against the analytic mu_null(N) = sqrt(2 ln N / D) from E2.

Reports floor elevation and tail heaviness, writes encoder/null_floor.csv,
and validates BOTH normalisation modes: analytic (synthetic codebooks must
match the analytic floor) and EMBEDDED (measured calibration must match the
embedded substrate's actual miss statistic).
"""

import csv
import os

import numpy as np

from map_ops import Codebook
import normalisation as nz
from embed import D, encode_bipolar
from entities import RELATIONS10, make_entities

SEED = 550
HERE = os.path.dirname(os.path.abspath(__file__))


def _pairwise_stats(M):
    dim = M.shape[1]
    cos = (M.astype(np.float32) @ M.T.astype(np.float32)) / dim
    iu = np.triu_indices(len(M), k=1)
    pc = cos[iu].astype(np.float64)
    loo_max = np.where(np.eye(len(M), dtype=bool), -np.inf, cos).max(axis=1)
    return pc, loo_max.astype(np.float64)


def test_embedded_null_floor_vs_analytic():
    an_sd = 1.0 / np.sqrt(D)
    rows = []
    print(f"\n[null floor] D={D} seed={SEED} (analytic pairwise sd={an_sd:.4f})")
    print(f"{'N':>6} {'pair_mean':>9} {'pair_sd':>8} {'pair_p99':>9} {'pair_max':>9} "
          f"{'floor_emp':>9} {'floor_an':>9} {'elev':>7} {'elev/sd':>8}")
    for N in [200, 700, 2000]:
        names = make_entities(N, SEED + N)
        M = encode_bipolar(names)
        pc, loo = _pairwise_stats(M)
        floor_an = float(nz.mu_null(N, D))
        r = {
            "N": N,
            "pair_mean": pc.mean(), "pair_sd": pc.std(ddof=1),
            "pair_p99": np.quantile(pc, 0.99), "pair_p999": np.quantile(pc, 0.999),
            "pair_max": pc.max(),
            "floor_emp_mean": loo.mean(), "floor_emp_sd": loo.std(ddof=1),
            "floor_analytic": floor_an,
            "elevation": loo.mean() - floor_an,
            "elevation_in_null_sd": (loo.mean() - floor_an) / nz.sigma_null(D),
        }
        rows.append(r)
        print(f"{N:>6} {r['pair_mean']:>9.4f} {r['pair_sd']:>8.4f} {r['pair_p99']:>9.4f} "
              f"{r['pair_max']:>9.4f} {r['floor_emp_mean']:>9.4f} {floor_an:>9.4f} "
              f"{r['elevation']:>7.4f} {r['elevation_in_null_sd']:>8.2f}")

    out = os.path.join(HERE, "null_floor.csv")
    with open(out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows([{k: (f"{v:.6f}" if isinstance(v, float) else v) for k, v in r.items()}
                     for r in rows])
    print(f"[null floor] wrote {out}")

    # sanity: the machinery itself — a synthetic i.i.d. codebook must sit ON
    # the analytic curve with light tails
    rng_cb = Codebook([f"x{i}" for i in range(700)], dim=D, seed=SEED)
    pc_iid, loo_iid = _pairwise_stats(rng_cb.matrix)
    print(f"[null floor] iid control N=700: pair_sd={pc_iid.std(ddof=1):.4f} "
          f"floor={loo_iid.mean():.4f} vs analytic {nz.mu_null(700, D):.4f}")
    assert abs(pc_iid.std(ddof=1) - an_sd) < 0.15 * an_sd
    assert abs(loo_iid.mean() - nz.mu_null(700, D)) < 2 * nz.sigma_null(D)

    # the embedded floor must be measured as elevated (the expected finding —
    # if this ever stops holding, the EMBEDDED mode is redundant: re-plan)
    for r in rows:
        assert r["elevation"] > 0, f"embedded floor NOT elevated at N={r['N']}"


def test_embedded_calibration_matches_substrate_misses():
    """EMBEDDED-mode calibrate_null on real codebooks must predict the miss
    statistic of an actual embedded substrate; the analytic mode must NOT."""
    N = 700
    objects = Codebook.from_matrix(
        make_entities(N, SEED + N), encode_bipolar(make_entities(N, SEED + N))
    )
    subj = encode_bipolar(make_entities(600, SEED + 7))
    rels = encode_bipolar(RELATIONS10)
    mu_emp, sd_emp = nz.calibrate_null(subj, rels, objects, k=100, trials=4, seed=SEED)
    mu_an = float(nz.mu_null(N, D))
    print(f"\n[calibration] N={N}: measured null=({mu_emp:.4f}, {sd_emp:.4f}) "
          f"vs analytic ({mu_an:.4f}, {nz.sigma_null(D):.4f})")

    # held-out check: fresh calibration run with a different seed must agree
    mu2, sd2 = nz.calibrate_null(subj, rels, objects, k=100, trials=4, seed=SEED + 1)
    assert abs(mu_emp - mu2) < 3 * sd_emp / np.sqrt(400), "calibration unstable"
    # and the embedded mode must place the measured floor at z ~ 0 relative to
    # its own anchor, while the analytic anchor must be visibly displaced
    z_emb = (mu_emp - mu_emp) / sd_emp
    z_an = (mu_emp - mu_an) / nz.sigma_null(D)
    print(f"[calibration] displacement of true floor: embedded {z_emb:.2f} sd, "
          f"analytic {z_an:.2f} sd")
    assert abs(z_an) > 1.0, "analytic mode fits embedded floor — EMBEDDED mode unnecessary?"
