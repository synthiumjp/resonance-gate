import json
import sys
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


def test_gemini_first_timestamp(tmp_path):
    p = tmp_path / "s.jsonl"
    _write_jsonl(p, [
        {"id": "1", "timestamp": "2026-09-01T10:00:00Z", "type": "user", "content": "hi"},
        {"id": "2", "timestamp": "2026-09-01T10:00:05Z", "type": "gemini", "content": "yo"},
    ])
    assert importers.gemini_first_timestamp(p) == "2026-09-01T10:00:00Z"


# ---- Codex CLI rollouts (2026-10-05) ---------------------------------------
# Fixtures are built from the types in openai/codex (see the importers module
# docstring), with made-up text.

_UUID = "5973b6c0-94b8-487b-a530-2aeb6098ae0e"


def _msg(role, *texts, kind=None, **extra):
    kind = kind or ("output_text" if role == "assistant" else "input_text")
    return {"type": "message", "role": role,
            "content": [{"type": kind, "text": t} for t in texts], **extra}


def _line(payload, ts="2026-09-20T09:00:05.000Z", kind="response_item"):
    return {"timestamp": ts, "type": kind, "payload": payload}


def _codex_layout_b(path, extra=()):
    _write_jsonl(path, [
        _line({"id": _UUID, "session_id": _UUID, "timestamp": "2026-09-20T09:00:00.000Z",
               "cwd": "/work/proj", "originator": "codex_cli_rs", "cli_version": "0.160.0",
               "source": "cli"}, kind="session_meta"),
        _line(_msg("developer", "<permissions instructions>sandbox</permissions instructions>")),
        _line(_msg("user", "# AGENTS.md instructions for /work/proj\n\n<INSTRUCTIONS>\n"
                           "You live in Atlantis.\n</INSTRUCTIONS>")),
        _line(_msg("user", "<environment_context>\n  <cwd>/work/proj</cwd>\n"
                           "</environment_context>")),
        _line(_msg("user", "I live in Fitzroy and I work as a nurse.")),
        _line({"type": "user_message", "message": "I live in Fitzroy and I work as a nurse."},
              kind="event_msg"),
        _line({"type": "reasoning", "summary": [], "encrypted_content": "xx"}),
        _line(_msg("assistant", "Looking around the repo first.", phase="commentary")),
        _line({"type": "function_call", "name": "shell", "arguments": "{}", "call_id": "c1"}),
        _line({"type": "function_call_output", "call_id": "c1",
               "output": {"content": "I live in Narnia."}}),
        _line(_msg("user", "<user_shell_command>\n<command>\nls\n</command>\n</user_shell_command>")),
        _line(_msg("assistant", "Thanks, noted.", phase="final_answer")),
        _line({"type": "token_count", "info": None}, kind="event_msg"),
        _line({"message": "summary", "replacement_history": None}, kind="compacted"),
        *extra,
    ])


def test_codex_layout_b_keeps_only_what_was_said(tmp_path):
    p = tmp_path / f"rollout-2026-09-20T09-00-00-{_UUID}.jsonl"
    _codex_layout_b(p)
    turns = list(importers.codex_turns(p))
    assert turns == [
        {"role": "user", "content": "I live in Fitzroy and I work as a nurse."},
        {"role": "assistant", "content": "Looking around the repo first."},
        {"role": "assistant", "content": "Thanks, noted."},
    ]
    blob = json.dumps(turns)
    for leaked in ("Atlantis", "Narnia", "sandbox", "environment_context", "AGENTS"):
        assert leaked not in blob, leaked
    assert importers.codex_session_id(p) == _UUID
    assert importers.codex_first_timestamp(p) == "2026-09-20T09:00:05.000Z"


def test_codex_session_id_falls_back_to_the_header(tmp_path):
    p = tmp_path / "copy.jsonl"
    _codex_layout_b(p)
    assert importers.codex_session_id(p) == _UUID


def test_codex_layout_a_header_then_raw_items(tmp_path):
    p = tmp_path / f"rollout-2025-05-07T17-24-21-{_UUID}.jsonl"
    _write_jsonl(p, [
        {"id": _UUID, "timestamp": "2025-05-07T17:24:21.123Z", "instructions": "be brief"},
        _msg("user", "<environment_context>\n  <cwd>/x</cwd>\n</environment_context>"),
        _msg("user", "I keep bees."),
        {"record_type": "state", "previous_response_id": "resp_1"},
        {"type": "function_call", "name": "shell", "arguments": "{}", "call_id": "c"},
        {"type": "function_call_output", "call_id": "c", "output": {"content": "x"}},
        _msg("assistant", "Lovely."),
        {"type": "reasoning", "id": "r", "summary": []},
    ])
    assert list(importers.codex_turns(p)) == [
        {"role": "user", "content": "I keep bees."},
        {"role": "assistant", "content": "Lovely."},
    ]
    assert importers.codex_session_id(p) == _UUID
    assert importers.codex_first_timestamp(p) == "2025-05-07T17:24:21.123Z"


