"""Supersession must resolve changing attributes without discarding knowledge."""
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import currency as C  # noqa: E402


def _job(v, s):
    return {"attr": "occupation", "value": v, "session": s}


def test_latest_value_wins_for_single_valued_attributes():
    facts = [_job("senior data scientist", 1), _job("lead data analyst", 3),
             _job("chief visionary officer", 56)]
    cur = C.current(facts)
    assert [f["value"] for f in cur] == ["chief visionary officer"]


def test_history_is_kept_not_deleted():
    """"Where did I work before?" is the same data read the other way. A
    memory that drops superseded values cannot answer it."""
    facts = [_job("senior data scientist", 1), _job("lead data analyst", 3),
             _job("chief visionary officer", 56)]
    hist = C.history(facts, "occupation")
    assert [v for v, _, _ in hist] == ["senior data scientist",
                                       "lead data analyst",
                                       "chief visionary officer"]
    assert [c for _, _, c in hist] == [False, False, True]
    assert all(f.get("superseded_by") is not None
               for f in C.resolve(facts) if not f["current"])


def test_restating_is_distinguished_from_superseding():
    """They mean opposite things about confidence: a repeat is corroboration,
    a change is revision. Collapsing them would make a fact look revised every
    time the user mentioned it again."""
    facts = [_job("freelancer", 29), _job("freelancer", 31), _job("founder", 39)]
    r = C.resolve(facts)
    assert r[0]["restated_by"] == 1 and r[0]["superseded_by"] is None
    assert r[1]["superseded_by"] == 2 and r[1]["restated_by"] is None


def test_multi_valued_attributes_all_survive():
    """The dangerous failure: applying 'latest wins' to hobbies would leave a
    person with exactly one hobby. Over-eager supersession loses data; a
    missed one only leaves clutter, so the default must be to accumulate."""
    facts = [{"attr": "hobby", "value": "puzzle games"},
             {"attr": "hobby", "value": "strategy games"},
             {"attr": "belief", "value": "data predicts behaviour"},
             {"attr": "belief", "value": "collaboration matters"}]
    assert len(C.current(facts)) == 4


def test_repeating_the_same_value_is_not_a_change():
    facts = [_job("freelancer", 29), _job("Freelancer", 31), _job("freelancer", 33)]
    cur = C.current(facts)
    assert len(cur) == 1 and cur[0]["session"] == 33


def test_subjects_are_scoped_independently():
    """Michelle changing jobs must not supersede her mentor's job."""
    facts = [{"attr": "occupation", "value": "data scientist"},
             {"attr": "sophia:occupation", "value": "mentor"},
             {"attr": "occupation", "value": "founder"}]
    cur = C.current(facts)
    vals = sorted(f["value"] for f in cur)
    assert vals == ["founder", "mentor"]


def test_history_is_scoped_to_one_subject():
    """Without scoping, a mentor's job lands in the owner's career timeline --
    which is exactly how the first version read."""
    facts = [{"attr": "occupation", "value": "data scientist", "session": 1},
             {"attr": "sophia:occupation", "value": "mentor", "session": 5},
             {"attr": "occupation", "value": "founder", "session": 39}]
    owner = C.history(facts, "occupation")
    assert [v for v, _, _ in owner] == ["data scientist", "founder"]
    assert C.history(facts, "occupation", subject="sophia") == [
        ("mentor", 5, True)]


def test_non_person_subjects_are_identifiable():
    for bad in ("Ai", "Team", "friends", "Colleagues"):
        assert C.is_non_person_subject(bad), bad
    for ok in ("Michelle Hernandez", "Sophia", "Alex Johnson"):
        assert not C.is_non_person_subject(ok), ok


def test_empty_and_single_inputs():
    assert C.current([]) == []
    one = C.current([_job("analyst", 1)])
    assert len(one) == 1 and one[0]["current"]
