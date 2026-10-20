"""Hooks for Codex CLI, Gemini CLI and Cursor (2026-10-05).

The memory itself is replaced by a recorder, so these run without the Stanza
parser: what is tested is which text each hook hands to profile_ingest, under
which conversation id, and what each hook prints. Payloads follow the
documented stdin of each tool (Codex: openai/codex codex-rs/hooks/schema;
Gemini: docs/hooks/reference.md; Cursor: cursor.com/docs/hooks). Rollout and
transcript contents are made up."""
import io
import json
import os
import sys

import pytest

from sourcedrecall import claude_hooks as H
from sourcedrecall import cursor_hooks as C

UUID = "5973b6c0-94b8-487b-a530-2aeb6098ae0e"


class FakePM:
    def __init__(self):
        self.ingested = []
        self.news_calls = 0
        self.facts = 0

    def profile_ingest(self, turns, **kw):
        self.ingested.append({"turns": turns, **kw})
        return {"facts": len(turns), "turns": len(turns),
                "conversation_id": kw["conversation_id"]}

    def profile_status(self):
        return {"asserted": self.facts, "provisional": 0}

    def profile_context(self, query, max_facts, scope=None):
        return {"block": "[MEMORY] The user lives in Fitzroy."}

    def profile_news(self):
        self.news_calls += 1
        return [{"id": "f1", "said": "I live in Fitzroy."}]

    def memory_file(self):
        return "/home/x/.sourcedrecall/conversations/MEMORY.md"


@pytest.fixture
def pm(tmp_path, monkeypatch):
    monkeypatch.setenv("SOURCEDRECALL_STATE", str(tmp_path / "state"))
    for k in ("SOURCEDRECALL_SCOPE", "CLAUDE_PROJECT_DIR", "SOURCEDRECALL_BRIEFING",
              "SOURCEDRECALL_NOTICE"):
        monkeypatch.delenv(k, raising=False)
    fake = FakePM()
    monkeypatch.setattr(H, "_setup_env", lambda owner: fake)
    return fake


def _write(path, recs):
    path.write_text("\n".join(json.dumps(r) for r in recs) + "\n")
    return str(path)


def _codex_rollout(tmp_path):
    def line(payload, kind="response_item"):
        return {"timestamp": "2026-09-20T09:00:05.000Z", "type": kind, "payload": payload}
    msg = lambda role, text: {"type": "message", "role": role, "content": [
        {"type": "output_text" if role == "assistant" else "input_text", "text": text}]}
    return _write(tmp_path / f"rollout-2026-09-20T09-00-00-{UUID}.jsonl", [
        line({"id": UUID, "timestamp": "2026-09-20T09:00:00.000Z", "cwd": "/work",
              "originator": "o", "cli_version": "1", "source": "cli"}, "session_meta"),
        line(msg("user", "<environment_context>\n<cwd>/work</cwd>\n</environment_context>")),
        line(msg("user", "I live in Fitzroy.")),
        line({"type": "function_call", "name": "shell", "arguments": "{}", "call_id": "c"}),
        line(msg("assistant", "Noted.")),
    ])


def _gemini_session(tmp_path):
    return _write(tmp_path / "session-1.jsonl", [
        {"sessionId": "gem-1", "projectHash": "h", "startTime": "t", "lastUpdated": "t"},
        {"id": "1", "timestamp": "2026-09-21T08:00:00Z", "type": "user",
         "content": [{"text": "I am allergic to penicillin."}]},
        {"id": "2", "timestamp": "2026-09-21T08:00:03Z", "type": "gemini",
         "content": "Noted.", "thoughts": [{"subject": "s"}]},
    ])


# ---- Codex -----------------------------------------------------------------

def test_codex_session_end_stores_the_rollout(pm, tmp_path):
    path = _codex_rollout(tmp_path)
    event = {"session_id": UUID, "transcript_path": path, "cwd": str(tmp_path),
             "hook_event_name": "SessionEnd", "reason": "other"}
    H.session_end(event, owner="Dana", sync=True, agent="codex")
    (got,) = pm.ingested
    assert got["conversation_id"] == f"codex:{UUID}"
    assert got["turns"] == [{"role": "user", "content": "I live in Fitzroy."},
                            {"role": "assistant", "content": "Noted."}]
    assert got["date"] == "2026-09-20T09:00:05.000Z"
    assert got["title"] == "I live in Fitzroy."


def test_codex_session_end_with_a_null_transcript_does_nothing(pm):
    out = H.session_end({"session_id": UUID, "transcript_path": None}, agent="codex")
    assert out["stored"] is False and not pm.ingested


