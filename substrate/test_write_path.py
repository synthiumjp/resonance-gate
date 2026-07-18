"""E3 Part 3 tests: echo-check pass rate, retraction suite, and the two
ambiguity routes through Memory.query. (Extraction precision, which needs
the mouth, lives in mouth/test_extraction.py.)"""

import numpy as np
import pytest

from entities import make_entities
from registry import Registry
from write_path import Memory, default_calibration

CANONICAL_RELATIONS = ["works at", "lives in", "was born in", "manages",
                       "reports to", "is married to", "is a sibling of",
                       "studied at", "is scheduled at"]
SEED = 909


@pytest.fixture(scope="module")
def calib():
    return default_calibration()


def fresh_memory(calib, entities=()):
    ent = Registry(list(entities))
    rel = Registry(CANONICAL_RELATIONS)
    return Memory(ent, rel, calib=calib)


def test_echo_check_pass_rate(calib):
    """E3 exit criterion: echo-check pass >= 99% over 100 writes."""
    pool = make_entities(220, SEED)
    mem = fresh_memory(calib, pool)
    rng = np.random.default_rng(SEED)
    accepted = 0
    for i in range(100):
        s, o = rng.choice(220, size=2, replace=False)
        r = CANONICAL_RELATIONS[int(rng.integers(len(CANONICAL_RELATIONS)))]
        accepted += mem.write(pool[s], r, pool[o]).accepted
    print(f"\n[echo] {accepted}/100 writes accepted (k={mem.k})")
    assert accepted >= 99


def test_retraction_deleted_stays_deleted(calib):
    pool = make_entities(60, SEED + 1)
    mem = fresh_memory(calib, pool)
    mem.write("Elena Ito", "lives in", pool[0])
    mem.write("Mark Lowe", "works at", pool[1])
    acc_before_c = mem.acc.copy()
    mem.write("Nina Vogel", "studied at", pool[2])
    assert mem.k == 3
    assert mem.forget("Nina Vogel", "studied at", pool[2])
    # subtracted bundle is BIT-EXACT: crosstalk of the remaining k=2 matches
    # a memory that never saw the record
    assert np.array_equal(mem.acc, acc_before_c)
    assert mem.k == 2
    q = mem.query("Nina Vogel", "studied at")
    print(f"\n[retract] post-forget query: action={q.action} u={q.op.u:.3f}")
    assert q.action in ("abstain", "recollect") and q.op.u > 0.5


def test_supersede_resolves_to_successor(calib):
    pool = make_entities(60, SEED + 2)
    mem = fresh_memory(calib, pool)
    mem.write("Elizabeth Carter", "lives in", "Geneva")
    mem.write("Peter Yang", "works at", pool[3])
    res = mem.supersede("Elizabeth Carter", "lives in", "Geneva", "Vienna")
    assert res.accepted and mem.k == 2
    q = mem.query("Elizabeth Carter", "lives in")
    print(f"\n[supersede] action={q.action} record={q.record}")
    assert q.action == "answer" and q.record[2] == "Vienna"


def test_stored_collision_routes_deliberate_stored(calib):
    pool = make_entities(60, SEED + 3)
    mem = fresh_memory(calib, pool)
    mem.write("Chris Wong", "works at", pool[4])
    mem.write("Chris Wong", "works at", pool[5])
    mem.write("Julia Quinn", "lives in", pool[6])
    q = mem.query("Chris Wong", "works at")
    print(f"\n[stored-d] action={q.action} tag={q.tag} m_l2={q.m_l2:.4f}")
    assert (q.action, q.tag) == ("deliberate", "stored")
    assert {t[0][2] for t in q.candidates} == {pool[4], pool[5]}


def test_two_toms_routes_deliberate_referential(calib):
    pool = make_entities(60, SEED + 4)
    mem = fresh_memory(calib, pool)
    mem.write("Tom (brother)", "works at", pool[7])
    mem.write("Tom (colleague)", "works at", pool[8])
    q = mem.query("Tom", "works at")
    print(f"\n[ref-d] action={q.action} tag={q.tag} m_ref={q.m_ref:.4f} "
          f"candidates={q.candidates}")
    assert (q.action, q.tag) == ("deliberate", "referential")
    assert set(q.candidates) == {"Tom (brother)", "Tom (colleague)"}
    # a SPECIFIC query still answers
    q2 = mem.query("Tom (brother)", "works at")
    assert q2.action == "answer" and q2.record[2] == pool[7]
