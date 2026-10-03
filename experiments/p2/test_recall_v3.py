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


def test_a_low_scoring_hit_is_NOT_filtered_out(monkeypatch, mem):
    """REVERSED IN e272, deliberately. This test used to assert the opposite
    -- that the floor removes each hit below it. That was e258's design and it
    was wrong: the known/unseen separation was only ever measured on the TOP-1
    score, so per-record filtering was doing a job no measurement supported,
    and it discarded true answers that ranked low. The floor now decides
    WHETHER to answer; the re-rank decides the order."""
    # isolates the FLOOR / ORDER semantics from the 2026-10-02 recall
    # margin, which is tested on its own below
    monkeypatch.setenv("RG_RECALL_MARGIN", "-1")
    _stub(monkeypatch, mem, [("a", -1.0), ("b", -9.0)])
    out = mem.recall_v3("q", min_score=-7.83)
    assert [f["value"] for f in out["ranked"]] == [
        "allergic to peanuts", "lumen health"]


def test_rank_order_survives_the_tier_split(monkeypatch, mem):
    """The provisional fact outranks both asserted ones: it must stay first
    in `ranked`. Bucketing by tier is what broke this."""
    # isolates the FLOOR / ORDER semantics from the 2026-10-02 recall
    # margin, which is tested on its own below
    monkeypatch.setenv("RG_RECALL_MARGIN", "-1")
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


def test_the_floor_is_OFF_by_default(monkeypatch, mem):
    """e277 REVERSES e260/e274. The floor was measured INERT with grounding
    on -- sweeping it -9.5..-6.0 left abstention at exactly 9/9 throughout,
    and disabling it recovered a true answer. It was described as one of two
    signals "both pulling weight"; that was true of a 14-node store and
    stopped being true without anyone re-checking. The mechanism stays for
    when grounding proves insufficient at scale."""
    assert MA.FLOOR_V3 is None
    _stub(monkeypatch, mem, [("a", -50.0)])
    monkeypatch.setattr(MA, "_grounded", lambda *a, **k: True)
    monkeypatch.setattr(MA, "_dense_grounded", lambda *a, **k: True)
    assert mem.recall_v3("What am I allergic to?")["abstain"] is False


def test_an_explicit_floor_is_still_honoured(monkeypatch, mem):
    _stub(monkeypatch, mem, [("a", -50.0)])
    assert mem.recall_v3("q", min_score=-7.83)["abstain"] is True


# ---- e272: the floor gates ABSTENTION, the re-rank orders what survives ---

def test_the_floor_is_a_top1_decision_not_a_per_record_filter(monkeypatch, mem):
    """e258 applied the floor to every record. The separation it rests on was
    only ever measured on the TOP-1 score, and per-record filtering silently
    discarded true answers that ranked low -- which is what stopped the e272
    re-rank from being able to promote one."""
    # isolates the FLOOR / ORDER semantics from the 2026-10-02 recall
    # margin, which is tested on its own below
    monkeypatch.setenv("RG_RECALL_MARGIN", "-1")
    _stub(monkeypatch, mem, [("a", -1.0), ("b", -20.0)])
    out = mem.recall_v3("q", min_score=-7.83)
    assert out["abstain"] is False
    assert [f["value"] for f in out["ranked"]] == [
        "allergic to peanuts", "lumen health"]


def test_everything_below_the_floor_still_abstains(monkeypatch, mem):
    _stub(monkeypatch, mem, [("a", -9.0), ("b", -9.5)])
    assert mem.recall_v3("q", min_score=-7.83)["abstain"] is True


