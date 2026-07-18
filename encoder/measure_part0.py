"""E3.2 Part 0: verify the two-geometry decoupling (blocking).

  a. Registry generalization via resolve() vs the lambda=0 baseline
     (0.927/0.964) — bar: within 0.01.
  b. Substrate envelope at lambda in {0.5, 0.75, 1.0}, substrate-side only;
     choose lambda = smallest within noise of best.
  c. Referential ambiguity: AUC of m_ref separating underspecified from
     specific queries over >= 40 hand-built cases — bar: >= 0.90.
  d. End-to-end sanity at the chosen lambda: four routes correct.

Writes encoder/part0_verification.csv. Usage: python measure_part0.py [--seed 775]
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
from map_ops import bundle, encode_record
from opinion import opinion
from l2_ambiguity import L2Store
from e31_common import Pools, auc, balanced_acc, build_substrate, calibrations, get_embeddings
from entities import RELATIONS10, make_entities
from test_generalization import DEV_SET, PERSON_CODEBOOK
from whitening import blend_transform, load_or_fit_zca
import registry as registry_mod
from registry import Registry

D = 8192


def part_a():
    ent = Registry(PERSON_CODEBOOK)
    rel = Registry(RELATIONS10)
    per_fam = {}
    for q, correct, fam in DEV_SET:
        book = rel if fam == "relation" else ent
        top = book.resolve(q, top=2)
        r = per_fam.setdefault(fam, [0, 0, 0])
        r[0] += 1
        r[1] += top[0][0] in correct
        r[2] += (top[0][0] in correct) or (top[1][0] in correct)
    n = sum(v[0] for v in per_fam.values())
    top1 = sum(v[1] for v in per_fam.values()) / n
    top2 = sum(v[2] for v in per_fam.values()) / n
    print(f"[a] registry generalization: top1={top1:.3f} top2={top2:.3f} "
          f"(lambda=0 projected baseline: 0.927/0.964)")
    for fam, (nn, t1, t2) in per_fam.items():
        print(f"[a]   {fam:>8}: {t1 / nn:.3f}/{t2 / nn:.3f}")
    return top1, top2


def part_b(seed):
    print(f"\n[b] substrate envelope, substrate-side only (seed={seed})")
    print(f"{'lambda':>7} {'null_mu':>8} {'k_max':>6} {'paging':>7} "
          f"{'AUC@50':>7} {'AUC@100':>8} {'AUC@150':>8}")
    mu, W = load_or_fit_zca()
    results = {}
    for lam in [0.5, 0.75, 1.0]:
        p = Pools(D, transform=blend_transform(mu, W, lam))
        nm, hm = calibrations(p, seed=seed)
        kmax = 2.0 * hm[0] ** 2 / (np.pi * nm[0] ** 2)
        aucs = []
        ss = np.random.SeedSequence(seed + int(lam * 100))
        for k, child in zip([50, 100, 150], ss.spawn(3)):
            trials = max(3, math.ceil(300 / k))
            a_h, m_h, a_m, m_m, k_eff = [], [], [], [], None
            for ts in child.generate_state(trials):
                q = build_substrate(p, k, int(ts))
                a_h.append(q["hit"][0]); m_h.append(q["hit"][1])
                a_m.append(q["miss"][0]); m_m.append(q["miss"][1])
                k_eff = q["k_eff"]
            u_h = opinion(np.concatenate(a_h), np.concatenate(m_h), k_eff, p.n_obj, D,
                          null_moments=nm, hit_moments=hm).u
            u_m = opinion(np.concatenate(a_m), np.concatenate(m_m), k_eff, p.n_obj, D,
                          null_moments=nm, hit_moments=hm).u
            aucs.append(auc(u_m, u_h))
        results[lam] = {"null_mu": nm[0], "k_max": kmax, "paging": 0.5 * kmax,
                        "aucs": aucs, "nm": nm, "hm": hm}
        print(f"{lam:>7.2f} {nm[0]:>8.4f} {kmax:>6.0f} {0.5 * kmax:>7.0f} "
              f"{aucs[0]:>7.4f} {aucs[1]:>8.4f} {aucs[2]:>8.4f}")

    best = max(results, key=lambda l: (min(results[l]["aucs"]), results[l]["k_max"]))
    chosen = None
    for lam in sorted(results):  # smallest first: prefer less transformation
        r = results[lam]
        if (min(r["aucs"]) >= min(results[best]["aucs"]) - 0.005
                and r["k_max"] >= 0.9 * results[best]["k_max"]):
            chosen = lam
            break
    print(f"[b] chosen lambda = {chosen} (best raw = {best}; rule: smallest within "
          f"0.005 AUC and 10% k_max of best)")
    return chosen, results


def part_c():
    ent = Registry(PERSON_CODEBOOK)
    underspecified = ["Tom", "Anna", "James", "Maria", "David", "Sarah", "Michael",
                      "Emma", "John", "Sofia", "Robert", "Laura", "Daniel", "Alice",
                      "Peter", "Nina", "Julia", "Mark", "Elena", "Elizabeth",
                      "Liz", "Chris"]  # bare nicknames with >= 2 candidates count too
    specific = ["Tom Baker", "Tom (brother)", "Anna Chen", "Anna (cousin)",
                "James Fischer", "Maria Garcia", "David Hansen", "Sarah Kim",
                "Michael Meyer", "Emma Nguyen", "John Patel", "Sofia Rios",
                "Robert Schmidt", "Laura Silva", "Daniel Diaz", "Alice Wong",
                "Peter Yang", "Nina Vogel", "Julia Quinn", "Mark Lowe",
                "Elena Ito", "Elizabeth Carter", "Katherine Novak", "William Weber"]
    m_u = [ent.m_ref(q) for q in underspecified]
    m_s = [ent.m_ref(q) for q in specific]
    a = auc(m_s, m_u)
    print(f"\n[c] referential ambiguity ({len(m_u)} underspecified vs {len(m_s)} specific)")
    print(f"[c] m_ref: underspecified mean={np.mean(m_u):.4f} sd={np.std(m_u):.4f}; "
          f"specific mean={np.mean(m_s):.4f} sd={np.std(m_s):.4f}")
    print(f"[c] AUC(m_ref) = {a:.4f} (bar 0.90)")
    return a, float(np.mean(m_u)), float(np.mean(m_s)), float(np.std(m_u + m_s))


def part_d(lam, nm, hm, seed):
    """20 written facts through registry -> whitened substrate -> gate."""
    print(f"\n[d] end-to-end sanity at lambda={lam} (seed={seed})")
    rng = np.random.default_rng(seed)
    ent = Registry(PERSON_CODEBOOK, lam=lam)
    rel = Registry(RELATIONS10, lam=lam)
    obj_names = make_entities(120, 881)
    ent.add(obj_names)

    facts = [("Tom Baker", "works at", obj_names[0]),
             ("Tom Barker", "works at", obj_names[1]),  # two Toms, distinct facts
             ("Elizabeth Carter", "lives in", obj_names[2]),
             ("Sarah Kim", "manages", "Daniel Diaz"),
             ("Peter Yang", "studied at", obj_names[3]),
             ("Nina Vogel", "was born in", obj_names[4]),
             ("Mark Lowe", "reports to", "Julia Quinn"),
             ("Emma Nguyen", "is married to", "John Patel"),
             ("Laura Silva", "resides in", obj_names[5]),
             ("Alice Wong", "works at", obj_names[6]),
             ("Robert Schmidt", "works at", obj_names[7]),
             ("Maria Garcia", "lives in", obj_names[8]),
             ("David Hansen", "studied at", obj_names[9]),
             ("James Fischer", "manages", "Sofia Rios"),
             ("Katherine Novak", "reports to", "Alice Wong"),
             ("Elena Ito", "was born in", obj_names[10]),
             ("Julia Quinn", "lives in", obj_names[11]),
             # stored collision: same (subj, rel), two objects
             ("Chris Wong", "works at", obj_names[12]),
             ("Chris Wong", "works at", obj_names[13]),
             ("William Weber", "resides in", obj_names[14])]

    acc = np.zeros(D, dtype=np.int64)
    store = L2Store(D)
    for s, r, o in facts:
        rec = encode_record(ent.vector(s), rel.vector(r), ent.vector(o))
        acc += rec
        store.append(ent.vector(s), rel.vector(r), o)
    B = np.sign(acc).astype(np.int8)
    B[B == 0] = 1
    k, N = len(facts), len(ent)
    obj_matrix = ent.matrix().astype(np.float32)

    def gate_query(subj_name, rel_name):
        noisy = np.roll(B.astype(np.int32) * ent.vector(subj_name).astype(np.int32)
                        * np.roll(rel.vector(rel_name).astype(np.int32), 1), -2)
        cos = (obj_matrix @ noisy.astype(np.float32)) / D
        order = np.argsort(-cos)[:2]
        a_v, m_v = cos[order[0]], cos[order[0]] - cos[order[1]]
        op = opinion(float(a_v), float(m_v), k, N, D, null_moments=nm, hit_moments=hm)
        c1, c2, o1, o2 = store.top2_batch(ent.vector(subj_name)[None, :],
                                          rel.vector(rel_name)[None, :])
        return op, ent.names[order[0]], float(c1[0] - c2[0]), (o1[0], o2[0])

    ok = True
    # route 1: hits answer
    hit_ok = 0
    for s, r, o in [facts[2], facts[4], facts[8]]:
        op, top1, m_l2, _ = gate_query(s, r)
        hit_ok += (op.u < 0.35) and (top1 == o) and (m_l2 > 0.3)
    print(f"[d] hits: {hit_ok}/3 answered (u low, correct object, no stored collision)")
    ok &= hit_ok == 3
    # route 2: misses -> high u
    miss_ok = 0
    for s, r in [("Sofia Rios", "studied at"), ("Daniel Diaz", "lives in"),
                 ("Benjamin Lopez", "works at")]:
        op, _, _, _ = gate_query(s, r)
        miss_ok += op.u > 0.65
    print(f"[d] misses: {miss_ok}/3 flagged ignorant (u high)")
    ok &= miss_ok == 3
    # route 3: stored collision -> stored-d (m_l2 == 0)
    op, _, m_l2, objs = gate_query("Chris Wong", "works at")
    stored_ok = (m_l2 < 0.05) and set(objs) == {obj_names[12], obj_names[13]}
    print(f"[d] stored collision: m_l2={m_l2:.4f}, both objects surfaced: {stored_ok}")
    ok &= stored_ok
    # route 4: two-Toms -> referential-d
    mr_tom, mr_full = ent.m_ref("Tom"), ent.m_ref("Elizabeth Carter")
    ref_ok = mr_tom < 0.05 and mr_full > 0.10
    print(f"[d] referential: m_ref('Tom')={mr_tom:.4f} vs "
          f"m_ref('Elizabeth Carter')={mr_full:.4f}: {ref_ok}")
    ok &= ref_ok
    print(f"[d] all four routes correct: {ok}")
    return ok


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=775)
    args = ap.parse_args()

    top1, top2 = part_a()
    chosen, envelope = part_b(args.seed)
    ref_auc, m_u_mean, m_s_mean, m_sd = part_c()
    r = envelope[chosen]
    e2e_ok = part_d(chosen, r["nm"], r["hm"], args.seed + 50)

    rows = [
        {"measure": "a_registry_gen_top1", "value": f"{top1:.4f}", "bar": ">=0.917"},
        {"measure": "a_registry_gen_top2", "value": f"{top2:.4f}", "bar": ">=0.954"},
        {"measure": "b_chosen_lambda", "value": f"{chosen}", "bar": "envelope-only"},
        {"measure": "b_k_max_chosen", "value": f"{r['k_max']:.0f}", "bar": ""},
        {"measure": "b_paging_chosen", "value": f"{r['paging']:.0f}", "bar": ""},
        {"measure": "b_ign_auc_50_100_150",
         "value": "/".join(f"{x:.4f}" for x in r["aucs"]), "bar": ""},
        {"measure": "c_referential_auc", "value": f"{ref_auc:.4f}", "bar": ">=0.90"},
        {"measure": "d_e2e_four_routes", "value": str(e2e_ok), "bar": "all true"},
    ]
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "part0_verification.csv")
    with open(out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["measure", "value", "bar"])
        w.writeheader()
        w.writerows(rows)
    print(f"\nwrote {out}")
    stop = (top1 < 0.917) or (top2 < 0.954) or (ref_auc < 0.90)
    print("PART 0 VERDICT:", "STOP — bar failed" if stop else "PASS — proceed")


if __name__ == "__main__":
    main()
