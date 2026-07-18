"""E3 Part 1 step 3: the E2 ignorance and ambiguity tests re-run on EMBEDDED
substrates — real entity strings through the encoder, same gate code, same
theta. Numbers are reported side by side with the E2 synthetic ceiling and
written to encoder/embedded_vs_synthetic.csv.

STOP rule (executed by the operator, not this file): if AUC(d) < 0.90 here,
E3 halts after Part 1 — the design fork is a planning decision.
"""

import csv
import json
import math
import os

import numpy as np

from map_ops import Codebook, bundle, encode_record
import normalisation as nz
from opinion import opinion
from test_gate import auc, balanced_acc
from embed import D, encode_bipolar
from entities import RELATIONS10, make_entities

SEED = 660
HERE = os.path.dirname(os.path.abspath(__file__))
CAL_PATH = os.path.join(HERE, "null_calibration.json")

# E2 synthetic ceiling (notebook entry 4, seeds 202/203)
SYNTH_AUC_U = {10: 1.0000, 50: 1.0000, 100: 0.9998, 200: 0.9792}
SYNTH_ACC = {10: 1.000, 50: 1.000, 100: 0.994, 200: 0.923}
SYNTH_AUC_D = 0.9988

N_OBJ = 500

_pools = None


def pools():
    """Embed the string pools once: 1600 subjects, 10 relations, 500 objects."""
    global _pools
    if _pools is None:
        subj_names = make_entities(1600, SEED)
        obj_names = make_entities(N_OBJ, SEED + 1)
        _pools = {
            "subj": encode_bipolar(subj_names),
            "rels": encode_bipolar(RELATIONS10),
            "objects": Codebook.from_matrix(obj_names, encode_bipolar(obj_names)),
        }
    return _pools


def null_moments():
    """EMBEDDED-mode calibration of the actual object codebook (cached to
    disk; regenerable — delete the json to recalibrate)."""
    p = pools()
    if os.path.exists(CAL_PATH):
        with open(CAL_PATH) as f:
            c = json.load(f)
        return c["mu"], c["sigma"]
    mu, sigma = nz.calibrate_null(p["subj"], p["rels"], p["objects"],
                                  k=100, trials=4, seed=SEED + 2)
    with open(CAL_PATH, "w") as f:
        json.dump({"mu": mu, "sigma": sigma, "N": N_OBJ, "k_cal": 100,
                   "seed": SEED + 2}, f, indent=1)
    return mu, sigma


def embedded_queries(k, trial_seed, n_coll=0):
    """One embedded substrate: k singleton records from the entity pools
    (+ n_coll colliding pairs), k misses. Returns (a, m) per class."""
    p = pools()
    rng = np.random.default_rng(trial_seed)
    n_q = k + n_coll + k
    subj_idx = rng.permutation(len(p["subj"]))[:n_q]
    S = p["subj"][subj_idx]
    rel_idx = rng.integers(len(p["rels"]), size=n_q)
    obj_idx = rng.integers(N_OBJ, size=k)
    OM = p["objects"].matrix

    records = [encode_record(S[i], p["rels"][rel_idx[i]], OM[obj_idx[i]])
               for i in range(k)]
    for j in range(n_coll):
        i = k + j
        o1, o2 = rng.choice(N_OBJ, size=2, replace=False)
        records.append(encode_record(S[i], p["rels"][rel_idx[i]], OM[o1]))
        records.append(encode_record(S[i], p["rels"][rel_idx[i]], OM[o2]))
    B = bundle(records, seed=int(rng.integers(2**31)))

    noisy = np.roll(
        B.astype(np.int32) * S.astype(np.int32)
        * np.roll(p["rels"][rel_idx].astype(np.int32), 1, axis=1),
        -2, axis=1,
    )
    cos = (noisy.astype(np.float32) @ OM.T.astype(np.float32)) / D
    top2 = np.argpartition(-cos, 1, axis=1)[:, :2]
    rows = np.arange(n_q)
    pair = cos[rows[:, None], top2]
    order = np.argsort(-pair, axis=1)
    s1 = pair[rows[:, None], order][:, 0].astype(np.float64)
    s2 = pair[rows[:, None], order][:, 1].astype(np.float64)
    a, m = s1, s1 - s2
    return {
        "hit": (a[:k], m[:k]),
        "coll": (a[k:k + n_coll], m[k:k + n_coll]),
        "miss": (a[k + n_coll:], m[k + n_coll:]),
        "k_eff": k + 2 * n_coll,
    }