def test_the_subject_rerank_promotes_a_subject_position_answer(monkeypatch, mem):
    """"What language is the billing service in?" -- the distractor mentions
    the entity as an OBJECT, the answer has it as SUBJECT."""
    nodes = {"x": _node("x", "work_on", "billing service",
                        "Alex works on the billing service"),
             "y": _node("y", "is", "written in go",
                        "the billing service is written in Go")}
    m = MA.Memory(_FakeGraph(nodes, {}), {})
    monkeypatch.setattr(m, "_index_v3", lambda: object())
    monkeypatch.setattr(MA._RV3, "retrieve_facts_v3",
                        lambda i, q, **kw: [(nodes["x"], -4.0),
                                            (nodes["y"], -9.0)],
                        raising=False)
    out = m.recall_v3("What language is the billing service in?")
    assert out["ranked"][0]["text"] == "the billing service is written in Go"


def test_the_rerank_can_be_switched_off(monkeypatch, mem):
    # isolates this mechanism from the 2026-10-02 answerability check,
    # whose stub texts here do not supply the asked attribute
    monkeypatch.setenv("RG_ANSWERABILITY", "0")
    monkeypatch.setenv("RG_ANSWER_TYPE", "0")
    nodes = {"x": _node("x", "work_on", "billing service",
                        "Alex works on the billing service"),
             "y": _node("y", "is", "written in go",
                        "the billing service is written in Go")}
    m = MA.Memory(_FakeGraph(nodes, {}), {})
    monkeypatch.setenv("RG_SUBJECT_RERANK", "0")
    monkeypatch.setattr(m, "_index_v3", lambda: object())
    monkeypatch.setattr(MA._RV3, "retrieve_facts_v3",
                        lambda i, q, **kw: [(nodes["x"], -4.0),
                                            (nodes["y"], -9.0)],
                        raising=False)
    out = m.recall_v3("What language is the billing service in?")
    assert out["ranked"][0]["text"] == "Alex works on the billing service"


def test_one_incidental_token_is_not_enough_to_promote():
    """"work" appearing in "works from home" is exactly the distractor this
    is meant to demote -- a single content-token match must not fire."""
    assert MA._subject_bonus("Where do I work?",
                             "Alex Reyes works from home") == 0.0
    assert MA._subject_bonus("What language is the billing service in?",
                             "the billing service is written in Go") > 0.0


def test_the_bonus_needs_a_contentful_query():
    assert MA._subject_bonus("What is it?", "anything at all") == 0.0


# ---- e274: grounding is a SECOND abstention signal, ANDed with the floor --

def test_a_high_scoring_but_ungrounded_hit_abstains(monkeypatch, mem):
    """The score floor degrades as the store grows (max-of-N rises with N);
    grounding does not. If no candidate shares a content word with the
    question AND nothing is semantically close, we hold no evidence about the
    topic however it was scored.

    Both routes are stubbed off here deliberately: the stub index carries no
    embeddings, and `_dense_grounded` DEFERS (returns True) when the signal is
    missing -- a missing signal must never be read as evidence of absence. So
    the dense route is disabled explicitly to test the lexical one."""
    _stub(monkeypatch, mem, [("a", 5.0)])          # well above the floor
    monkeypatch.setattr(MA, "_dense_grounded", lambda *a, **k: False)
    assert mem.recall_v3("What is my favourite film?")["abstain"] is True


def test_dense_grounding_alone_is_enough(monkeypatch, mem):
    """Paraphrase: "What is my role at work?" shares no content word with "is
    a backend engineer there", and lexical-only grounding rejected it."""
    # isolates this mechanism from the 2026-10-02 answerability check,
    # whose stub texts here do not supply the asked attribute
    monkeypatch.setenv("RG_ANSWERABILITY", "0")
    monkeypatch.setenv("RG_ANSWER_TYPE", "0")
    _stub(monkeypatch, mem, [("a", -1.0)])
    monkeypatch.setattr(MA, "_grounded", lambda *a, **k: False)
    monkeypatch.setattr(MA, "_dense_grounded", lambda *a, **k: True)
    assert mem.recall_v3("What is my role at work?")["abstain"] is False


def test_a_missing_dense_signal_defers_rather_than_abstains(monkeypatch, mem):
    """An index with no embeddings must not be read as "nothing matches"."""
    _stub(monkeypatch, mem, [("a", -1.0)])
    assert MA._dense_grounded(object(), "anything") is True


