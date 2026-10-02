"""Credentials never enter the memory (2026-10-02)."""
import json
import os

import pytest

from sourcedrecall.secrets import MARK, scrub


@pytest.mark.parametrize("text", [
    "My password for the staging server is hunter2.",
    "Here's my API key: sk-proj-abc123def456ghi789jkl012mno345.",
    "My PIN is 4821.",
    "My card number is 4111 1111 1111 1111.",
    "My SSN is 123-45-6789",
    "token: ghp_abcdefghijklmnopqrstuvwxyz0123456789",
])
def test_a_credential_is_removed(text):
    out = scrub(text)
    assert MARK in out
    for secret in ("hunter2", "sk-proj", "4821", "4111", "123-45", "ghp_"):
        assert secret not in out


@pytest.mark.parametrize("text", [
    "Call me on 0412 345 678.", "I live in Fitzroy.",
    "My password manager is 1Password.", "The order number is 4111 1111 1111 1112.",
    "I knocked every pin down.",
])
def test_ordinary_text_is_left_alone(text):
    assert scrub(text) == text


def test_nothing_secret_is_stored(tmp_path, monkeypatch):
    pytest.importorskip("stanza")
    monkeypatch.setenv("RG_MEMORY_DIR", str(tmp_path))
    monkeypatch.setenv("RG_NLI", "0")
    import sourcedrecall.profile_memory as pm
    pm._state.update({"mem": None, "audit_pass": None, "needs_reload": False,
                      "uncached_turns": None, "transcripts": None})
    pm._ingest_state.update({"extractor": None, "owner": None})
    pm.profile_ingest([{"role": "user", "content":
                        "My password for the staging server is hunter2."},
                       {"role": "user", "content": "I live in Fitzroy."}],
                      conversation_id="a", owner_name="Dana Cole",
                      date="2026-03-02")
    for f in os.listdir(tmp_path):
        assert "hunter2" not in open(tmp_path / f, encoding="utf-8").read(), f
    r = pm.profile_recall("What is my password?")
    assert "hunter2" not in json.dumps(r)
