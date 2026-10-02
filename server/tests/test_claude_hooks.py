"""Claude Code hooks (2026-10-02): automatic capture at session end, the
memory briefing at session start. Driven with a SYNTHETIC transcript that
contains every kind of line the reader must skip -- tool calls, tool
results, thinking, meta and sidechain lines, slash-command echoes, injected
system reminders -- because the transcript format is not a documented
contract and anything unknown must be ignored, never stored."""
import json

import pytest

pytest.importorskip("stanza", reason="ingest needs the rgx parser (stanza)")

from sourcedrecall import claude_hooks as H  # noqa: E402


def _line(**kw):
    return json.dumps(kw) + "\n"


def _transcript(path):
    rows = [
        _line(type="user", isMeta=True, timestamp="2026-09-20T09:00:00Z",
              message={"role": "user", "content": "Caveat: meta line"}),
        _line(type="user", timestamp="2026-09-20T09:00:05Z",
              message={"role": "user", "content":
                       "I live in Fitzroy and I work as a nurse at St Vincent's."}),
        _line(type="assistant", message={"role": "assistant", "content": [
            {"type": "thinking", "thinking": "the user is a nurse"},
            {"type": "text", "text": "Thanks! Noted."}]}),
        _line(type="assistant", message={"role": "assistant", "content": [
            {"type": "tool_use", "name": "Bash", "input": {"command": "ls"}}]}),
        _line(type="user", message={"role": "user", "content": [
            {"type": "tool_result", "content": "I live in Narnia."}]}),
        _line(type="user", message={"role": "user", "content":
              "<command-name>/model</command-name> opus"}),
        _line(type="user", message={"role": "user", "content":
              "<system-reminder>You live in Atlantis.</system-reminder>"
              "I'm allergic to penicillin."}),
        _line(type="user", isSidechain=True, message={"role": "user",
              "content": "I live in Mordor."}),
        _line(type="system", content="compact boundary"),
    ]
    path.write_text("".join(rows))
    return str(path)


def test_the_reader_keeps_only_human_speech_and_visible_replies(tmp_path):
    turns, first = H.read_transcript(_transcript(tmp_path / "t.jsonl"))
    assert first == "2026-09-20T09:00:05Z"
    assert turns == [
        {"role": "user", "content":
         "I live in Fitzroy and I work as a nurse at St Vincent's."},
        {"role": "assistant", "content": "Thanks! Noted."},
        {"role": "user", "content": "I'm allergic to penicillin."},
    ]
    joined = json.dumps(turns)
    for leaked in ("Narnia", "Mordor", "Atlantis", "/model", "the user is a nurse"):
        assert leaked not in joined, leaked


@pytest.fixture
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("SOURCEDRECALL_STATE", str(tmp_path / "state"))
    monkeypatch.delenv("RG_MEMORY_DIR", raising=False)
    import sourcedrecall.profile_memory as pm

    def reset():
        pm._state.update({"mem": None, "audit_pass": None,
                          "needs_reload": False, "uncached_turns": None,
                          "transcripts": None})
        pm._ingest_state.update({"extractor": None, "owner": None})
    reset()
    yield tmp_path
    reset()


def test_session_end_stores_the_session_with_its_date(home):
    t = _transcript(home / "t.jsonl")
    out = H.session_end({"transcript_path": t, "session_id": "abc"},
                        owner="Dana Cole", sync=True)
    assert out["facts"] >= 2 and out["model_calls"] == 0
    import sourcedrecall.profile_memory as pm
    r = pm.profile_recall("Where do I live?")
    top = r["ranked"][0]
    assert "Fitzroy" in top["text"]
    assert top["receipts"][0]["date"] == "2026-09-20"
    assert "Narnia" not in json.dumps(r) and "Mordor" not in json.dumps(r)


def test_a_resumed_session_is_not_stored_twice(home):
    t = _transcript(home / "t.jsonl")
    ev = {"transcript_path": t, "session_id": "abc"}
    H.session_end(ev, owner="Dana Cole", sync=True)
    again = H.session_end(ev, owner="Dana Cole", sync=True)
    assert again["facts"] == 0 and again["skipped_cached"] >= 1


def test_session_start_briefs_the_agent_once_there_is_memory(home):
    assert H.session_start({}, owner="Dana Cole") is None   # empty: no noise
    H.session_end({"transcript_path": _transcript(home / "t.jsonl"),
                   "session_id": "abc"}, owner="Dana Cole", sync=True)
    out = H.session_start({"source": "startup"}, owner="Dana Cole")
    ctx = out["hookSpecificOutput"]
    assert ctx["hookEventName"] == "SessionStart"
    assert "I live in Fitzroy" in ctx["additionalContext"]
    assert len(ctx["additionalContext"]) <= 10000      # Claude Code's cap


def test_session_end_without_a_transcript_does_nothing(home):
    assert H.session_end({}, owner="Dana Cole")["stored"] is False


def test_the_summary_can_be_turned_off(home, monkeypatch):
    H.session_end({"transcript_path": _transcript(home / "t.jsonl"),
                   "session_id": "abc"}, owner="Dana Cole", sync=True)
    monkeypatch.setenv("SOURCEDRECALL_BRIEFING", "off")
    assert H.session_start({"source": "startup"}, owner="Dana Cole") is None