def test_codex_skips_every_kind_of_injected_user_text(tmp_path):
    p = tmp_path / "r.jsonl"
    injected = [
        "<user_instructions>\nbe nice\n</user_instructions>",
        "<turn_aborted>\nstopped\n</turn_aborted>",
        "<subagent_notification>{}</subagent_notification>",
        "<skill>\n<name>x</name>\n</skill>",
        "<codex_internal_context source=\"goal\">g</codex_internal_context>",
        "<external_foo>bar</external_foo>",
        "<hook_prompt hook_run_id=\"h1\">run the tests</hook_prompt>",
        "Warning: The maximum number of unified exec processes you can keep open is 60",
        "Another language model started to solve this problem and produced a summary "
        "of its thinking process. You also have access to...",
    ]
    _write_jsonl(p, [_line(_msg("user", t)) for t in injected]
                 + [_line(_msg("user", '<image name=[Image #1] path="/a.png">',
                               "</image>", "What is in this picture?"))]
                 + [_line(_msg("user", "My cat is called Biscuit."))])
    assert list(importers.codex_turns(p)) == [
        {"role": "user", "content": "What is in this picture?"},
        {"role": "user", "content": "My cat is called Biscuit."},
    ]


def test_codex_keeps_the_request_after_the_context_marker(tmp_path):
    p = tmp_path / "r.jsonl"
    _write_jsonl(p, [_line(_msg("user", "context\n## My request for Codex:\nfix the bug"))])
    assert [t["content"] for t in importers.codex_turns(p)] == ["fix the bug"]


def test_codex_a_rollback_removes_the_last_user_turns(tmp_path):
    p = tmp_path / "r.jsonl"
    _write_jsonl(p, [
        _line(_msg("user", "first")), _line(_msg("assistant", "a1")),
        _line(_msg("user", "second")), _line(_msg("assistant", "a2")),
        _line(_msg("user", "third")), _line(_msg("assistant", "a3")),
        _line({"type": "thread_rolled_back", "num_turns": 2}, kind="event_msg"),
        _line(_msg("user", "fourth")),
    ])
    assert [t["content"] for t in importers.codex_turns(p)] == ["first", "a1", "fourth"]


def test_codex_subagent_rollouts_are_not_read(tmp_path):
    p = tmp_path / "r.jsonl"
    _write_jsonl(p, [
        _line({"id": _UUID, "timestamp": "t", "cwd": "/", "originator": "o",
               "cli_version": "1", "source": {"subagent": {"other": "guardian"}}},
              kind="session_meta"),
        _line(_msg("user", "Review this approval request.")),
    ])
    assert list(importers.codex_turns(p)) == []


def test_codex_compressed_rollout_says_what_to_do(tmp_path, monkeypatch):
    monkeypatch.setitem(sys.modules, "compression", None)
    monkeypatch.setitem(sys.modules, "zstandard", None)
    p = tmp_path / "rollout-x.jsonl.zst"
    p.write_bytes(b"\x28\xb5\x2f\xfd")
    with pytest.raises(ValueError, match="zstd"):
        list(importers.codex_turns(p))
    assert importers.main(["codex", str(p)]) == 2


def test_codex_main_stores_with_a_prefixed_id_and_the_session_date(tmp_path, monkeypatch):
    p = tmp_path / f"rollout-2026-09-20T09-00-00-{_UUID}.jsonl"
    _codex_layout_b(p)
    seen = {}

    class FakePM:
        @staticmethod
        def profile_ingest(turns, **kw):
            seen.update(kw, turns=turns)
            return {"facts": 1, "turns": len(turns), "conversation_id": kw["conversation_id"]}

    import sourcedrecall
    monkeypatch.setattr(sourcedrecall, "profile_memory", FakePM, raising=False)
    monkeypatch.setitem(sys.modules, "sourcedrecall.profile_memory", FakePM)
    assert importers.main(["codex", str(p), "--owner", "Dana"]) == 0
    assert seen["conversation_id"] == f"codex:{_UUID}"
    assert seen["date"] == "2026-09-20T09:00:05.000Z"
    assert len(seen["turns"]) == 3


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
    pytest.importorskip("stanza", reason="ingest needs the rgx parser (stanza)")
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
