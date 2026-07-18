"""E2 exit tests, on synthetic random-vector substrates only (scope guard:
no mouth, no embeddings, no LLM, no resonator — the gate's geometry must be
cleanly attributable to the substrate).

Tests:
  1. validation — analytic mu curves vs the E1 capacity CSV.
  a. IGNORANCE — u separates written from never-written across k, same theta.
  b. AMBIGUITY — d dominates on planted collisions, b on clean singletons (C3).
  c. CODEBOOK DRIFT — N-aware vs k-only normalisation across N (figure CSV).
  d. SATURATION ROUTING — the gate flags saturation where the capacity law says.
"""

import csv
import math
import os

import numpy as np

from map_ops import Codebook, bundle, encode_record
import normalisation as nz
from normalisation import (
    is_saturated,
    k_max,
    k_sat,
    mu_hit,
    mu_null,
    paging_threshold,
)
from opinion import opinion
from controller import Action, route

D = 8192
SEED = 202
HERE = os.path.dirname(os.path.abspath(__file__))


# ---------------------------------------------------------------- helpers

def synth(k, N, dim, seed, n_coll=0, n_miss=None):
    """Fresh synthetic substrate: k singleton triples (+ n_coll colliding
    pairs: same (subj, rel), two different objects, both written). Returns
    (a, m) arrays per query class and the true load k_eff."""
    rng = np.random.default_rng(seed)
    n_miss = k if n_miss is None else n_miss
    n_q = k + n_coll + n_miss
    subj = (rng.integers(0, 2, size=(n_q, dim), dtype=np.int8) * 2 - 1).astype(np.int8)
    rels = (rng.integers(0, 2, size=(10, dim), dtype=np.int8) * 2 - 1).astype(np.int8)
    rel_idx = rng.integers(10, size=n_q)
    objects = Codebook([f"o{i}" for i in range(N)], dim=dim, seed=int(rng.integers(2**31)))
    obj_idx = rng.integers(N, size=k)

    records = [
        encode_record(subj[i], rels[rel_idx[i]], objects.matrix[obj_idx[i]])
        for i in range(k)
    ]
    for j in range(n_coll):
        i = k + j
        o1, o2 = rng.choice(N, size=2, replace=False)
        records.append(encode_record(subj[i], rels[rel_idx[i]], objects.matrix[o1]))
        records.append(encode_record(subj[i], rels[rel_idx[i]], objects.matrix[o2]))
    B = bundle(records, seed=int(rng.integers(2**31)))

    # vectorised unbind_obj for all queries (hits, collisions, misses)
    noisy = np.roll(
        B.astype(np.int32) * subj.astype(np.int32)
        * np.roll(rels[rel_idx].astype(np.int32), 1, axis=1),
        -2, axis=1,
    )
    cos = (noisy.astype(np.float32) @ objects.matrix.T.astype(np.float32)) / dim
    top2 = np.argpartition(-cos, 1, axis=1)[:, :2]
    rows = np.arange(n_q)
    pair = cos[rows[:, None], top2]
    order = np.argsort(-pair, axis=1)
    s1 = pair[rows[:, None], order][:, 0].astype(np.float64)
    s2 = pair[rows[:, None], order][:, 1].astype(np.float64)

    a, m = s1, s1 - s2
    sl_hit, sl_coll, sl_miss = slice(0, k), slice(k, k + n_coll), slice(k + n_coll, n_q)
    return {
        "hit": (a[sl_hit], m[sl_hit]),
        "coll": (a[sl_coll], m[sl_coll]),
        "miss": (a[sl_miss], m[sl_miss]),
        "k_eff": k + 2 * n_coll,
    }


