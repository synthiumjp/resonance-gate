"""profile_* tools: the p2 world/profile memory bridged in as a read+correct
slice. LLM-free -- the fixture's profile_cache.jsonl covers every turn, so
Memory.load only ever replays the cache (no misses, no LLM call).
"""

import hashlib
import json

import pytest


def _write_fixture(tmp_path):
    """A tiny synthetic export: 3 conversations. c1 additionally carries an
    assistant turn plus two more human turns (fenced in ``` so _is_prose
    skips them -- no cache entry required, no effect on uncached_turns) so
    rehydrate has something real to page in, truncate, and role-filter.
    Facts are pre-extracted into profile_cache.jsonl, keyed by sha1 of the
    exact (stripped, 1800-char-truncated) turn text build_facts hashes --
    computed here via the loader itself so the hash can never drift from the
    real truncation rule. build_facts also walks the ASSISTANT's own turns
    now (the hearsay pass, entry 246 completion) looking for evidential==
    "report" clauses, so every prose assistant turn needs a cache entry too
    (empty here -- none of this fixture's assistant turns are hearsay) or
    uncached_turns would stop being 0."""
    convs = [
        {"uuid": "c1", "name": "Chat about life",
         "created_at": "2026-01-01T00:00:00Z",
         "chat_messages": [
             {"sender": "human",
              "text": "I live in Melbourne and work as a researcher."},
             {"sender": "assistant",
              "text": "Got it -- Melbourne, researcher. Anything else?"},
             {"sender": "human", "text": "```\nnot prose, a code block\n```"},
             {"sender": "assistant", "text": "Sure thing."},
             {"sender": "human", "text": "```\nanother code block\n```"},
         ]},
        {"uuid": "c2", "name": "Second chat",
         "created_at": "2026-01-02T00:00:00Z",
         "chat_messages": [{"sender": "human",
                             "text": "Still in Melbourne, working as a researcher this week."}]},
        {"uuid": "c3", "name": "Health chat",
         "created_at": "2026-01-03T00:00:00Z",
         "chat_messages": [{"sender": "human",
                             "text": "I'm allergic to penicillin, just found out."}]},
    ]
    conv_path = tmp_path / "conversations.json"
    conv_path.write_text(json.dumps(convs))

    import sourcedrecall.profile_memory  # noqa: F401 -- bridges sys.path onto p2
    import run_profile_full as PF
    import run_wire as RW
    stream, _ = PF.load_stream_and_titles(str(conv_path))
    astream = RW._load_assistant_stream(str(conv_path))

    facts_by_text = {
        "I live in Melbourne and work as a researcher.":
            [{"attribute": "location", "value": "Melbourne"},
             {"attribute": "occupation", "value": "Researcher"}],
        "Still in Melbourne, working as a researcher this week.":
            [{"attribute": "location", "value": "Melbourne"},
             {"attribute": "occupation", "value": "Researcher"}],
        "I'm allergic to penicillin, just found out.":
            [{"attribute": "allergy", "value": "Penicillin"}],
        # non-prose turns: never looked up (build_facts filters them before
        # hashing), but the fixture-writing loop below still walks every
        # human turn in the stream, so a key is needed to avoid a KeyError.
        "```\nnot prose, a code block\n```": [],
        "```\nanother code block\n```": [],
        # assistant turns: no hearsay in this fixture, so empty facts --
        # still need a cache entry or build_facts's assistant pass counts
        # them uncached.
        "Got it -- Melbourne, researcher. Anything else?": [],
        "Sure thing.": [],
    }
    cache_path = tmp_path / "profile_cache.jsonl"
    with open(cache_path, "w") as f:
        for _, _, _, text in list(stream) + list(astream):
            h = hashlib.sha1(text.encode("utf-8")).hexdigest()
            f.write(json.dumps({"h": h, "f": facts_by_text[text]}) + "\n")
    return tmp_path


@pytest.fixture
def pm(tmp_path, monkeypatch):
    """A fresh profile_memory module state, pointed at a fresh fixture dir.
    The Memory singleton is module-global (process-wide), so it must be reset
    around every test even though tmp_path itself is already per-test."""
    _write_fixture(tmp_path)
    monkeypatch.setenv("RG_MEMORY_DIR", str(tmp_path))
    import sourcedrecall.profile_memory as mod

    def _reset():
        mod._state.update({"mem": None, "audit_pass": None,
                            "needs_reload": False, "uncached_turns": None,
                            "transcripts": None})

    _reset()
    yield mod
    _reset()


def test_recall_found_with_receipts_and_wiring(pm):
    out = pm.profile_recall("Melbourne")
    assert out["found"] is True and out["abstain"] is False
    assert out["source"] == "rg-p2-memory"
    assert out["asserted"][0]["attribute"] == "location"
    assert out["asserted"][0]["value"] == "melbourne"
    assert out["asserted"][0]["receipts"]
    wired_attrs = {w["fact"]["attribute"] for w in out["wired"]}
    assert "occupation" in wired_attrs
    for w in out["wired"]:
        assert w["via"]


def test_recall_abstains_honestly(pm):
    out = pm.profile_recall("favourite constellation")
    assert out["found"] is False and out["abstain"] is True
    assert out["source"] == "rg-p2-memory"


def test_context_block_carries_do_not_invent_rule(pm):
    block = pm.profile_context()["block"]
    assert "location: melbourne" in block
    assert "UNKNOWN" in block and "don't know" in block