def test_a_grounded_hit_is_returned(monkeypatch, mem):
    _stub(monkeypatch, mem, [("a", -1.0)])
    out = mem.recall_v3("What am I allergic to?")
    assert out["abstain"] is False


def test_grounding_can_be_switched_off(monkeypatch, mem):
    # isolates this mechanism from the 2026-10-02 answerability check,
    # whose stub texts here do not supply the asked attribute
    monkeypatch.setenv("RG_ANSWERABILITY", "0")
    monkeypatch.setenv("RG_ANSWER_TYPE", "0")
    _stub(monkeypatch, mem, [("a", 5.0)])
    monkeypatch.setenv("RG_GROUNDING", "0")
    assert mem.recall_v3("What is my favourite film?")["abstain"] is False


def test_a_contentless_query_defers_to_the_floor(monkeypatch, mem):
    """Nothing to ground against is not evidence of absence."""
    _stub(monkeypatch, mem, [("a", -1.0)])
    assert mem.recall_v3("What is it?")["abstain"] is False


# ---- e280: a refusal is an EMPTY RESULT SET decided by a NAMED gate --------

_NO_PAYLOAD = ("ranked", "asserted", "unconfirmed", "wired")


def _assert_empty_refusal(out, gate):
    assert out["abstain"] is True and out["found"] is False
    assert out["gate"] == gate
    for k in _NO_PAYLOAD:
        assert not out.get(k), f"abstention carried a payload under {k!r}"


def test_the_empty_store_gate_is_named_and_empty():
    MA.gate_reset()
    empty = MA.Memory(_FakeGraph({}, {}), {})
    _assert_empty_refusal(empty.recall_v3("anything"), "empty-store")
    assert MA.gate_report()["empty-store"] == 1


def test_the_floor_gate_is_named_and_empty(monkeypatch, mem):
    MA.gate_reset()
    _stub(monkeypatch, mem, [("a", -9.0), ("b", -9.5)])
    out = mem.recall_v3("what car do i drive?", min_score=-7.7)
    _assert_empty_refusal(out, "score-floor")
    assert MA.gate_report()["score-floor"] == 1


def test_the_grounding_gate_is_named_and_empty(monkeypatch, mem):
    MA.gate_reset()
    _stub(monkeypatch, mem, [("a", 5.0)])
    monkeypatch.setattr(MA, "_dense_grounded", lambda *a, **k: False)
    out = mem.recall_v3("What is my favourite film?")
    _assert_empty_refusal(out, "grounding")
    assert MA.gate_report() == {**{g: 0 for g in MA.GATES}, "grounding": 1}


def test_the_no_candidates_gate_is_named_and_empty(monkeypatch, mem):
    MA.gate_reset()
    _stub(monkeypatch, mem, [])
    _assert_empty_refusal(mem.recall_v3("what car do i drive?"), "no-candidates")


def test_a_hit_names_no_gate(monkeypatch, mem):
    monkeypatch.setenv("RG_ANSWER_TYPE", "0")   # the stub record is no car
    _stub(monkeypatch, mem, [("a", 5.0)])
    out = mem.recall_v3("what car do i drive?")
    assert out["abstain"] is False and "gate" not in out


# ---- e281: the owner's name grounds nothing; short plurals stem -----------

def test_the_owners_name_is_not_a_content_word(monkeypatch, mem):
    """Every record starts with the owner's name, so a question that names
    the owner shared a token with every record and grounded on anything."""
    monkeypatch.setitem(mem.g.nodes, "a", {**mem.g.nodes["a"],
                                          "text": "Martin Mark uses Postgres"})
    _stub(monkeypatch, mem, [("a", 5.0)])
    monkeypatch.setattr(MA, "_dense_grounded", lambda *a, **k: False)
    idx = _StubIndex(); idx.owner = "Martin Mark"
    monkeypatch.setattr(mem, "_index_v3", lambda: idx)   # one instance, keeps owner
    out = mem.recall_v3("What is Martin Mark's blood type?")
    _assert_empty_refusal(out, "grounding")


