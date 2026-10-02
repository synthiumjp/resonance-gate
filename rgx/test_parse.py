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
    ("I feed my dog every morning.", "feeds"),
    ("I succeed at most things I try.", "succeeds"),
    ("I proceed carefully with new projects.", "proceeds"),
    ("I pass the test every time.", "passes"),
    ("I address problems directly.", "addresses"),
    ("I process my emotions through journaling.", "processes"),
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


# ---- K. evidentiality gaps found in stored distractors after e242 (e246) --
# GAP 1: `evidential` was read from `_report_frame`/`_generic_or_expl_frame`/
# `hedge` and attached per-body in the closing loop that runs over EVERY
# branch's `records` (copular, verbal, third-party-subject) for the clause,
# not inside any one branch -- so a hedge-adverb sentence rendered through
# the third-party-subject branch (E/e240, Rule 3/e243) must still come out
# tagged, and the fronted hedge adverb itself must not survive in the text.
# GAP 2: `_generic_or_expl_frame`'s `expl` check climbs REPORT_CHAIN
# (ccomp/xcomp/advcl/csubj) to ANY ancestor with an `expl` child regardless
# of that ancestor's upos, so an ADJECTIVE predicate with expletive "It"
# ("It's interesting how...", "It's fascinating to consider that...") is
# caught the same as a verb ("it seems that...").

def test_hedge_is_tagged_on_the_third_party_subject_branch(ex):
    out = ex.extract_turn(
        "Interestingly, this evolving preference signifies your interest "
        "in exploring different pet species.", role="assistant")
    assert out, out
    assert all(r.evidential == "report" for r in out), out
    assert not any("interestingly" in r.text.lower() for r in out), out


def test_adjectival_expletive_ccomp_is_tagged_report(ex):
    out = ex.extract_turn(
        "It's interesting how you expressed a preference for films that "
        "reinforce existing beliefs.", role="assistant")
    matches = [r for r in out if r.text.startswith(
        "Martin Mark expressed a preference for films")]
    assert matches, out
    assert all(r.evidential == "report" for r in matches), out


def test_adjectival_expletive_xcomp_is_tagged_report(ex):
    out = ex.extract_turn(
        "It's fascinating to consider that your evolving preferences "
        "reflect a deeper curiosity.", role="assistant")
    matches = [r for r in out if r.text.startswith(
        "Martin Mark's evolving preferences reflect")]
    assert matches, out
    assert all(r.evidential == "report" for r in matches), out


def test_plain_second_person_no_expletive_is_not_tagged(ex):
    out = ex.extract_turn(
        "You expressed a preference for films that reinforce existing "
        "beliefs.", role="assistant")
    assert out, out
    assert all(r.evidential is None for r in out), out


# ---- render_defects: clitic_residue, bare_been, stray_complementizer,
# advmod_between_verb_and_obj, plural_head_singular_agr (all found by
# reading raw u0 output, none visible to token-overlap scoring)

def test_embedded_perfect_clitic_is_expanded_not_left_raw(ex):
    # "The support I've received from my network is..." -- "'ve" is the AUX
    # of an acl:relcl ("received") that ends up embedded inside a LARGER
    # copular span (the third-party-owner branch), not walked as its own
    # clause's head aux -- the one spot `_third` already covered. Left raw,
    # `_shift`'s `\bI\b` still matched the "I" inside "I've", producing
    # "Martin Mark've received".
    out = texts(ex, "The support I've received from my network is indeed "
                     "a powerful force in navigating this transition.")
    assert out, out
    assert not any("'ve" in t for t in out), out
    assert any("has received" in t for t in out), out


def test_embedded_negation_clitic_reads_as_two_words(ex):
    # "the fact that they don't exhibit..." is PERIPHERY kept in a FULL
    # record, not this clause's own head -- its "n't" was never in any
    # `negdrop` set and rendered as a literal, unspaced clitic.
    out = texts(ex, "I find snakes unsettling due to their unpredictable "
                     "movements and the fact that they don't exhibit the "
                     "social behaviors in pets.")
    assert out, out
    assert not any("n't" in t for t in out), out
    assert any("do not exhibit" in t for t in out), out


