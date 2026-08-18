"""A group is not a person, and an employer is not a job title.

Both defects shipped in user 10's store and no metric could see them:
"Ai works as empathetic interaction", "Michelle Hernandez works as apple".
"""
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import run_profile_full as PF  # noqa: E402


def test_non_person_subject_cannot_hold_a_personal_attribute():
    for subj in ("Ai", "Team", "friends", "Colleagues", "Society"):
        assert PF.reject_subject_attr(subj, "occupation"), subj
        assert PF.reject_subject_attr(subj, "age"), subj


def test_real_people_are_untouched():
    for subj in ("Michelle Hernandez", "Sophia", "Alex Johnson", None, ""):
        assert not PF.reject_subject_attr(subj, "occupation"), subj


def test_non_personal_attributes_on_groups_are_kept():
    """Rejecting everything about a group would drop real context. Only the
    crossing is corrupt: "Ai's age is 45" is nonsense, "team dynamic is
    collaborative" is merely unexciting."""
    assert not PF.reject_subject_attr("team", "dynamic")
    assert not PF.reject_subject_attr("friends", "activity")


def test_organisations_are_reslotted_not_rejected():
    for org in ("apple", "google", "innovative ai corp", "acme labs",
                "foo technologies", "bar ltd"):
        assert PF.is_organization(org), org
        assert PF.reslot_attr("occupation", org) == "employer", org


def test_qualified_company_names_are_still_companies():
    """"google (part-time)" reached the store as an OCCUPATION because the
    test matched bare names only. A qualifier does not stop a company being a
    company."""
    for org in ("google (part-time)", "apple - contract", "acme labs (remote)",
                "innovative ai corp, seattle"):
        assert PF.is_organization(org), org
        assert PF.reslot_attr("occupation", org) == "employer", org


def test_qualifiers_do_not_turn_job_titles_into_companies():
    for job in ("data scientist (part-time)", "founder - ai startup",
                "consultant (remote)", "analyst, contract"):
        assert not PF.is_organization(job), job


def test_real_job_titles_are_left_alone():
    """The failure that would matter: re-slotting a true occupation into
    employer silently empties the job field."""
    for job in ("senior data scientist", "lead data analyst", "freelancer",
                "founder and ceo", "chief visionary officer", "executive",
                "entrepreneur", "part-time role", "mentor", "consultant"):
        assert not PF.is_organization(job), job
        assert PF.reslot_attr("occupation", job) == "occupation", job


def test_reslot_only_touches_job_slots():
    assert PF.reslot_attr("location", "apple") == "location"
    assert PF.reslot_attr("hobby", "acme labs") == "hobby"
