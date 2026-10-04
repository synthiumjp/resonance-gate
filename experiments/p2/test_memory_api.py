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


def test_correction_deny_removes_fact_and_its_edges():
    m = _memory()
    assert m.recall("researcher")["found"]
    applied = m.apply_corrections([
        {"action": "deny", "attribute": "occupation", "value": "researcher"}])
    assert applied == [("denied", "occupation=researcher")]
    assert m.recall("researcher")["abstain"]          # gone from recall
    for a, b in m.g.edges:                            # and from the wiring
        assert "occupation=researcher" not in (a, b)
    assert m.g.audit()["pass"]                        # graph still sound


def test_correction_confirm_promotes_provisional():
    m = _memory()
    r = m.recall("penicillin")
    assert r["asserted"] == [] and r["unconfirmed"]
    m.apply_corrections([
        {"action": "confirm", "attribute": "allergy", "value": "penicillin"}])
    r = m.recall("penicillin")
    assert r["asserted"][0]["status"] == "owner-confirmed"
    assert r["asserted"][0]["mentions"] == 2          # confirmation is evidence
    assert r["unconfirmed"] == []
    assert "allergy: penicillin" in m.context_block(query="penicillin")
    assert m.g.audit()["pass"]


def _memory_with_hearsay():
    from test_wire import _hearsay_fact
    facts = [_fact(41, "location", "melbourne", _convs(*range(10)))]
    prov = [_fact(1, "allergy", "penicillin", _convs(30))]
    hearsay = [_hearsay_fact(3, "location", "reykjavik", _convs(40, 41, 42))]
    g = WireGraph.from_facts(facts, n_convs=50, provisional=prov, hearsay=hearsay)
    return Memory(g)


def test_hearsay_absent_from_profile_and_asserted_unconfirmed():
    m = _memory_with_hearsay()
    assert all(f["value"] != "reykjavik" for f in m.profile())
    r = m.recall("reykjavik")
    assert r["found"] is True
    assert r["asserted"] == [] and r["unconfirmed"] == []
    assert [f["value"] for f in r["hearsay"]] == ["reykjavik"]
    assert r["hearsay"][0]["status"] == "hearsay"
    assert r["hearsay"][0]["mentions"] == 3


def test_hearsay_absent_from_context_block():
    m = _memory_with_hearsay()
    # recall() found the hearsay match (not abstention), but context_block's
    # asserted/wired/unconfirmed lines must never render an assistant claim
    # as if it were a stored user fact.
    b = m.context_block(query="reykjavik")
    assert "reykjavik" not in b
    assert "UNKNOWN" in b            # do-not-invent rule still present
    b2 = m.context_block()           # profile block (query=None)
    assert "reykjavik" not in b2


def test_context_block_is_verbatim_and_rule_bearing():
    m = _memory()
    b = m.context_block(query="melbourne")
    assert "location: melbourne" in b and "said 41x" in b
    assert "UNKNOWN" in b and "don't know" in b  # the do-not-invent rule
    # abstain -> explicit do-not-invent block, never silence
    b2 = m.context_block(query="favourite colour")
    assert "Nothing stored matches" in b2 and "UNKNOWN" in b2
    # a single mention renders WITHOUT a repeat count (2026-10-02 contract)
    b3 = m.context_block(query="penicillin")
    assert "penicillin" in b3 and "said " not in b3.split("[MEMORY RULES]")[0]
    # profile block. e261: the header claims "corroborated" ONLY when the
    # block is corroborated-only; this fixture has provisional facts too, and
    # they are now rendered (labeled) instead of being dropped, so the header
    # is the broader one and the single-mention facts must be present.
    b4 = m.context_block()
    assert b4.startswith("[MEMORY: what the user has told you]")
    assert "location: melbourne" in b4
    assert "penicillin" in b4      # single-mention facts are rendered too


