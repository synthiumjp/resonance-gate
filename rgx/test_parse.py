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


def test_were_agrees_with_the_singular_owner_even_in_the_past(ex):
    # e236's Tense=Past guard ran before the were->was rule and shipped
    # "Martin Mark were born". Number agreement is not tense.
    out = texts(ex, "You were born on 1996-08-02.", role="assistant")
    assert any("was born" in p for p in out), out
    assert not any("were born" in p for p in out), out


# ---- A. shared subject in coordinated clauses (e240) ---------------------
# UD basic deps do not propagate the subject to a `conj` head, so the second
# half of a coordinated clause never got its own nsubj and the walker just
# skipped it.

def test_conjunct_inherits_the_subject(ex):
    out = texts(ex, "I moved to Ohio in 2019 and started a new job.")
    assert len(out) == 2, out
    assert "Martin Mark started a new job" in out, out


# ---- B. fronted modifiers (e240) ------------------------------------------
# A pre-head modifier is attached before the subject in UD but rendered by
# id, so it landed mid-clause: "is Interestingly also curious", "is
# enhancing By integrating X Y". A sentence-initial discourse adverb is
# dropped outright; a substantive pre-subject clause is moved to the end.

def test_sentence_initial_adverb_is_dropped(ex):
    out = " ".join(texts(ex, "Interestingly, I was also curious about "
                             "finding recipes that focus solely on flavor."))
    assert "interestingly" not in out.lower(), out
    assert "also curious" in out, out


def test_fronted_clause_moves_to_the_end(ex):
    out = " ".join(texts(ex, "By integrating eco-friendly practices into "
                             "my daily routine, I am enhancing my personal "
                             "well-being."))
    assert not out.lower().startswith("martin mark is enhancing by "
                                       "integrating"), out
    assert "well being by integrating" in out.lower(), out


# ---- C. "not only" is not negation (e240) ---------------------------------
# "I am not only enhancing X" was stored as "is not enhancing X" -- a fact
# INVERSION, the worst class of defect here, since the record shares every
# content word with the truth and states its opposite.

def test_not_only_is_not_negation(ex):
    out = texts(ex, "I am not only enhancing my well-being but also "
                    "contributing to the planet.")
    assert out
    assert not any(" not " in f" {p} " for p in out), out
    assert any("enhancing" in p for p in out), out


# ---- D. the assistant's "I" is not the owner (e240) -----------------------
# `allow` used to be FIRST|SECOND on an assistant turn, so the assistant's
# own opinion was attributed to the user: "I think X" -> "Martin Mark
# thinks X"; "I remember you expressing Z" -> "Martin Mark remembers Martin
# Mark expressing Z".

def test_assistant_opinion_is_not_attributed_to_the_user(ex):
    out = texts(ex, "I think the Sphynx cat's behavior resonated with "
                    "your need.", role="assistant")
    assert not any(p.startswith("Martin Mark thinks") for p in out), out


def test_embedded_second_person_clause_still_extracts(ex):
    """The matrix "I remember" is the assistant's own claim and is dropped;
    the embedded ccomp is about the user and survives on its own."""
    out = texts(ex, "I remember you mentioned your preference for fresh "
                    "smoothies.", role="assistant")
    assert out == ["Martin Mark mentioned Martin Mark's preference for "
                   "fresh smoothies"], out


def test_matrix_clause_with_bare_first_person_subject_is_dropped(ex):
    out = texts(ex, "You said you were born on 1996-08-02.", role="assistant")
    assert any("was born" in p for p in out), out


# ---- E. third-party subject with the owner inside the clause (e240) ------
# A clause used to be emitted only when the subject WAS the owner or
# owner-possessed. "Susan's encouragement was crucial during my venture"
# and "My friend Thomas's support inspires me" produced nothing at all --
# the whole reason Relationship-kind facts scored so badly.

def test_poss_chain_reaches_the_owner_through_a_named_third_party(ex):
    out = texts(ex, "My friend ThomasSusan's support inspires me to stay "
                    "focused.")
    assert out == ["Martin Mark's friend ThomasSusan's support inspires "
                   "Martin Mark to stay focused"], out


def test_third_party_subject_with_owner_elsewhere_in_the_clause(ex):
    out = texts(ex, "Susan's emotional encouragement was crucial during "
                    "my entrepreneurial venture.")
    assert out == ["Susan's emotional encouragement was crucial during "
                   "Martin Mark's entrepreneurial venture"], out


def test_bare_pronoun_subject_is_not_treated_as_a_third_party(ex):
    """"she" is unresolved coreference, not a third party the parser can
    name -- rendering it verbatim would misattribute the antecedent."""
    out = texts(ex, "She works with me every day.")
    assert not any("She works" in p for p in out), out


# ---- F. evidentiality: hearsay/hedge frames in assistant turns (e242) -----
# HaluMem's "interference" memories are the assistant FALSELY remembering
# things about the user. On user 0, 29/66 stored-but-wrong records sit under
# an evidential/hedge frame in the source sentence, vs. 18/162 legitimate
# assistant-sourced facts. Tagged, not dropped, so a consumer can choose.

def test_report_verb_with_first_person_subject_is_tagged_report(ex):
    out = ex.extract_turn(
        "I remember you mentioned your preference for fresh smoothies.",
        role="assistant")
    assert len(out) == 1, out
    assert "mentioned" in out[0].text
    assert out[0].evidential == "report", out


def test_report_verb_perfect_aspect_is_tagged_report(ex):
    out = ex.extract_turn(
        "I've noticed that your preference for classical music has evolved "
        "to include its therapeutic benefits.", role="assistant")
    matches = [r for r in out if "evolved" in r.text]
    assert matches, out
    assert matches[0].evidential == "report", out