def test_third_party_copular_keeps_its_perfect_aux(ex):
    # bare_been: the third-party-owner copular branch un-drops subj/cop but
    # used to leave the clause's own aux ("has") excluded, orphaning "been"
    # with no perfect auxiliary: "Networking always been a key part...".
    out = texts(ex, "Networking has always been a key part of my career "
                     "development.")
    assert out, out
    assert any("has always been" in t for t in out), out
    assert not any(t for t in out
                   if "been" in t and "has been" not in t
                   and "has always been" not in t), out


def test_matrix_complementizer_does_not_leak_into_the_child_span(ex):
    # stray_complementizer: "that"/"like" is a `mark` child of the embedded
    # clause's OWN head (introducing it as a complement of the outer verb),
    # not part of its predicate -- nothing excluded it from the walk.
    out = texts(ex, "I believe that my journey is a testament to my "
                     "resilience and determination to make a positive "
                     "impact in the world.")
    assert out, out
    assert not any(" is that " in t for t in out), out
    assert any(t.startswith("Martin Mark's journey is a testament")
               for t in out), out


def test_preverbal_adverb_stays_before_the_verb(ex):
    # advmod_between_verb_and_obj: `lead + verb + tail` always put every arg
    # AFTER the verb, so "I RECENTLY visited a sanctuary" (adverb before the
    # verb) came out "visited RECENTLY a sanctuary".
    out = texts(ex, "I recently visited a reptile sanctuary, and it was "
                     "quite an experience.")
    assert "Martin Mark recently visited a reptile sanctuary" in out, out


def test_preverbal_adverb_on_a_possessed_subject(ex):
    out = texts(ex, "My approach to gaming now includes a cautious "
                     "evaluation of cognitive benefits.")
    assert any("approach to gaming now includes" in t for t in out), out
    assert not any("includes now" in t for t in out), out


def test_plural_possessed_subject_keeps_plural_agreement(ex):
    # plural_head_singular_agr: the verbal is_self/sp branch re-agreed the
    # aux to 3rd-singular whenever `sp is not None` (a possessed subject),
    # right even for "my job IS" but wrong for "my friends ... HAVE" --
    # "friends and colleagues has played" shipped.
    out = texts(ex, "My friends and colleagues have played a pivotal role "
                     "in my journey.")
    assert any("friends and colleagues have played" in t for t in out), out
    assert not any("colleagues has played" in t for t in out), out


def test_singular_possessed_subject_still_agrees(ex):
    # The fix must not blunt the case it was never wrong about: a SINGULAR
    # possessed subject's own aux was already agreeing correctly in the
    # source, and must still show up unchanged (not un-agreed to a base
    # form) now that `agree` gates on `is_self` instead of firing blindly.
    out = texts(ex, "My colleague has completed the project for me.")
    assert any("colleague has completed" in t for t in out), out


# ---- owner_pronoun: opt-in pronominalisation of repeated owner mentions --

def test_owner_pronoun_default_is_unchanged():
    """The whole point of the default: two extractors, one with
    owner_pronoun left at its default (None), must produce byte-identical
    text to the pre-existing behaviour -- so every banked artifact stays
    valid without anyone having to pass anything."""
    plain = Extractor(owner_name="Martin Mark", check=False)
    explicit_none = Extractor(owner_name="Martin Mark", check=False,
                               owner_pronoun=None)
    src = ("Susan's support inspires me to maintain my focus on promoting "
           "well being in both my personal and professional life.")
    assert texts(plain, src) == texts(explicit_none, src)
    assert any("Martin Mark's focus" in t for t in texts(plain, src))


def test_owner_pronoun_collapses_repeated_possessives():
    ex = Extractor(owner_name="Martin Mark", check=False,
                    owner_pronoun="his")
    out = texts(ex, "My physical health remains stable due to my active "
                     "lifestyle and focus on well being.")
    assert out, out
    t = out[0]
    assert t.count("Martin Mark") == 1, t
    assert "his active lifestyle" in t, t