def test_conflicts_and_clarification():
    """Acquisition-frame clarification hook (entry 137): same-slot evolving
    values surface as an open conflict with an ask; context_block carries it."""
    from wire import WireGraph
    # A GENUINE substitution (apple -> google), a REWORDING that must not be
    # reported as a conflict (entry 154: NLI distinguishes these; the previous
    # version of this fixture used a rewording and asserted it WAS a conflict,
    # which the NLI-confirmed implementation correctly refused), and a
    # single-valued slot with one value.
    facts = [
        (3, "employer", "apple", [("Jan 05, 2025", "s1"), ("Feb 10, 2025", "s2"),
                                  ("Mar 01, 2025", "s3")]),
        (2, "employer", "google", [("Mar 20, 2025", "s4"),
                                   ("Apr 02, 2025", "s5")]),
        (2, "school", "deakin university", [("Jan 05, 2025", "s1")]),
        (2, "school", "deakin uni", [("Feb 01, 2025", "s7")]),
        (2, "city", "melbourne", [("Jan 05, 2025", "s1"), ("Jun 01, 2025", "s6")]),
    ]
    g = WireGraph.from_facts(facts, n_convs=6)
    m = Memory(g)
    cf = m.conflicts()
    attrs = {c["attribute"] for c in cf}
    assert "employer" in attrs          # linked evolving values -> conflict
    assert "city" not in attrs          # single value -> no conflict
    assert "school" not in attrs        # a rewording is not a conflict
    emp = next(c for c in cf if c["attribute"] == "employer")
    assert "Which is current" in emp["ask"]
    assert any("consolidated" in v["evidence"] or "repeated" in v["evidence"]
               for v in emp["values"])
    block = m.context_block()
    assert "MEMORY CONFLICTS" in block and "ASK the user" in block


def test_spacing_evidence_profile():
    import spacing as SP
    nd = {"convs": {"s1": "Jan 05, 2025", "s2": "Mar 01, 2025"}, "n_mentions": 2}
    p = SP.evidence_profile(nd)
    assert p["spacing"] == "spaced" and p["span_days"] > 30
    assert 0.3 < SP.consolidation(nd) <= 1.0
    massed = {"convs": {"s1": "Jan 05, 2025", "s2": "Jan 06, 2025"}, "n_mentions": 2}
    assert SP.evidence_profile(massed)["spacing"] == "massed"
    assert SP.consolidation(massed) < SP.consolidation(nd)


def test_consolidation_receipts_and_lability():
    """Gist nodes must cite >=2 episodes (auditable abstraction) and a new
    uncovered fact in the same slot must return the gist to a labile state."""
    import consolidate as C
    eps = [
        {"id": "e1", "attr": "value", "value": "solitude for recharging",
         "n_mentions": 2, "convs": {"s1": "Jan 05, 2025"}},
        {"id": "e2", "attr": "value", "value": "quiet mornings to think clearly",
         "n_mentions": 1, "convs": {"s2": "Feb 11, 2025"}},
    ]
    g = C.make_gist("value", eps, llm=lambda p: "Values quiet solitude for mental clarity.")
    assert g and g["tier"] == "gist"
    assert len(g["sources"]) == 2 and set(g["sources"]) == {"e1", "e2"}
    assert "PATTERN from 2 memories" in C.format_gist(g)
    # a single episode can never make a gist (no corroboration -> no abstraction)
    assert C.make_gist("value", eps[:1], llm=lambda p: "Anything.") is None
    # a model that finds no pattern must not produce one
    assert C.make_gist("value", eps, llm=lambda p: "NONE") is None
    # reconsolidation: prediction error, not contradiction detection.
    # A fact the gist already predicts leaves it stable...
    C.mark_labile([g], {"attr": "value", "value": "enjoys solitude to recharge"})
    assert g["stale"] is False
    # ...one it does not predict (novel OR contradictory) makes it labile.
    C.mark_labile([g], {"attr": "value", "value": "thrives in loud open offices"})
    assert g["stale"] is True
    # different slot: untouched
    g2 = dict(g, attr="city", stale=False)
    C.mark_labile([g2], {"attr": "value", "value": "anything at all"})
    assert g2["stale"] is False


