"""Subjectless fragments that open a user turn (rgx.fragments)."""
import pytest

pytest.importorskip("stanza")

from rgx import Extractor


@pytest.fixture(scope="module")
def ex():
    return Extractor(owner_name="Dana Cole", check=True)


def run(ex, text, prev=None):
    ex.reset_world()
    return ex.extract_turn(text, role="user", prev=prev)


@pytest.mark.parametrize("turn,want", [
    ("Still nursing at St Vincent's though.", "Dana Cole is still nursing at St Vincent's"),
    ("Vegetarian now, for about a year.", "Dana Cole is vegetarian now"),
    ("Training for a marathon in May.", "Dana Cole is training for a marathon in May"),
    ("Pregnant!", "Dana Cole is pregnant"),
])
def test_a_fragment_opening_a_turn_is_about_the_speaker(ex, turn, want):
    assert any(r.text.startswith(want) for r in run(ex, turn))


def test_the_record_keeps_the_words_as_typed(ex):
    recs = run(ex, "Still nursing at St Vincent's though.")
    assert recs and recs[0].source == "Still nursing at St Vincent's though."


@pytest.mark.parametrize("turn", ["Looking good!", "Getting there.",
                                  "Working on it.", "Thinking about it.",
                                  "Nothing much.", "Morning!",
                                  "Sounds good, thanks."])
def test_talk_is_not_a_fragment_fact(ex, turn):
    assert run(ex, turn) == []


@pytest.mark.parametrize("prev", ["What does your sister do?", "How is Sam?",
                                  "Is she still there?", "How's the family?",
                                  "How's the baby?", "What's the dog up to?",
                                  "How is mom?", "Tell me about your wife.",
                                  "Here's a draft bio for Anna: she is a nurse.",
                                  "The character is a knight.", "Great. Any news?"])
def test_an_answer_about_someone_else_is_not_about_the_user(ex, prev):
    assert run(ex, "Nursing at St Vincent's.", prev=prev) == []


@pytest.mark.parametrize("prev", [None, "What do you do for work?",
                                  "Are you still working nights?"])
def test_an_answer_to_an_open_question_is(ex, prev):
    assert run(ex, "Nursing at St Vincent's.", prev=prev)


def test_fragments_can_be_switched_off(ex, monkeypatch):
    monkeypatch.setenv("RG_FRAGMENTS", "0")
    assert run(ex, "Still nursing at St Vincent's though.") == []


def test_extract_passes_the_assistant_turn_along(ex):
    ex.reset_world()
    out = ex.extract([{"role": "assistant", "content": "What does your sister do?"},
                      {"role": "user", "content": "Nursing at St Vincent's."}])
    assert out == []


# review 2026-10-02: each of these stored a false fact about the user
@pytest.mark.parametrize("turn", [
    "Married? No.", "Pregnant? Not me.", "Pregnant women should avoid sushi.",
    "Married with Children is my favourite show.", "Divorced dads get less time.",
    "Vegetarian or not, he eats it.", "Pregnant. Just kidding.",
    "Nursing at St Vincent's, my sister.", "Stealing cars is wrong.",
    "Hiring engineers is hard.", "Quoting Shakespeare: Hating the player.",
    "Breaking news: stocks crash.", "Reading your message now.",
    "Sending you the file.",
])
def test_a_sentence_or_a_retraction_is_not_a_fragment_fact(ex, turn):
    assert not any(r.text.startswith("Dana Cole is") for r in run(ex, turn))


def test_a_later_fragment_continues_a_statement_about_the_user(ex):
    recs = run(ex, "I handed in my notice at the cafe. Starting as a paralegal "
                   "at a law firm on Monday.")
    assert any(r.text.startswith("Dana Cole is starting as a paralegal") for r in recs)
    assert any(r.source == "Starting as a paralegal at a law firm on Monday."
               for r in recs)


def test_a_later_fragment_after_someone_else_is_theirs(ex):
    recs = run(ex, "My sister is a nurse. Working nights at the Alfred.")
    assert not any("Dana Cole is working" in r.text for r in recs)


@pytest.mark.parametrize("turn,want", [
    ("Sold the Corolla on Saturday.", "Dana Cole sold the Corolla on Saturday"),
    ("Cancelled the gym membership.", "Dana Cole cancelled the gym membership"),
])
def test_a_past_tense_fragment_is_about_the_speaker(ex, turn, want):
    assert want in [r.text for r in run(ex, turn)]


@pytest.mark.parametrize("turn", ["Sell the Corolla.", "Put the keys away."])
def test_an_imperative_is_not_a_fragment_fact(ex, turn):
    assert run(ex, turn) == []


# review 2026-10-02 (round 2)
@pytest.mark.parametrize("turn", [
    "I'm writing a story about Anna. Married in 1990, divorced in 2000.",
    "I met Sam today. Moved to Paris in May.",
    "I love my dog. Chewed the sofa again.",
])
def test_a_fragment_after_a_sentence_about_someone_else_is_theirs(ex, turn):
    recs = run(ex, turn)
    assert len(recs) <= 1


@pytest.mark.parametrize("prev", ["What would you like me to include in the speech?",
                                  "Can you summarise this?"])
def test_a_fragment_answering_a_task_is_material_not_news(ex, prev):
    assert run(ex, "Worked at Ford for 30 years. Married in 1965.", prev=prev) == []
