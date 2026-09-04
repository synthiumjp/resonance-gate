"""Unit tests for Chomsky Binding Theory as a coreference-link veto.
Examples are the canonical textbook cases."""

from binding import violates_binding
from _fixtures import (
    condition_b_same_clause,
    cross_sentence_pronoun,
    reflexive_cross_clause,
    reflexive_same_clause,
)


def test_condition_a_satisfied_not_vetoed():
    herself, rachel = reflexive_same_clause()
    assert violates_binding(herself, rachel) is False


def test_condition_a_violated_cross_clause_vetoed():
    himself, tom, rachel = reflexive_cross_clause()
    assert violates_binding(himself, rachel) is True    # wrong clause -> veto
    assert violates_binding(himself, tom) is False        # right clause -> allowed


def test_condition_b_same_clause_vetoed():
    her, rachel = condition_b_same_clause()
    assert violates_binding(her, rachel) is True


def test_cross_sentence_pronoun_not_vetoed():
    """Binding theory only governs same-clause structure -- it must not
    fire across a sentence boundary, or it would block the dominant
    real-world case (a pronoun resolved in a later turn)."""
    she, rachel = cross_sentence_pronoun()
    assert violates_binding(she, rachel) is False
