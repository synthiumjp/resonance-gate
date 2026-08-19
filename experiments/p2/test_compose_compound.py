"""compose_compound: does grouping+rendering produce natural, correct English
without inventing a second renderer, and does it stay bounded/conservative
where the probe (merge_probe.py) showed unbounded merging degenerates?"""
import os
import re
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import compose_compound as CC  # noqa: E402
import propositions as PR  # noqa: E402

OWNER = "Michelle Hernandez"

# The known bug class (propositions.py's own docstring): a verb template
# ending " to" glued to a gerund value produces "plans to joining a club".
# Every compound this file ever builds must be free of it -- checked in every
# positive test via this helper rather than trusted by construction.
_BROKEN = re.compile(r"\b\w+ to \w+ing\b")


def _assert_clean(sentences):
    for s in sentences:
        assert not _BROKEN.search(s), f"verb/gerund mismatch leaked through: {s!r}"
    return sentences


def f(attr, value, n=1, tier="asserted"):
    return {"attr": attr, "value": value, "n_mentions": n, "tier": tier}


# --------------------------------------------------------------------------
# empty / single input -- the degenerate cases a grouping function must not
# crash or hallucinate a compound out of.
# --------------------------------------------------------------------------

def test_empty_input_yields_no_compounds():
    assert CC.compose([], owner=OWNER) == []


def test_single_fact_yields_no_compounds():
    """One fact is not a sentence to compound -- it is already the whole
    sentence, and render() already owns rendering it alone."""
    assert CC.compose([f("occupation", "founder")], owner=OWNER) == []


# --------------------------------------------------------------------------
# unrelated facts must not merge -- the conservative-default requirement.
# A grouping rule permissive enough to catch everything degenerates to
# merge_probe's "all" strategy, its explicitly-not-a-proposal upper bound.
# --------------------------------------------------------------------------

def test_unrelated_facts_produce_no_compound():
    """Neither attribute is in any family and their values share no tokens:
    two true facts about the same person that simply do not belong in one
    sentence."""
    facts = [f("name", "Michelle Hernandez"),
             f("pet", "a golden retriever named max")]
    assert CC.compose(facts, owner=OWNER) == []


def test_different_subjects_never_merge_even_in_the_same_family():
    """Michelle's motivation and her mentor Sophia's motivation share a
    family but not a grammatical subject -- merging them would attribute
    Sophia's inner life to Michelle."""
    facts = [f("motivation", "cognitive curiosity"),
             f("sophia:motivation", "helping others succeed")]
    assert CC.compose(facts, owner=OWNER) == []


def test_retracted_facts_are_never_composed_as_true():
    """A retracted fact merged into a stated sentence would assert something
    the store no longer believes."""
    facts = [f("hobby", "reading", tier="asserted"),
             f("hobby", "hiking", tier="retracted")]
    # only one non-retracted fact remains -- below the size-2 floor
    assert CC.compose(facts, owner=OWNER) == []


# --------------------------------------------------------------------------
# one compound per attribute family this module touches, each checked for
# grammar (no leaked verb/gerund mismatch) and content (every input value's
# key token survives into the compound).
# --------------------------------------------------------------------------

def test_narrative_family_compounds_motivation_and_value():
    """Mirrors the task's own motivating example: HaluMem gold bundles a
    stated motivation with a stated focus/value into one sentence; our
    atoms emit them as two records of the same family."""
    facts = [f("motivation", "cognitive curiosity for testing boundaries"),
             f("value", "innovative solutions and shared goals")]
    out = _assert_clean(CC.compose(facts, owner=OWNER))
    assert len(out) == 1
    s = out[0]
    assert s.startswith(OWNER)
    assert "cognitive curiosity" in s
    assert "innovative solutions and shared goals" in s


def test_narrative_family_survives_the_gerund_shape_mismatch():
    """The exact case that broke render() naively: "plan" wants an
    infinitive but the extractor's value is a gerund ("joining a technology
    club"), so render() itself falls back to the possessive form. The
    compound must carry that fallback through unmangled, not paper over it
    with a second verb-agreement attempt."""
    facts = [f("plan", "joining a technology club"),
             f("value", "innovative solutions and shared goals")]
    out = _assert_clean(CC.compose(facts, owner=OWNER))
    assert len(out) == 1
    s = out[0]
    assert "joining a technology club" in s
    assert "innovative solutions and shared goals" in s
    assert "plans to joining" not in s


def test_work_family_compounds_occupation_and_employer():
    facts = [f("occupation", "lead consultant"),
             f("employer", "brightpath consultancy")]
    out = _assert_clean(CC.compose(facts, owner=OWNER))
    assert len(out) == 1
    s = out[0]
    assert "works as lead consultant" in s
    assert "works at brightpath consultancy" in s


