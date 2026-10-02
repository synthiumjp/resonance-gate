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