def test_session_end_hands_the_agent_to_the_worker(pm, tmp_path, monkeypatch):
    launched = []
    monkeypatch.setattr(H.subprocess, "Popen", lambda cmd, **kw: launched.append(cmd))
    path = _codex_rollout(tmp_path)
    out = H.session_end({"session_id": UUID, "transcript_path": path, "cwd": "/work"},
                        agent="codex")
    assert out["stored"] == "pending"
    job = json.load(open(out["job"]))
    assert job["agent"] == "codex" and job["transcript_path"] == path
    assert launched[0][-2:] == ["_worker", out["job"]]
    # the worker, run with that job, stores the session
    assert H.main(["_worker", out["job"]]) == 0
    assert pm.ingested[0]["conversation_id"] == f"codex:{UUID}"
    assert not os.path.exists(out["job"])


def test_the_claude_default_is_unchanged(pm, tmp_path):
    t = tmp_path / "t.jsonl"
    _write(t, [{"type": "user", "timestamp": "2026-09-20T09:00:05Z",
                "message": {"role": "user", "content": "I live in Fitzroy."}}])
    H.session_end({"session_id": "abc", "transcript_path": str(t)}, sync=True)
    assert pm.ingested[0]["conversation_id"] == "claude-code:abc"


def test_codex_session_start_prints_context_and_a_notice_naming_codex(pm, monkeypatch,
                                                                      capsys):
    pm.facts = 1
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(
        {"session_id": UUID, "source": "startup", "cwd": "/work",
         "hook_event_name": "SessionStart", "model": "m", "permission_mode": "default",
         "transcript_path": None})))
    assert H.main(["session-start", "--agent", "codex"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["hookSpecificOutput"]["hookEventName"] == "SessionStart"
    assert "Fitzroy" in out["hookSpecificOutput"]["additionalContext"]
    assert "Ask Codex to forget" in out["systemMessage"]


# ---- Gemini ----------------------------------------------------------------

def test_gemini_session_end_stores_the_chat_with_its_session_id(pm, tmp_path):
    path = _gemini_session(tmp_path)
    H.session_end({"session_id": "other-id", "transcript_path": path, "cwd": str(tmp_path),
                   "hook_event_name": "SessionEnd", "reason": "exit",
                   "timestamp": "2026-09-21T09:00:00Z"},
                  sync=True, agent="gemini")
    (got,) = pm.ingested
    assert got["conversation_id"] == "gem-1"          # as `sourcedrecall-import gemini`
    assert [t["content"] for t in got["turns"]] == ["I am allergic to penicillin.", "Noted."]
    assert got["date"] == "2026-09-21T08:00:00Z"


def test_gemini_session_start_notice_names_gemini(pm, monkeypatch, capsys):
    pm.facts = 1
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps({"source": "startup"})))
    assert H.main(["session-start", "--agent", "gemini"]) == 0
    assert "Ask Gemini to forget" in json.loads(capsys.readouterr().out)["systemMessage"]


# ---- Cursor ----------------------------------------------------------------

def _ev(name, **kw):
    return {"conversation_id": "conv-1", "generation_id": "g", "model": "m",
            "hook_event_name": name, "cursor_version": "1.7.2",
            "workspace_roots": ["/work/proj"], "user_email": None,
            "transcript_path": None, **kw}


def test_cursor_records_prompts_and_replies_and_stores_at_stop(pm):
    assert C.handle(_ev("beforeSubmitPrompt", prompt="I live in Fitzroy.",
                        attachments=[]), "Dana") == {"continue": True}
    assert C.handle(_ev("afterAgentResponse", text="Let me look.")) == {}
    assert C.handle(_ev("afterAgentResponse", text="Noted.")) == {}
    assert C.handle(_ev("afterAgentThought", text="private thinking")) == {}
    assert C.handle(_ev("stop", status="completed", loop_count=0),
                    "Dana", sync=True) == {}
    (got,) = pm.ingested
    assert got["conversation_id"] == "cursor:conv-1"
    assert got["turns"] == [
        {"role": "user", "content": "I live in Fitzroy."},
        {"role": "assistant", "content": "Let me look.\nNoted."},
    ]
    assert os.path.exists(C.spool_path("conv-1"))       # kept until sessionEnd


def test_cursor_session_end_stores_and_removes_the_spool(pm):
    C.handle(_ev("beforeSubmitPrompt", prompt="I keep bees."))
    C.handle(_ev("sessionEnd", session_id="conv-1", reason="user_close"),
             sync=True)
    assert pm.ingested[0]["turns"] == [{"role": "user", "content": "I keep bees."}]
    assert not os.path.exists(C.spool_path("conv-1"))