def test_lifestyle_family_coalesces_a_shared_verb():
    """Two hobbies share the SAME verb ("enjoys"); the natural compound
    states the verb once, not "enjoys reading and enjoys hiking"."""
    facts = [f("hobby", "reading historical fiction"),
             f("hobby", "long distance hiking")]
    out = _assert_clean(CC.compose(facts, owner=OWNER))
    assert len(out) == 1
    s = out[0]
    assert s.count("enjoys") == 1
    assert "reading historical fiction" in s
    assert "long distance hiking" in s


def test_place_family_compounds_location_and_residence():
    """location and residence render through the SAME verb ("lives in"); the
    dedupe path applies here too, not only to hobby-shaped families."""
    facts = [f("location", "hobart"), f("residence", "a harbourside flat")]
    out = _assert_clean(CC.compose(facts, owner=OWNER))
    assert len(out) == 1
    assert out[0].count("lives in") == 1


def test_health_family_mixes_verb_and_possessive_clauses():
    """health_condition has a verb template; mental_health does not, so
    render() falls back to the possessive form for it. The compound must
    join a verb clause to a possessive clause correctly."""
    facts = [f("health_condition", "hypertension, managed with medication"),
             f("mental_health", "stable and improving")]
    out = _assert_clean(CC.compose(facts, owner=OWNER))
    assert len(out) == 1
    s = out[0]
    assert "has the health condition hypertension" in s
    assert f"{OWNER}'s mental health is stable and improving" in s


# --------------------------------------------------------------------------
# the group-size cap -- a run-on sentence of every family member helps
# nothing (merge_probe's "all" strategy is the degenerate case this guards
# against).
# --------------------------------------------------------------------------

def test_group_size_is_capped_and_the_overflow_fact_is_dropped_not_merged():
    """Four mutually-linkable hobbies: the cap (3) means the fourth cannot
    join the first group, and on its own (group size 1) it is not emitted
    as a compound at all -- it stays an atom, which is the caller's job, not
    this function's."""
    facts = [f("hobby", "pottery", n=4), f("hobby", "chess", n=3),
             f("hobby", "gardening", n=2), f("hobby", "cycling", n=1)]
    out = _assert_clean(CC.compose(facts, owner=OWNER, cap=3))
    assert len(out) == 1
    s = out[0]
    for kept in ("pottery", "chess", "gardening"):
        assert kept in s
    assert "cycling" not in s


def test_cap_is_configurable():
    facts = [f("hobby", "pottery"), f("hobby", "chess"),
             f("hobby", "gardening"), f("hobby", "cycling")]
    out = _assert_clean(CC.compose(facts, owner=OWNER, cap=2))
    # two groups of 2 rather than one group of 3 + a dropped singleton
    assert len(out) == 2
    all_text = " ".join(out)
    for v in ("pottery", "chess", "gardening", "cycling"):
        assert v in all_text


# --------------------------------------------------------------------------
# lexical-overlap linking across DIFFERENT families -- the third signal.
# --------------------------------------------------------------------------

def test_cross_family_facts_link_on_shared_value_tokens():
    """"goal" and "activity" are different families, but sharing >=2
    content tokens in their values is the same evidence merge_probe's
    by_overlap used -- a real cross-family relation, not noise."""
    facts = [f("goal", "expand the consultancy into new markets"),
             f("activity", "researching new consultancy markets weekly")]
    out = _assert_clean(CC.compose(facts, owner=OWNER))
    assert len(out) == 1


def test_owner_name_tokens_do_not_manufacture_a_spurious_link():
    """Every rendered fact about the owner would otherwise share the owner's
    name tokens with every other -- granularity.py's exact caution. Without
    stripping them, unrelated facts would falsely appear to overlap by
    >=2 tokens whenever the owner's full name is folded into a value."""
    facts = [f("belief", "Michelle Hernandez trusts her own judgment"),
             f("pet", "Michelle Hernandez's cat is named Hernandez Jr")]
    assert CC.compose(facts, owner=OWNER) == []


# --------------------------------------------------------------------------
# determinism -- required by the spec, and by anything measuring a fixed
# coverage number against it.
# --------------------------------------------------------------------------

def test_composition_is_deterministic():
    facts = [f("motivation", "curiosity"), f("value", "honesty and trust"),
             f("occupation", "founder"), f("employer", "acme corp")]
    a = CC.compose(facts, owner=OWNER)
    b = CC.compose(facts, owner=OWNER)
    assert a == b


def test_no_owner_falls_back_to_the_user_without_crashing():
    facts = [f("motivation", "curiosity"), f("value", "honesty and trust")]
    out = _assert_clean(CC.compose(facts, owner=None))
    assert len(out) == 1
    assert out[0].startswith("The user")
