"""Unit tests for the E3.2 two-source opinion and tagged controller routing."""

import numpy as np

from controller import Action, route_tagged
from opinion import opinion_two_source

# a comfortable hit at k=20, N=500 under analytic moments
HIT_A = 0.30
MISS_A = 0.03
K, N = 20, 500


def test_referential_dominates_and_tags():
    op = opinion_two_source(HIT_A, K, N, m_ref=0.01, m_l2=0.8)
    assert op.tag == "referential" and op.d > op.b and op.u < 0.2
    action, tag = route_tagged(op, saturated=False)
    assert action is Action.DELIBERATE and tag == "referential"


def test_stored_dominates_and_tags():
    op = opinion_two_source(HIT_A, K, N, m_ref=0.45, m_l2=0.0)
    assert op.tag == "stored" and op.d > op.b
    action, tag = route_tagged(op, saturated=False)
    assert action is Action.DELIBERATE and tag == "stored"


def test_both_margins_clean_answers_untagged():
    op = opinion_two_source(HIT_A, K, N, m_ref=0.45, m_l2=0.8)
    assert op.b > op.d and op.u < 0.2
    action, tag = route_tagged(op, saturated=False)
    assert action is Action.ANSWER and tag is None


def test_ignorance_beats_ambiguity():
    op = opinion_two_source(MISS_A, K, N, m_ref=0.01, m_l2=0.0)
    assert op.u > 0.85
    action, tag = route_tagged(op, saturated=False)
    assert action is Action.ABSTAIN and tag is None


def test_l1_hint_fallback_when_no_sources():
    op = opinion_two_source(HIT_A, K, N, m_l1=0.005)
    assert op.tag == "l1-hint" and op.d > op.b


def test_saturation_overrides_with_no_tag():
    op = opinion_two_source(HIT_A, K, N, m_ref=0.01)
    action, tag = route_tagged(op, saturated=True)
    assert action is Action.RECOLLECT and tag is None


def test_bdu_sums_to_one():
    for kw in [dict(m_ref=0.1), dict(m_l2=0.3), dict(m_ref=0.4, m_l2=0.0), dict()]:
        op = opinion_two_source(HIT_A, K, N, **kw)
        assert abs(op.b + op.d + op.u - 1.0) < 1e-12
