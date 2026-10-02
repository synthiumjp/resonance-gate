"""Supersession must resolve changing attributes without discarding knowledge."""
import os

import pytest
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import currency as C  # noqa: E402


def _job(v, s):
    return {"attr": "occupation", "value": v, "session": s}


def test_latest_value_wins_for_single_valued_attributes():
    facts = [_job("senior data scientist", 1), _job("lead data analyst", 3),
             _job("chief visionary officer", 56)]
    cur = C.current(facts)
    assert [f["value"] for f in cur] == ["chief visionary officer"]


def test_history_is_kept_not_deleted():
    """"Where did I work before?" is the same data read the other way. A
    memory that drops superseded values cannot answer it."""
    facts = [_job("senior data scientist", 1), _job("lead data analyst", 3),
             _job("chief visionary officer", 56)]
    hist = C.history(facts, "occupation")
    assert [v for v, _, _ in hist] == ["senior data scientist",
                                       "lead data analyst",
                                       "chief visionary officer"]
    assert [c for _, _, c in hist] == [False, False, True]
    assert all(f.get("superseded_by") is not None
               for f in C.resolve(facts) if not f["current"])


def test_restating_is_distinguished_from_superseding():
    """They mean opposite things about confidence: a repeat is corroboration,
    a change is revision. Collapsing them would make a fact look revised every
    time the user mentioned it again."""
    facts = [_job("freelancer", 29), _job("freelancer", 31), _job("founder", 39)]
    r = C.resolve(facts)
    assert r[0]["restated_by"] == 1 and r[0]["superseded_by"] is None
    assert r[1]["superseded_by"] == 2 and r[1]["restated_by"] is None


def test_multi_valued_attributes_all_survive():
    """The dangerous failure: applying 'latest wins' to hobbies would leave a
    person with exactly one hobby. Over-eager supersession loses data; a
    missed one only leaves clutter, so the default must be to accumulate."""
    facts = [{"attr": "hobby", "value": "puzzle games"},
             {"attr": "hobby", "value": "strategy games"},
             {"attr": "belief", "value": "data predicts behaviour"},
             {"attr": "belief", "value": "collaboration matters"}]
    assert len(C.current(facts)) == 4


def test_repeating_the_same_value_is_not_a_change():
    facts = [_job("freelancer", 29), _job("Freelancer", 31), _job("freelancer", 33)]
    cur = C.current(facts)
    assert len(cur) == 1 and cur[0]["session"] == 33


def test_subjects_are_scoped_independently():
    """Michelle changing jobs must not supersede her mentor's job."""
    facts = [{"attr": "occupation", "value": "data scientist"},
             {"attr": "sophia:occupation", "value": "mentor"},
             {"attr": "occupation", "value": "founder"}]
    cur = C.current(facts)
    vals = sorted(f["value"] for f in cur)
    assert vals == ["founder", "mentor"]


def test_history_is_scoped_to_one_subject():
    """Without scoping, a mentor's job lands in the owner's career timeline --
    which is exactly how the first version read."""
    facts = [{"attr": "occupation", "value": "data scientist", "session": 1},
             {"attr": "sophia:occupation", "value": "mentor", "session": 5},
             {"attr": "occupation", "value": "founder", "session": 39}]
    owner = C.history(facts, "occupation")
    assert [v for v, _, _ in owner] == ["data scientist", "founder"]
    assert C.history(facts, "occupation", subject="sophia") == [
        ("mentor", 5, True)]


def test_non_person_subjects_are_identifiable():
    for bad in ("Ai", "Team", "friends", "Colleagues"):
        assert C.is_non_person_subject(bad), bad
    for ok in ("Michelle Hernandez", "Sophia", "Alex Johnson"):
        assert not C.is_non_person_subject(ok), ok


def test_empty_and_single_inputs():
    assert C.current([]) == []
    one = C.current([_job("analyst", 1)])
    assert len(one) == 1 and one[0]["current"]


# --- write-time supersession (W1) -----------------------------------------

