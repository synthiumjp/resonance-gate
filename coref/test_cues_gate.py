"""Unit tests for the coref decision gate: a binding veto beats a high
model score and top salience outright; below that, model confidence and
centering salience jointly decide CONFIDENT vs. POSSIBLE."""

from centering import CenteringState
from cues_gate import Decision, gate_pronoun_link
from _fixtures import condition_b_same_clause, cross_sentence_pronoun


def _salient_state(name):
    st = CenteringState()
    st.update([(name, "nsubj")])
    return st


def test_binding_veto_overrides_high_model_score_and_top_salience():
    her, rachel = condition_b_same_clause()
    st = _salient_state("Rachel")
    decision, reason = gate_pronoun_link(
        her, rachel, "Rachel", model_score=0.99, centering=st)
    assert decision is Decision.REJECTED
    assert reason == "binding-theory-veto"


def test_low_model_score_rejected():
    she, rachel = cross_sentence_pronoun()
    st = _salient_state("Rachel")
    decision, _ = gate_pronoun_link(
        she, rachel, "Rachel", model_score=0.2, centering=st)
    assert decision is Decision.REJECTED


def test_top_salience_and_good_score_confident():
    she, rachel = cross_sentence_pronoun()
    st = _salient_state("Rachel")
    decision, _ = gate_pronoun_link(
        she, rachel, "Rachel", model_score=0.8, centering=st)
    assert decision is Decision.CONFIDENT


def test_low_salience_demotes_to_possible():
    she, rachel = cross_sentence_pronoun()
    st = CenteringState()
    st.update([("Tom", "nsubj"), ("Rachel", "dobj")])   # Rachel present, rank 1
    decision, _ = gate_pronoun_link(
        she, rachel, "Rachel", model_score=0.8, centering=st,
        max_salience_rank=0)
    assert decision is Decision.POSSIBLE
