"""The two properties that must NEVER regress, enforced (e265).

PURITY and ABSTENTION are the product's promises: nothing the user did not
assert reaches the store, and a topic never mentioned returns an honest
"never seen". Recall is a quality target and moves around; these two are
contracts, so they get a test rather than a scorecard line.

Runs the token-overlap arm only -- it needs stanza (already required by the
rgx suite) but not the v3 models. Use `python tools/dogfood.py --v3` for the
full scorecard.
"""
import os
import shutil
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import dogfood as DF  # noqa: E402


@pytest.fixture(scope="module")
def store():
    tmp = tempfile.mkdtemp(prefix="rg-dogfood-test-")
    try:
        pmem = DF.build(tmp, v3=False)
        pmem.profile_status()
        mem = pmem._state["mem"]
        nodes = list(mem.g.nodes.values()) + list(mem.g.provisional.values())
        yield pmem, " || ".join((d.get("text") or "") for d in nodes)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


@pytest.mark.parametrize("fragment,who", DF.MUST_NOT_ASSERT)
def test_purity_nothing_unasserted_is_stored(store, fragment, who):
    """A missing fact is a bad answer; an invented one is a broken promise."""
    _, blob = store
    assert fragment.lower() not in blob.lower(), (
        f"{fragment!r} is in the store, but: {who}")


@pytest.mark.parametrize("question", DF.UNSEEN)
def test_abstention_on_a_never_mentioned_topic(store, question):
    pmem, _ = store
    out = pmem.profile_recall(question)
    assert out.get("abstain") is True, (
        f"answered {question!r} with {DF.facts_of(out)[:2]}")


def test_the_assistants_hearsay_is_tiered_not_asserted(store):
    """"I remember you mentioning that you play the cello" -- the assistant
    said it, the user never did. It may be receipted; it may not be a fact."""
    pmem, blob = store
    assert "cello" not in blob.lower()
    mem = pmem._state["mem"]
    hearsay = " ".join((d.get("text") or "")
                       for d in getattr(mem.g, "hearsay", {}).values())
    assert "cello" in hearsay.lower(), "the receipt should still exist"


def test_recall_has_not_collapsed(store):
    """A floor, not a target -- so a change that guts recall to buy purity
    cannot pass silently."""
    pmem, _ = store
    hits = sum(1 for q, needle in DF.ANSWERABLE.items()
               if any(needle.lower() in g.lower()
                      for g in DF.facts_of(pmem.profile_recall(q))))
    assert hits >= 6, f"only {hits}/{len(DF.ANSWERABLE)} answerable questions hit"


def test_a_causal_clause_keeps_its_reason(store):
    """e266: rgx emits a short atom and a fuller record off one clause, and
    they collide on the same slot. First-wins kept the atom, so "I left my
    last job at Perrin because the commute was brutal" stored only "left ...
    at Perrin" -- the REASON, which is the point of the sentence, was
    dropped."""
    _, blob = store
    assert "commute" in blob.lower(), blob


# ---- CURRENCY (e273): a LIVING memory must supersede ---------------------
# These run on the V3 arm. Not to flatter them: the token-overlap default
# cannot RETRIEVE these facts at all (e258 measured it at 5/10 against v3's
# 9/10), so on that path there is nothing to order and the probe would be
# measuring the retriever, not currency. The demotion itself is implemented on
# BOTH paths -- a superseded fact ranks last wherever it surfaces.


@pytest.fixture(scope="module")
def store_v3():
    tmp = tempfile.mkdtemp(prefix="rg-dogfood-v3-")
    try:
        pmem = DF.build(tmp, v3=True)
        pmem.profile_status()
        mem = pmem._state["mem"]
        nodes = list(mem.g.nodes.values()) + list(mem.g.provisional.values())
        yield pmem, " || ".join((d.get("text") or "") for d in nodes)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


@pytest.mark.parametrize("q,fresh,stale", DF.CURRENCY,
                         ids=[c[0] for c in DF.CURRENCY])
def test_the_current_value_is_returned(store_v3, q, fresh, stale):
    pmem, _ = store_v3
    got = DF.facts_of(pmem.profile_recall(q))
    assert any(fresh.lower() in g.lower() for g in got[:3]), (
        f"{q!r} did not return the current value {fresh!r}: {got[:3]}")


@pytest.mark.parametrize("q,fresh,stale", DF.CURRENCY,
                         ids=[c[0] for c in DF.CURRENCY])
def test_the_stale_value_is_not_returned_first(store_v3, q, fresh, stale):
    """Demoted, never hidden: a receipt is permanent and "you told me X, then
    Y" beats silence. What must never happen is the stale value coming back
    FIRST, as though it still held."""
    pmem, _ = store_v3
    got = DF.facts_of(pmem.profile_recall(q))
    assert not (got and stale.lower() in got[0].lower()), (
        f"{q!r} returned the superseded {stale!r} first: {got[0]}")


def test_a_fact_is_never_merged_with_its_own_negation(store):
    """e273: `_cluster` merges values by token overlap, so "a vegetarian" and
    "no longer a vegetarian" scored 1.0 and merged -- with the POSITIVE
    winning the label because it had more mentions. Ledger 5l recorded this
    about instruments; the clusterer is the same algorithm deciding what the
    store believes."""
    _, blob = store
    assert "no longer a vegetarian" in blob.lower()