def _node(attr, value, sessions):
    return {"id": f"{attr}={value}", "attr": attr, "value": value,
            "convs": {f"s{i}": f"2025-01-{i+1:02d}" for i in sessions}}


def test_mark_current_supersedes_by_latest_session():
    nodes = [_node("occupation", "senior data scientist", [1]),
             _node("occupation", "lead data analyst", [3]),
             _node("occupation", "chief visionary officer", [56])]
    n = C.mark_current(nodes)
    assert n == 2
    cur = [x for x in nodes if x["current"]]
    assert [x["value"] for x in cur] == ["chief visionary officer"]
    assert all(x["superseded_by"] == "occupation=chief visionary officer"
               for x in nodes if not x["current"])


def test_mark_current_is_subject_scoped():
    """The mentor changing jobs must not supersede the owner's job."""
    nodes = [_node("occupation", "founder", [39]),
             _node("sophia:occupation", "mentor", [50])]
    C.mark_current(nodes)
    assert all(x["current"] for x in nodes)


def test_mark_current_leaves_multi_valued_attributes_alone():
    nodes = [_node("hobby", "puzzle games", [2]),
             _node("hobby", "strategy games", [40]),
             _node("belief", "data predicts behaviour", [1]),
             _node("belief", "collaboration matters", [30])]
    assert C.mark_current(nodes) == 0
    assert all(x["current"] for x in nodes)


def test_mark_current_handles_non_ordinal_conversation_ids():
    """run_wire/memops paths use real uuids, which carry no session order --
    the date must carry it instead of everything collapsing to one bucket."""
    a = {"id": "city=hobart", "attr": "city", "value": "hobart",
         "convs": {"abc-123": "2024-01-01"}}
    b = {"id": "city=sydney", "attr": "city", "value": "sydney",
         "convs": {"def-456": "2025-06-01"}}
    C.mark_current([a, b])
    assert b["current"] and not a["current"]


def test_mark_current_is_idempotent():
    nodes = [_node("city", "hobart", [1]), _node("city", "sydney", [9])]
    first = C.mark_current(nodes)
    second = C.mark_current(nodes)
    assert first == 1 and second == 1
    assert sum(1 for x in nodes if x["current"]) == 1


def test_mark_current_on_a_single_node_changes_nothing():
    nodes = [_node("occupation", "analyst", [4])]
    assert C.mark_current(nodes) == 0
    assert nodes[0]["current"] and nodes[0]["superseded_by"] is None


# --- state-slot aliasing (W2a) --------------------------------------------

def test_aliases_group_one_concept_spelled_many_ways():
    """Six slot names for physical health, all current and contradictory, was
    the real reason W1 fired on 22 of 1270 nodes (e214)."""
    nodes = [_node("physical_condition", "normal, no chronic diseases", [1]),
             _node("health_status", "hypertension managed", [30]),
             _node("health_condition", "chronic disease", [55])]
    C.mark_current(nodes)
    cur = [x for x in nodes if x["current"]]
    assert len(cur) == 1 and cur[0]["value"] == "chronic disease"


def test_a_slot_naming_itself_past_can_never_win():
    """"I used to work at Google", said late, must not become the current
    employer. The extractor already told us it is old -- in the slot name."""
    nodes = [_node("employer", "innovative ai corp", [10]),
             _node("former_employer", "google", [56])]
    C.mark_current(nodes)
    cur = [x for x in nodes if x["current"]]
    assert len(cur) == 1 and cur[0]["value"] == "innovative ai corp"


def test_past_only_group_still_yields_something():
    """If every value is past-marked we must not return an empty answer."""
    nodes = [_node("former_employer", "apple", [1]),
             _node("previous_employer", "google", [9])]
    C.mark_current(nodes)
    assert sum(1 for x in nodes if x["current"]) == 1


