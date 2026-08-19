"""Entity resolution must merge one person's subjects without ever merging
two different people's."""
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import entity_resolve as ER  # noqa: E402


def _same(mapping, a, b):
    return mapping[a] == mapping[b]


# --- the four real merge cases, mined straight from HaluMem user 10's own
# dialogue and gold memory points ("BrownKaren is my Colleague, Karen is a
# colleague..."). Our extractor lowercases every subject before storage
# (canon_subject), so by the time these reach the store the CamelCase case
# boundary is already gone -- these are the literal strings the real store
# holds, not the CamelCase spelling from the transcript. ------------------

def test_karen_and_brownkaren_merge():
    """The colleague case: a bare first name and the SurnameFirstname
    concatenation the extractor also produced from the same sentence."""
    m = ER.resolve_subjects(["karen", "brownkaren"])
    assert _same(m, "karen", "brownkaren")


def test_donald_and_millerdonald_merge():
    m = ER.resolve_subjects(["donald", "millerdonald"])
    assert _same(m, "donald", "millerdonald")


def test_sophia_and_sophia_mentor_qualifier_merge():
    """A parenthetical qualifier ("(mentor)") is not part of the name --
    stripping it, not treating it as a distinguishing token, is what lets
    this collapse into the plain "sophia" subject."""
    m = ER.resolve_subjects(["sophia", "sophia (mentor)"])
    assert _same(m, "sophia", "sophia (mentor)")


def test_linh_and_nguyen_linh_merge():
    """Unlike the CamelCase cases, this pair is already spaced -- the short
    form is exactly one of the words in the full name."""
    m = ER.resolve_subjects(["linh", "nguyen linh"])
    assert _same(m, "linh", "nguyen linh")


def test_all_four_cases_together_in_one_store():
    """The real shape: all four pairs plus unrelated subjects in the same
    store, resolved in one call."""
    subs = ["karen", "brownkaren", "donald", "millerdonald",
            "sophia", "sophia (mentor)", "linh", "nguyen linh",
            "team", "ai"]
    m = ER.resolve_subjects(subs)
    assert _same(m, "karen", "brownkaren")
    assert _same(m, "donald", "millerdonald")
    assert _same(m, "sophia", "sophia (mentor)")
    assert _same(m, "linh", "nguyen linh")
    # and the four people stay apart from each other
    people = {m["karen"], m["donald"], m["sophia"], m["linh"]}
    assert len(people) == 4


# --- THE SAFETY RULE ------------------------------------------------------

def test_ambiguous_short_name_merges_with_neither_candidate():
    """The whole point of this module: if "karen" could be BrownKaren OR
    SmithKaren, merging into either fabricates a relationship with the wrong
    person. Zero merges beats one wrong merge -- all three subjects must
    stay distinct."""
    m = ER.resolve_subjects(["karen", "brownkaren", "smithkaren"])
    assert m["karen"] != m["brownkaren"]
    assert m["karen"] != m["smithkaren"]
    assert m["brownkaren"] != m["smithkaren"]
    # the ambiguous short name is left as itself, not silently dropped
    assert m["karen"].lower() == "karen"


def test_ambiguous_spaced_full_names_also_block_the_merge():
    """Same guard, spaced-name shape: "alex" could be Alex Johnson or Alex
    Nguyen in the same store."""
    m = ER.resolve_subjects(["alex", "alex johnson", "alex nguyen"])
    assert m["alex"] != m["alex johnson"]
    assert m["alex"] != m["alex nguyen"]
    assert m["alex johnson"] != m["alex nguyen"]


def test_three_way_ambiguity_also_blocks():
    m = ER.resolve_subjects(["donald", "millerdonald", "wilsondonald",
                             "mooredonald"])
    assert m["donald"] == "Donald"


# --- the owner's own name must never be merged into a third party --------

