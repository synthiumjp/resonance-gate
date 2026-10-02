"""The prose filter keeps pasted terminal output away from the parser
without throwing away short first-person statements that happen to be
mostly digits."""
import pytest

from prose import _is_prose


@pytest.mark.parametrize("text", ["I'm 34.", "We have 3 kids.", "I'm married.",
                                  "My PIN is 4821."])
def test_a_short_first_person_line_is_prose(text):
    assert _is_prose(text)


@pytest.mark.parametrize("text", ["Swapins:  1245194", "42% 17/40 3.2s",
                                  "```\nprint(1)\n```"])
def test_terminal_output_is_not(text):
    assert not _is_prose(text)