def test_owner_pronoun_object_position_after_first_mention():
    ex = Extractor(owner_name="Martin Mark", check=False,
                    owner_pronoun="his")
    out = texts(ex, "Susan's support inspires me to maintain my focus on "
                     "promoting well being in both my personal and "
                     "professional life.")
    assert out, out
    t = out[0]
    assert t.count("Martin Mark") == 1, t
    assert "inspires Martin Mark" in t, t          # first mention: kept
    assert "maintain his focus" in t, t            # subsequent possessive
    assert "his personal" in t, t


def test_owner_pronoun_never_inferred_default_is_their():
    """DO NOT infer gender from the owner's name, ever. A caller that asks
    for pronominalisation without saying which pronoun gets the neutral
    default -- never a guess pulled from `owner_name`."""
    ex = Extractor(owner_name="Martin Mark", check=False,
                    owner_pronoun="their")
    out = texts(ex, "My physical health remains stable due to my active "
                     "lifestyle and focus on well being.")
    assert out, out
    assert "their active lifestyle" in out[0], out[0]
    assert "his" not in out[0] and "her" not in out[0], out[0]


def test_owner_pronoun_obj_is_derived_when_not_given():
    ex = Extractor(owner_name="Martin Mark", check=False,
                    owner_pronoun="her")
    out = texts(ex, "Susan's support inspires me to maintain my focus on "
                     "well being.")
    assert out, out
    assert "inspires Martin Mark" in out[0], out[0]
    assert "her focus" in out[0], out[0]


def test_owner_pronoun_does_not_mangle_an_identity_statement():
    # "Martin Mark's name is Martin Mark" -- the second mention is the
    # VALUE being asserted (the owner's own name), not a further reference
    # to them. Pronominalising it produced "name is them", which (before
    # the STOP-list fix in check.py, below) failed the grounding filter and
    # silently dropped the record instead of just mis-wording it.
    ex = Extractor(owner_name="Martin Mark", check=False,
                    owner_pronoun="their")
    out = texts(ex, "My name is Martin Mark.")
    assert "Martin Mark's name is Martin Mark" in out, out


def test_owner_pronoun_object_form_is_grounded(ex=None):
    # him/them were missing from check.py's STOP set (only the possessive
    # forms his/her/their/its were there) -- an object-pronoun mention that
    # ends up as the record's only remaining content word failed the
    # grounding prefilter and the record vanished, not just reworded.
    ex = Extractor(owner_name="Martin Mark", check=True, owner_pronoun="his")
    out = texts(ex, "Susan's support inspires me to maintain my focus on "
                     "well being.")
    assert out, out
    assert any("his focus" in t for t in out), out


# ---- L. relative pronouns resolved to their antecedent (e259) ------------
# A relative clause is walked as a clause in its own right, so its relative
# pronoun rendered LITERALLY as an argument: "It's in Go, which I didn't know
# before I joined" produced "<owner> did not know which" -- a meaningless
# record that also acted as a retrieval attractor in the product store (e258,
# it ranked first for nearly every unanswerable question). The antecedent is
# the clause head's own UD parent, so it is recoverable.

def test_relative_pronoun_object_resolves_to_its_antecedent(ex):
    out = texts(ex, "It's in Go, which I didn't know before I joined.")
    assert any("did not know Go" in p for p in out), out
    assert not any("know which" in p for p in out), out


def test_antecedent_is_a_noun_phrase_not_the_clause_it_heads(ex):
    """`Go` is the copular ROOT of "It's in Go", so an unrestricted render of
    its subtree gave "did not know It's in Go"."""
    out = texts(ex, "It's in Go, which I didn't know before I joined.")
    assert not any("know It" in p or "know 's" in p for p in out), out


def test_the_antecedent_keeps_its_determiner(ex):
    out = texts(ex, "She recommended a book, which I enjoyed.")
    assert any("enjoyed a book" in p for p in out), out


def test_relative_pronoun_resolution_on_a_proper_noun(ex):
    out = texts(ex, "I use Postgres, which I learned last year.")
    assert any("learned Postgres" in p for p in out), out
    assert not any("learned which" in p for p in out), out


