"""answerability.answers -- unit cases found by tools/scale_test.py."""
import pytest

import answerability as A


@pytest.mark.parametrize("text,ok", [
    ("Alex Reyes's manager Priya suggested it", False),   # the owner's name
    ("Alex Reyes's manager is Priya Sharma", True),
    ("Priya Sharma runs the team", True),
])
def test_a_last_name_must_follow_the_person(text, ok):
    q = A.read_question("What is Priya's last name?")
    assert A.answers({"text": text}, q, owner="Alex Reyes") is ok


@pytest.mark.parametrize("text,ok", [
    ("Alex Reyes has a cat called Tom", True),
    ("Alex Reyes's cat Tom sleeps a lot", True),
    ("Alex Reyes has a dog and a cat at home", False),
])
def test_a_pet_name(text, ok):
    q = A.read_question("What is my cat's name?")
    assert A.answers({"text": text}, q, owner="Alex Reyes") is ok


def test_an_entity_is_mentioned_only_by_all_its_words():
    q = A.read_question("What language is the billing service in?")
    assert A.answers({"text": "the billing service is written in Go"}, q)
    assert not A.answers({"text": "Quin moved the pricing service to Java"}, q)


def test_what_is_my_x_called_asks_for_a_name():
    q = A.read_question("What is my daughter called?")
    assert q == ("daughter", "name")
    assert A.answers({"text": "Jordan Pike's daughter Maya just turned six"}, q,
                     owner="Jordan Pike")


@pytest.mark.parametrize("q,text", [
    ("What is my wife's name?", "Dana Cole's wife is Priya"),
    ("What is my dentist called?", "Dana Cole's dentist is Dr Lee"),
    ("What language is the Atlas project written in?", "Atlas is written in Go"),
])
def test_review2_answers_restored(q, text):
    assert A.answers({"text": text}, A.read_question(q), owner="Dana Cole")


# ---- answer types (answer_type.py), 2026-10-02 ----------------------------
import answer_type as AT

needs_wn = pytest.mark.skipif(AT._wn() is None, reason="WordNet not installed")


@needs_wn
@pytest.mark.parametrize("q,sent,ok", [
    ("Which food do I dislike?", "I'm vegetarian and I can't stand cilantro.", True),
    ("Which food do I dislike?", "I love tacos.", False),
    ("What is my beverage of choice?", "I switched to tea years ago.", True),
    ("What city was I born in?", "I was born in Leeds.", True),
    ("What city was I born in?", "I went to Lyon in the spring.", False),
    ("Do I have any children?", "My daughter Maya just turned six.", True),
    ("Do I have any children?", "I have a dog and a cat at home.", False),
    ("Do I have any children?", "Send me recipes for the kids.", False),
    ("Do I own any pets?", "I have a dog and a cat at home.", True),
    ("What instrument do I play?", "I play the cello badly.", True),
    ("What sport do I play?", "I play the cello badly.", False),
    ("What language is the billing service in?", "It is written in Go.", True),
])
def test_answer_type(q, sent, ok):
    t = AT.question_type(q)
    assert t
    assert AT.has_type(sent, t[0], t[1], AT.question_verbs(q, t[0]),
                       possess=AT.is_presence(q)) is ok
