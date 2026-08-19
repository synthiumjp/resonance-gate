"""Non-person subjects generalise past an exact-word set; person subjects
must not be lost. See person_subject.py's docstring for the asymmetry this
is built around: a wrong rejection permanently loses a real person's facts,
a wrong acceptance costs one junk record a later stage can still drop.
"""
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import person_subject as PS  # noqa: E402


# --- the leaking examples, measured on user 10's real store (entry: this
# module's own docstring) -- reject_subject_attr's exact-word set lets every
# one of these through. --------------------------------------------------

def test_organization_by_name_is_rejected():
    """"Visionary Ai Solutions" is a company BY NAME, not a bare word in any
    exact set -- caught only by reusing run_profile_full.is_organization's
    suffix rule ("solutions")."""
    assert not PS.is_person_subject("Visionary Ai Solutions")


def test_abstract_collective_nouns_are_rejected():
    """"network", "organization", "startup" name a category of thing, never
    one identifiable person."""
    for subj in ("network", "organization", "startup", "community"):
        assert not PS.is_person_subject(subj), subj


def test_plural_role_head_nouns_are_rejected():
    """"Team Members", "Key Stakeholders", "Academic Advisors" share no
    common first word -- an exact-word set on the whole string can never
    catch all three. What they share is the HEAD NOUN (last word), which is
    what this rule actually matches against."""
    for subj in ("Team Members", "Key Stakeholders", "Academic Advisors",
                 "Colleagues"):
        assert not PS.is_person_subject(subj), subj


def test_plural_head_noun_generalises_to_unseen_qualifiers():
    """The whole point of matching the head noun rather than the exact
    phrase: a qualifier this rule has never seen before ("Overseas") still
    gets caught because the noun it modifies ("Partners") is the tell."""
    assert not PS.is_person_subject("Overseas Partners")
    assert not PS.is_person_subject("Founding Investors")


# --- real people must survive ---------------------------------------------

def test_camelcase_merged_names_are_accepted():
    """HaluMem's own writing of a name as one merged token: Surname+Firstname,
    no space, each half capitalised. A rule that doesn't recognise this shape
    has no positive signal to fall back on for these subjects."""
    for subj in ("AndersonElizabeth", "BrownKaren"):
        assert PS.is_person_subject(subj), subj


def test_single_given_names_are_accepted():
    assert PS.is_person_subject("Karen")
    assert PS.is_person_subject("Sophia")


def test_spaced_full_names_are_accepted():
    for subj in ("Nguyen Linh", "Michelle Hernandez", "Alex Johnson"):
        assert PS.is_person_subject(subj), subj


def test_owner_is_accepted():
    """The profile owner's own name, however it is passed, is a person."""
    assert PS.is_person_subject("Michelle Hernandez")


def test_empty_and_none_are_accepted():
    """No subject means a self-fact -- the store owner. There is nothing
    here to reject, and self-facts must never be dropped by this rule."""
    assert PS.is_person_subject(None)
    assert PS.is_person_subject("")
    assert PS.is_person_subject("   ")


def test_honorific_is_accepted():
    assert PS.is_person_subject("Dr. Alvarez")
    assert PS.is_person_subject("Mrs. Kim")


def test_relation_qualified_subject_is_accepted():
    """llm_profile.canon_subject renders "my friend chris" as
    "chris (friend)" -- the relation tag is itself evidence of a specific
    person, not a category."""
    assert PS.is_person_subject("chris (friend)")
    assert PS.is_person_subject("maria (mentor)")


# --- the deliberate accept-by-design case ----------------------------------

def test_ambiguous_unknown_subject_is_accepted_by_design():
    """"Blue Horizon" could be a company's nickname or a person's alias --
    nothing here confidently says either way. The rule is built to ACCEPT on
    genuine uncertainty because a wrong rejection is the expensive error
    (permanent fact loss); a wrong acceptance is one junk record a later
    stage can still drop. This is not a gap in the rule, it is the design."""
    assert PS.is_person_subject("Blue Horizon")


# --- the attribute-evidence signal, exercised directly ---------------------

def test_org_only_attributes_reject_a_name_the_word_rules_missed():
    """A subject whose NAME gives no verdict (no org suffix, not an abstract
    noun, no person shape) but whose STORED FACTS look like a company's --
    this is the generalising case the word-only rules cannot reach."""
    assert not PS.is_person_subject("blueleaf", facts=["industry", "headcount"])


def test_person_only_attributes_are_never_overridden_by_absence_of_shape():
    """age/birth_date/gender are strong person evidence even for a subject
    whose name shape alone was inconclusive."""
    assert PS.is_person_subject("nightowl93", facts=["age", "gender"])


def test_positive_name_shape_shields_attribute_evidence():
    """A real person's name is trusted over noisy attribute data: even if
    her subject somehow carried a stray org-shaped attribute, the name
    itself already settles it. Attribute evidence only gets consulted when
    the name is inconclusive (see module docstring, signal 4 vs signal 5)."""
    assert PS.is_person_subject("Michelle Hernandez", facts=["industry"])


def test_facts_accepts_dicts_and_prefixed_attrs():
    """The store's fact dicts carry a 'subject:attr' key sometimes; the
    bare attribute must still be read out of it."""
    facts = [{"attribute": "sophia:industry"}, {"attribute": "sophia:headcount"}]
    assert not PS.is_person_subject("brightline", facts=facts)


# --- signals that must not fire on real content -----------------------------

def test_non_person_exact_words_still_covered():
    """The old baseline's bare-word set must still work -- this rule is a
    superset, not a replacement that regresses the easy cases."""
    for subj in ("Ai", "Team", "friends", "Colleagues", "Society"):
        assert not PS.is_person_subject(subj), subj


def test_qualified_organization_names_still_rejected():
    """A qualifier does not turn a company into a person, matching
    run_profile_full's own "google (part-time)" case."""
    assert not PS.is_person_subject("Innovative AI Corp, Seattle")
    assert not PS.is_person_subject("Acme Labs (remote)")


def test_surname_ending_in_s_is_not_caught_by_the_plural_rule():
    """The plural-role rule matches a curated vocabulary, not "ends in s" --
    a real surname must never be caught by spelling alone."""
    assert PS.is_person_subject("Chris Evans")
    assert PS.is_person_subject("Jones")
    assert PS.is_person_subject("Williams")
