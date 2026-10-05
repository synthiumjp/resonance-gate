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


# ---- ChatGPT and Claude.ai data exports (2026-10-05), made-up data -------

def _chatgpt_export():
    def node(nid, parent, children, role=None, text=None, ctype="text", t=0, **meta):
        msg = None
        if role:
            msg = {"author": {"role": role}, "create_time": t,
                   "content": {"content_type": ctype,
                               "parts": [text] if text is not None else []},
                   "metadata": meta}
        return nid, {"id": nid, "parent": parent, "children": children, "message": msg}
    mapping = dict([
        node("root", None, ["sys"]),
        node("sys", "root", ["ctx"], "system", "", t=1),
        node("ctx", "sys", ["u1"], "user", "Custom instructions", "user_editable_context",
             t=2, is_visually_hidden_from_conversation=True),
        node("u1", "ctx", ["a1"], "user", "I live in Perth and I keep bees.", t=3),
        node("a1", "u1", ["u2old", "u2"], "assistant", "Lovely.", t=4),
        node("u2old", "a1", [], "user", "I live in Mars.", t=5),     # edited away
        node("u2", "a1", ["tool"], "user", "My sister is called Ana.", t=6),
        node("tool", "u2", ["a2"], "tool", "search results", "execution_output", t=7),
        node("a2", "tool", [], "assistant", "Noted.", t=8),
    ])
    return [{"title": "Bees", "create_time": 1767225600.0,   # 2026-01-01
             "conversation_id": "c-1", "current_node": "a2", "mapping": mapping}]


def test_chatgpt_export_reads_the_branch_the_user_saw(tmp_path):
    p = tmp_path / "conversations.json"
    p.write_text(json.dumps(_chatgpt_export()))
    (cid, title, date, turns), = importers.chatgpt_conversations(p)
    assert (cid, title, date) == ("c-1", "Bees", "2026-01-01")
    assert turns == [
        {"role": "user", "content": "I live in Perth and I keep bees."},
        {"role": "assistant", "content": "Lovely."},
        {"role": "user", "content": "My sister is called Ana."},
        {"role": "assistant", "content": "Noted."},
    ]


def test_chatgpt_export_from_the_zip(tmp_path):
    import zipfile
    z = tmp_path / "export.zip"
    with zipfile.ZipFile(z, "w") as f:
        f.writestr("conversations.json", json.dumps(_chatgpt_export()))
        f.writestr("chat.html", "<html></html>")
    assert len(list(importers.chatgpt_conversations(z))) == 1


def test_claude_export(tmp_path):
    p = tmp_path / "conversations.json"
    p.write_text(json.dumps([{
        "uuid": "k-1", "name": "Moving", "created_at": "2026-02-03T10:00:00.000000Z",
        "chat_messages": [
            {"sender": "human", "text": "I moved to Leeds last month.",
             "attachments": [{"extracted_content": "I live in Rome."}]},
            {"sender": "assistant", "text": "",
             "content": [{"type": "text", "text": "Welcome to Leeds."},
                         {"type": "tool_use", "name": "x"}]},
        ]}]))
    (cid, title, date, turns), = importers.claude_conversations(p)
    assert (cid, title, date) == ("k-1", "Moving", "2026-02-03")
    assert turns == [{"role": "user", "content": "I moved to Leeds last month."},
                     {"role": "assistant", "content": "Welcome to Leeds."}]


@pytest.fixture
def pm(tmp_path, monkeypatch):
    monkeypatch.setenv("RG_MEMORY_DIR", str(tmp_path / "mem"))
    monkeypatch.setenv("RG_NLI", "0")
    monkeypatch.delenv("SOURCEDRECALL_OWNER", raising=False)
    import sourcedrecall.profile_memory as mod

    def reset():
        mod._state.update({"mem": None, "audit_pass": None,
                           "needs_reload": False, "uncached_turns": None,
                           "transcripts": None})
        mod._ingest_state.update({"extractor": None, "owner": None})
    reset()
    yield mod
    reset()


def test_an_export_is_stored_once(tmp_path, pm, capsys):
    p = tmp_path / "conversations.json"
    p.write_text(json.dumps(_chatgpt_export()))
    assert importers.main(["chatgpt", str(p), "--owner", "Dana Cole"]) == 0
    first = capsys.readouterr().out
    assert "in 1 conversations" in first
    r = pm.profile_recall("Where do I live?")
    assert "Perth" in r["ranked"][0]["text"] and "Mars" not in json.dumps(r)
    importers.main(["chatgpt", str(p), "--owner", "Dana Cole"])
    assert "stored 0 new facts" in capsys.readouterr().out
