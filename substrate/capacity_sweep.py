"""E1 exit criterion 2: capacity curves for the load-normalised gate.

For k in {10,25,50,100,200,350,500}: distributions of a (resolution, top cosine)
and m (margin, s1-s2) for in-memory queries (hits) and never-written queries
(misses), >= 20 fresh-substrate trials per k, object codebook >= 500 entries.
Writes capacity_curves.csv next to this script and prints a summary table.

Usage: python capacity_sweep.py [--seed N] [--dim D] [--trials T]
"""

import argparse
import csv
import os
import numpy as np

from map_ops import Codebook, bundle, encode_record

KS = [10, 25, 50, 100, 200, 350, 500]
N_RELATIONS = 10
N_OBJECTS = 500


def run_trial(k, dim, trial_seed):
    """One fresh substrate: k written triples, k never-written (subj, rel) queries.

    Returns (n_correct, a_hit, m_hit, a_miss, m_miss) arrays of length k.
    """
    rng = np.random.default_rng(trial_seed)
    cb_seeds = rng.integers(0, 2**31, size=3)
    # 2k subjects: first k are written, last k are query-only (guaranteed misses)
    subjects = Codebook([f"s{i}" for i in range(2 * k)], dim=dim, seed=int(cb_seeds[0]))
    relations = Codebook([f"r{i}" for i in range(N_RELATIONS)], dim=dim, seed=int(cb_seeds[1]))
    objects = Codebook([f"o{i}" for i in range(N_OBJECTS)], dim=dim, seed=int(cb_seeds[2]))

    rel_idx = rng.integers(N_RELATIONS, size=2 * k)
    obj_idx = rng.integers(N_OBJECTS, size=k)

    B = bundle(
        [
            encode_record(subjects.matrix[i], relations.matrix[rel_idx[i]], objects.matrix[obj_idx[i]])
            for i in range(k)
        ],
        seed=int(rng.integers(0, 2**31)),
    )

    # vectorised unbind_obj for all 2k queries (first k hits, last k misses):
    # permute(B * subj * permute(rel,1), -2)
    S = subjects.matrix.astype(np.int32)
    R1 = np.roll(relations.matrix[rel_idx].astype(np.int32), 1, axis=1)
    noisy = np.roll(B.astype(np.int32) * S * R1, -2, axis=1)

    cos = (noisy.astype(np.float32) @ objects.matrix.T.astype(np.float32)) / dim
    top2 = np.argpartition(-cos, 1, axis=1)[:, :2]
    row = np.arange(2 * k)
    s_pair = cos[row[:, None], top2]
    order = np.argsort(-s_pair, axis=1)
    s1 = s_pair[row[:, None], order][:, 0]
    s2 = s_pair[row[:, None], order][:, 1]
    top1 = top2[row[:, None], order][:, 0]

    n_correct = int((top1[:k] == obj_idx).sum())
    a, m = s1, s1 - s2
    return n_correct, a[:k], m[:k], a[k:], m[k:]


def cohens_d(x, y):
    nx, ny = len(x), len(y)
    sp = np.sqrt(((nx - 1) * np.var(x, ddof=1) + (ny - 1) * np.var(y, ddof=1)) / (nx + ny - 2))
    return (np.mean(x) - np.mean(y)) / sp


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--dim", type=int, default=8192)
    ap.add_argument("--trials", type=int, default=20)
    args = ap.parse_args()

    print(f"capacity sweep: seed={args.seed} D={args.dim} trials/k={args.trials} "
          f"rel_pool={N_RELATIONS} obj_pool={N_OBJECTS}")

    ss = np.random.SeedSequence(args.seed)
    rows = []
    for k, child in zip(KS, ss.spawn(len(KS))):
        trial_seeds = child.generate_state(args.trials)
        correct, a_hit, m_hit, a_miss, m_miss = 0, [], [], [], []
        for ts in trial_seeds:
            c, ah, mh, am, mm = run_trial(k, args.dim, int(ts))
            correct += c
            a_hit.append(ah)
            m_hit.append(mh)
            a_miss.append(am)
            m_miss.append(mm)
        a_hit, m_hit = np.concatenate(a_hit), np.concatenate(m_hit)
        a_miss, m_miss = np.concatenate(a_miss), np.concatenate(m_miss)
        rows.append({
            "k": k,
            "accuracy": correct / (k * args.trials),
            "a_hit_mean": np.mean(a_hit), "a_hit_sd": np.std(a_hit, ddof=1),
            "a_miss_mean": np.mean(a_miss), "a_miss_sd": np.std(a_miss, ddof=1),
            "m_hit_mean": np.mean(m_hit), "m_hit_sd": np.std(m_hit, ddof=1),
            "cohens_d": cohens_d(a_hit, a_miss),
        })
        print(f"  k={k} done")

    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "capacity_curves.csv")
    with open(out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        for r in rows:
            w.writerow({key: (f"{v:.6f}" if isinstance(v, float) else v) for key, v in r.items()})
    print(f"wrote {out}\n")

    hdr = f"{'k':>5} {'acc':>7} {'a_hit':>7} {'sd':>7} {'a_miss':>7} {'sd':>7} {'m_hit':>7} {'sd':>7} {'d(a)':>7}"
    print(hdr)
    print("-" * len(hdr))
    for r in rows:
        print(f"{r['k']:>5} {r['accuracy']:>7.4f} {r['a_hit_mean']:>7.4f} {r['a_hit_sd']:>7.4f} "
              f"{r['a_miss_mean']:>7.4f} {r['a_miss_sd']:>7.4f} "
              f"{r['m_hit_mean']:>7.4f} {r['m_hit_sd']:>7.4f} {r['cohens_d']:>7.2f}")


if __name__ == "__main__":
    main()