def gather(kind, k, N, trials, seed_seq, n_coll=0):
    """Accumulate (a, m) for one query class over `trials` fresh substrates."""
    a_all, m_all, k_eff = [], [], None
    for ts in seed_seq.generate_state(trials):
        s = synth(k, N, D, int(ts), n_coll=n_coll)
        a, m = s[kind]
        a_all.append(a)
        m_all.append(m)
        k_eff = s["k_eff"]
    return np.concatenate(a_all), np.concatenate(m_all), k_eff


def auc(pos, neg):
    """P(score_pos > score_neg), rank-based (ties get half credit)."""
    pos, neg = np.asarray(pos, dtype=np.float64), np.asarray(neg, dtype=np.float64)
    both = np.concatenate([pos, neg])
    order = both.argsort(kind="mergesort")
    ranks = np.empty(len(both))
    ranks[order] = np.arange(1, len(both) + 1)
    # average ranks over exact ties
    sorted_vals = both[order]
    i = 0
    while i < len(both):
        j = i
        while j + 1 < len(both) and sorted_vals[j + 1] == sorted_vals[i]:
            j += 1
        if j > i:
            ranks[order[i:j + 1]] = (i + j) / 2 + 1
        i = j + 1
    n_p, n_n = len(pos), len(neg)
    return (ranks[:n_p].sum() - n_p * (n_p + 1) / 2) / (n_p * n_n)


def balanced_acc(u_hit, u_miss, thr=0.5):
    return 0.5 * (np.mean(u_hit < thr) + np.mean(u_miss >= thr))


def best_balanced_acc(u_hit, u_miss):
    best = 0.0
    for thr in np.unique(np.concatenate([u_hit, u_miss])):
        best = max(best, balanced_acc(u_hit, u_miss, thr))
    return best


# ------------------------------------------------- 1. analytic validation

def test_analytic_mu_curves_match_e1_csv():
    """mu_hit(k) and mu_null(N) vs the measured E1 curves, full k grid.

    Tolerance 0.006 absolute: the first-order extreme-value form of mu_null
    overshoots the measured floor by ~1 null-sd (~0.005), and mu_hit picks up
    a sign-clipping bias of similar size at full saturation. Both anchors must
    still land within ~1.5 null-sd of measurement everywhere."""
    t = nz._sigmas()
    err_hit = np.abs(mu_hit(t["k"]) - t["a_hit_mean"])
    err_null = np.abs(mu_null(500, D) - t["a_miss_mean"])
    print("\n[validation] k grid:", t["k"].astype(int).tolist())
    print(f"[validation] |mu_hit - measured| max = {err_hit.max():.4f}")
    print(f"[validation] |mu_null(500) - measured floor| max = {err_null.max():.4f}")
    assert err_hit.max() <= 0.006
    assert err_null.max() <= 0.006


# ------------------------------------------------------- a. IGNORANCE

def test_ignorance_u_separates_hits_from_misses():
    """u must separate written from never-written queries at every k at or
    below the paging threshold — AUC >= 0.95 — and the SAME theta (0.0, i.e.
    the u = 0.5 boundary) must classify well at every such k. AUC is
    threshold-free, so the load-invariance claim is tested as: fixed-theta
    balanced accuracy >= 0.90 and within 0.05 of the best per-k threshold."""
    N = 500
    pt = paging_threshold(D, N)
    ss = np.random.SeedSequence(SEED)
    print(f"\n[ignorance] N={N} D={D} paging_threshold={pt:.0f} seed={SEED}")
    print(f"{'k':>5} {'AUC(u)':>8} {'acc@theta':>10} {'acc@best':>9}")
    for k, child in zip([10, 50, 100, 200], ss.spawn(4)):
        assert k <= pt
        trials = max(2, math.ceil(400 / k))
        a_h, m_h, k_eff = gather("hit", k, N, trials, child)
        a_m, m_m, _ = gather("miss", k, N, trials, child)
        u_h = opinion(a_h, m_h, k_eff, N, D).u
        u_m = opinion(a_m, m_m, k_eff, N, D).u
        auc_u = auc(u_m, u_h)
        acc = balanced_acc(u_h, u_m)
        acc_best = best_balanced_acc(u_h, u_m)
        print(f"{k:>5} {auc_u:>8.4f} {acc:>10.4f} {acc_best:>9.4f}")
        assert auc_u >= 0.95, f"AUC {auc_u:.3f} < 0.95 at k={k}"
        assert acc >= 0.90, f"same-theta acc {acc:.3f} < 0.90 at k={k}"
        assert acc >= acc_best - 0.05, f"theta miscalibrated at k={k}"