def test_learned_write_rules():
    """Corrections become write POLICY (entry 140): recurring errors are
    blocked at ingest across surface variants, slot repairs are learned, and
    every block is quarantined rather than destroyed."""
    import write_rules as WR
    corr = [
        {"action": "deny", "attribute": "collaborator", "value": "cacioli"},
        {"action": "retype", "attribute": "tool", "value": "tic tracker",
         "new_attribute": "project"},
    ]
    rules = WR.induce(corr)
    # generalizes across surface forms of the same error
    for v in ("Jon-Paul Cacioli", "JP Cacioli", "dr jp cacioli"):
        assert WR.decide(rules, "collaborator", v)[0] == "deny"
    # slot repair is learned, not hard-coded
    act, det = WR.decide(rules, "tool", "tic_tracker")
    assert act == "retype" and det["new_attribute"] == "project"
    # unrelated writes are untouched
    assert WR.decide(rules, "collaborator", "ada lovelace")[0] == "allow"
    assert WR.decide(rules, "tool", "ripgrep")[0] == "allow"
    # a denied slot is riskier than an untouched one, but not condemned
    assert WR.risk_score(rules, "collaborator") > WR.risk_score(rules, "city")
    assert WR.risk_score(rules, "collaborator") < 1.0
    # amplification: one rule, many blocked recurrences
    recs = [{"f": [{"attribute": "collaborator", "value": "JP Cacioli"}]}] * 4
    st = WR.apply_to_extractions(rules, recs)
    assert st["blocked"] == 4


def test_receipt_operations_are_non_destructive():
    """Receipts as first-class objects (entry 147): every operation retains
    evidence -- decay changes weight, invalidate changes status, split keeps
    both halves."""
    import receipts as RC
    from datetime import datetime
    n = {"id": "x", "attr": "employer", "value": "google",
         "n_mentions": 2, "convs": {"s1": "Jan 05, 2025", "s2": "Mar 01, 2025"}}
    now = datetime(2026, 1, 5)
    # strengthen: new receipt, value untouched, idempotent per conversation
    RC.strengthen(n, "s3", "Jun 01, 2025")
    assert n["n_mentions"] == 3 and n["value"] == "google"
    RC.strengthen(n, "s3", "Jun 01, 2025")
    assert n["n_mentions"] == 3          # same conversation cannot double-count
    # salience: decays with age but never reaches zero, and more receipts win
    s_now = RC.salience(n, now)
    older = {"convs": {"s9": "Jan 05, 2020"}, "n_mentions": 1}
    assert 0 < RC.salience(older, now) < s_now
    # merge: receipts unioned, absorbed wording retained
    m = RC.merge(n, {"id": "y", "attr": "employer", "value": "google inc",
                     "n_mentions": 1, "convs": {"s4": "Jul 01, 2025"}})
    assert len(m["convs"]) == 4 and "google inc" in m["variants"]
    # split: partition preserves every receipt across both halves
    hit, miss = RC.split(m, lambda c, d: d is not None and d.year == 2025)
    assert len(hit["convs"]) + (len(miss["convs"]) if miss else 0) == 4
    # invalidate: retained, flagged, receipts intact
    inv = RC.invalidate(n, "owner denied")
    assert inv["invalid"]["reason"] == "owner denied" and len(inv["convs"]) == 3
    # dynamics: reports aging without changing the store
    d = RC.dynamics([n, older])
    assert d["facts"] == 2 and d["receipts"] == 4 and d["read_as_of"]


