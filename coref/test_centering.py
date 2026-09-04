"""Unit tests for the Centering Theory salience tracker: Cf ranking,
Cb/transition computation, and the rank_of() query the coref gate uses."""

from centering import CenteringState, Transition


def test_rank_prefers_subject_over_other_roles():
    st = CenteringState()
    st.update([("Rachel", "nsubj"), ("friend", "attr")])
    assert st.rank_of("Rachel") == 0
    assert st.rank_of("friend") == 1


def test_unmentioned_entity_ranks_past_the_list():
    st = CenteringState()
    st.update([("Rachel", "nsubj")])
    assert st.rank_of("Tom") == 2   # len(cf) + 1


def test_first_turn_transition_is_undefined():
    st = CenteringState()
    t = st.update([("Rachel", "nsubj")])
    assert t is None
    assert st.cb == "Rachel"


def test_continue_transition_when_topic_stays_top_of_cf():
    st = CenteringState()
    st.update([("Rachel", "nsubj")])
    t = st.update([("Rachel", "nsubj"), ("Chicago", "obl")])
    assert t is Transition.CONTINUE
    assert st.cb == "Rachel"


def test_retain_transition_when_topic_persists_but_not_topmost():
    st = CenteringState()
    st.update([("Rachel", "nsubj"), ("Tom", "dobj")])       # cb -> Rachel
    t = st.update([("Tom", "nsubj"), ("Rachel", "dobj")])   # Rachel still
    assert t is Transition.RETAIN                            # mentioned, but
    assert st.cb == "Rachel"                                  # no longer topmost


def test_shift_transition_when_topic_drops_out():
    st = CenteringState()
    st.update([("Rachel", "nsubj")])                          # cb -> Rachel
    st.update([("Rachel", "nsubj"), ("Tom", "dobj")])         # still cb -> Rachel (CONTINUE)
    t = st.update([("Tom", "nsubj")])                          # Rachel drops out
    assert t is Transition.SHIFT
    assert st.cb == "Tom"