def test_narrative_slots_are_NOT_aliased():
    """motivation holds 233 values for one user; merging narrative slots would
    make supersession actively wrong."""
    for a in ("motivation", "value", "belief", "plan", "goal",
              "motivation_strategy", "routine", "habit", "health_habit",
              "health_concern", "health_choice"):
        canon, _ = C.canon_state_attr(a)
        assert canon not in C.SINGLE_VALUED, f"{a} -> {canon} must stay multi-valued"
    nodes = [_node("motivation", "curiosity", [1]),
             _node("motivation_strategy", "growth", [40])]
    C.mark_current(nodes)
    assert all(x["current"] for x in nodes)


def test_mental_and_physical_health_do_not_merge():
    nodes = [_node("physical_health", "stable", [1]),
             _node("mental_health", "positive", [2])]
    C.mark_current(nodes)
    assert all(x["current"] for x in nodes)


def test_canon_state_attr_reports_past_without_renaming_the_store():
    assert C.canon_state_attr("former_employer") == ("employer", True)
    assert C.canon_state_attr("employer") == ("employer", False)
    assert C.canon_state_attr("health_status") == ("health_condition", False)
    assert C.canon_state_attr("wholly_unknown_slot") == ("wholly_unknown_slot", False)


def test_a_genuine_tie_leaves_both_current():
    """Two values in the SAME session with the same evidence: we do not know
    which is current. Picking by list order chose a job duty over "chief
    visionary officer" on the real store."""
    a = _node("occupation", "chief visionary officer", [56])
    b = _node("occupation", "enhancing decision-making", [56])
    C.mark_current([a, b])
    assert a["current"] and b["current"]


def test_corroboration_breaks_a_same_session_tie():
    a = dict(_node("occupation", "chief visionary officer", [56]), n_mentions=3)
    b = dict(_node("occupation", "enhancing decision-making", [56]), n_mentions=1)
    C.mark_current([a, b])
    assert a["current"] and not b["current"]


def test_recency_still_beats_corroboration_across_sessions():
    """A well-corroborated OLD value must not outrank a newer one -- that is
    the whole point of supersession."""
    a = dict(_node("occupation", "data scientist", [1]), n_mentions=9)
    b = dict(_node("occupation", "founder", [40]), n_mentions=1)
    C.mark_current([a, b])
    assert b["current"] and not a["current"]


def test_the_current_node_records_what_it_replaced():
    """Retrieval returns the CURRENT node and ranks the old value far lower,
    so old->new alone hides the pair from every reader. "updated X from A to
    B" needs A on the node that actually surfaces."""
    nodes = [_node("monthly_income", "8210 usd", [1]),
             _node("monthly_income", "8700 usd", [40])]
    C.mark_current(nodes)
    cur = [x for x in nodes if x["current"]][0]
    assert cur["value"] == "8700 usd"
    assert cur["supersedes"] == ["8210 usd"]


def test_supersedes_accumulates_in_order_across_a_chain():
    nodes = [_node("occupation", "analyst", [1]),
             _node("occupation", "lead", [10]),
             _node("occupation", "founder", [40])]
    C.mark_current(nodes)
    cur = [x for x in nodes if x["current"]][0]
    assert cur["value"] == "founder"
    assert cur["supersedes"] == ["analyst", "lead"]


def test_supersedes_prefers_the_retired_node_s_proposition_text():
    """entry 244 follow-up: rgx facts carry a full proposition in "text";
    "supersedes" is read verbatim by callers (eval_rgp2.py's "updated
    from:" annotation), so a bare value like "since becoming the senior
    director" (an ungrammatical fragment out of context) must not leak --
    the retired node's own text should be used when present."""
    old = _node("occupation", "since becoming the senior director", [1])
    old["text"] = "Martin Mark has worked previously with Acme"
    new = _node("occupation", "director of engineering", [40])
    C.mark_current([old, new])
    assert new["current"] and not old["current"]
    assert new["supersedes"] == ["Martin Mark has worked previously with Acme"]


def test_supersedes_falls_back_to_value_when_no_text():
    """LLM-cache facts have no "text" -- unchanged from before."""
    old = _node("occupation", "analyst", [1])
    new = _node("occupation", "founder", [40])
    C.mark_current([old, new])
    cur = [x for x in (old, new) if x["current"]][0]
    assert cur["supersedes"] == ["analyst"]


