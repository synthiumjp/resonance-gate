"""Regression tests for the person shift.

Every case here is a defect that SHIPPED and that no metric could see. Three
came from reading the raw artifacts for HaluMem users 0 and 1 (entry 234):
they were ungrammatical in a way that token-overlap scoring is blind to,
because the mangled record shares every content word with the correct one.
"""
import pytest

from rgx import Extractor


@pytest.fixture(scope="module")
def ex():
    return Extractor(owner_name="Martin Mark", check=False)


def texts(ex, content, role="user"):
    return [r.text for r in ex.extract_turn(content, role=role)]


# ---- A. detached clitics ------------------------------------------------
# Stanza splits "I'd" into ["I", "'d"]. Appending -s to the clitic produced
# "Martin Mark 'ds like to share ..." -- 2.5% of every record on user 1.

@pytest.mark.parametrize("src,want", [
    ("I'd like to share my background.", "would"),
    ("I'll start by contacting local experts.", "will"),
    ("I've been running for three years.", "has"),
])
def test_clitic_is_expanded_not_inflected(ex, src, want):
    out = " ".join(texts(ex, src))
    assert "'ds" not in out and "'lls" not in out and "'ves" not in out
    assert want in out


# ---- B. the subject span was rendered without the person shift ----------
# `s.text(subj, ...)` was called with owner=None at three sites, so a pronoun
# EMBEDDED in the subject survived while the subject's own possessive was
# rewritten: "Martin Mark's ability to empower your team is ...".

def test_pronoun_inside_the_subject_is_shifted(ex):
    out = " ".join(texts(ex, "Your ability to empower your team is "
                             "impressive.", role="assistant"))
    assert "your" not in out.lower()
    assert "Martin Mark" in out


def test_first_person_inside_the_subject_is_shifted(ex):
    out = " ".join(texts(ex, "My plan for my business is ambitious."))
    assert " my " not in f" {out.lower()} "


# ---- C. agreement in subordinate clauses --------------------------------
# The matrix verb was agreed; verbs deeper in the span were not, because the
# shift is a string pass that cannot see it just made a subject singular.

def test_subordinate_clause_verb_agrees(ex):
    out = " ".join(texts(ex, "I dislike wrestling because I find wrestling "
                             "too confrontational."))
    assert "Mark find " not in out
    assert "finds" in out


def test_adverbial_clause_verb_agrees(ex):
    out = " ".join(texts(ex, "As I continue to expand, I need more staff."))
    assert "Mark continue " not in out


def test_infinitive_is_not_agreed(ex):
    """Only a verb with its OWN nsubj is agreed -- an infinitive has none."""
    out = " ".join(texts(ex, "I want to continue running."))
    assert "to continues" not in out


def test_past_tense_is_left_alone(ex):
    out = " ".join(texts(ex, "I continued running because I enjoyed it."))
    assert "continueds" not in out and "enjoyeds" not in out


# ---- the commitment that must not regress -------------------------------

def test_negation_is_never_inverted(ex):
    """The defect that stored every negated fact as its opposite."""
    out = " ".join(texts(ex, "I don't like boxing."))
    assert "not" in out


# ---- D. questions are not assertions ------------------------------------
# "What kind of personality do you have?" was emitted as "Martin Mark does
# have What kind of personality" -- a claim nobody made. ~12% of records on
# both HaluMem users (e235). The metric cannot see this: an out-of-gold
# record is dropped from BOTH sides of precision = k/n, so asserting a
# question as a fact costs exactly zero. Product defect, benchmark-invisible.

@pytest.mark.parametrize("q", [
    "What kind of personality do you have?",
    "Can you tell me about your educational background?",
    "How do you plan to leverage this achievement?",
    "What are your life goals?",
    "What specific steps are you considering for expansion?",
    "Who introduced you to running?",
])
def test_questions_emit_nothing(ex, q):
    assert texts(ex, q, role="assistant") == []


def test_embedded_wh_clause_still_extracts(ex):
    """Declarative. The wh-word is embedded, there is no inversion."""
    out = texts(ex, "I'm considering what specific steps to take.")
    assert out and any("Martin Mark" in r for r in out)


def test_wh_complement_of_a_declarative_survives(ex):
    out = texts(ex, "I don't know how to fix the roof.")
    assert out


def test_presupposition_survives_the_question_carrying_it(ex):
    """Per-CLAUSE, not per-sentence: the advcl is not inverted, so it stays."""
    out = " ".join(texts(ex, "Since you moved to Albi last year, how are "
                             "you settling in?", role="assistant"))
    assert "Albi" in out
    assert "settling" not in out


# ---- E. agreement has two more edges ------------------------------------

def test_modal_leaves_its_verb_bare(ex):
    """The aux carries finiteness. Introduced by the e234 agreement fix and
    caught by reading what the interrogative filter was dropping."""
    out = " ".join(texts(ex, "I have thought about how I might measure "
                             "success."))
    assert "might measures" not in out and "might measure" in out


def test_modal_leaves_its_verb_bare_in_the_matrix(ex):
    out = " ".join(texts(ex, "I know that I should exercise more often."))
    assert "should exercises" not in out


@pytest.mark.parametrize("src,bad,good", [
    ("I said I would consider the offer.", "saids", "said"),
    ("I told my team about the plan.", "tolds", "told"),
])
def test_irregular_past_is_not_inflected(ex, src, bad, good):
    """Shipped in 0.1.0: _third's past-tense guard was `endswith("ed")`, so
    every irregular past fell through to the default and took an -s."""
    out = " ".join(texts(ex, src))
    assert bad not in out and good in out