def test_render_is_lint_clean_across_the_vocabulary():
    """No (attribute, value) shape may render as broken English.

    The two shipped bugs -- "plans to joining a club", "is motivated by to
    contribute" -- were each a specific verb meeting a specific value shape.
    Pinning those two cases only pins those two cases, and the verb table has
    nineteen entries. This crosses the WHOLE vocabulary with the value shapes
    that occur in real stores and asserts the store_view lint finds nothing,
    so a new verb cannot be added with the same class of defect.
    """
    import sys, os
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import propositions as P
    from store_view import MALFORMED

    shapes = [
        "joining a technology club",          # gerund
        "to contribute to the vision",        # infinitive
        "san jose",                           # bare noun
        "a senior data scientist",            # determiner + noun
        "expand the team",                    # bare verb
        "exploring options and seeking a mentor",
        "being more consistent",
        "that data predicts behaviour",       # clause
        "regular exercise",
    ]
    owner = "Michelle Hernandez"
    bad = []
    for attr in list(P._VERBAL) + ["name", "savings", "custom_attribute"]:
        for value in shapes:
            out = P.render({"attr": attr, "value": value}, owner=owner)
            if not out:
                continue
            for name, rx, why in MALFORMED:
                if rx.search(out + " (provisional)"):
                    bad.append((name, attr, value, out))
    assert not bad, "renderer produces malformed prose:\n" + "\n".join(
        f"  [{n}] {a}/{v!r} -> {o}" for n, a, v, o in bad[:10])


def test_proposition_rendering():
    """Facts render as natural-language propositions (entry 162): the form
    every comparable system stores and the form HaluMem's gold uses."""
    import propositions as P
    owner = "michelle hernandez"
    cases = [
        ({"attr": "name", "value": "michelle hernandez"},
         "The user's name is Michelle Hernandez"),
        ({"attr": "birth_date", "value": "1980-04-20"},
         "Michelle Hernandez's birth date is 1980-04-20"),
        ({"attr": "location", "value": "san jose"},
         "Michelle Hernandez lives in san jose"),
        ({"attr": "employer", "value": "apple"},
         "Michelle Hernandez works at apple"),
        ({"attr": "preference", "value": "black coffee for alertness"},
         "Michelle Hernandez prefers black coffee for alertness"),
        # subject-prefixed attrs keep THEIR subject, not the owner's
        ({"attr": "nguyen linh:contribution", "value": "innovative ideas"},
         "Nguyen Linh's contribution is innovative ideas"),
    ]
    for fact, want in cases:
        assert P.render(fact, owner=owner) == want, (fact, P.render(fact, owner=owner))
    # "plans to to expand" must not double the infinitive
    assert P.render({"attr": "plan", "value": "to expand the team"},
                    owner=owner) == "Michelle Hernandez plans to expand the team"
    # SHAPE MISMATCH -> possessive fallback, never malformed English.
    # Both of these shipped: 69 of user 10's 1014 records (7%) read as
    # "plans to joining a club" or "is motivated by to contribute" before the
    # renderer checked whether the value fit the verb it was being glued to.
    # A gerund cannot follow "plans to"...
    assert P.render({"attr": "plan", "value": "joining a technology club"},
                    owner=owner) == ("Michelle Hernandez's plan is joining a "
                                     "technology club")
    assert P.render({"attr": "goal", "value": "seeking a mentor"},
                    owner=owner) == "Michelle Hernandez's goal is seeking a mentor"
    # ...and an infinitive cannot follow a verb that wants a noun phrase.
    assert P.render({"attr": "motivation", "value": "to contribute to the vision"},
                    owner=owner) == ("Michelle Hernandez's motivation is to "
                                     "contribute to the vision")
    # the well-shaped cases still take the verb template
    assert P.render({"attr": "motivation", "value": "cognitive curiosity"},
                    owner=owner) == "Michelle Hernandez is motivated by cognitive curiosity"
    # nothing the renderer emits may contain these two joins
    for attr, value in (("plan", "joining a club"), ("goal", "exploring options"),
                        ("motivation", "to lead a team"), ("plan", "to ship it")):
        out = P.render({"attr": attr, "value": value}, owner=owner)
        assert " to " + value.split()[0] not in out or not value.startswith("to "), out
        assert "plans to joining" not in out and "motivated by to" not in out, out

    # degenerate input yields nothing rather than malformed prose
    assert P.render({"attr": "", "value": "x"}) == ""
    assert P.render({"attr": "city", "value": ""}) == ""
    # no owner known -> still well-formed
    assert P.render({"attr": "city", "value": "hobart"}).startswith("The user lives in")
    # owner discovery + tier annotation
    facts = [{"attr": "name", "value": "jo blogs", "n_mentions": 3},
             {"attr": "city", "value": "hobart", "n_mentions": 1}]
    assert P.owner_name(facts) == "jo blogs"
    out = P.render_all(facts, owner=P.owner_name(facts), with_tier=True)
    assert out[0].endswith("(confirmed x3)") and out[1].endswith("(mentioned once)")


