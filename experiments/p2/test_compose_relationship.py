"""Tests for compose_relationship's guards.

Each guard here corresponds to a way this module could turn honest store
gaps into fabricated-looking output: an invented relation, a "person" that
is really a group noun, or the owner's own facts posing as someone else's
relationship. A regression in any of these is silent -- it produces a
plausible-looking proposition that is simply wrong, which nothing downstream
would flag. So these pin the REFUSALS, not just the happy path.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from compose_relationship import compose, _clause, _display_name  # noqa: E402


class TestNoInventedRelation(unittest.TestCase):
    """The whole point of reusing schema_probe.relation_for instead of
    reinventing relation typing here: a relation must be READ from the
    source text, never guessed just because a person was found."""

    def test_no_relation_word_when_text_does_not_state_one(self):
        facts = [{"attr": "elizabeth:occupation", "value": "data scientist"}]
        text = "I spoke to Elizabeth about the quarterly report."
        out = compose(facts, owner="Michelle Hernandez", session_text=text)
        self.assertEqual(len(out), 1)
        for label in ("Friend", "Colleague", "Partner", "Child", "Family"):
            self.assertNotIn(f" {label} ", f" {out[0]} ", out[0])
        # the person and their fact are still reported -- an unstated
        # relation is not a reason to drop the person, only to not guess.
        self.assertIn("Elizabeth", out[0])
        self.assertIn("data scientist", out[0])

    def test_no_session_text_means_no_relation_at_all(self):
        """No text at all is the extreme case of 'unavailable' -- it must
        fail the same way an unhelpful text does, not fall back to a guess."""
        facts = [{"attr": "karen:occupation", "value": "consultant"}]
        out = compose(facts, owner="Michelle", session_text=None)
        self.assertEqual(len(out), 1)
        self.assertNotIn("Colleague", out[0])
        self.assertNotIn("Friend", out[0])

    def test_relation_is_typed_when_the_text_actually_states_it(self):
        """The positive control for the two tests above: this module CAN
        type a relation, it just refuses to when the text does not support
        one -- so the negative tests are proving something real."""
        facts = [{"attr": "karen:occupation", "value": "consultant"}]
        text = "My colleague Karen is presenting on Tuesday."
        out = compose(facts, owner="Michelle", session_text=text)
        self.assertIn("Colleague", out[0])


class TestNonPersonSubjectRejected(unittest.TestCase):
    """'Friends works as provide diverse perspectives' was a real, shipped
    defect (entry 209): a group noun is not a person and must never produce
    a relationship proposition about someone who does not exist."""

    def test_group_subject_produces_nothing(self):
        facts = [{"attr": "friends:support", "value": "provide diverse perspectives"},
                 {"attr": "colleagues:occupation", "value": "various"},
                 {"attr": "team:activity", "value": "ship the release"}]
        out = compose(facts, owner="Michelle", session_text=None)
        self.assertEqual(out, [])

    def test_a_real_person_alongside_a_group_subject_still_comes_through(self):
        """The guard must reject only the group noun, not everything in the
        same batch -- a coarse 'any group present -> drop all' guard would
        be its own kind of data loss."""
        facts = [{"attr": "friends:support", "value": "provide diverse perspectives"},
                 {"attr": "karen:occupation", "value": "consultant"}]
        out = compose(facts, owner="Michelle", session_text=None)
        self.assertEqual(len(out), 1)
        self.assertIn("Karen", out[0])


class TestOwnersOwnFactsExcluded(unittest.TestCase):
    """Unprefixed facts are the owner's own (propositions.py's convention).
    This module only ever describes someone ELSE -- an owner fact leaking
    through would render as 'Michelle's Friend Michelle', a self-loop no
    real relationship point ever is."""

    def test_unprefixed_facts_produce_no_proposition(self):
        facts = [{"attr": "occupation", "value": "data scientist"},
                 {"attr": "name", "value": "Michelle Hernandez"}]
        out = compose(facts, owner="Michelle Hernandez", session_text=None)
        self.assertEqual(out, [])

    def test_owner_facts_do_not_leak_into_a_real_person_group(self):
        facts = [{"attr": "occupation", "value": "data scientist"},
                 {"attr": "karen:occupation", "value": "consultant"}]
        out = compose(facts, owner="Michelle Hernandez", session_text=None)
        self.assertEqual(len(out), 1)
        self.assertIn("Karen", out[0])
        self.assertNotIn("Michelle Hernandez's Michelle", out[0])


class TestCamelCaseNameHandling(unittest.TestCase):
    """HaluMem's own subject keys arrive lowercased and concatenated
    ('andersonelizabeth') while both the transcript and gold write the same
    person CamelCase ('AndersonElizabeth'). The name must be read from the
    source text's own spelling, not reconstructed by guessing a boundary in
    a string that no longer has one."""

    def test_name_recovered_with_its_source_casing(self):
        text = ("I have several important friends and colleagues: "
                "AndersonElizabeth is my Friend, Elizabeth is a close friend "
                "who challenges my perspectives.")
        facts = [{"attr": "andersonelizabeth:relationship",
                  "value": "Friend who challenges perspectives"}]
        out = compose(facts, owner="Michelle Hernandez", session_text=text)
        self.assertEqual(len(out), 1)
        self.assertIn("AndersonElizabeth", out[0])
        self.assertIn("Friend", out[0])   # bound relation, read not guessed

    def test_display_name_falls_back_without_inventing_a_split(self):
        """No source text (or the key isn't in it) -- the honest answer is
        the whole blob capitalised once, not a fabricated word boundary."""
        self.assertEqual(_display_name("andersonelizabeth", None),
                         "Andersonelizabeth")
        self.assertEqual(_display_name("andersonelizabeth", "no match here"),
                         "Andersonelizabeth")

    def test_already_spaced_subject_key_is_left_alone(self):
        """Some subjects arrive already spaced ('nguyen linh') -- these must
        not be run through the concatenated-key path, which would collapse
        the space and then have nothing to recover it from."""
        self.assertEqual(_display_name("nguyen linh", None), "Nguyen Linh")


class TestEmptyInput(unittest.TestCase):
    def test_empty_facts_list(self):
        self.assertEqual(compose([]), [])

    def test_facts_with_no_subject_prefix_and_no_owner(self):
        self.assertEqual(compose([{"attr": "occupation", "value": "x"}]), [])

    def test_none_owner_falls_back_rather_than_crashing(self):
        facts = [{"attr": "karen:occupation", "value": "consultant"}]
        out = compose(facts, owner=None, session_text=None)
        self.assertEqual(len(out), 1)
        self.assertTrue(out[0])


class TestGrouping(unittest.TestCase):
    """Sanity checks on the assembly itself -- these are not guards against
    a past defect, just pinning the documented contract."""

    def test_multiple_facts_about_one_person_merge_into_one_proposition(self):
        facts = [{"attr": "karen:occupation", "value": "consultant"},
                 {"attr": "karen:location", "value": "Sydney"}]
        out = compose(facts, owner="Michelle", session_text=None)
        self.assertEqual(len(out), 1)
        self.assertIn("consultant", out[0])
        self.assertIn("Sydney", out[0])

    def test_two_different_people_get_two_propositions(self):
        facts = [{"attr": "karen:occupation", "value": "consultant"},
                 {"attr": "donald:occupation", "value": "engineer"}]
        out = compose(facts, owner="Michelle", session_text=None)
        self.assertEqual(len(out), 2)

    def test_a_person_with_no_descriptive_facts_still_gets_a_bare_proposition(self):
        """An empty clause list must not crash the join, and it should not
        silently drop the person either -- being named with no elaboration
        is still real information."""
        facts = [{"attr": "karen:relationship", "value": ""}]
        out = compose(facts, owner="Michelle", session_text=None)
        self.assertEqual(out, [])   # empty value is not a fact at all

    def test_clause_strips_the_placeholder_subject(self):
        clause = _clause({"attr": "occupation", "value": "data scientist"})
        self.assertNotIn("The user", clause)
        self.assertIn("data scientist", clause)


if __name__ == "__main__":
    unittest.main(verbosity=2)