def test_restatements_do_not_pollute_supersedes():
    nodes = [_node("city", "hobart", [1]), _node("city", "hobart", [5]),
             _node("city", "sydney", [9])]
    C.mark_current(nodes)
    cur = [x for x in nodes if x["current"]][0]
    assert cur["supersedes"] == ["hobart", "hobart"] or cur["supersedes"] == ["hobart"]
    assert "sydney" not in cur["supersedes"]


def test_a_more_detailed_phrasing_is_the_same_fact_not_a_revision():
    """"8700 usd" and "8700 usd monthly" are one fact. Calling it a revision
    made the store report a change that never happened -- on an update metric
    a fabricated update is worse than none."""
    nodes = [_node("income", "8700 usd monthly", [3]),
             _node("monthly_income", "8700 usd", [40])]
    C.mark_current(nodes)
    cur = [x for x in nodes if x["current"]][0]
    assert cur["supersedes"] == [], cur["supersedes"]


def test_overlapping_but_different_values_are_still_a_revision():
    nodes = [_node("monthly_income", "8210 usd", [1]),
             _node("monthly_income", "8700 usd", [40])]
    C.mark_current(nodes)
    cur = [x for x in nodes if x["current"]][0]
    assert cur["supersedes"] == ["8210 usd"]


# ---- 2026-10-02: STATE CHANGES on the parser's own predicate keys ---------

class _G:
    def __init__(self, nodes):
        self.nodes, self.provisional = nodes, {}


def _n(nid, attr, value, conv, text=None, source=None):
    return {"id": nid, "attr": attr, "value": value, "convs": {conv: "2026-10-02"},
            "text": text or value, "source": source or text or value}


ORDER = {"c1": 0, "c2": 1}


def test_a_later_move_replaces_where_you_live():
    """The stranger's test: 'I moved to Brunswick' left 'lives in Fitzroy'
    current, and 'Where do I live?' answered Fitzroy."""
    g = _G({"a": _n("a", "live_in", "in Fitzroy", "c1"),
            "b": _n("b", "move_to", "to Brunswick", "c2")})
    out = C.mark_state_changes(g, order=ORDER)
    assert out == [("a", "b")]
    assert g.nodes["a"]["current"] is False and g.nodes["a"]["ceased"] is True
    assert g.nodes["b"].get("current", True) is True


def test_a_restatement_is_not_a_change():
    g = _G({"a": _n("a", "move_to", "to Brunswick", "c1"),
            "b": _n("b", "live_in", "in Brunswick now", "c2")})
    assert C.mark_state_changes(g, order=ORDER) == []


def test_two_statements_in_one_conversation_are_not_ordered():
    g = _G({"a": _n("a", "live_in", "in Fitzroy", "c1"),
            "b": _n("b", "move_to", "to Brunswick", "c1")})
    assert C.mark_state_changes(g, order=ORDER) == []


def test_also_means_a_second_job_not_a_new_one():
    """Found by the first run of this pass: 'I also joined the Alfred'
    marked St Vincent's 'no longer true'."""
    g = _G({"a": _n("a", "work_as", "as a nurse at St Vincent's", "c1"),
            "b": _n("b", "join", "the Alfred as a ward manager", "c2",
                    source="I also joined the Alfred as a ward manager.")})
    assert C.mark_state_changes(g, order=ORDER) == []


def test_a_new_job_replaces_the_old_employer():
    g = _G({"a": _n("a", "work_at", "at Acme", "c1"),
            "b": _n("b", "get", "a job at Canva", "c2")})
    assert C.mark_state_changes(g, order=ORDER) == [("a", "b")]


def test_a_plan_never_enters_a_family():
    """'thinking about moving to X' is filed under think, not move_to."""
    g = _G({"a": _n("a", "live_in", "in Fitzroy", "c1"),
            "b": _n("b", "think", "about moving to Brunswick", "c2")})
    assert C.mark_state_changes(g, order=ORDER) == []