def test_owner_first_name_never_absorbed_into_an_unrelated_subject():
    """Extraction sometimes files the owner's own first name as a bare
    subject (a self-reference artifact). Without this guard it could
    unambiguously suffix-match some unrelated colleague's concatenated name
    and silently attribute the owner's own facts to them."""
    m = ER.resolve_subjects(["michelle", "johnsonmichelle"],
                            owner="Michelle Hernandez")
    assert m["michelle"] != m["johnsonmichelle"]
    assert m["michelle"].lower() == "michelle"


def test_owner_full_name_subject_never_absorbs_a_third_party_either():
    """If the owner's own full name somehow appears as a subject string
    (rather than being unprefixed, the normal case), it must not act as a
    magnet for other subjects either."""
    m = ER.resolve_subjects(["michelle hernandez", "michelle"],
                            owner="Michelle Hernandez")
    assert m["michelle hernandez"] != m["michelle"]


def test_owner_guard_does_not_block_unrelated_merges():
    """The guard is scoped to the owner's own name tokens -- it must not
    make the module over-cautious about everyone else."""
    m = ER.resolve_subjects(["karen", "brownkaren"], owner="Michelle Hernandez")
    assert _same(m, "karen", "brownkaren")


# --- basic contract --------------------------------------------------------

def test_empty_input():
    assert ER.resolve_subjects([]) == {}


def test_single_subject():
    m = ER.resolve_subjects(["sophia"])
    assert m == {"sophia": "Sophia"}


def test_idempotence_same_call_twice():
    subs = ["karen", "brownkaren", "donald", "millerdonald", "team"]
    assert ER.resolve_subjects(subs) == ER.resolve_subjects(subs)


def test_idempotence_on_canonical_output():
    """Feeding the CANONICAL identities back in must not trigger further
    merging -- if it did, the "canonical" form would not actually be a fixed
    point and repeated resolution passes could drift."""
    subs = ["karen", "brownkaren", "donald", "millerdonald", "sophia",
            "sophia (mentor)", "linh", "nguyen linh"]
    first = ER.resolve_subjects(subs)
    canon = sorted(set(first.values()))
    second = ER.resolve_subjects(canon)
    assert second == {c: c for c in canon}


def test_nothing_merges_when_names_are_unrelated():
    """The common case: a handful of genuinely distinct people. No pair
    should collapse."""
    subs = ["karen", "donald", "sophia", "linh", "maria", "lisa"]
    m = ER.resolve_subjects(subs)
    assert len(set(m.values())) == len(subs)


def test_case_and_whitespace_differences_merge():
    m = ER.resolve_subjects(["Karen", "  karen  ", "KAREN"])
    assert len({m["Karen"], m["  karen  "], m["KAREN"]}) == 1


def test_camelcase_split_when_case_survives():
    """If a subject ever DOES retain its original case (not guaranteed by
    the store, but this module should not depend on lowercasing having
    already happened), the case boundary is split directly rather than
    falling back to the suffix heuristic."""
    m = ER.resolve_subjects(["Karen", "BrownKaren"])
    assert _same(m, "Karen", "BrownKaren")


def test_short_name_below_minimum_length_is_not_suffix_matched():
    """A 2-letter first name is too easy to hit by coincidence ("al" is a
    suffix of dozens of unrelated words) -- must not silently merge."""
    m = ER.resolve_subjects(["al", "royal"])
    assert m["al"] != m["royal"]


def test_non_destructive_does_not_mutate_input():
    subs = ["karen", "brownkaren"]
    before = list(subs)
    ER.resolve_subjects(subs)
    assert subs == before


def test_returns_every_distinct_subject_even_when_unmatched():
    subs = ["ai", "team", "friends"]
    m = ER.resolve_subjects(subs)
    assert set(m.keys()) == set(subs)


def test_duplicate_inputs_do_not_break_anything():
    m = ER.resolve_subjects(["karen", "karen", "brownkaren", "brownkaren"])
    assert _same(m, "karen", "brownkaren")


def test_blank_and_none_entries_are_ignored():
    m = ER.resolve_subjects(["karen", "", None, "brownkaren"])
    assert "" not in m
    assert _same(m, "karen", "brownkaren")