def test_cursor_a_second_stop_resends_the_whole_conversation(pm):
    """Storing is idempotent in the memory (only new turns are added), so the
    hook can send everything each time."""
    C.handle(_ev("beforeSubmitPrompt", prompt="one"))
    C.handle(_ev("stop", status="completed"), sync=True)
    C.handle(_ev("beforeSubmitPrompt", prompt="two"))
    C.handle(_ev("stop", status="completed"), sync=True)
    assert [t["content"] for t in pm.ingested[1]["turns"]] == ["one", "two"]


def test_cursor_stop_without_anything_recorded_does_nothing(pm):
    assert C.handle(_ev("stop", status="aborted"), sync=True) == {}
    assert not pm.ingested


def test_cursor_stop_starts_a_background_worker(pm, tmp_path, monkeypatch):
    launched = []
    monkeypatch.setattr(H.subprocess, "Popen", lambda cmd, **kw: launched.append(cmd))
    C.handle(_ev("beforeSubmitPrompt", prompt="I keep bees."), "Dana")
    C.handle(_ev("stop", status="completed"), "Dana")
    job_file = launched[0][-1]
    job = json.load(open(job_file))
    assert job["conversation_id"] == "conv-1" and job["cwd"] == "/work/proj"
    assert H.main(["_worker", job_file]) == 0
    assert pm.ingested[0]["conversation_id"] == "cursor:conv-1"


def test_cursor_session_start_gives_additional_context_and_marks_nothing_seen(pm):
    pm.facts = 1
    out = C.handle(_ev("sessionStart", session_id="conv-1", is_background_agent=False,
                       composer_mode="agent"))
    assert "Fitzroy" in out["additional_context"]
    assert pm.news_calls == 0       # the user cannot see a notice in Cursor
    pm.facts = 0
    assert C.handle(_ev("sessionStart", session_id="conv-1")) == {}


def test_cursor_never_blocks_a_prompt_even_when_it_fails(pm, monkeypatch, capsys):
    def boom(*a, **k):
        raise OSError("disk full")
    monkeypatch.setattr(C, "_append", boom)
    assert C.handle(_ev("beforeSubmitPrompt", prompt="hi")) == {"continue": True}
    assert "disk full" in capsys.readouterr().err
    assert C.handle({"hook_event_name": "beforeSubmitPrompt", "prompt": "x"}) == {
        "continue": True}                                  # no conversation id


def test_cursor_command_reads_stdin_and_prints_json(pm, monkeypatch, capsys):
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(
        _ev("beforeSubmitPrompt", prompt="I keep bees."))))
    assert H.main(["cursor", "--owner", "Dana"]) == 0
    assert json.loads(capsys.readouterr().out) == {"continue": True}
    assert C.read_spool(C.spool_path("conv-1"))[0] == [
        {"role": "user", "content": "I keep bees."}]
    monkeypatch.setattr(sys, "stdin", io.StringIO("not json"))
    assert H.main(["cursor"]) == 0
    assert json.loads(capsys.readouterr().out) == {}


def test_unreadable_hook_input_is_logged_not_ignored(pm, monkeypatch, capsys, tmp_path):
    # 2026-10-13 (clean-install test on Windows): a transcript path with
    # backslashes in hand-written JSON was skipped without a trace
    monkeypatch.setattr(sys, "stdin", io.StringIO('{"session_id": "x", "transcript_path": "D:\\a\\_temp"}'))
    assert H.main(["session-end", "--owner", "Dana"]) == 0
    assert "not JSON" in capsys.readouterr().err
    log = tmp_path / "state" / "hook.log"
    assert log.exists() and "not JSON" in log.read_text()


def test_windows_plugin_users_are_told_once_how_to_turn_on_the_tools(pm, monkeypatch, tmp_path):
    # 2026-10-13 (Claude Code on native Windows): the plugin's MCP launcher
    # does not start there; the installed sourcedrecall.exe does
    exe_dir = tmp_path / "venv" / "Scripts"
    exe_dir.mkdir(parents=True)
    (exe_dir / "sourcedrecall.exe").write_text("")
    monkeypatch.setattr(sys, "executable", str(exe_dir / "python.exe"))
    monkeypatch.setattr(os, "name", "nt")
    monkeypatch.setenv("CLAUDE_PLUGIN_ROOT", str(tmp_path / "plugin"))
    first = H.session_start({"source": "startup"}, owner="Dana Cole")
    assert "claude mcp add sourcedrecall" in first["systemMessage"]
    assert 'SOURCEDRECALL_OWNER="Dana Cole"' in first["systemMessage"]
    assert str(exe_dir / "sourcedrecall.exe") in first["systemMessage"]
    again = H.session_start({"source": "startup"}, owner="Dana Cole") or {}
    assert "claude mcp add" not in (again.get("systemMessage") or "")


