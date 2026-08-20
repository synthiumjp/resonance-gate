"""The UD extractor must hold the invariants the spaCy one had to be taught.

Ported because spaCy scores 61.45% LAS on conversational data against Stanza's
85.19% (CAIT, arXiv:2605.19718). These tests pin the behaviours that cost real
bugs in the spaCy version -- above all that a negated fact is never stored as
its opposite.
"""
import os
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

stanza = pytest.importorskip("stanza")
import grammar_ud as U  # noqa: E402

OWNER = "Martin Mark"


@pytest.fixture(scope="module")
def nlp():
    return stanza.Pipeline("en", processors="tokenize,pos,lemma,depparse",
                           use_gpu=False, verbose=False)


def props(t, nlp, role="user"):
    return [p for p, _ in U.extract(t, nlp, OWNER, role=role)]


@pytest.mark.parametrize("text,banned", [
    ("I don't like boxing.", "likes boxing"),
    ("I do not enjoy skydiving.", "enjoys skydiving"),
])
def test_negation_never_inverts(text, banned, nlp):
    """UD marks negation as `advmod` by LEMMA, not with a `neg` label. The
    spaCy version keyed on the label and inverted every negated fact."""
    out = " | ".join(props(text, nlp))
    assert banned not in out, out
    assert "not" in out, out


def test_positive_unchanged(nlp):
    assert any("likes boxing" in p for p in props("I like boxing.", nlp))


def test_comma_splice_yields_two_clean_clauses(nlp):
    """UD labels a splice `parataxis`, so it needs no special handling -- the
    spaCy version absorbed it as a `ccomp` and duplicated one clause into the
    other."""
    out = props("I dislike violent video games, I avoid violent video games.", nlp)
    assert any("dislikes violent video games" in p for p in out), out
    assert any("avoids violent video games" in p for p in out), out
    assert not any(p.count("violent video games") > 1 for p in out), out


def test_relationship_survives_a_colon_list(nlp):
    """The colon made spaCy's copula the ROOT and hid the relation."""
    out = props("I have friends and colleagues: ThomasSusan is my Friend, "
                "Susan's support inspires me.", nlp)
    assert any("Friend ThomasSusan" in p for p in out), out


def test_coordinated_subject_does_not_break_the_relation(nlp):
    """In spaCy, coordinating the subject flipped `Friend` from attr to nmod
    and the rule stopped firing. UD makes the predicate the head either way."""
    out = props("ThomasSusan is my Friend, Susan's support and encouragement "
                "inspire me.", nlp)
    assert any("Friend ThomasSusan" in p for p in out), out


def test_passive_with_possessed_subject(nlp):
    out = props("Your motivation is driven by your desire.", nlp, role="assistant")
    assert any("motivation" in p and "desire" in p for p in out), out


def test_second_person_only_for_assistant_turns(nlp):
    t = "You have been reflecting on your career."
    assert props(t, nlp, role="user") == []
    assert any(OWNER in p for p in props(t, nlp, role="assistant"))


def test_no_first_person_residue(nlp):
    for p in props("I work at Acme and I live in Columbus.", nlp):
        assert not any(w in p.split() for w in ("I", "my", "me")), p


def test_auxiliary_and_negation_stay_out_of_the_tail(nlp):
    """Including `aux`/`cop` in the argument list put the auxiliary and the
    negation into the object as well: "does not like do n't boxing"."""
    for p in props("I don't like boxing.", nlp):
        assert "n't" not in p and " do " not in p, p
