"""context_block's contract (e261) -- what an AGENT is actually handed.

The no-query path rendered corroborated facts ONLY. People state a self-fact
once, so on a real store that is almost nothing: 12 of 14 nodes in the e258
dogfood store were single-mention and an agent received two lines out of
fourteen facts, while the RULES text explained what an "UNCONFIRMED" line
meant -- a category that path never emitted.
"""
import pytest

import memory_api as MA


class _FakeGraph:
    def __init__(self, nodes, provisional):
        self.nodes = nodes
        self.provisional = provisional
        self.hearsay = {}


def _node(nid, attr, value, text, mentions=2, tier="asserted"):
    return {"id": nid, "attr": attr, "value": value, "text": text,
            "n_mentions": mentions, "convs": {"c1": "2026-09-04"},
            "tier": tier, "toks": set(value.split()), "n_hearsay": 0,
            "current": True, "superseded_by": None}


@pytest.fixture
def mem(monkeypatch):
    nodes = {"a": _node("a", "is", "allergic to peanuts",
                        "Alex is allergic to peanuts")}
    prov = {"b": _node("b", "is", "at lumen health",
                       "Alex is at Lumen Health", 1, "provisional"),
            "c": _node("c", "is", "a backend engineer",
                       "Alex is a backend engineer", 1, "provisional")}
    m = MA.Memory(_FakeGraph(nodes, prov), {})
    monkeypatch.setattr(m, "conflicts", lambda: [])
    return m


def test_single_mention_facts_reach_the_block(mem):
    block = mem.context_block()
    assert "Lumen Health" in block
    assert "backend engineer" in block


def test_they_are_labeled_unconfirmed_not_passed_off_as_corroborated(mem):
    block = mem.context_block()
    for line in block.splitlines():
        if "Lumen Health" in line:
            assert line.startswith("- UNCONFIRMED (seen once):"), line
            assert "mentions" not in line


def test_corroborated_facts_come_first_and_keep_their_count(mem):
    lines = [l for l in mem.context_block().splitlines() if l.startswith("- ")]
    assert lines[0] == "- Alex is allergic to peanuts  (x2 mentions)"
    assert all("UNCONFIRMED" in l for l in lines[1:])


def test_the_budget_covers_both_tiers(mem):
    lines = [l for l in mem.context_block(max_facts=2).splitlines()
             if l.startswith("- ")]
    assert len(lines) == 2


def test_the_header_says_corroborated_only_when_that_is_true(mem):
    assert mem.context_block().startswith("[MEMORY: profile of the user]")
    corr_only = MA.Memory(_FakeGraph(dict(mem.g.nodes), {}), {})
    corr_only.conflicts = lambda: []
    assert corr_only.context_block().startswith(
        "[MEMORY: corroborated profile of the user]")


def test_an_empty_store_says_so_and_still_carries_the_rules(mem):
    empty = MA.Memory(_FakeGraph({}, {}), {})
    empty.conflicts = lambda: []
    block = empty.context_block()
    assert "Nothing is stored about the user yet" in block
    assert "MEMORY RULES" in block


def test_profile_still_returns_corroborated_only(mem):
    """A caller asking for the corroborated profile must keep getting exactly
    that -- provisional facts are a separate call, never merged in."""
    assert [f["value"] for f in mem.profile()] == ["allergic to peanuts"]


def test_provisional_profile_is_ordered_and_bounded(mem):
    assert len(mem.provisional_profile(top=1)) == 1
    assert mem.provisional_profile(top=0) == []


def test_the_rules_no_longer_claim_every_line_is_corroborated(mem):
    """The old text asserted one tier for a block that renders two."""
    assert "The facts above are corroborated" not in mem.context_block()
    assert "CORROBORATED" in MA._RULES and "UNCONFIRMED" in MA._RULES
