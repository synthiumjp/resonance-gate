"""The parser must never invert a fact.

Negation was dropped for the whole life of this file: spaCy gives "n't"/"not"/
"never" the dep `neg`, not `aux`, so the auxiliary-chain code collected the
auxiliary and discarded the negation. Every negated statement became its
opposite -- "I don't like boxing" was stored as "Martin Mark does like
boxing".

It was invisible to every metric we had: the inverted sentence shares every
content token with the true one, so token-overlap coverage scores it
identically, and the official judge only sees it if that particular gold point
happens to be scored. It surfaced by reading judged misses.
"""
import os
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

spacy = pytest.importorskip("spacy")
import grammar_parse as G  # noqa: E402

OWNER = "Martin Mark"


@pytest.fixture(scope="module")
def nlp():
    return spacy.load("en_core_web_sm")


def props(text, nlp, role="user"):
    return [p for p, _ in G.extract(text, nlp, OWNER, role=role)]


@pytest.mark.parametrize("text,forbidden", [
    ("I don't like boxing.", "does like boxing"),
    ("I do not enjoy skydiving.", "does enjoy skydiving"),
    ("I don't want a promotion.", "wants a promotion"),
])
def test_negation_is_never_dropped(text, forbidden, nlp):
    """The inversion bug. A dropped negation is not a miss, it is a LIE, and
    an evidence layer that stores it has failed at the only thing it claims."""
    out = " | ".join(props(text, nlp))
    assert forbidden not in out, out
    assert "not" in out or "n't" in out or out == "", out


def test_positive_statements_are_unchanged(nlp):
    """The fix must not make everything negative."""
    out = props("I like boxing.", nlp)
    assert any("likes boxing" in p for p in out), out
    assert not any(" not " in p for p in out), out


def test_person_shift_is_total(nlp):
    """A stored fact must not still be in the speaker's voice."""
    for p in props("I have been reflecting on my career.", nlp):
        assert " my " not in f" {p} " and not p.startswith("I "), p


def test_second_person_only_applies_to_assistant_turns(nlp):
    """In a USER turn "you" is the assistant. Treating it as the owner would
    file the model's own attributes as the person's."""
    text = "You have been reflecting on your career."
    assert props(text, nlp, role="user") == []
    assert any("Martin Mark" in p for p in props(text, nlp, role="assistant"))


def test_relationship_keeps_relation_name_and_descriptor(nlp):
    """Gold writes relation + name + descriptor; the bare relation shares too
    few tokens with that to ever match."""
    out = props("ThomasSusan is my Friend, Susan's support inspires me.", nlp)
    rel = [p for p in out if "Friend" in p]
    assert rel and "ThomasSusan" in rel[0], out


def test_no_first_person_residue_anywhere(nlp):
    for text in ("I work at Acme as a director.",
                 "I am currently Employed, working in healthcare."):
        for p in props(text, nlp):
            assert not any(w in p.split() for w in ("I", "my", "me")), p
