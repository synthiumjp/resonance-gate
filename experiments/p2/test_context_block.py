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


def test_a_single_mention_is_not_dressed_up_as_repeated(mem):
    """2026-10-02 contract: no UNCONFIRMED nag on every line (a first-hand
    statement is good evidence), but a fact said once must never carry a
    repeat count either."""
    block = mem.context_block()
    for line in block.splitlines():
        if "Lumen Health" in line:
            assert "UNCONFIRMED" not in line, line
            assert "said " not in line and "mentions" not in line, line


def test_repeated_facts_come_first_and_keep_their_count(mem):
    lines = [l for l in mem.context_block().splitlines() if l.startswith("- ")]
    assert "Alex is allergic to peanuts" in lines[0]
    assert "said 2x" in lines[0]
    assert all("said " not in l for l in lines[1:])


def test_the_budget_covers_both_tiers(mem):
    lines = [l for l in mem.context_block(max_facts=2).splitlines()
             if l.startswith("- ")]
    assert len(lines) == 2


def test_the_header_says_what_the_lines_are(mem):
    assert mem.context_block().startswith("[MEMORY: what the user has told you]")


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


def test_the_rules_keep_the_do_not_invent_instruction_and_drop_the_nag(mem):
    """2026-10-02: the old rules told the agent to ask the user to confirm
    every single-mention fact -- nearly every fact, so it nagged. What must
    survive any rewrite is the instruction not to invent."""
    assert "UNKNOWN" in MA._RULES and "don't know" in MA._RULES
    assert "confirm" not in MA._RULES
    assert "(no longer true)" in MA._RULES


# ---- 2026-10-02: the context block quotes what was actually said ----------

def test_a_fact_renders_with_its_verbatim_quote(monkeypatch):
    import memory_api as MA
    monkeypatch.delenv("RG_CONTEXT_QUOTES", raising=False)
    f = {"attribute": "work_at", "value": "acme",
         "text": "Alex Reyes works at Acme",
         "said": "I work at Acme as a backend engineer.",
         "mentions": 1, "receipts": [{"date": "2026-10-02"}]}
    # 2026-10-03: the date and the user's words lead, the summary follows
    assert MA._render_fact(f) == ('[2026-10-02] "I work at Acme as a backend '
                                  'engineer."  (Alex Reyes works at Acme)')
    monkeypatch.setenv("RG_LINE_LAYOUT", "summary")
    assert MA._render_fact(f) == ('Alex Reyes works at Acme  '
                                  '["I work at Acme as a backend engineer." · 2026-10-02]')


def test_a_superseded_fact_says_so(monkeypatch):
    """review 2026-09-05 A4: a fact the user had replaced rendered as current."""
    import memory_api as MA
    monkeypatch.delenv("RG_CONTEXT_QUOTES", raising=False)
    f = {"attribute": "a", "value": "v", "text": "Alex works at Acme",
         "current": False, "mentions": 2, "said": "I work at Acme.",
         "receipts": [{"date": "2026-09-01"}]}
    assert MA._render_fact(f) == ('[2026-09-01] (no longer true) "I work at Acme."'
                                  ' · said 2x  (Alex works at Acme)')


def test_the_quote_can_be_switched_off(monkeypatch):
    import memory_api as MA
    monkeypatch.setenv("RG_CONTEXT_QUOTES", "0")
    f = {"attribute": "a", "value": "v", "text": "T", "said": "S"}
    assert MA._render_fact(f) == "T"   # no quote, and no date/count to show


def test_a_fact_without_a_source_renders_as_before(monkeypatch):
    import memory_api as MA
    monkeypatch.delenv("RG_CONTEXT_QUOTES", raising=False)
    assert MA._render_fact({"attribute": "a", "value": "v", "text": "T"}) == "T"
    assert MA._render_fact({"attribute": "a", "value": "v"}) == "a: v"


def test_a_long_quote_is_truncated_not_dropped(monkeypatch):
    import memory_api as MA
    monkeypatch.delenv("RG_CONTEXT_QUOTES", raising=False)
    out = MA._render_fact({"attribute": "a", "value": "v", "text": "T",
                           "said": "x" * 500})
    assert '..."' in out and out.endswith("(T)") and len(out) < 230