def test_a_conflict_shows_only_when_the_question_names_its_attribute(monkeypatch):
    """2026-10-04 (LoCoMo dev): "is" in any question matched the attribute
    "is" by substring and printed "I have 5 values for your is"."""
    m = Memory(WireGraph.from_facts([], n_convs=1))
    monkeypatch.setattr(m, "conflicts", lambda: [
        {"attribute": "is", "ask": "I have 5 values for your is"},
        {"attribute": "employer", "ask": "Which employer is current?"}])
    monkeypatch.setattr(m, "_recall_for_context", lambda q: {
        "found": True, "ranked": [{"text": "T", "said": "S", "receipts": [{"date": "2026-01-01"}]}]})
    b = m.context_block("What is my favourite colour?")
    assert "values for your is" not in b and "MEMORY CONFLICTS" not in b
    assert "Which employer is current?" in m.context_block("Who is my employer?")


def test_retrieved_messages_join_the_block_within_its_budget(monkeypatch):
    """2026-10-04 (LoCoMo dev): the user's own messages that match best are
    added for answers no fact holds -- above the verbatim floor, not when
    already shown through a fact, and in place of the lowest-ranked facts."""
    monkeypatch.setenv("RG_EVIDENCE", "facts")   # the fact block's merge
    m = Memory(WireGraph.from_facts([], n_convs=1))
    m.conflicts = lambda: []
    facts = [{"text": f"Sam Lee fact {i}", "said": f"Fact {i}.",
              "receipts": [{"date": f"2026-01-0{i + 1}"}]} for i in range(4)]
    monkeypatch.setattr(m, "_recall_for_context", lambda q: {"found": True, "ranked": facts})
    m.messages_for = lambda q: [
        {"text": "Fact 0.", "date": "2026-01-01", "score": 2.0},          # shown already
        {"text": "The grandma is from Sweden, it was her necklace.",
         "date": "2026-02-01", "score": 1.0, "asked": "Where is she from?"},
        {"text": "Something unrelated entirely here.", "date": "2026-02-02", "score": -9.0}]
    lines = [l for l in m.context_block("Where is my grandma from?", max_facts=4).splitlines()
             if l.startswith("- ")]
    assert len(lines) == 4
    sweden = [l for l in lines if "Sweden" in l]
    assert sweden and "(their words)" in sweden[0] and 'in reply to "Where is she from?"' in sweden[0]
    assert not any("unrelated" in l for l in lines)
    assert sum("Fact 0." in l for l in lines) == 1


def test_messages_block_reads_wider_for_lists_and_notes_links(monkeypatch):
    """2026-10-04 (LoCoMo dev, multi-hop)."""
    monkeypatch.setenv("RG_EVIDENCE", "messages")
    m = Memory(WireGraph.from_facts([], n_convs=1))
    m.conflicts = lambda: []
    asked = []
    msgs = [{"text": f"I tried thing {i} this year.", "date": f"2026-01-{i + 10}",
             "score": 1.0, "conv": None} for i in range(12)]
    msgs.append({"text": "It's been four years since I moved from my home country.",
                 "date": "2026-02-01", "score": 1.0, "conv": None})
    def mf(q, k=3):
        asked.append(k)
        return msgs[-1:] if "move" in q else msgs[:k]
    m.messages_for = mf
    m.links = {"home country": "Sweden"}
    monkeypatch.setattr(m, "_recall_for_context", lambda q: {"found": False})
    lines = [l for l in m.context_block("What activities does Sam partake in?", max_facts=5)
             .splitlines() if l.startswith("- ")]
    assert asked[-1] >= 10 and len(lines) >= 10
    block = m.context_block("Where did Sam move from?", max_facts=5)
    line = next(l for l in block.splitlines() if "home country" in l)
    assert "home country: Sweden" in line