def test_a_clause_with_no_relative_pronoun_is_unchanged(ex):
    out = texts(ex, "I bought a car, which was expensive.")
    assert any("bought a car" in p for p in out), out


# ---- M. deictic-empty values are not stored (e262) -----------------------
# "I like it a lot actually" stored "<owner> likes it a lot actually" -- a
# fact whose complement is an unresolved referent. 16.67% of a real
# conversational store, 0.71% of HaluMem u0. Cross-turn resolution is the
# better answer and is deliberately NOT attempted: a wrong antecedent is a
# confident false memory, the worst outcome for an evidence layer.

# The `ex` fixture runs with check=False -- it exercises the PARSER. These
# assert a FILTER, so they need the checked extractor the product uses.

@pytest.fixture(scope="module")
def checked(ex):
    return Extractor(owner_name="Martin Mark", check=True, _nlp=ex._nlp)


def test_a_deictic_only_complement_is_not_stored(checked):
    assert texts(checked, "I like it a lot actually.") == []
    assert texts(checked, "I don't miss it much.") == []


def test_the_same_sentence_with_a_real_complement_is_kept(checked):
    out = texts(checked, "I like Go a lot actually.")
    assert any("likes Go" in p for p in out), out


def test_a_relationship_survives_a_deictic_complement(checked):
    """A relationship's content is its PARTICIPANTS. Rejecting these cost
    more than the empty records were worth: the manager relation lived only
    in a record whose value was "it"."""
    out = texts(checked, "My manager Priya suggested it.")
    assert any("manager Priya" in p for p in out), out


def test_a_deictic_alongside_real_content_is_kept(checked):
    out = texts(checked, "I am a backend engineer there.")
    assert any("backend engineer" in p for p in out), out


# ---- N. the copular perfect keeps its aspect (e263) ----------------------
# The copular branch drops every `aux` child along with the copula and
# rebuilds the copula from a literal "is", so a PERFECT lost its aspect:
# "I've been at Lumen Health for about three years now" rendered as "<owner>
# IS at Lumen Health for about three years now" -- not English, and it reads
# as a location rather than a tenure. The verbal branch never had this bug.
# Same family as e256's bare_been.

def test_a_copular_perfect_keeps_has_been(ex):
    out = texts(ex, "I've been at Lumen Health for about three years now.")
    assert any(p.startswith("Martin Mark has been at Lumen Health") for p in out), out
    assert not any("Mark is at Lumen" in p for p in out), out


def test_a_copular_present_is_unchanged(ex):
    out = texts(ex, "I am a backend engineer there.")
    assert any("Martin Mark is a backend engineer" in p for p in out), out


def test_the_perfect_reaches_the_possessed_slot_branch_too(ex):
    out = texts(ex, "My commute has been brutal.")
    assert any("Martin Mark's commute has been brutal" in p for p in out), out


def test_a_possessed_slot_in_the_present_is_unchanged(ex):
    out = texts(ex, "My job is stressful.")
    assert any("Martin Mark's job is stressful" in p for p in out), out


def test_the_verbal_perfect_is_untouched(ex):
    out = texts(ex, "I've worked at Acme for two years.")
    assert any("has worked at Acme" in p for p in out), out


# ---- O. a finite aux agrees with its HEAD's shifted subject (e264) -------
# UD attaches a subject to the head VERB, not to the aux, so the agreement
# rule -- which asks for the token's OWN nsubj -- never fired on a finite aux
# inside a rendered span: "The support you've received" shifted to "The
# support Martin Mark have received". e243 saw this and queued it
# ("agreement inside relative clauses is not done"); it is 1.31% of u0.

def test_aux_in_a_relative_clause_agrees_after_the_shift(ex):
    out = texts(ex, "The support you've received from your network is a "
                    "powerful force.", role="assistant")
    assert any("Martin Mark has received" in p for p in out), out
    assert not any("Mark have received" in p for p in out), out
    assert not any("Mark've" in p for p in out), out


def test_the_same_holds_for_a_first_person_relative_clause(ex):
    out = texts(ex, "The insights I've gained have helped me a lot.")
    assert any("Martin Mark has gained" in p for p in out), out


