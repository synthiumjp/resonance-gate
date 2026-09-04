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
