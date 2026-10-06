"""Counterexamples from the adversarial review of 2026-10-06. Each rule that
reads more than the words say -- presupposition triggers, decisions from
assent, standing instructions, questions without "?" -- must stay quiet on
these, and still fire on the true cases next to them."""
import pytest

from rgx import Extractor  # noqa: E402

pytest.importorskip("stanza")


@pytest.fixture(scope="module")
def ex():
    return Extractor(owner_name="Dana Cole", check=True)


def texts(ex, turn, prev=None):
    return [r.text for r in ex.extract_turn(turn, prev=prev)]


@pytest.mark.parametrize("turn", [
    "First year at Oxford was hard back in 1998.",
    "Day 3 of the conference was boring.",
    "Day two of Christmas, my sister called.",
    "Five years with Jenny ended in 2010.",
    "Three months with Python was enough, back in college.",
    "Anniversary dinner with Ben was cancelled last year.",
    "Six months into the war, my grandfather left.",
    "Third week as a result, the bug returned.",
    "First day at Hogwarts in the book is magical.",
    "Fourth week as a kid I broke my arm.",
    "Second week at Tesco I quit.",
])
def test_no_current_state_is_presupposed(ex, turn):
    out = texts(ex, turn)
    assert not any(t.endswith(" now") or " now " in t for t in out
                   if "works at" in t or "is with" in t or " is on " in t
                   or "is doing" in t or "is a " in t), out


@pytest.mark.parametrize("user,assistant", [
    ("Perfect, it works now", "I recommend adding a trailing slash to the URL."),
    ("great, thanks, that explains it", "We could use tuples to avoid that."),
    ("yes I did", "Did you restart the server? I suggest restarting."),
    ("ok so what next", "I'd suggest checking line 4."),
    ("yeah that is what I thought", "I'd suggest checking line 4."),
    ("alright, I read it", "I recommend the book Sapiens."),
    ("Let's try again tomorrow, I am tired.", None),
    ("let's add that later", None),
])
def test_not_a_decision(ex, user, assistant):
    assert not any("decided with the assistant" in t for t in texts(ex, user, assistant))


def test_a_restated_acceptance_is_a_decision(ex):
    out = texts(ex, "alright let's switch to Tailwind", "We could keep plain CSS.")
    assert any("decided with the assistant: switch to Tailwind" in t for t in out), out


@pytest.mark.parametrize("turn", [
    "Summarize this paragraph for me.",
    "Don't forget my sister's birthday is Friday.",
    "Always forget my keys.",
])
def test_not_a_standing_instruction(ex, turn):
    assert not any("asked the assistant" in t for t in texts(ex, turn)), texts(ex, turn)


def test_a_reminder_to_act_still_is(ex):
    out = texts(ex, "Don't forget to run the tests before you commit.")
    assert any("asked the assistant" in t for t in out), out