def test_a_main_clause_aux_is_still_agreed(ex):
    out = texts(ex, "I've worked at Acme for two years.")
    assert any("has worked at Acme" in p for p in out), out


def test_an_aux_whose_head_subject_is_not_shifted_is_left_alone(ex):
    """Only a subject the shift rewrites triggers agreement."""
    out = texts(ex, "The reports they've filed are late.", role="user")
    assert not any("they has" in p for p in out), out


# ---- P. a question's relative clause is not a fact about the user (e264) --
# THE MOST SERIOUS DEFECT CLASS: what leaks here is not noise but a plausible
# FALSE fact. The assistant ASKS "Are there specific workshops you're
# particularly interested in?" and the store ASSERTED "<owner> is particularly
# interested in attending". Two escapes: the interrogative climb covered
# complements only (ccomp/xcomp) and stopped at the antecedent noun, and an
# existential matrix ("Are there...") has `there` as an expletive so the
# inversion test never saw a subject to compare against.

def test_a_relative_clause_under_an_existential_question_is_not_asserted(ex):
    out = texts(ex, "Are there specific workshops or seminars you're "
                    "particularly interested in attending?", role="assistant")
    assert out == [], out


def test_a_relative_clause_under_a_plain_existential_question(ex):
    out = texts(ex, "Are there specific strategies you plan to employ to "
                    "maintain this balance?", role="assistant")
    assert out == [], out


def test_a_subject_position_wh_question_is_not_stored_verbatim(ex):
    """No subject-aux inversion to detect, and the wh-word is a DETERMINER of
    the subject rather than the subject itself."""
    out = texts(ex, "What specific aspects of relaxation are most important "
                    "to you?", role="assistant")
    assert out == [], out


def test_a_presupposition_still_survives_its_question(ex):
    """e235's designed behaviour: an advcl under a question is presupposed,
    not asked. Broadening the climb must not take this with it."""
    out = texts(ex, "Since you moved to Albi, how are you settling in?",
                role="assistant")
    assert any("moved to Albi" in p for p in out), out


def test_an_ordinary_relative_clause_is_untouched(ex):
    out = texts(ex, "I bought a car, which was expensive.")
    assert any("bought a car" in p for p in out), out


def test_a_statement_before_a_question_still_extracts(ex):
    out = texts(ex, "You mentioned you work at Acme. Is that right?",
                role="assistant")
    assert any("works at Acme" in p for p in out), out


# ---- Q. same-turn pronoun subject, owner-possessed antecedent (e267) -----
# "My car is a Volvo. It is very reliable." stored the first clause and threw
# the second away -- a bare pronoun subject is refused, rightly, because
# rendering an unresolved antecedent misattributes it. Restricted to the only
# case where the antecedent is unambiguous AND the rendering is honest: same
# TURN, OWNER-POSSESSED antecedent, EXACTLY ONE candidate.

def test_a_pronoun_resolves_to_a_single_owner_possessed_antecedent(ex):
    out = texts(ex, "My car is a Volvo. It is very reliable.")
    assert any("Martin Mark's car is very reliable" in p for p in out), out


def test_it_works_for_a_second_owner_possessed_noun(ex):
    out = texts(ex, "My commute is long. It is exhausting.")
    assert any("Martin Mark's commute is exhausting" in p for p in out), out


def test_TWO_candidates_DECLINE_rather_than_guess(ex):
    """A wrong antecedent is a confident false memory. Ambiguity must lose
    the fact, never invent one."""
    out = texts(ex, "My car is a Volvo. My bike is red. It is very reliable.")
    assert not any("very reliable" in p for p in out), out


def test_a_non_possessed_antecedent_stays_out_of_scope(ex):
    """Resolving "the billing service" would make the store hold facts about
    THINGS rather than about the user -- a change to what the store is for,
    not a defect fix."""
    out = texts(ex, "Mostly the billing service. It is written in Go.")
    assert out == [], out


def test_a_pronoun_cannot_resolve_within_its_own_sentence(ex):
    """The carry updates only after a sentence is fully walked."""
    out = texts(ex, "It is very reliable, my car.")
    assert not any("car is very reliable" in p for p in out), out


