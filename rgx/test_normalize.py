"""Parse normalisation (rgx/normalize.py, 2026-10-15): the same facts from
either parser. Each case was a difference between Stanza's combined models
and the EWT-only parser; both must give the facts here."""
import pytest

from rgx import Extractor


@pytest.fixture(scope="module")
def ex():
    return Extractor(owner_name="Dana Cole")


def texts(ex, turn, role="user"):
    ex.reset_world()
    return [r.text for r in ex.extract_turn(turn, role=role)]


@pytest.mark.parametrize("turn, want", [
    ("I never got divorced.", "Dana Cole never got divorced"),
    ("I got divorced.", "Dana Cole got divorced"),
    ("Got promoted to team lead.", "Dana Cole got promoted to team lead"),
    ("They made me a senior designer today, with a pay bump.",
     "Dana Cole was made a senior designer today with a pay bump"),
    ("Rewatched Alien last night, best sci-fi ever made imo.",
     "Dana Cole rewatched Alien last night"),
    ("I'm married.", "Dana Cole is married"),
])
def test_the_fact_whichever_reading(ex, turn, want):
    assert want in texts(ex, turn)


def test_a_state_participle_is_a_state(ex):
    ex.reset_world()
    r = ex.extract_turn("I'm married.", role="user")[0]
    assert (r.kind, r.predicate, r.value) == ("attr", "is", "married")


def test_a_contrast_is_not_part_of_the_object(ex):
    assert texts(ex, "I drink tea, never coffee.") == ["Dana Cole drinks tea"]


def test_neither_nor_negates(ex):
    out = texts(ex, "Neither my wife nor I like horror movies.")
    assert out and all("not like" in t for t in out), out


def test_a_report_of_the_user_keeps_its_subject(ex):
    assert texts(ex, "I remember you mentioning you play the cello.",
                 role="assistant") == ["Dana Cole plays the cello"]


@pytest.mark.parametrize("turn", [
    "They made me a sandwich.",
    "Nursing at St Vincent's, my sister.",
    "Stolen cars are cheap.",
    "Married with Children is my favourite show.",
])
def test_not_a_fact_about_the_user(ex, turn):
    assert not any(t.startswith("Dana Cole") for t in texts(ex, turn))
