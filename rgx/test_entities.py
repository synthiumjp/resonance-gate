"""Tests for the person registry and mention linking (rgx/entities.py).

These run without stanza -- entities.py operates on already-extracted
records, so the suite is pure python and fast.
"""
import pytest

from rgx.entities import (Registry, attach_relations, build_registry,
                          camel_parts, RELATION_NOUNS)

OWNER = "Martin Mark"


def rec(text, session=0, turn=0):
    return {"text": text, "session": session, "turn": turn}


# ---- A. harvesting relation statements ----------------------------------

def test_harvests_a_relation_from_an_owner_possessive():
    r = build_registry([rec("Martin Mark's friend Susan is supportive")], OWNER)
    assert set(r.people) == {"Susan"}
    assert r.people["Susan"].relation == "friend"


def test_plural_relation_distributes_over_a_conjoined_list():
    r = build_registry(
        [rec("Martin Mark's colleagues Daniel and Joshua offered insights")],
        OWNER)
    assert set(r.people) == {"Daniel", "Joshua"}
    assert r.people["Daniel"].relation == "colleague"
    assert r.people["Joshua"].relation == "colleague"


def test_a_job_title_is_not_a_relation():
    """'director' is a role the person holds, not a relation to the owner."""
    r = build_registry([rec("Martin Mark's director Susan approved it")], OWNER)
    assert r.people == {}


def test_the_owner_is_never_registered_as_a_third_party():
    r = build_registry([rec("Martin Mark's friend Martin is odd")], OWNER)
    assert "Martin" not in r.people


def test_a_bare_name_with_no_relation_statement_is_not_registered():
    r = build_registry([rec("Susan's support inspires Martin Mark")], OWNER)
    assert r.people == {}


def test_receipts_carry_the_session_and_turn_of_the_assertion():
    r = build_registry(
        [rec("Martin Mark's friend Susan is supportive", session=3, turn=7)],
        OWNER)
    assert r.people["Susan"].receipts == [(3, 7)]


# ---- B. the camel-case merge (the unique-name gate on the registry) ------

def test_camel_parts_splits_a_halumem_persona_name():
    assert camel_parts("WilliamsJoshua") == ["Williams", "Joshua"]
    assert camel_parts("Susan") == ["Susan"]


def test_a_bare_name_folds_into_its_unique_camelcase_canonical():
    r = build_registry([
        rec("Martin Mark's Colleague WilliamsJoshua"),
        rec("Martin Mark's colleague Joshua is instrumental"),
    ], OWNER)
    assert set(r.people) == {"WilliamsJoshua"}
    p = r.people["WilliamsJoshua"]
    assert "Joshua" in p.aliases
    assert p.relations["colleague"] == 2       # support merged, not lost


def test_a_bare_name_shared_by_two_canonicals_does_not_fold():
    r = build_registry([
        rec("Martin Mark's colleague WilliamsJoshua"),
        rec("Martin Mark's friend SmithJoshua"),
        rec("Martin Mark's colleague Joshua"),
    ], OWNER)
    assert "Joshua" in r.people          # stayed its own person
    assert r.resolve("Joshua")[1] == "exact"


# ---- C. the resolution cascade ------------------------------------------

def test_exact_beats_everything():
    r = build_registry([rec("Martin Mark's friend Susan is kind")], OWNER)
    person, strategy, conf = r.resolve("Susan")
    assert (person.canonical, strategy, conf) == ("Susan", "exact", 0.95)


def test_alias_resolves_a_bare_first_name_to_its_canonical():
    r = build_registry([rec("Martin Mark's Colleague WilliamsJoshua")], OWNER)
    person, strategy, conf = r.resolve("Joshua")
    assert person.canonical == "WilliamsJoshua"
    assert (strategy, conf) == ("alias", 0.85)


def test_an_ambiguous_mention_is_DECLINED_not_guessed():
    """The whole point of the divergence from arXiv:2603.27277 sec. 3.4:
    where their cascade falls back to fuzzy matching, we decline."""
    r = build_registry([
        rec("Martin Mark's colleague WilliamsJoshua"),
        rec("Martin Mark's friend SmithJoshua"),
    ], OWNER)
    person, strategy, conf = r.resolve("Joshua")
    assert person is None
    assert strategy == "ambiguous"
    assert conf == 0.0


