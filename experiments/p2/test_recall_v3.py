"""recall_v3's contract (e258) -- the score floor and the rank order.

These do NOT load the v3 models. The retriever is stubbed, because what is
being tested is the WIRING: an earlier draft of recall_v3 destroyed the
reranker's ordering by bucketing hits into asserted-then-unconfirmed, and
shipped without a score floor at all (abstention on unseen topics went
8/8 -> 0/8 on the dogfood store). Both are wiring defects a model-loading
test would be too slow to guard.
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
def mem():
    nodes = {"a": _node("a", "is", "allergic to peanuts",
                        "Alex is allergic to peanuts"),
             "b": _node("b", "work_at", "lumen health",
                        "Alex works at Lumen Health")}
    prov = {"c": _node("c", "like", "go", "Alex likes Go", 1, "provisional")}
    return MA.Memory(_FakeGraph(nodes, prov), {})


class _StubIndex:
    pass


def _stub(monkeypatch, mem, results):
    """results: [(node_id, score)] in the order the reranker would return."""
    monkeypatch.setattr(mem, "_index_v3", lambda: _StubIndex())
    allnodes = dict(mem.g.nodes)
    allnodes.update(mem.g.provisional)

    def fake(index, question, **kw):
        out = [(allnodes[nid], sc) for nid, sc in results]
        top_n = kw.get("top_n")
        return out[:top_n] if top_n else out
    monkeypatch.setattr(MA._RV3, "retrieve_facts_v3", fake, raising=False)


def test_everything_below_the_floor_abstains(monkeypatch, mem):
    _stub(monkeypatch, mem, [("a", -9.0), ("b", -9.5)])
    out = mem.recall_v3("what car do i drive?", min_score=-7.7)
    assert out["abstain"] is True
    assert out["found"] is False


def test_a_hit_above_the_floor_is_returned(monkeypatch, mem):
    _stub(monkeypatch, mem, [("a", -1.0)])
    out = mem.recall_v3("what am i allergic to?", min_score=-7.7)
    assert out["abstain"] is False
    assert out["ranked"][0]["text"] == "Alex is allergic to peanuts"


def test_the_floor_filters_per_hit_not_all_or_nothing(monkeypatch, mem):
    _stub(monkeypatch, mem, [("a", -1.0), ("b", -9.0)])
    out = mem.recall_v3("q", min_score=-7.7)
    assert [f["value"] for f in out["ranked"]] == ["allergic to peanuts"]


def test_rank_order_survives_the_tier_split(monkeypatch, mem):
    """The provisional fact outranks both asserted ones: it must stay first
    in `ranked`. Bucketing by tier is what broke this."""
    _stub(monkeypatch, mem, [("c", 5.0), ("a", 1.0), ("b", 0.5)])
    out = mem.recall_v3("q", min_score=-7.7)
    assert [f["value"] for f in out["ranked"]] == [
        "go", "allergic to peanuts", "lumen health"]
    assert out["ranked"][0]["status"] == "unconfirmed-single-mention"


def test_unconfirmed_is_still_reported_separately(monkeypatch, mem):
    _stub(monkeypatch, mem, [("c", 5.0), ("a", 1.0)])
    out = mem.recall_v3("q", min_score=-7.7)
    assert [f["value"] for f in out["unconfirmed"]] == ["go"]
    assert [f["value"] for f in out["asserted"]] == ["allergic to peanuts"]


def test_scores_are_exposed_on_every_returned_fact(monkeypatch, mem):
    _stub(monkeypatch, mem, [("a", -2.25)])
    out = mem.recall_v3("q", min_score=-7.7)
    assert out["ranked"][0]["score"] == -2.25
    assert out["floor"] == -7.7


def test_an_empty_store_abstains_without_touching_the_index(mem):
    empty = MA.Memory(_FakeGraph({}, {}), {})
    assert empty.recall_v3("anything")["abstain"] is True


def test_the_floor_comes_from_the_environment_when_unset(monkeypatch, mem):
    _stub(monkeypatch, mem, [("a", -5.0)])
    monkeypatch.setenv("RG_PROFILE_V3_FLOOR", "-3.0")
    assert mem.recall_v3("q")["abstain"] is True
    monkeypatch.setenv("RG_PROFILE_V3_FLOOR", "-9.0")
    assert mem.recall_v3("q")["abstain"] is False


def test_the_default_floor_is_the_documented_pilot_value():
    assert MA.FLOOR_V3 == -7.7