def test_no_windows_note_elsewhere(pm, monkeypatch, tmp_path):
    monkeypatch.setenv("CLAUDE_PLUGIN_ROOT", str(tmp_path / "plugin"))
    out = H.session_start({"source": "startup"}, owner="Dana Cole") or {}
    assert "claude mcp add" not in (out.get("systemMessage") or "")


def test_the_first_message_says_a_session_is_being_stored(pm, monkeypatch, tmp_path):
    # 2026-10-14: "your memory is empty" while the last session was still stored
    from sourcedrecall.paths import jobs_dir
    with open(os.path.join(jobs_dir(), "sourcedrecall-job-x.json"), "w") as f:
        f.write("{}")
    out = H._welcome("claude")
    assert "being stored now" in out["systemMessage"]
    assert not (tmp_path / "state" / ".welcomed").exists()   # the welcome can still come later


# 2026-10-20 (JP's install): a worker killed partway left no trace and its
# session's facts were never stored. Jobs now wait in the state dir and the
# next session start reruns one whose worker is gone.

def _old_job(payload, age=120):
    import time
    from sourcedrecall.paths import jobs_dir
    p = os.path.join(jobs_dir(), "sourcedrecall-job-old.json")
    with open(p, "w") as f:
        json.dump(payload, f)
    os.utime(p, (time.time() - age, time.time() - age))
    return p


def test_the_worker_logs_that_it_started_before_storing(pm, tmp_path, capsys):
    t = _write(tmp_path / "t.jsonl", [{"type": "user", "timestamp": "2026-09-20T09:00:05Z",
                                       "message": {"role": "user", "content": "I live in Fitzroy."}}])
    job = _old_job({"transcript_path": t, "session_id": "abc"})
    assert H.main(["_worker", job]) == 0
    lines = [json.loads(l) for l in capsys.readouterr().out.splitlines()]
    assert lines[0]["session"] == "abc" and "started" in lines[0]
    assert lines[1]["conversation_id"] == "claude-code:abc"
    assert not os.path.exists(job)


def test_a_job_left_by_a_dead_worker_is_rerun_at_session_start(pm, monkeypatch):
    launched = []
    monkeypatch.setattr(H.subprocess, "Popen", lambda cmd, **kw: launched.append(cmd))
    job = _old_job({"transcript_path": "/x.jsonl", "session_id": "abc"})
    H.session_start({"source": "startup"}, owner="Dana Cole")
    assert launched and launched[0][-2:] == ["_worker", job]
    assert json.load(open(job))["tries"] == 1
    launched.clear()
    H.session_start({"source": "startup"}, owner="Dana Cole")   # its age was renewed
    assert not launched


def test_a_new_job_or_one_still_being_stored_is_left_alone(pm, monkeypatch):
    launched = []
    monkeypatch.setattr(H.subprocess, "Popen", lambda cmd, **kw: launched.append(cmd))
    _old_job({"session_id": "new"}, age=5)
    H._rerun_orphans()
    assert not launched
    job = _old_job({"session_id": "busy"})
    with open(job) as held:
        assert H._try_lock(held)                 # a running worker holds it
        H._rerun_orphans()
    assert not launched and json.load(open(job)).get("tries") is None


def test_a_worker_finds_its_job_already_taken(pm, capsys):
    job = _old_job({"transcript_path": "/x.jsonl", "session_id": "abc"})
    with open(job) as held:
        assert H._try_lock(held)
        assert H.main(["_worker", job]) == 0
    assert capsys.readouterr().out == "" and os.path.exists(job) and not pm.ingested


def test_a_job_that_keeps_dying_is_given_up_and_logged(pm, monkeypatch, tmp_path):
    launched = []
    monkeypatch.setattr(H.subprocess, "Popen", lambda cmd, **kw: launched.append(cmd))
    job = _old_job({"transcript_path": "/x.jsonl", "session_id": "abc", "tries": 3})
    H._rerun_orphans()
    assert not launched and not os.path.exists(job)
    assert os.path.exists(job[:-len(".json")] + ".failed")
    log = open(tmp_path / "state" / "hook.log").read()
    assert '"gave_up": true' in log
