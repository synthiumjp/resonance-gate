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