def test_a_real_shared_word_still_grounds_with_the_name_present(monkeypatch, mem):
    # the stub snapshots node texts, so set the text BEFORE stubbing
    monkeypatch.setitem(mem.g.nodes, "a", {**mem.g.nodes["a"],
                                          "text": "Martin Mark uses Postgres"})
    _stub(monkeypatch, mem, [("a", 5.0)])
    monkeypatch.setattr(MA, "_dense_grounded", lambda *a, **k: False)
    idx = _StubIndex(); idx.owner = "Martin Mark"
    monkeypatch.setattr(mem, "_index_v3", lambda: idx)
    assert mem.recall_v3("Does Martin Mark use Postgres?")["abstain"] is False


def test_strip_owner_removes_only_the_name():
    assert MA._strip_owner("What is Alex Reyes's blood type?", "Alex Reyes") == \
        "What is blood type?"
    assert MA._strip_owner("blood type", None) == "blood type"


def test_short_plurals_share_a_stem():
    for a, b in (("dogs", "dog"), ("cars", "car"), ("jobs", "job"), ("gyms", "gym")):
        assert MA._stem(a) == MA._stem(b) == b
    assert MA._stem("bus") == "bus" and MA._stem("gas") == "gas"


# ---- review 2026-10-02: `wired` seeds from rank 1 or not at all ------------

class _WalkGraph:
    def __init__(self, nodes):
        self.nodes = nodes
        self.provisional = {}
        self.seeds = []

    def neighbourhood(self, seeds, **kw):
        self.seeds.append(dict(seeds))
        return []


def test_wired_seeds_from_rank_one_only():
    g = _WalkGraph({"b": {"id": "b", "current": True}})
    m = MA.Memory(g, {})
    m._wired_v3([({"id": "p"}, 9.0), ({"id": "b"}, 1.0)])   # rank 1 provisional
    assert g.seeds == [], "a lower-ranked corroborated hit was used as the seed"
    m._wired_v3([({"id": "b"}, 9.0)])
    assert g.seeds == [{"b": 1.0}]


def test_a_ceased_fact_never_seeds_wired():
    g = _WalkGraph({"b": {"id": "b", "current": False}})
    MA.Memory(g, {})._wired_v3([({"id": "b"}, 9.0)])
    assert g.seeds == []


# ---- 2026-10-02: recall returns what answers, not the whole pool ----------

def test_a_confident_answer_comes_back_alone(monkeypatch, mem):
    monkeypatch.delenv("RG_RECALL_MARGIN", raising=False)
    _stub(monkeypatch, mem, [("a", 5.0), ("b", -7.0), ("c", -8.0)])
    out = mem.recall_v3("what am I allergic to?")
    assert [f["value"] for f in out["ranked"]] == ["allergic to peanuts"]


def test_close_neighbours_are_kept(monkeypatch, mem):
    monkeypatch.delenv("RG_RECALL_MARGIN", raising=False)
    _stub(monkeypatch, mem, [("a", -3.0), ("b", -4.5), ("c", -12.0)])
    out = mem.recall_v3("q")
    assert [f["value"] for f in out["ranked"]] == [
        "allergic to peanuts", "lumen health"]


def test_the_first_answer_is_never_cut(monkeypatch, mem):
    """The re-rank may put a lower RAW score first; the cut is relative to
    the best raw score but never removes the fact the re-rank chose."""
    monkeypatch.delenv("RG_RECALL_MARGIN", raising=False)
    monkeypatch.setenv("RG_SUBJECT_RERANK", "0")
    _stub(monkeypatch, mem, [("a", -9.0), ("b", 2.0)])
    out = mem.recall_v3("q", min_score=-20)
    assert out["ranked"][0]["value"] == "allergic to peanuts"