def test_the_first_sentence_is_unaffected(ex):
    out = texts(ex, "My car is a Volvo. It is very reliable.")
    assert any("Martin Mark's car is a Volvo" in p for p in out), out


# ---- R. the user's WORLD, not the user's profile (e269) ------------------
# JP: "most people rely on facts about their world. they KNOW the facts on
# themselves." An owner-subject-only store keeps "Alex works on the billing
# service" -- which the user already knows -- and throws away "the billing
# service is written in Go", which is what they would actually forget.
# An entity joins the world when the OWNER links themselves to it.

def test_a_world_entity_can_be_the_subject_of_a_later_clause(ex):
    out = texts(ex, "I work on the billing service. It is written in Go.")
    assert any("billing service is written in Go" in p for p in out), out


def test_the_entity_keeps_its_modifiers(ex):
    """Storing the bare head gave the entity "service", and the record read
    "service is written in Go"."""
    out = texts(ex, "I work on the billing service. It is written in Go.")
    assert not any(p.startswith("service is") for p in out), out


def test_a_world_entity_persists_across_turns(ex):
    ex.reset_world()
    ex.extract_turn("I work on the billing service.", role="user")
    out = [r.text for r in ex.extract_turn(
        "The billing service is written in Go.", role="user")]
    ex.reset_world()
    assert any("billing service is written in Go" in p for p in out), out


def test_generic_knowledge_never_becomes_a_world_fact(ex):
    """The guard rail the whole mechanism rests on."""
    out = texts(ex, "Cats are independent animals.", role="assistant")
    assert out == [], out
    out = texts(ex, "There are several good databases available.",
                role="assistant")
    assert not any("databases" in p for p in out), out


def test_an_assistant_turn_cannot_establish_a_world_entity(ex):
    ex.reset_world()
    ex.extract_turn("There are several good databases available.",
                    role="assistant")
    out = [r.text for r in ex.extract_turn(
        "The databases are slow.", role="user")]
    ex.reset_world()
    assert out == [], out


def test_coordination_gives_TWO_candidates_and_declines(ex):
    """"I have a dog and a cat" must put BOTH in scope. Collecting only the
    obj head left one candidate and produced a confident wrong guess."""
    out = texts(ex, "I have a dog and a cat. It is friendly.")
    assert not any("friendly" in p for p in out), out


def test_an_owner_possessed_antecedent_still_renders_as_possessed(ex):
    """e267's case must not be swallowed by e269's -- the owner OWNS a car,
    they merely work on a billing service."""
    out = texts(ex, "My car is a Volvo. It is very reliable.")
    assert any("Martin Mark's car is very reliable" in p for p in out), out


def test_a_direct_object_carries_to_a_verbal_follow_up(ex):
    """2026-10-02: "I maintain the checkout service" makes the service a
    direct object, which took the possessive path, and that path renders
    copular clauses only. "It is written in Rust" was dropped."""
    out = texts(ex, "I maintain the checkout service. It is written in Rust.")
    assert any(p == "the checkout service is written in Rust" for p in out), out
    out = texts(ex, "I bought a new car. It was made in Japan.")
    assert any(p == "the new car was made in Japan" for p in out), out


def test_a_carried_object_keeps_its_negation(ex):
    out = texts(ex, "I maintain the checkout service. It is not written in Rust.")
    assert not any(p.endswith("is written in Rust") for p in out), out


def test_two_objects_still_decline_a_verbal_follow_up(ex):
    out = texts(ex, "I have a dog and a cat. It barks at night.")
    assert not any("barks" in p for p in out), out


def test_the_world_can_be_switched_off(ex, monkeypatch):
    monkeypatch.setenv("RG_WORLD", "0")
    out = texts(ex, "I work on the billing service. It is written in Go.")
    assert not any("written in Go" in p for p in out), out


# ---- S. FACT INVERSION regressions, found by adversarial review (e276) ----
# Two independent reviewers found the same class in the same region: a clause
# whose subject is a third party or a world entity lost its NEGATION, so the
# store asserted the OPPOSITE of what was said. Ledger 5l names this the worst
# class there is -- the false record shares every content word with the true
# one, so no overlap metric can see it, and the six-axis product harness
# scored 21/21 on purity while this was live.