def test_hobbies_never_participate():
    g = _G({"a": _n("a", "like", "jazz", "c1"),
            "b": _n("b", "like", "techno", "c2")})
    assert C.mark_state_changes(g, order=ORDER) == []


# ---- 2026-10-02: the general inventory -- role, diet, status, age, car, kids

def _pair(a1, v1, a2, v2):
    return _G({"a": _n("a", a1, v1, "c1"), "b": _n("b", a2, v2, "c2")})


@pytest.mark.parametrize("old,new", [
    (("is", "a nurse"), ("is", "a ward manager now")),
    (("work_as", "as a software engineer"), ("become", "a team lead")),
    (("is", "vegetarian"), ("go", "vegan")),
    (("is", "vegetarian"), ("eat", "meat again")),
    (("is", "single"), ("marry_in", "in June")),
    (("is", "34 years old"), ("turn", "35")),
    (("drive", "a Volvo"), ("drive", "a Skoda now")),
    (("drive", "a Volvo"), ("buy", "a Tesla")),
    (("have", "two kids"), ("have", "three kids now")),
    (("is", "married"), ("divorce", "last year")),
    (("is", "single"), ("engage", "")),
    (("is", "married"), ("separate", "")),
    (("is", "a nurse"), ("retire", "last year")),
    (("is", "33"), ("is", "34")),
])
def test_a_later_value_replaces_a_single_valued_state(old, new):
    g = _pair(*old, *new)
    assert C.mark_state_changes(g, order=ORDER) == [("a", "b")]


@pytest.mark.parametrize("old,new", [
    (("is", "a nurse"), ("is", "now a senior nurse at the Alfred")),  # restated
    (("is", "a nurse"), ("is", "a huge fan of jazz")),                 # not a role
    (("is", "a teacher"), ("is", "a runner")),                         # hobby
    (("is", "vegetarian"), ("is", "a morning person")),
    (("drive", "a Volvo"), ("buy", "a new kettle")),
    (("like", "jazz"), ("like", "techno")),                            # multi-valued
    (("is", "a nurse"), ("dad_retire", "")),                           # someone else
    (("is", "divorced"), ("divorce", "")),                             # same value
])
def test_things_that_are_not_a_change_of_the_same_state(old, new):
    assert C.mark_state_changes(_pair(*old, *new), order=ORDER) == []


def test_a_role_and_an_employer_from_one_sentence_change_independently():
    """'I work as a nurse at St Vincent's' states both; a later new role at
    the same place replaces the role and leaves the employer current."""
    g = _G({"a": _n("a", "work_as", "as a nurse at St Vincent's", "c1"),
            "b": _n("b", "is", "a ward manager at St Vincent's now", "c2")})
    assert C.mark_state_changes(g, order=ORDER) == [("a", "b")]


@pytest.mark.parametrize("text,said,attr,value,want", [
    ("Dana Cole is eating keto today", "I'm eating keto today.", "eat", "keto today", True),
    ("Dana Cole is so tired", "I'm so tired.", "is", "so tired", True),
    ("Dana Cole is in Sydney this week", "I'm in Sydney this week.", "is", "in sydney this week", True),
    ("Dana Cole is vegetarian", "I'm vegetarian.", "is", "vegetarian", False),
    ("Dana Cole is busy with the billing service migration", "I'm busy with the billing service migration.", "is", "busy with the billing service migration", False),
    ("Dana Cole works at Acme", "I currently work at Acme.", "work_at", "at acme", False),
])
def test_a_remark_tied_to_its_moment(text, said, attr, value, want):
    assert C.passing(text, said, attr, value) is want


def test_a_passing_remark_never_replaces_a_lasting_state():
    g = _G({"a": _n("a", "live_in", "in fitzroy", "c1"),
            "b": _n("b", "live_in", "in sydney this week", "c2",
                    source="I live in Sydney this week.")})
    assert C.mark_state_changes(g, order=ORDER) == []
