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



# review round 3: every one of these leaked through the first scrubber
@pytest.mark.parametrize("text,secret", [
    ("pw: hunter2", "hunter2"), ("My pw is hunter2", "hunter2"),
    ("hunter2 is my password", "hunter2"), ("I use hunter2 as my password", "hunter2"),
    ("My password, hunter2, is weak", "hunter2"), ("I set my password to hunter2", "hunter2"),
    ("my password's hunter2", "hunter2"), ("The PIN is: 4821", "4821"),
    ("the wifi password? it's tulip99", "tulip99"),
    ("What is my password? It is hunter2", "hunter2"),
    ("My password is the following. hunter2", "hunter2"),
    ("my login is bob / hunter2", "hunter2"), ("user: bob, pass: hunter2", "hunter2"),
    ("mongodb://bob:hunter2@host", "hunter2"),
    ('My password is "correct horse battery staple"', "battery"),
    ("account number is 1234 5678 9012", "5678"), ("my SSN is 123 45 6789", "6789"),
    ("my door code is 4821", "4821"), ("the code to the safe is 4821", "4821"),
    ("My bank account is 12345678", "12345678"), ("my wifi key is hunter2", "hunter2"),
    ("The key is hunter2", "hunter2"),
    ("Authorization: Bearer abcdefghijklmnopqrstuvwxyz123456", "abcdefghij"),
])
def test_review3_leaks_are_closed(text, secret):
    assert secret not in scrub(text)


@pytest.mark.parametrize("text", [
    "the secret is that I hate my job", "I forgot my password again.",
    "The key is to stay calm.", "my secret is out",
])
def test_review3_ordinary_sentences_survive(text):
    assert scrub(text) == text


def test_only_the_credential_sentence_goes():
    assert scrub("I live in Fitzroy. My PIN is 4821. I like jazz.") == \
        "I live in Fitzroy. [secret removed] I like jazz."