def test_correct_deny_applies_live_and_writes_corrections_line(pm):
    assert pm.profile_recall("researcher")["found"] is True
    res = pm.profile_correct("deny", "occupation", "researcher")
    assert res["applied"] == "live"
    assert res["log"] == [("denied", "occupation=researcher")]

    assert pm.profile_recall("researcher")["abstain"] is True

    corr_path = pm._corrections_path()
    written = [json.loads(l) for l in open(corr_path) if l.strip()]
    assert written == [{"action": "deny", "attribute": "occupation",
                        "value": "researcher"}]


def test_correct_confirm_applies_live(pm):
    out = pm.profile_recall("penicillin")
    assert out["found"] is True and out["unconfirmed"]
    res = pm.profile_correct("confirm", "allergy", "penicillin")
    assert res["applied"] == "live"
    out = pm.profile_recall("penicillin")
    assert out["asserted"] and out["asserted"][0]["status"] == "owner-confirmed"


def test_correct_retype_flags_needs_reload_then_takes_effect_after_reload(pm):
    # before: a provisional fact under the old attribute
    out = pm.profile_recall("penicillin")
    assert out["unconfirmed"] and out["unconfirmed"][0]["attribute"] == "allergy"

    res = pm.profile_correct("retype", "allergy", "penicillin",
                              new_attribute="medical_condition")
    assert res["applied"] == "on-reload"
    assert res["needs_reload"] is True
    assert pm.profile_status()["needs_reload"] is True

    corr_path = pm._corrections_path()
    written = [json.loads(l) for l in open(corr_path) if l.strip()]
    assert written == [{"action": "retype", "attribute": "allergy",
                        "value": "penicillin", "new_attribute": "medical_condition"}]

    # live graph is untouched by a retype -- still the old attribute
    out = pm.profile_recall("penicillin")
    assert out["unconfirmed"][0]["attribute"] == "allergy"

    pm.reload()
    assert pm.profile_status()["needs_reload"] is False
    out = pm.profile_recall("penicillin")
    assert out["unconfirmed"][0]["attribute"] == "medical_condition"


def test_correct_rejects_bad_action_and_retype_without_new_attribute(pm):
    r1 = pm.profile_correct("nonsense", "location", "melbourne")
    assert "error" in r1 and r1["applied"] is None
    r2 = pm.profile_correct("retype", "allergy", "penicillin")
    assert "error" in r2 and r2["applied"] is None


def test_status_counts_and_audit_pass(pm):
    st = pm.profile_status()
    assert st["loaded"] is True
    assert st["asserted"] == 2          # location + occupation (>= 2 mentions)
    assert st["provisional"] == 1       # allergy (single mention)
    assert st["edges"] == 1             # location <-> occupation, shared 2 convs
    assert st["audit_pass"] is True
    assert st["needs_reload"] is False
    assert st["uncached_turns"] == 0    # every turn is in the fixture cache
    assert st["data_dir"] == str(pm._data_dir())


def test_recall_receipts_carry_conversation_id(pm):
    out = pm.profile_recall("Melbourne")
    receipts = out["asserted"][0]["receipts"]
    assert receipts
    for r in receipts:
        assert set(r) == {"date", "conversation", "conversation_id"}
        assert r["conversation_id"] in ("c1", "c2")


def test_rehydrate_round_trip_from_a_receipt(pm):
    out = pm.profile_recall("Melbourne")
    conv_id = out["asserted"][0]["receipts"][0]["conversation_id"]
    r = pm.rehydrate(conv_id)
    assert r["found"] is True
    assert r["conversation_id"] == conv_id
    texts = [t["text"] for t in r["turns"]]
    fixture_sentence = ("I live in Melbourne and work as a researcher."
                         if conv_id == "c1" else
                         "Still in Melbourne, working as a researcher this week.")
    assert fixture_sentence in texts


def test_rehydrate_max_turns_truncates(pm):
    full = pm.rehydrate("c1", max_turns=40)
    assert full["found"] is True
    assert full["n_turns_total"] == 5
    assert len(full["turns"]) == 5
    assert full["truncated"] is False

    capped = pm.rehydrate("c1", max_turns=2)
    assert capped["n_turns_total"] == 5      # total is honest, not the cap
    assert len(capped["turns"]) == 2
    assert capped["truncated"] is True


def test_rehydrate_include_assistant_false_filters_to_human(pm):
    r = pm.rehydrate("c1", max_turns=40, include_assistant=False)
    assert all(t["role"] == "human" for t in r["turns"])
    assert r["n_turns_total"] == 3            # 3 human turns in c1's fixture
    assert len(r["turns"]) == 3
    assert r["truncated"] is False


def test_rehydrate_unknown_id_is_honest_not_a_guess(pm):
    r = pm.rehydrate("no-such-conversation-uuid")
    assert r == {"found": False,
                 "error": "no such conversation in the backing store"}


def test_rehydrate_survives_reload(pm):
    r1 = pm.rehydrate("c1")
    assert r1["found"] is True
    assert pm._state["transcripts"] is not None

    pm.reload()
    assert pm._state["transcripts"] is None   # reload evicts the stale index

    r2 = pm.rehydrate("c1")
    assert r2["found"] is True
    assert r2["turns"] == r1["turns"]


def test_status_missing_env_raises_clearly(monkeypatch):
    monkeypatch.delenv("RG_MEMORY_DIR", raising=False)
    import sourcedrecall.profile_memory as mod
    mod._state.update({"mem": None, "audit_pass": None,
                       "needs_reload": False, "uncached_turns": None,
                       "transcripts": None})
    with pytest.raises(mod.MemoryNotConfigured):
        mod.profile_status()
