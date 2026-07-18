"""Tests for the E1 MAP substrate. All randomness seeded (printed where relevant)."""

import numpy as np
import pytest

from map_ops import (
    Codebook,
    bind,
    bundle,
    encode_record,
    permute,
    unbind_obj,
    unbind_rel,
    unbind_subj,
)

SEED = 42
D = 8192


def _rand_bipolar(rng, dim=D):
    return (rng.integers(0, 2, size=dim, dtype=np.int8) * 2 - 1).astype(np.int8)


def test_bind_self_inverse():
    rng = np.random.default_rng(SEED)
    a, b = _rand_bipolar(rng), _rand_bipolar(rng)
    assert np.array_equal(bind(bind(a, b), b), a)
    assert np.array_equal(bind(bind(a, b), a), b)


def test_permute_inverse():
    rng = np.random.default_rng(SEED)
    v = _rand_bipolar(rng)
    for k in (1, 2, 17, D - 1):
        assert np.array_equal(permute(permute(v, k), -k), v)


def test_bundle_deterministic_under_fixed_seed():
    rng = np.random.default_rng(SEED)
    # even count guarantees zero ties exist, exercising the seeded coin
    vecs = [_rand_bipolar(rng) for _ in range(4)]
    s = np.sum(np.stack(vecs).astype(np.int64), axis=0)
    assert (s == 0).any(), "test needs ties to exercise the tie-break"
    b1 = bundle(vecs, seed=7)
    b2 = bundle(vecs, seed=7)
    assert np.array_equal(b1, b2)
    assert set(np.unique(b1)) <= {-1, 1}
    b3 = bundle(vecs, seed=8)
    assert not np.array_equal(b1, b3), "different seed should break ties differently"


def test_single_record_round_trip_all_roles():
    subjects = Codebook([f"s{i}" for i in range(20)], dim=D, seed=1)
    relations = Codebook([f"r{i}" for i in range(20)], dim=D, seed=2)
    objects = Codebook([f"o{i}" for i in range(20)], dim=D, seed=3)

    R = encode_record(subjects["s3"], relations["r5"], objects["o7"])

    for noisy, book, expect in [
        (unbind_obj(R, subjects["s3"], relations["r5"]), objects, "o7"),
        (unbind_subj(R, relations["r5"], objects["o7"]), subjects, "s3"),
        (unbind_rel(R, subjects["s3"], objects["o7"]), relations, "r5"),
    ]:
        (name, cos), _ = book.cleanup(noisy)
        assert name == expect
        assert cos == pytest.approx(1.0)  # single record: exact recovery


def test_e1_exit_round_trip_50_triples():
    """E1 exit criterion 1: 50 triples in one bundle at D=8192, object retrieval
    by (subj, rel) with cleanup accuracy >= 0.99. Relation pool 10, object pool 200."""
    n, seed = 50, SEED
    print(f"\n[E1 round-trip] seed={seed} D={D} n_triples={n} rel_pool=10 obj_pool=200")
    subjects = Codebook([f"s{i}" for i in range(n)], dim=D, seed=seed)
    relations = Codebook([f"r{i}" for i in range(10)], dim=D, seed=seed + 1)
    objects = Codebook([f"o{i}" for i in range(200)], dim=D, seed=seed + 2)

    rng = np.random.default_rng(seed + 3)
    triples = [
        (f"s{i}", f"r{rng.integers(10)}", f"o{rng.integers(200)}") for i in range(n)
    ]
    B = bundle(
        [encode_record(subjects[s], relations[r], objects[o]) for s, r, o in triples],
        seed=seed + 4,
    )

    hits, a_vals, m_vals = 0, [], []
    for s, r, o in triples:
        (name, s1), (_, s2) = objects.cleanup(unbind_obj(B, subjects[s], relations[r]))
        hits += name == o
        a_vals.append(s1)
        m_vals.append(s1 - s2)

    acc = hits / n
    print(
        f"[E1 round-trip] accuracy={acc:.3f}  "
        f"a mean={np.mean(a_vals):.4f} min={np.min(a_vals):.4f}  "
        f"m mean={np.mean(m_vals):.4f} min={np.min(m_vals):.4f}"
    )
    assert acc >= 0.99
