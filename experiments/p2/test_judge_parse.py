"""Regression tests for halumem_run.parse_verdict (the dev-harness/two_judge
local-judge verdict parser).

Two real defects fixed here:
  (a) substring matching let "incorrect" and "not correct" -- both containing
      the literal substring "correct" -- read as the "correct" verdict,
      because "correct" was tested first. Flatters results.
  (b) an unparseable completion was silently coerced to "omission" instead
      of being surfaced, violating the EXPERIMENT_LEDGER.md rule that an
      out-of-set score must not be silently coerced into a valid one.

SCOPE: this parser is used only by the dev harness (halumem_run.py) and
two_judge.py. The official HaluMem harness dispatches on exact equality and
never calls this function -- no banked/official number is touched by this.

    python3 -m pytest experiments/p2/test_judge_parse.py
"""
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(_HERE))
for p in (_HERE, _ROOT):
    if p not in sys.path:
        sys.path.insert(0, p)

import halumem_run as HR


def test_correct():
    assert HR.parse_verdict("correct") == "correct"


def test_correct_with_punctuation_and_case():
    assert HR.parse_verdict("Correct.") == "correct"


def test_hallucination():
    assert HR.parse_verdict("hallucination") == "hallucination"


def test_omission():
    assert HR.parse_verdict("omission") == "omission"


def test_incorrect_is_not_correct():
    """The core defect: "incorrect" contains the substring "correct" but is
    not the "correct" verdict -- and is not a valid label at all, so it must
    come back as the UNPARSEABLE sentinel, never silently as "correct" (the
    old bug) or silently as "omission" (the other old bug)."""
    v = HR.parse_verdict("incorrect")
    assert v != "correct"
    assert v == HR.UNPARSEABLE


def test_incorrect_case_insensitive():
    v = HR.parse_verdict("INCORRECT")
    assert v != "correct"
    assert v == HR.UNPARSEABLE


def test_not_correct_is_not_correct():
    """"not correct" is two separate words; a naive \\bcorrect\\b match would
    still catch the second word as if the judge had said the bare "correct"
    verdict. Must not read as correct."""
    v = HR.parse_verdict("not correct")
    assert v != "correct"
    assert v == HR.UNPARSEABLE


def test_think_block_wrapping_a_verdict():
    txt = "<think>the user said melbourne, gold says melbourne</think>correct"
    assert HR.parse_verdict(txt) == "correct"


def test_think_block_with_negated_correct_inside_and_real_verdict_outside():
    txt = "<think>this is not correct reasoning but</think> hallucination"
    assert HR.parse_verdict(txt) == "hallucination"


def test_empty_output_is_unparseable():
    assert HR.parse_verdict("") == HR.UNPARSEABLE


def test_garbage_output_is_unparseable():
    assert HR.parse_verdict("blah blah nonsense response") == HR.UNPARSEABLE


def test_unparseable_is_not_one_of_the_three_valid_labels():
    assert HR.UNPARSEABLE not in ("correct", "hallucination", "omission")


def test_ambiguous_multiple_labels_is_unparseable():
    """Two whole-word valid labels both appearing is not something we should
    guess between -- surface it instead of picking one via fixed priority."""
    v = HR.parse_verdict("correct hallucination")
    assert v == HR.UNPARSEABLE


def test_two_judge_delegates_to_same_parser():
    """two_judge.py must not carry its own drifted copy of this logic --
    it should score with the identical fixed parser."""
    import two_judge as TJ
    assert TJ._parse_verdict("incorrect") == HR.UNPARSEABLE
    assert TJ._parse_verdict("correct") == "correct"