# ------------------------------------------------------- b. AMBIGUITY

def test_ambiguity_c3_split():
    """Planted collisions (same (subj, rel), two objects, both written) must
    come out d-dominant; clean singleton hits b-dominant. C3 separation =
    AUC of d, collision vs clean hit. Exit bar: > 0.90."""
    k, n_coll, N, trials = 50, 10, 500, 5
    ss = np.random.SeedSequence(SEED + 1)
    a_h, m_h, a_c, m_c, k_eff = [], [], [], [], None
    for ts in ss.generate_state(trials):
        s = synth(k, N, D, int(ts), n_coll=n_coll)
        a_h.append(s["hit"][0]); m_h.append(s["hit"][1])
        a_c.append(s["coll"][0]); m_c.append(s["coll"][1])
        k_eff = s["k_eff"]
    a_h, m_h = np.concatenate(a_h), np.concatenate(m_h)
    a_c, m_c = np.concatenate(a_c), np.concatenate(m_c)

    op_h = opinion(a_h, m_h, k_eff, N, D)
    op_c = opinion(a_c, m_c, k_eff, N, D)
    auc_d = auc(op_c.d, op_h.d)
    frac_d_dom = np.mean((op_c.d > op_c.b) & (op_c.d > op_c.u))
    frac_b_dom = np.mean((op_h.b > op_h.d) & (op_h.b > op_h.u))
    print(f"\n[ambiguity/C3] k_eff={k_eff} N={N} seed={SEED + 1} "
          f"({trials * n_coll} collisions vs {trials * k} clean hits)")
    print(f"[ambiguity/C3] *** C3 SEPARATION: AUC(d) = {auc_d:.4f} ***")
    print(f"[ambiguity/C3] d dominant on collisions: {frac_d_dom:.3f}; "
          f"b dominant on clean hits: {frac_b_dom:.3f}; "
          f"mean u: coll={np.mean(op_c.u):.3f} clean={np.mean(op_h.u):.3f}")
    assert auc_d > 0.90, f"C3 split AUC {auc_d:.3f} <= 0.90"
    assert frac_d_dom > 0.7
    assert frac_b_dom > 0.9


# --------------------------------------------------- c. CODEBOOK DRIFT

