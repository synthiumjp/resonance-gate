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
    # 2026-10-03 (stale dev set): getting a thing makes it the user's
    ("Do I have any pets?", "We adopted a kitten called Pickle.", True),
    ("Do I own a car?", "We bought a used Corolla on Saturday.", True),
    ("Do I have any pets?", "Should we adopt a kitten?", False),
    ("Do I own a car?", "I play golf on Sundays.", False),
    ("What instrument do I play?", "I play the cello badly.", True),
    ("What sport do I play?", "I play the cello badly.", False),
    ("What language is the billing service in?", "It is written in Go.", True),
])
def test_answer_type(q, sent, ok):
    t = AT.question_type(q)
    assert t
    assert AT.has_type(sent, t[0], t[1], AT.question_verbs(q, t[0]),
                       possess=AT.is_presence(q)) is ok


# ---- semantic grounding and entity matching (dev paraphrase set, 2026-10-03)

@needs_wn
@pytest.mark.parametrize("q,text,ok", [
    ("Do I have any siblings?", "My sister Priya is flying in from Perth next week", True),
    ("What health conditions do I have?", "Got diagnosed with type 2 diabetes last year", True),
    ("What animal shares my home?", "Mochi, my ginger tabby, knocked the plant off", True),
    ("What did I purchase recently?", "Bought a Dyson vacuum on sale", True),
    ("Do I have any pets?", "We got a puppy called Bruno", True),
    ("Do I have any children?", "I have a dog and a cat at home.", False),
    ("What city was I born in?", "My friend Dev lives in Leiden.", False),
    ("What is my blood type?", "I'm vegetarian and I can't stand cilantro.", False),
    ("When is my birthday?", "Alex Reyes was promoted to senior engineer last month", False),
    ("What is my favourite film?", "Alex Reyes drives a Skoda now", False),
])
def test_semantic_grounding(q, text, ok):
    assert AT.semantic_grounded(q, text) is ok


@pytest.mark.parametrize("text,ent", [
    ("Mum's turning seventy next month", "mother"),
    ("My brother Callum is a plumber in Geelong", "sibling"),
])
def test_kin_words_mention_the_entity(text, ent):
    assert A._mentions(text, ent)


def test_home_is_the_user():
    assert A.read_question("Which suburb is home?") == (None, "suburb")
    assert A.read_question("How old is my mother going to be?") == ("mother", "old")


@pytest.mark.parametrize("q,text,ok", [
    # 2026-10-03 (fresh install on the Mac): a kind of the entity answers
    # "breed"/"make" though the word is never said
    ("What breed is my dog?", "Sam Reed's dog Biscuit is a beagle", True),
    ("What breed is my dog?", "Sam Reed's dog is a golden retriever", True),
    ("What breed is my dog?", "Sam Reed's dog is a puppy", False),   # one step: not a breed
    ("What breed is my dog?", "Sam Reed's dog Biscuit loves the beach", False),
    ("What make is my car?", "Sam Reed's car is a Toyota", True),
    ("What make is my car?", "Sam Reed's car is a sedan", False),
])
def test_a_kind_answers_breed_or_make(q, text, ok):
    r = A.read_question(q)
    assert r and r[1] in ("breed", "make"), r
    assert A.answers({"text": text}, r, owner="Sam Reed") is ok
