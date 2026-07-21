"""Query-contract tests: the read interface an LLM connects to must return
corroborated+receipted facts, labeled unconfirmed singles, or an honest
abstain -- and the injection block must carry the do-not-invent rule."""

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from wire import WireGraph
from memory_api import Memory
from test_wire import _fact, _convs


def _memory():
    facts = [
        _fact(41, "location", "melbourne", _convs(*range(10))),
        _fact(25, "occupation", "researcher", _convs(*range(10))),
        _fact(12, "project", "rg", _convs(8, 9, 22, 23)),
    ]
    prov = [_fact(1, "allergy", "penicillin", _convs(30))]
    g = WireGraph.from_facts(facts, n_convs=40, provisional=prov)
    return Memory(g, titles={"c00": "first chat", "c30": "health chat"})


def test_recall_returns_receipted_asserted_and_wired():
    m = _memory()
    r = m.recall("melbourne")
    assert r["found"] and not r["abstain"]
    assert r["asserted"][0]["attribute"] == "location"
    assert r["asserted"][0]["status"] == "corroborated"
    assert r["asserted"][0]["mentions"] == 41
    assert r["asserted"][0]["receipts"], "every fact carries receipts"
    wired = {w["fact"]["attribute"] for w in r["wired"]}
    assert "occupation" in wired
    for w in r["wired"]:
        assert w["via"], "every wired fact carries its edge path"
        for e in w["via"]:
            assert e["shared_conversations"] >= 2


def test_recall_abstains_honestly():
    r = _memory().recall("favourite colour")
    assert r["abstain"] and not r["found"]
    assert "never seen" in r["answer"]


def test_recall_labels_unconfirmed_singles():
    r = _memory().recall("penicillin")
    assert r["found"]
    assert r["asserted"] == []
    assert r["unconfirmed"][0]["status"] == "unconfirmed-single-mention"


def test_profile_is_most_evidenced_first():
    p = _memory().profile()
    assert [f["mentions"] for f in p] == sorted(
        [f["mentions"] for f in p], reverse=True)
    assert all(f["status"] == "corroborated" for f in p)


def test_context_block_is_verbatim_and_rule_bearing():
    m = _memory()
    b = m.context_block(query="melbourne")
    assert "location: melbourne" in b and "x41" in b
    assert "UNKNOWN" in b and "don't know" in b  # the do-not-invent rule
    # abstain -> explicit do-not-invent block, never silence
    b2 = m.context_block(query="favourite colour")
    assert "Nothing stored matches" in b2 and "UNKNOWN" in b2
    # unconfirmed singles are labeled in the block
    b3 = m.context_block(query="penicillin")
    assert "UNCONFIRMED (seen once)" in b3
    # profile block
    b4 = m.context_block()
    assert "corroborated profile" in b4 and "location: melbourne" in b4