def test_codebook_drift_n_aware_vs_k_only():
    """Repeat the ignorance test at N in {200, 700, 2000}, N-aware
    normalisation ON vs OFF (k-only: N pinned to the calibration value 500).
    The k-only gate's calibration (miss-side z, fixed-theta accuracy) drifts
    with N; the full z(a) gate's does not. Writes figure-ready CSV."""
    k, trials, N_ref = 100, 4, 500
    ss = np.random.SeedSequence(SEED + 2)
    rows, z_miss_by_mode = [], {"n_aware": [], "k_only": []}
    print(f"\n[drift] k={k} N_ref(k-only)={N_ref} seed={SEED + 2}")
    print(f"{'N':>6} {'mode':>8} {'AUC(u)':>8} {'acc@theta':>10} {'z_miss':>8} {'u_miss':>7} {'u_hit':>7}")
    for N, child in zip([200, 700, 2000], ss.spawn(3)):
        a_h, m_h, k_eff = gather("hit", k, N, trials, child)
        a_m, m_m, _ = gather("miss", k, N, trials, child)
        for mode, N_used in [("n_aware", N), ("k_only", N_ref)]:
            op_h = opinion(a_h, m_h, k_eff, N_used, D)
            op_m = opinion(a_m, m_m, k_eff, N_used, D)
            r = {
                "N": N, "k": k_eff, "mode": mode,
                "auc": auc(op_m.u, op_h.u),
                "acc_at_theta": balanced_acc(op_h.u, op_m.u),
                "z_hit_mean": float(np.mean(op_h.z)),
                "z_miss_mean": float(np.mean(op_m.z)),
                "u_hit_mean": float(np.mean(op_h.u)),
                "u_miss_mean": float(np.mean(op_m.u)),
            }
            rows.append(r)
            z_miss_by_mode[mode].append(r["z_miss_mean"])
            print(f"{N:>6} {mode:>8} {r['auc']:>8.4f} {r['acc_at_theta']:>10.4f} "
                  f"{r['z_miss_mean']:>8.3f} {r['u_miss_mean']:>7.3f} {r['u_hit_mean']:>7.3f}")

    out = os.path.join(HERE, "drift_comparison.csv")
    with open(out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"[drift] wrote {out}")

    drift_aware = np.ptp(z_miss_by_mode["n_aware"])
    drift_konly = np.ptp(z_miss_by_mode["k_only"])
    print(f"[drift] miss-anchor drift across N (z units): "
          f"N-aware={drift_aware:.3f} vs k-only={drift_konly:.3f}")
    for r in rows:
        if r["mode"] == "n_aware":
            assert r["acc_at_theta"] >= 0.95, f"N-aware gate degraded at N={r['N']}"
    assert drift_aware < 0.6, "N-aware calibration drifted with N"
    assert drift_konly > 2 * drift_aware, "k-only gate did not show the expected drift"


# ------------------------------------------------ d. SATURATION ROUTING

def test_saturation_flag_fires_where_capacity_law_predicts():
    """Past the paging threshold the gate must flag saturation (expected
    mu_hit(k) within one null-sd of mu_null(N)) instead of emitting confident
    b. The flag boundary k_sat must sit where the capacity law puts it, and
    empirically: separability at a flagged load is materially worse than at
    any unflagged load at/below the paging threshold."""
    N = 500
    ks = k_sat(D, N)
    km = k_max(D, N)
    pt = paging_threshold(D, N)
    print(f"\n[saturation] N={N}: paging={pt:.0f} < k_sat={ks:.0f} < k_max={km:.0f}")
    assert pt < ks < km
    assert not is_saturated(int(ks) - 5, N, D) and is_saturated(int(ks) + 5, N, D)
    assert not is_saturated(200, N, D) and is_saturated(420, N, D)

    ss = np.random.SeedSequence(SEED + 3)
    aucs = {}
    for k, child in zip([200, 420], ss.spawn(2)):
        a_h, m_h, k_eff = gather("hit", k, N, 2, child)
        a_m, m_m, _ = gather("miss", k, N, 2, child)
        u_h = opinion(a_h, m_h, k_eff, N, D).u
        u_m = opinion(a_m, m_m, k_eff, N, D).u
        aucs[k] = auc(u_m, u_h)

        # controller: every query at a flagged load routes away from ANSWER
        sat = is_saturated(k_eff, N, D)
        ops = [opinion(a, m, k_eff, N, D) for a, m in zip(a_h[:50], m_h[:50])]
        actions = {route(op, saturated=sat) for op in ops}
        if sat:
            assert Action.ANSWER not in actions, "confident b emitted at saturation"
            assert actions == {Action.RECOLLECT}
        else:
            assert Action.ANSWER in actions

    print(f"[saturation] AUC(u) unflagged k=200: {aucs[200]:.4f}  "
          f"flagged k=420: {aucs[420]:.4f}")
    assert aucs[200] > aucs[420] + 0.05, "flag boundary not tracking separability loss"