def test_third_party_copular_negation_survives(ex):
    out = texts(ex, "WilsonRobert is not a fan of jazz.")
    assert any("is not a fan" in p for p in out), out
    assert not any("WilsonRobert is a fan" in p for p in out), out


def test_third_party_verbal_negation_survives(ex):
    out = texts(ex, "WilsonRobert does not like jazz.")
    assert any("does not like jazz" in p for p in out), out


def test_world_subject_passive_negation_survives(ex):
    ex.reset_world()
    ex.extract_turn("I work on the billing service.", role="user")
    out = [r.text for r in ex.extract_turn(
        "The billing service is not written in Go.", role="user")]
    ex.reset_world()
    assert any("is not written in Go" in p for p in out), out
    assert not any(p.endswith("is written in Go") for p in out), out


def test_the_positive_form_is_unaffected(ex):
    ex.reset_world()
    ex.extract_turn("I work on the billing service.", role="user")
    out = [r.text for r in ex.extract_turn(
        "The billing service is written in Go.", role="user")]
    ex.reset_world()
    assert any("is written in Go" in p for p in out), out


def test_a_relative_pronoun_antecedent_beats_the_world_carry(ex):
    """"that" is both a RELPRON and a _PRON_SUBJ, so in a SUBJECT relative
    clause the ids collided and e269's world entity overwrote e259's correct
    antecedent: "a disease that affects millions" became "a doctor affects
    millions". The antecedent is read off THIS clause and always wins."""
    out = texts(ex, "I met a doctor who treats a disease that affects "
                    "millions of people.")
    assert any("a disease affects millions" in p for p in out), out
    assert not any("a doctor affects millions" in p for p in out), out


# ---- T. the rest of the adversarial-review findings (e276) ---------------

def test_a_past_copular_stays_past(ex):
    """"I was very anxious during college" stored "IS very anxious during
    college", beside "feels much calmer now" from the same turn -- two
    contradictory present-tense claims. e263 handled only the perfect."""
    out = texts(ex, "I was very anxious during college, but I feel much "
                    "calmer now.")
    assert any("was very anxious" in p for p in out), out
    assert not any("is very anxious" in p for p in out), out


def test_a_future_copular_stays_future(ex):
    out = texts(ex, "I will be a manager next year.")
    assert any("will be a manager" in p for p in out), out
    assert not any("Mark is a manager" in p for p in out), out


def test_a_root_clause_conditional_is_not_asserted(ex):
    """"If only I had studied medicine" asserted that he DID -- the exact
    opposite of the regret. A conditional with no separate main clause is a
    ROOT carrying the mark itself, and the head's own mark was never checked."""
    assert texts(ex, "If only I had studied medicine instead of law.") == []


def test_even_if_is_concessive_and_the_main_clause_survives(ex):
    """"EVEN if X, Y" asserts Y. Suppressing it lost the fact entirely."""
    out = texts(ex, "Even if it is raining, I always go for a run every "
                    "morning.")
    assert any("goes for a run" in p for p in out), out


def test_an_object_competes_as_an_antecedent(ex):
    """"My friend has a cat. It is very playful." attributed the CAT's
    playfulness to the FRIEND, because only owner-possessed nominals counted
    as candidates and there was therefore exactly one."""
    out = texts(ex, "My friend has a cat. It is very playful.")
    assert not any("playful" in p for p in out), out


def test_a_copular_complement_does_not_compete(ex):
    """In "My car is a Volvo" the Volvo IS the car, not a second entity."""
    out = texts(ex, "My car is a Volvo. It is very reliable.")
    assert any("car is very reliable" in p for p in out), out


def test_an_indirect_question_under_a_wondering_verb_is_not_asserted(ex):
    out = texts(ex, "I wonder what city I moved to when I was a kid.")
    assert not any("moved what city" in p for p in out), out


def test_a_wh_complement_under_a_KNOWING_verb_still_survives(ex):
    """Narrow on purpose: the first version of the fix fired on any wh-word
    and broke five tests asserting e235/e237's deliberate design."""
    out = texts(ex, "I know what I want.")
    assert out, out


