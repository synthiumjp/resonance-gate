import json
import pytest

from sourcedrecall import importers


def _write_jsonl(path, recs):
    path.write_text("\n".join(json.dumps(r) for r in recs) + "\n")


def test_gemini_jsonl(tmp_path):
    p = tmp_path / "session-x.jsonl"
    _write_jsonl(p, [
        {"sessionId": "abc", "projectHash": "h", "startTime": "t", "lastUpdated": "t"},
        {"id": "1", "timestamp": "t", "type": "user", "content": [{"text": "I live in Perth."}]},
        {"id": "2", "timestamp": "t", "type": "gemini", "content": "Noted.",
         "thoughts": [{"subject": "s"}]},
        {"id": "3", "timestamp": "t", "type": "user", "content": "Scratch that."},
        {"$rewindTo": "3"},
        {"id": "4", "timestamp": "t", "type": "info", "content": "ignored"},
    ])
    assert list(importers.gemini_turns(p)) == [
        {"role": "user", "content": "I live in Perth."},
        {"role": "assistant", "content": "Noted."},
    ]
    assert importers.gemini_session_id(p) == "abc"


def test_gemini_patch_remove_and_thought_parts(tmp_path):
    p = tmp_path / "s.jsonl"
    _write_jsonl(p, [
        {"id": "1", "type": "user", "content": "hello"},
        {"id": "2", "type": "gemini",
         "content": [{"text": "hidden", "thought": True}, {"text": "hi there"}]},
        {"id": "3", "type": "user", "content": "remove me"},
        {"$patch": {"removeIds": ["3"]}},
    ])
    assert [t["content"] for t in importers.gemini_turns(p)] == ["hello", "hi there"]


def test_gemini_single_json(tmp_path):
    p = tmp_path / "session-y.json"
    p.write_text(json.dumps({"sessionId": "zzz", "messages": [
        {"id": "1", "type": "user", "content": "I own a cat."},
        {"id": "2", "type": "gemini", "content": "Nice.", "toolCalls": []},
    ]}))
    assert [t["role"] for t in importers.gemini_turns(p)] == ["user", "assistant"]
    assert importers.gemini_session_id(p) == "zzz"


def test_codex_not_implemented(tmp_path):
    with pytest.raises(NotImplementedError):
        list(importers.codex_turns(tmp_path / "rollout.jsonl"))
    assert importers.main(["codex", str(tmp_path / "rollout.jsonl")]) == 2
