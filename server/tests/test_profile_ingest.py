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


def test_the_context_block_quotes_the_users_own_sentence(pm):
    """2026-10-02: the proposition is a rewrite; the quote is what was said.
    Every inversion class fixed since e240 lived in the rewrite, so the block
    an agent receives must carry the original sentence beside it."""
    pm.profile_ingest([{"role": "user",
                        "content": "Neither my wife nor I like horror movies."}],
                      conversation_id="q1", owner_name="Ada Byron")
    block = pm.profile_context()["block"]
    assert '"Neither my wife nor I like horror movies."' in block
    out = pm.profile_recall("Do I like horror movies?")
    said = [f.get("said") for f in out.get("ranked") or out.get("unconfirmed") or []]
    assert "Neither my wife nor I like horror movies." in said


def test_one_sentence_is_one_mention_however_many_records_it_yields(pm):
    """2026-10-02: rgx emits a short and a full record off a modified clause,
    both under one (key, value). They were counted as two mentions, so a
    single sentence came out CORROBORATED ("said more than once")."""
    pm.profile_ingest([{"role": "user",
                        "content": "I might be interested in learning Swift."}],
                      conversation_id="m1", owner_name="Ada Byron")
    out = pm.profile_recall("Am I interested in learning Swift?")
    facts = (out.get("ranked") or []) + (out.get("unconfirmed") or [])
    swift = [f for f in facts if "Swift" in (f.get("text") or "")]
    assert swift and all(f["mentions"] == 1 for f in swift), swift
    assert all(f["status"] == "unconfirmed-single-mention" for f in swift)


def test_two_turns_are_two_mentions(pm):
    pm.profile_ingest([{"role": "user", "content": "I live in Leeds."},
                       {"role": "user", "content": "Like I said, I live in Leeds."}],
                      conversation_id="m2", owner_name="Ada Byron")
    out = pm.profile_recall("Where do I live?")
    leeds = [f for f in (out.get("ranked") or []) if "Leeds" in (f.get("text") or "")]
    assert leeds and leeds[0]["mentions"] == 2, leeds


def test_a_move_makes_the_old_address_no_longer_true(pm):
    """The second stranger test: after 'I moved to Brunswick', 'Where do I
    live?' still answered Fitzroy, unmarked."""
    U = lambda c: {"role": "user", "content": c}
    pm.profile_ingest([U("I live in Fitzroy.")], conversation_id="d1",
                      owner_name="Dana Cole", date="2026-09-25")
    pm.profile_ingest([U("Big news, I moved to Brunswick last weekend.")],
                      conversation_id="d2", owner_name="Dana Cole",
                      date="2026-10-02")
    out = pm.profile_recall("Where do I live?")
    ranked = out["ranked"]
    assert "Brunswick" in ranked[0]["text"] and ranked[0]["current"] is True
    fitz = [f for f in ranked if "Fitzroy" in f["text"]]
    assert fitz and fitz[0]["current"] is False
    assert "(no longer true)" in pm.profile_context("where do I live")["block"]


def test_an_older_conversation_imported_later_stays_older(pm):
    """Order follows when a conversation HAPPENED, not when it was imported."""
    U = lambda c: {"role": "user", "content": c}
    pm.profile_ingest([U("Big news, I moved to Brunswick last weekend.")],
                      conversation_id="n", owner_name="Dana Cole",
                      date="2026-10-02")
    pm.profile_ingest([U("I live in Fitzroy.")], conversation_id="o",
                      owner_name="Dana Cole", date="2026-09-01")
    ranked = pm.profile_recall("Where do I live?")["ranked"]
    fitz = [f for f in ranked if "Fitzroy" in f["text"]]
    assert fitz and fitz[0]["current"] is False


def test_a_bad_date_is_refused_not_misfiled(pm):
    import pytest as _pt
    with _pt.raises(ValueError):
        pm.profile_ingest([{"role": "user", "content": "I live in Leeds."}],
                          owner_name="Dana Cole", date="last tuesday")


def test_a_fresh_install_answers_never_seen_not_a_file_error(pm):
    """Second new-user test: the first profile_recall on an empty memory
    raised FileNotFoundError for conversations.json."""
    out = pm.profile_recall("Where do I live?")
    assert out["found"] is False and out["abstain"] is True
    assert "Nothing is stored" in pm.profile_context()["block"]
    assert pm.profile_status()["asserted"] == 0