def test_the_margin_can_be_switched_off(monkeypatch, mem):
    monkeypatch.setenv("RG_RECALL_MARGIN", "-1")
    _stub(monkeypatch, mem, [("a", 5.0), ("b", -7.0), ("c", -8.0)])
    assert len(mem.recall_v3("q")["ranked"]) == 3


# ---- 2026-10-02: answerability -- a fact about the entity is not an answer

def test_a_known_entity_with_an_unknown_attribute_is_refused(monkeypatch, mem):
    monkeypatch.delenv("RG_ANSWERABILITY", raising=False)
    monkeypatch.setitem(mem.g.nodes, "a", {**mem.g.nodes["a"],
                                          "text": "Alex's partner Sam works from home"})
    _stub(monkeypatch, mem, [("a", 5.0)])
    out = mem.recall_v3("What is my partner's job?")
    assert out["abstain"] is True and out["gate"] == "attribute"
    assert [f["text"] for f in out["known_about"]] == ["Alex's partner Sam works from home"]


def test_a_fact_that_supplies_the_attribute_answers(monkeypatch, mem):
    monkeypatch.delenv("RG_ANSWERABILITY", raising=False)
    monkeypatch.setitem(mem.g.nodes, "a", {**mem.g.nodes["a"],
                                          "text": "Alex's partner Lee is a chef"})
    _stub(monkeypatch, mem, [("a", 5.0)])
    assert mem.recall_v3("What is my partner's job?")["abstain"] is False


def test_questions_without_a_checkable_attribute_are_left_alone(monkeypatch, mem):
    import answerability as AN
    for q in ("Do I own any pets?", "What do I eat?", "Who is my manager?",
              "What is my car like?"):
        assert AN.read_question(q) is None, q


def test_the_entity_must_be_the_one_asked_about():
    """'scooter is blue' must not answer 'What colour is my car?'"""
    import answerability as AN
    qr = AN.read_question("What colour is my car?")
    assert not AN.answers({"text": "Alex's scooter is blue"}, qr)
    assert AN.answers({"text": "Alex's car is blue"}, qr)


def test_dense_grounding_counts_only_the_facts_returned():
    """tools/scale_test.py: over the whole store the best similarity rises
    with its size; a close fact that is not returned grounds nothing."""
    import numpy as np
    import memory_api as M

    class Idx:
        facts = [{"t": "a"}, {"t": "b"}]
        emb = np.array([[1.0, 0.0], [0.0, 1.0]])

    class Bi:
        def encode(self, qs, normalize_embeddings=True):
            return np.array([[1.0, 0.0]])
    orig = M._RV3._models
    M._RV3._models = lambda: (Bi(), None)
    try:
        idx = Idx()
        assert M._dense_grounded(idx, "q", threshold=0.9)
        assert M._dense_grounded(idx, "q", threshold=0.9, among=[idx.facts[0]])
        assert not M._dense_grounded(idx, "q", threshold=0.9, among=[idx.facts[1]])
    finally:
        M._RV3._models = orig


def test_marking_later_changes_never_loses_or_crashes():
    """2026-10-03: the first version replaced items with copies and then
    looked the originals up -- ValueError, silently turned into "never
    seen" by the fallback retriever."""
    import memory_api as MA
    mk = lambda i, t, d: {"id": i, "text": t, "said": t, "current": True,
                          "receipts": [{"date": d}]}
    facts = [mk("a", "Alex Reyes has no pets", "2026-01-01"),
             mk("b", "Alex Reyes adopted a kitten", "2026-03-01"),
             mk("c", "Alex Reyes moved to Coburg now", "2026-04-01"),
             mk("d", "Alex Reyes lives in Fitzroy", "2026-02-01")]
    out = MA._mark_later_changes(facts, "Alex Reyes")
    assert sorted(f["id"] for f in out) == ["a", "b", "c", "d"]
    marked = {f["id"]: f.get("changed_later") for f in out}
    assert marked["a"] and marked["d"]
    ids = [f["id"] for f in out]
    assert ids.index(marked["a"]) < ids.index("a")
