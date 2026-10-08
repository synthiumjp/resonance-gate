"""The prose filter keeps pasted terminal output away from the parser
without throwing away short first-person statements that happen to be
mostly digits."""
import pytest

from prose import _is_prose, prose_only


@pytest.mark.parametrize("text", ["I'm 34.", "We have 3 kids.", "I'm married."])
def test_a_short_first_person_line_is_prose(text):
    assert _is_prose(text)


@pytest.mark.parametrize("text", ["Swapins:  1245194", "42% 17/40 3.2s",
                                  "My PIN is 4821.", "My PIN is 4821 5512 9930 1123",
                                  "I'm 192.168.1.1",
                                  "```\nprint(1)\n```"])
def test_terminal_output_is_not(text):
    assert not _is_prose(text)


# ---- adversarial review, 2026-10-09 ------------------------------------------

@pytest.mark.parametrize("text,gone", [
    ("what do you make of this\n\nFrom: Tom <t@x.com>\nSubject: Rent\n\nNever pay in cash. "
     "Always pay by the 1st.\n\nTom", "Never pay"),
    ("Can you summarise this?\n\nI live in Paris. I work at Google. Never skip leg day.", "Paris"),
    ("thoughts?\n> Always CC legal on every reply.\n> I live in Paris.", "Paris"),
    ("Proofread this: I am a nurse and I love my job.", "nurse"),
])
def test_pasted_material_without_a_noun_or_quoted_is_not_the_users(text, gone):
    assert gone not in prose_only(text)


@pytest.mark.parametrize("text,kept", [
    ("Following my last message: I live in Leeds, not York.", "Leeds"),
    ("Fix this issue: I can't log in. FYI I live in Leeds.", "Leeds"),
    ("Here are my notes:\nI'm vegan\nI work at Stripe", "vegan"),
    ("Quick question on this thread: my manager said I should switch to Go. I work at Acme.", "Acme"),
])
def test_the_users_own_words_after_an_introduction_are_kept(text, kept):
    assert kept in prose_only(text)