def test_a_short_verb_is_grounded_after_the_person_shift(ex):
    """`_content` dropped 2-character tokens from the SOURCE side, so "go"
    was invisible and the shift's "goes" read as invented content -- the
    whole record was silently dropped."""
    out = texts(ex, "I go to the gym on Tuesdays.")
    assert any("goes to the gym" in p for p in out), out


# ---- 2026-10-02: every record carries its source sentence, verbatim ------

def test_a_record_carries_its_own_sentence_verbatim():
    from rgx import Extractor
    ex = Extractor(owner_name="Martin Mark")
    turn = "I work at Acme as a backend engineer. My partner Sam is a chef."
    recs = ex.extract_turn(turn, role="user")
    assert recs
    for r in recs:
        assert r.source in ("I work at Acme as a backend engineer.",
                            "My partner Sam is a chef."), r.source
        # the source is the sentence the record was read FROM
        if "Acme" in r.text:
            assert r.source.startswith("I work at Acme")
        if "chef" in r.text:
            assert r.source.startswith("My partner Sam")


def test_the_source_survives_into_the_cache_fact():
    from rgx import Extractor
    from rgx.facts import to_fact
    ex = Extractor(owner_name="Martin Mark")
    f = [to_fact(r) for r in ex.extract_turn("I live in Leeds.", role="user")]
    assert any(x and x.get("source") == "I live in Leeds." for x in f)


# ---- 2026-10-02: three defects found by reading the first MEMORY.md --------

def test_a_stranded_preposition_is_not_a_fact():
    from rgx import Extractor
    ex = Extractor(owner_name="Dana Cole")
    out = [r.text for r in ex.extract_turn("The ward I work on has 30 beds.", role="user")]
    assert "Dana Cole works on" not in out
    assert any("30 beds" in t for t in out)


def test_an_assistant_report_frame_is_not_stored_beside_its_claim():
    from rgx import Extractor
    ex = Extractor(owner_name="Dana Cole")
    out = [r.text for r in ex.extract_turn(
        "I remember you mentioning you play the cello.", role="assistant")]
    assert out == ["Dana Cole plays the cello"]


def test_a_phrasal_verb_keeps_its_particle():
    from rgx import Extractor
    ex = Extractor(owner_name="Dana Cole")
    for turn, want in (("I grew up in Leeds.", "grew up in Leeds"),
                       ("I gave up smoking last year.", "gave up smoking")):
        ex.reset_world()
        assert any(want in r.text for r in ex.extract_turn(turn, role="user")), turn


# ---- life events and short statements (2026-10-02) -----------------------
# A verb with nothing after it was always dropped, because "I agree" and "I
# see" are talk. That also dropped "I retired", "I got divorced last year"
# ("last year" was not counted as an argument) and "I'm engaged!".

@pytest.mark.parametrize("turn,want", [
    ("I got divorced last year.", "Martin Mark got divorced last year"),
    ("I'm engaged!", "Martin Mark is engaged"),
    ("I retired last year.", "Martin Mark retired last year"),
    ("I got laid off.", "Martin Mark got laid off"),
    ("My dad retired.", "Martin Mark's dad retired"),
    ("I cut my hair last week.", "Martin Mark cut Martin Mark's hair last week"),
    ("I moved to Brisbane last year.", "Martin Mark moved to Brisbane last year"),
])
def test_a_life_event_needs_nothing_after_the_verb(checked, turn, want):
    assert want in texts(checked, turn)


@pytest.mark.parametrize("turn", ["I agree.", "I see.", "I know.",
                                  "Thanks, that worked."])
def test_talk_with_nothing_after_the_verb_is_still_dropped(checked, turn):
    assert texts(checked, turn) == []


def test_a_number_is_content_at_any_length(checked):
    assert "Martin Mark is 34" in texts(checked, "I'm 34.")


def test_quit_keeps_the_form_that_was_typed(checked):
    """Stanza read "I quit" as present and the record said "quits", a habit."""
    assert "Martin Mark quit" in texts(checked, "I quit.")