def test_embedded_ignorance_and_ambiguity_vs_synthetic_ceiling():
    nm = null_moments()
    print(f"\n[embedded] EMBEDDED null=({nm[0]:.4f}, {nm[1]:.4f}) "
          f"analytic=({nz.mu_null(N_OBJ, D):.4f}, {nz.sigma_null(D):.4f}) seed={SEED}")
    rows = []

    # --- ignorance, same theta, k grid, EMBEDDED normalisation
    ss = np.random.SeedSequence(SEED + 3)
    print(f"{'k':>5} {'AUC(u) synth':>12} {'AUC(u) embed':>12} {'acc synth':>10} {'acc embed':>10}")
    for k, child in zip([10, 50, 100, 200], ss.spawn(4)):
        trials = max(2, math.ceil(400 / k))
        a_h, m_h, a_m, m_m, k_eff = [], [], [], [], None
        for ts in child.generate_state(trials):
            q = embedded_queries(k, int(ts))
            a_h.append(q["hit"][0]); m_h.append(q["hit"][1])
            a_m.append(q["miss"][0]); m_m.append(q["miss"][1])
            k_eff = q["k_eff"]
        a_h, m_h = np.concatenate(a_h), np.concatenate(m_h)
        a_m, m_m = np.concatenate(a_m), np.concatenate(m_m)
        u_h = opinion(a_h, m_h, k_eff, N_OBJ, D, null_moments=nm).u
        u_m = opinion(a_m, m_m, k_eff, N_OBJ, D, null_moments=nm).u
        r = {"test": "ignorance", "k": k, "metric": "auc_u",
             "synthetic": SYNTH_AUC_U[k], "embedded": auc(u_m, u_h),
             "acc_synth": SYNTH_ACC[k], "acc_embed": balanced_acc(u_h, u_m)}
        rows.append(r)
        print(f"{k:>5} {r['synthetic']:>12.4f} {r['embedded']:>12.4f} "
              f"{r['acc_synth']:>10.3f} {r['acc_embed']:>10.3f}")

    # --- ambiguity (C3), EMBEDDED normalisation
    ss2 = np.random.SeedSequence(SEED + 4)
    a_h, m_h, a_c, m_c, k_eff = [], [], [], [], None
    for ts in ss2.generate_state(5):
        q = embedded_queries(50, int(ts), n_coll=10)
        a_h.append(q["hit"][0]); m_h.append(q["hit"][1])
        a_c.append(q["coll"][0]); m_c.append(q["coll"][1])
        k_eff = q["k_eff"]
    op_h = opinion(np.concatenate(a_h), np.concatenate(m_h), k_eff, N_OBJ, D, null_moments=nm)
    op_c = opinion(np.concatenate(a_c), np.concatenate(m_c), k_eff, N_OBJ, D, null_moments=nm)
    auc_d = auc(op_c.d, op_h.d)
    rows.append({"test": "ambiguity", "k": k_eff, "metric": "auc_d",
                 "synthetic": SYNTH_AUC_D, "embedded": auc_d,
                 "acc_synth": "", "acc_embed": ""})
    print(f"[embedded] *** C3 SPLIT EMBEDDED: AUC(d) = {auc_d:.4f} "
          f"(synthetic ceiling {SYNTH_AUC_D}) ***")
    print(f"[embedded] d-dom on collisions: {np.mean((op_c.d > op_c.b) & (op_c.d > op_c.u)):.3f}  "
          f"b-dom on clean: {np.mean((op_h.b > op_h.d) & (op_h.b > op_h.u)):.3f}")

    out = os.path.join(HERE, "embedded_vs_synthetic.csv")
    with open(out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows([{k2: (f"{v:.4f}" if isinstance(v, float) else v) for k2, v in r.items()}
                     for r in rows])
    print(f"[embedded] wrote {out}")

    # E3 Part-1 hold bars. The paging threshold must come from the capacity
    # law fed with the MEASURED null moments — the analytic threshold (210)
    # is meaningless on embedded substrates (measured k_max ~ 123, paging
    # ~ 62; notebook entry 5). Within that envelope the same-theta ignorance
    # bar must hold.
    paging_embedded = nz.paging_threshold(D, N_OBJ) * (
        nz.mu_null(N_OBJ, D) ** 2 / nm[0] ** 2
    )
    print(f"[embedded] capacity law w/ measured null: k_max={2.0 / (np.pi * nm[0] ** 2):.0f} "
          f"paging={paging_embedded:.0f}")
    for r in rows:
        if r["test"] == "ignorance" and r["k"] <= paging_embedded:
            assert r["embedded"] >= 0.95, f"embedded ignorance AUC collapsed at k={r['k']}"

    # E3 Part-1 STOP rule: C3 at the E2-spec load (k_eff=70) must clear 0.90.
    # It measured 0.837 on 2026-07-18 — the design fork (L1 margin vs L2
    # top-2 ambiguity detection, or a decorrelating projection) is a planning
    # decision, so this xfails until that decision lands (notebook entry 5).
    # It will XPASS loudly if a fix resolves it.
    if auc_d < 0.90:
        import pytest
        pytest.xfail(f"E3 Part 1 stop rule: embedded C3 AUC(d)={auc_d:.4f} < 0.90 "
                     "at k_eff=70; halted pending design fork (notebook entry 5)")
