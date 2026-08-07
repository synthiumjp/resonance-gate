"""Tests for the gap-directed probe's guards, and for S3c relation typing.

The guards are the whole reason this module is safe to run: a slot-directed
question presupposes the slot has a value, so the model will find one whether
or not the text states it. S3b measured 50% clean precision without them.
These tests pin the guards down rather than the recovery rate, because a
regression in a guard is silent -- it shows up as a plausible wrong value in a
previously empty slot, which nothing downstream can flag.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from schema_probe import (probe_gaps, reject, relation_for,  # noqa: E402
                          split_multi)


class TestRelationTyping(unittest.TestCase):
    """S3c. The probe used to file people under whichever slot it asked
    about, so gold's 'Friend AndersonElizabeth' became `colleagues`."""

    def test_reads_relation_from_text(self):
        for text, value, want in [
            ("I had coffee with my friend Elizabeth Anderson.",
             "Elizabeth Anderson", "friends"),
            ("My colleague Karen Brown is presenting Tuesday.",
             "Karen Brown", "colleagues"),
            ("Karen Brown, a coworker from Sydney, joined us.",
             "Karen Brown", "colleagues"),
            ("Elizabeth and I go way back -- a friend since uni.",
             "Elizabeth", "friends"),
            ("My wife Sarah booked the tickets.", "Sarah", "partner"),
            ("My daughter Maya started school.", "Maya", "children"),
            ("My manager Dave signed it off.", "Dave", "colleagues"),
            ("My younger brother Tom visited.", "Tom", "family"),
        ]:
            self.assertEqual(relation_for(text, value), want, text)

    def test_camelcase_surnames_match_their_source(self):
        """HaluMem writes 'AndersonElizabeth'; the transcript writes
        'Anderson Elizabeth'. Without splitting the case boundary the name is
        never found in the very text it came from, and every relation reads
        as unstated."""
        self.assertEqual(
            relation_for("Anderson Elizabeth is a good friend of mine.",
                         "AndersonElizabeth"), "friends")

    def test_unstated_relation_is_none_not_a_guess(self):
        """The point of S3c. Returning None means 'we found a person and the
        text did not say who they are' -- which is the honest answer, and the
        thing the old code papered over by reusing the probed slot."""
        for text, value in [
            ("I spoke to Elizabeth Anderson about the report.",
             "Elizabeth Anderson"),
            ("Elizabeth was there.", "Elizabeth"),
            # 'same team' / 'we work together' are phrasal, not relation
            # NOUNS. Deliberately not recognised: adding loose phrases to the
            # vocabulary buys recall by reintroducing exactly the invented
            # relation this fix removes. A known, accepted miss.
            ("BrownKaren and I are on the same team at work.", "BrownKaren"),
        ]:
            self.assertIsNone(relation_for(text, value), text)

    def test_distant_relation_word_does_not_bleed(self):
        text = "Elizabeth handled it. " + "filler " * 40 + "My brother called."
        self.assertIsNone(relation_for(text, "Elizabeth"))

    def test_probe_retypes_and_reports(self):
        turns = ["I had lunch with my friend Elizabeth Anderson "
                 "and my coworker Karen Brown."]

        def fake(_prompt):
            return [{"attribute": "colleagues",
                     "value": "Elizabeth Anderson, Karen Brown"}]

        found, report, _rej = probe_gaps([], turns, fake,
                                         owner_tokens={"michelle"})
        by_val = {f["value"]: f["attribute"] for f in found}
        self.assertEqual(by_val.get("Elizabeth Anderson"), "friends")
        self.assertEqual(by_val.get("Karen Brown"), "colleagues")
        # a probe that only ever confirmed what it asked would report 0
        self.assertGreater(sum(r.get("retyped", 0) for r in report), 0)

    def test_person_with_no_stated_relation_is_rejected(self):
        turns = ["I spoke to Elizabeth Anderson about the quarterly report."]

        def fake(_prompt):
            return [{"attribute": "colleagues", "value": "Elizabeth Anderson"}]

        found, _report, rej = probe_gaps([], turns, fake, owner_tokens=set())
        self.assertEqual([f for f in found if f["value"] == "Elizabeth Anderson"], [])
        self.assertTrue(any(r["why"] == "relation not stated" for r in rej))


class TestGuards(unittest.TestCase):
    """S3b's guards -- pinned so a later change cannot quietly drop them."""

    def test_self_reference_rejected(self):
        self.assertEqual(reject("partner", "Michelle", {"michelle", "hernandez"}),
                         "self-reference")

    def test_conflation_rejected_on_singular_slots(self):
        self.assertEqual(
            reject("personality", "Both parents deceased, Married, Two children",
                   set()),
            "conflated (singular slot, list value)")

    def test_multi_slot_keeps_its_list(self):
        self.assertIsNone(reject("friends", "Karen Brown", set()))

    def test_overlong_value_rejected(self):
        self.assertIsNotNone(reject("job_title", " ".join(["word"] * 13), set()))

    def test_split_multi_only_splits_multi_slots(self):
        self.assertEqual(split_multi("colleagues", "Karen Brown, Dave Smith"),
                         ["Karen Brown", "Dave Smith"])
        self.assertEqual(split_multi("job_title", "Head of Data and Analytics"),
                         ["Head of Data and Analytics"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