def test_an_unknown_mention_is_declined():
    r = build_registry([rec("Martin Mark's friend Susan is kind")], OWNER)
    assert r.resolve("Gregory") == (None, "unknown", 0.0)


def test_the_owner_is_declined_as_a_mention():
    r = build_registry([rec("Martin Mark's friend Susan is kind")], OWNER)
    assert r.resolve("Martin")[1] == "owner"


def test_no_fuzzy_fallback_exists():
    """A near-miss spelling must NOT resolve."""
    r = build_registry([rec("Martin Mark's friend Susan is kind")], OWNER)
    assert r.resolve("Susana")[0] is None
    assert r.resolve("Suzan")[0] is None


# ---- D. contested relations ---------------------------------------------

def test_a_contested_person_reports_its_split():
    r = build_registry([
        rec("Martin Mark's friend Susan is pivotal"),
        rec("Martin Mark's friend Susan is supportive"),
        rec("Martin Mark's colleague Susan is a source of support"),
    ], OWNER)
    p = r.people["Susan"]
    assert p.contested is True
    assert p.relation == "friend"
    assert p.relation_confidence == pytest.approx(2 / 3)


def test_an_uncontested_person_is_full_confidence():
    r = build_registry([rec("Martin Mark's friend Susan is kind")], OWNER)
    assert r.people["Susan"].relation_confidence == 1.0
    assert r.people["Susan"].contested is False


# ---- E. attachment -------------------------------------------------------

def test_attaches_the_relation_to_a_bare_leading_mention():
    r = build_registry([rec("Martin Mark's friend Susan is supportive")], OWNER)
    out = attach_relations("Susan's support inspires Martin Mark", r, OWNER)
    assert out == "Martin Mark's friend Susan's support inspires Martin Mark"


def test_does_not_double_attach_an_already_related_mention():
    r = build_registry([rec("Martin Mark's friend Susan is supportive")], OWNER)
    text = "Martin Mark's friend Susan is supportive"
    assert attach_relations(text, r, OWNER) == text


def test_only_the_first_mention_of_a_person_is_rewritten():
    r = build_registry([rec("Martin Mark's friend Susan is supportive")], OWNER)
    out = attach_relations("Susan called and Susan left", r, OWNER)
    assert out == "Martin Mark's friend Susan called and Susan left"


def test_a_contested_person_is_left_bare_by_default():
    r = build_registry([
        rec("Martin Mark's friend Susan is pivotal"),
        rec("Martin Mark's colleague Susan is a source of support"),
    ], OWNER)
    text = "Susan's support inspires Martin Mark"
    assert attach_relations(text, r, OWNER) == text


def test_a_contested_person_attaches_when_the_floor_is_lowered():
    r = build_registry([
        rec("Martin Mark's friend Susan is pivotal"),
        rec("Martin Mark's friend Susan is kind"),
        rec("Martin Mark's colleague Susan is a source of support"),
    ], OWNER)
    out = attach_relations("Susan's support helps", r, OWNER,
                           min_confidence=0.6)
    assert out.startswith("Martin Mark's friend Susan's support")


def test_an_unknown_name_is_left_untouched():
    r = build_registry([rec("Martin Mark's friend Susan is kind")], OWNER)
    text = "Gregory's advice was useful"
    assert attach_relations(text, r, OWNER) == text


def test_attachment_is_a_no_op_with_an_empty_registry():
    r = build_registry([], OWNER)
    text = "Susan's support inspires Martin Mark"
    assert attach_relations(text, r, OWNER) == text


# ---- F. the disposition log ---------------------------------------------

def test_the_log_records_every_mention_including_declines():
    r = build_registry([rec("Martin Mark's friend Susan is kind")], OWNER)
    log = []
    attach_relations("Susan met Gregory and Martin Mark", r, OWNER, _log=log)
    by = {e["mention"]: e for e in log}
    assert by["Susan"]["strategy"] == "exact"
    assert by["Gregory"]["strategy"] == "unknown"
    assert by["Martin"]["strategy"] == "owner"


def test_the_log_carries_relation_confidence_and_contest_flag():
    r = build_registry([
        rec("Martin Mark's friend Susan is pivotal"),
        rec("Martin Mark's colleague Susan helps"),
    ], OWNER)
    log = []
    attach_relations("Susan helps", r, OWNER, _log=log)
    assert log[0]["contested"] is True
    assert log[0]["relation_confidence"] == pytest.approx(0.5)