def test_plain_second_person_restatement_is_not_tagged(ex):
    out = ex.extract_turn(
        "Your approach to gaming now includes a cautious evaluation of "
        "cognitive benefits.", role="assistant")
    assert out
    assert all(r.evidential is None for r in out), out


def test_sentence_initial_hedge_adverb_is_tagged_report(ex):
    out = ex.extract_turn(
        "Interestingly, your health status seems to have changed to "
        "Excellent.", role="assistant")
    assert out
    assert any(r.evidential == "report" for r in out), out


def test_evidentiality_is_assistant_turn_only(ex):
    out = ex.extract_turn("I remember I used to avoid skydiving.",
                          role="user")
    assert out
    assert all(r.evidential is None for r in out), out


def test_expletive_construction_is_tagged_report(ex):
    out = ex.extract_turn("It seems that you have been sleeping better.",
                          role="assistant")
    assert out
    assert any(r.evidential == "report" for r in out), out


# ---- F. `_third`'s spelling guards (e238) ----------------------------------
# `endswith("ed") or endswith("s")` is a SPELLING test, not a morphology one,
# and it fired on ordinary present-tense verbs that happen to end that way:
# "need", "focus", "discuss" were all left uninflected.

@pytest.mark.parametrize("src,want", [
    ("I need to focus on these areas.", "needs"),
    ("I focus on quality.", "focuses"),
    ("I discuss it with my team.", "discusses"),
])
def test_third_person_spelling_guard(ex, src, want):
    out = " ".join(texts(ex, src))
    assert want in out, out


# ---- G. two interrogative escapes (e237) -----------------------------------

def test_ccomp_under_an_interrogative_matrix_is_dropped(ex):
    """"do you THINK" is the question; its complement is not a separate
    assertion just because it shows no inversion of its own."""
    out = texts(ex, "What steps do you think you'll take?", role="assistant")
    assert out == [], out


def test_wh_word_dropped_from_a_surviving_presupposition(ex):
    out = texts(ex, "When you joined the conservation group, did you find "
                    "it rewarding?", role="assistant")
    assert out == ["Martin Mark joined the conservation group"], out


# ---- H. atom + full when a clause has a periphery (e243) -------------------
# 132/315 judged misses on user 0 were the gold fact buried inside a longer
# clause: "... dislikes formal wear because ... finds it restrictive and
# prefer clothing that ..." vs gold "... dislikes formal wear". Surplus
# records are precision-free on this benchmark, so both the atomic CORE and
# the FULL clause are emitted when the clause has a periphery.

def test_atom_and_full_are_both_emitted(ex):
    out = ex.extract_turn(
        "I dislike formal wear because I find it restrictive.")
    # A third record ("Martin Mark finds it restrictive") also comes out,
    # independently of Rule 1: the advcl is `advcl` -- one of CLAUSE_DEPS --
    # so the main loop walks it as its OWN clause too, same as it always
    # has. Rule 1 only concerns the core/full split of the FIRST clause.
    assert len(out) >= 2, out
    assert out[0].text == "Martin Mark dislikes formal wear", out
    assert "because" in out[1].text, out
    assert out[0].value == "formal wear" == out[1].value, out


def test_no_periphery_emits_a_single_record(ex):
    out = texts(ex, "I live in Columbus.")
    assert len(out) == 1, out


# ---- I. object control (e243) ----------------------------------------------
# An xcomp/ccomp with no nsubj of its own inherits the matrix verb's OBJECT
# as its logical subject -- "I remember you expressing skepticism..." --
# but only for a gerund/participial complement; an infinitival xcomp is
# control of a different, unstated subject ("I want to go").

def test_object_control_gerund_complement(ex):
    out = ex.extract_turn(
        "I remember you expressing skepticism about integrating this new "
        "preference into your daily life.", role="assistant")
    # "integrating..." is itself an advcl of "expressing", so Rule 1 also
    # splits this into a core + full pair -- both must satisfy the object-
    # control assertions below.
    assert out, out
    assert all(r.text.startswith("Martin Mark expressed skepticism") or
               r.text.startswith("Martin Mark expressing skepticism")
               for r in out), out
    assert all(r.evidential == "report" for r in out), out


def test_infinitival_xcomp_is_not_object_control(ex):
    out = texts(ex, "I want to go hiking.")
    assert not any(t.startswith("Martin Mark go") for t in out), out


# ---- J. named third-party subject (e243) -----------------------------------
# 52/154 (u0) and 78/256 (u1) judged misses have a NAMED third party as the
# source sentence's subject, in USER turns, with the owner nowhere in the
# clause -- "WilsonRobert recommended a yoga class near the office". Rule E
# (owner elsewhere in the clause) does not fire here, so the record was
# simply dropped. A bare common-noun subject must not fire, and it is user
# turns only -- an assistant's claim about a third party with no owner link
# is not the same kind of grounded fact.

def test_named_third_party_subject_is_kept(ex):
    out = texts(ex, "WilsonRobert recommended a yoga class near the office.")
    assert out == ["WilsonRobert recommended a yoga class near the office"], out
    recs = ex.extract_turn(
        "WilsonRobert recommended a yoga class near the office.")
    assert recs[0].kind == "relationship", recs


def test_generic_common_noun_subject_does_not_fire(ex):
    out = texts(ex, "Cats are independent animals.")
    assert out == [], out


def test_named_third_party_is_user_turn_only(ex):
    out = texts(ex, "WilsonRobert recommended a yoga class.", role="assistant")
    assert out == [], out
