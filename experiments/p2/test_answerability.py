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
