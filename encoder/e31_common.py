"""Shared machinery for the E3.1 fork-decision measurements.

Everything here is measurement plumbing behind standalone scripts — no
default gate behaviour changes. Embeddings are disk-cached (one MiniLM pass
per unique string, ever), so the D=8192 arm, the D=16384 arm, and the
whitening sweep all reuse the same embedding pass.
"""

import json
import os
import numpy as np

from map_ops import Codebook, bundle, encode_record
from embed import EMBED_DIM, embed_strings, project_bipolar
from entities import RELATIONS10, make_entities

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE_PATH = os.path.join(HERE, ".emb_cache.npz")
POOL_SEED = 660  # matches the E3 Part-1 pools for comparability

_cache = None


def get_embeddings(strings):
    """Disk-cached MiniLM embeddings, row-aligned with `strings`."""
    global _cache
    if _cache is None:
        if os.path.exists(CACHE_PATH):
            z = np.load(CACHE_PATH, allow_pickle=False)
            _cache = dict(zip(json.loads(str(z["names"])), z["mat"]))
        else:
            _cache = {}
    missing = [s for s in dict.fromkeys(strings) if s not in _cache]
    if missing:
        for s, e in zip(missing, embed_strings(missing)):
            _cache[s] = e
        names = list(_cache.keys())
        np.savez_compressed(
            CACHE_PATH,
            names=json.dumps(names),
            mat=np.stack([_cache[n] for n in names]),
        )
    return np.stack([_cache[s] for s in strings])


def encode(strings, d, transform=None):
    """Strings -> bipolar via cache (+ optional embedding-space transform,
    e.g. the whitening blend)."""
    e = get_embeddings(strings)
    if transform is not None:
        e = transform(e)
    return project_bipolar(e, d)


class Pools:
    """The E3 entity pools (1600 subjects, 10 relations, 500 objects) encoded
    at dimension d with an optional embedding transform."""

    def __init__(self, d, transform=None, n_obj=500):
        self.d = d
        self.n_obj = n_obj
        self.subj_names = make_entities(1600, POOL_SEED)
        self.obj_names = make_entities(n_obj, POOL_SEED + 1)
        self.subj = encode(self.subj_names, d, transform)
        self.rels = encode(RELATIONS10, d, transform)
        self.objects = Codebook.from_matrix(self.obj_names, encode(self.obj_names, d, transform))


def build_substrate(p, k, trial_seed, n_coll=0):
    """One embedded substrate over pools p: k singleton records (+ n_coll
    colliding pairs), k miss queries. Returns per-class (a, m), k_eff, and
    the record list [(subj_row, rel_idx, obj_idx)] for L2-store measurements."""
    rng = np.random.default_rng(trial_seed)
    n_q = k + n_coll + k
    subj_idx = rng.permutation(len(p.subj))[:n_q]
    S = p.subj[subj_idx]
    rel_idx = rng.integers(len(p.rels), size=n_q)
    obj_idx = rng.integers(p.n_obj, size=k)
    OM = p.objects.matrix

    records = [(int(subj_idx[i]), int(rel_idx[i]), int(obj_idx[i])) for i in range(k)]
    for j in range(n_coll):
        i = k + j
        o1, o2 = rng.choice(p.n_obj, size=2, replace=False)
        records.append((int(subj_idx[i]), int(rel_idx[i]), int(o1)))
        records.append((int(subj_idx[i]), int(rel_idx[i]), int(o2)))
    B = bundle(
        [encode_record(p.subj[s], p.rels[r], OM[o]) for s, r, o in records],
        seed=int(rng.integers(2**31)),
    )

    noisy = np.roll(
        B.astype(np.int32) * S.astype(np.int32)
        * np.roll(p.rels[rel_idx].astype(np.int32), 1, axis=1),
        -2, axis=1,
    )
    cos = (noisy.astype(np.float32) @ OM.T.astype(np.float32)) / p.d
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
        "records": records,
        "query_subj_idx": subj_idx,
        "query_rel_idx": rel_idx,
    }


def gather_classes(p, k, trials, seed, n_coll=0):
    """Accumulate (a, m) per query class over fresh substrates."""
    ss = np.random.SeedSequence(seed)
    out = {"hit": ([], []), "coll": ([], []), "miss": ([], [])}
    k_eff = None
    for ts in ss.generate_state(trials):
        q = build_substrate(p, k, int(ts), n_coll=n_coll)
        for cls in out:
            out[cls][0].append(q[cls][0])
            out[cls][1].append(q[cls][1])
        k_eff = q["k_eff"]
    return {cls: (np.concatenate(v[0]), np.concatenate(v[1])) for cls, v in out.items()}, k_eff


def auc(pos, neg):
    """P(score_pos > score_neg), rank-based (ties get half credit)."""
    pos, neg = np.asarray(pos, dtype=np.float64), np.asarray(neg, dtype=np.float64)
    both = np.concatenate([pos, neg])
    order = both.argsort(kind="mergesort")
    ranks = np.empty(len(both))
    ranks[order] = np.arange(1, len(both) + 1)
    sv = both[order]
    i = 0
    while i < len(both):
        j = i
        while j + 1 < len(both) and sv[j + 1] == sv[i]:
            j += 1
        if j > i:
            ranks[order[i:j + 1]] = (i + j) / 2 + 1
        i = j + 1
    n_p, n_n = len(pos), len(neg)
    return (ranks[:n_p].sum() - n_p * (n_p + 1) / 2) / (n_p * n_n)


def balanced_acc(u_hit, u_miss, thr=0.5):
    return 0.5 * (np.mean(u_hit < thr) + np.mean(u_miss >= thr))


def calibrations(p, seed=771):
    """Null + hit calibrations for pools p (EMBEDDED full-measured mode)."""
    import normalisation as nz
    nm = nz.calibrate_null(p.subj, p.rels, p.objects, k=100, trials=4, seed=seed)
    hm = nz.calibrate_hit(p.subj, p.rels, p.objects, k_refs=(25, 50, 100),
                          trials=3, seed=seed + 1)
    return nm, hm
