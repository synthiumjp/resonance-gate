"""Unit tests for the v0 fixed-threshold controller: one per routing branch."""

from controller import U_IGNORANT, U_WEAK, Action, route
from opinion import Opinion


def op(b, d, u):
    return Opinion(b=b, d=d, u=u, z=0.0, m_z=0.0)


def test_saturated_routes_recollect():
    assert route(op(0.9, 0.05, 0.05), saturated=True) is Action.RECOLLECT


def test_saturated_without_l2_abstains():
    assert route(op(0.9, 0.05, 0.05), saturated=True, l2_available=False) is Action.ABSTAIN


def test_confident_ignorance_abstains():
    assert route(op(0.05, 0.05, 0.9), saturated=False) is Action.ABSTAIN
    assert route(op(0.1, 0.05, U_IGNORANT), saturated=False) is Action.ABSTAIN


def test_weak_resolution_recollects_with_l2():
    assert route(op(0.3, 0.2, 0.5), saturated=False) is Action.RECOLLECT
    assert route(op(0.4, 0.25, U_WEAK), saturated=False) is Action.RECOLLECT


def test_weak_resolution_abstains_without_l2():
    assert route(op(0.3, 0.2, 0.5), saturated=False, l2_available=False) is Action.ABSTAIN


def test_ambiguity_deliberates():
    assert route(op(0.3, 0.6, 0.1), saturated=False) is Action.DELIBERATE


def test_clean_belief_answers():
    assert route(op(0.85, 0.05, 0.1), saturated=False) is Action.ANSWER
