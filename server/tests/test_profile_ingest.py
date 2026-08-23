"""profile_ingest: the only WRITE-with-extraction path in this server, and
the extractor is rgx (a deterministic grammar-rule parser over a dependency
parse) -- never a language model. rgx.Extractor needs stanza, which most
dev/CI venvs for this repo (including .venv, which has `mcp`) do NOT have
installed; ~/rg_private/halumem/official/.venv has stanza but not `mcp`.
This whole module is skipped unless stanza is importable -- run it with:

    timeout 300 ~/rg_private/halumem/official/.venv/bin/python \
        -m pytest server/tests/test_profile_ingest.py -q
"""

import json

import pytest

pytest.importorskip(
    "stanza", reason="profile_ingest needs stanza (rgx.Extractor); run with "
                      "~/rg_private/halumem/official/.venv/bin/python")


_TURNS = [
    {"role": "user", "content": "My name is Ada Byron. I live in London "
                                 "and I work at the Analytical Engine Co."},
    {"role": "assistant", "content": "I remember you mentioning you moved "
                                      "from Bath."},
    {"role": "user", "content": "I don't like boxing."},
]


@pytest.fixture
def pm(tmp_path, monkeypatch):
    """A fresh profile_memory module state, pointed at an EMPTY fixture dir
    (no conversations.json / cache yet -- profile_ingest creates both)."""
    monkeypatch.setenv("RG_MEMORY_DIR", str(tmp_path))
    monkeypatch.delenv("SOURCEDRECALL_OWNER", raising=False)
    import sourcedrecall.profile_memory as mod

    def _reset():
        mod._state.update({"mem": None, "audit_pass": None,
                            "needs_reload": False, "uncached_turns": None,
                            "transcripts": None})
        mod._ingest_state.update({"extractor": None, "owner": None})

    _reset()
    yield mod
    _reset()


def test_ingest_writes_cache_and_conversation_record(pm):
    res = pm.profile_ingest(list(_TURNS), conversation_id="conv1",
                             title="Test convo", owner_name="Ada Byron")
    assert res["conversation_id"] == "conv1"
    assert res["turns"] == 3
    assert res["skipped_cached"] == 0
    assert res["model_calls"] == 0
    # location + employer + negated "like" -- at least these three non-hearsay
    assert res["facts"] >= 3
    # the assistant's "I remember you mentioning..." clause(s)
    assert res["hearsay"] >= 1

    cache_path = pm._cache_path()
    lines = [json.loads(l) for l in open(cache_path) if l.strip()]
    assert len(lines) == 3

    conv_path = pm._conversations_path()
    convs = json.load(open(conv_path))
    assert len(convs) == 1
    assert convs[0]["uuid"] == "conv1"
    assert convs[0]["name"] == "Test convo"
    assert len(convs[0]["chat_messages"]) == 3
    assert [m["sender"] for m in convs[0]["chat_messages"]] == \
        ["human", "assistant", "human"]

    # reload happened as part of ingest -- every ingested turn's hash is now
    # in the cache, so a fresh build sees nothing uncached
    assert pm.profile_status()["uncached_turns"] == 0


def test_london_and_negation_surfaced_bath_hearsay_is_not(pm):
    pm.profile_ingest(list(_TURNS), conversation_id="conv1",
                       owner_name="Ada Byron")

    london = pm.profile_recall("London")
    assert london["found"] is True
    texts = [f.get("text") or "" for f in
             london["asserted"] + london["unconfirmed"]]
    assert any("London" in t for t in texts)

    block = pm.profile_context("where does Ada live")["block"]
    assert "London" in block

    boxing = pm.profile_recall("boxing")
    assert boxing["found"] is True
    box_texts = [f.get("text") or "" for f in
                 boxing["asserted"] + boxing["unconfirmed"]]
    assert any("does not like boxing" in t for t in box_texts)

    bath = pm.profile_recall("Bath")
    assert bath["found"] is True
    # never volunteered as the user's own asserted/unconfirmed fact
    assert not any("bath" in (f.get("text") or "").lower()
                   for f in bath.get("asserted", []))
    assert not any("bath" in (f.get("text") or "").lower()
                   for f in bath.get("unconfirmed", []))
    # but IS reported under the hearsay key, receipted
    assert bath.get("hearsay")
    assert any("bath" in (h.get("text") or "").lower()
               for h in bath["hearsay"])
    for h in bath["hearsay"]:
        assert h["status"] == "hearsay"
        assert h["receipts"]


def test_second_ingest_of_same_turns_is_a_cache_no_op(pm):
    r1 = pm.profile_ingest(list(_TURNS), conversation_id="conv1",
                            owner_name="Ada Byron")
    assert r1["skipped_cached"] == 0

    r2 = pm.profile_ingest(list(_TURNS), conversation_id="conv1",
                            owner_name="Ada Byron")
    assert r2["skipped_cached"] == 3
    assert r2["facts"] == 0
    assert r2["hearsay"] == 0
    assert r2["turns"] == 3


def test_owner_name_falls_back_to_env(pm, monkeypatch):
    monkeypatch.setenv("SOURCEDRECALL_OWNER", "Ada Byron")
    pm.profile_ingest(list(_TURNS), conversation_id="conv1")
    london = pm.profile_recall("London")
    texts = [f.get("text") or "" for f in
             london["asserted"] + london["unconfirmed"]]
    assert any("Ada Byron" in t for t in texts)


def test_empty_turns_is_a_safe_no_op(pm):
    res = pm.profile_ingest([])
    assert res == {"conversation_id": None, "turns": 0, "facts": 0,
                    "hearsay": 0, "skipped_cached": 0, "model_calls": 0}
