"""Coding history (2026-10-22, sourcedrecall.coding): a session's failures and
what fixed them, commands that worked, commits and decisions, read from its
tool calls with no model call. Driven with a synthetic Claude Code
transcript in the format real ones use (tool_use / tool_result pairs by id,
is_error, "Exit code N" in the result)."""
import json

import pytest

from sourcedrecall import claude_hooks as H
from sourcedrecall import coding as C


def _line(**kw):
    return json.dumps(kw) + "\n"


def _use(i, name, **inp):
    return _line(type="assistant", timestamp="2026-10-01T10:00:00Z",
                 message={"role": "assistant", "content": [
                     {"type": "tool_use", "id": i, "name": name, "input": inp}]})


def _result(i, text, error=False):
    return _line(type="user", timestamp="2026-10-01T10:00:01Z",
                 message={"role": "user", "content": [
                     {"type": "tool_result", "tool_use_id": i, "content": text,
                      "is_error": error}]})


def _say(role, text):
    return _line(type=role, timestamp="2026-10-01T10:00:02Z", cwd="/w/proj",
                 gitBranch="fix-parser",
                 message={"role": role, "content": text if role == "user"
                          else [{"type": "text", "text": text}]})


def _transcript(path):
    rows = [
        _say("user", "The parser tests fail on empty input, can you fix them?"),
        _use("t1", "Bash", command="ls src"),
        _result("t1", "parser.py\nutil.py"),
        _use("t2", "Bash", command="cd /w/proj && uv run pytest tests/test_parser.py -q"),
        _result("t2", "Exit code 1\n____ test_empty ____\nTraceback (most recent call last):\n"
                      "  File \"src/parser.py\", line 12\nKeyError: 'tokens'\n"
                      "FAILED tests/test_parser.py::test_empty - KeyError: 'tokens'\n"
                      "I live in Narnia.", error=True),
        _say("assistant", "The failure is because parse() reads tokens before checking "
                          "for empty input. I'll guard it."),
        _use("t3", "Edit", file_path="/w/proj/src/parser.py", old_string="a", new_string="b"),
        _result("t3", "The file has been updated."),
        _say("user", "Let's use an early return instead of raising, the CLI expects None."),
        _use("t4", "Bash", command="uv run pytest tests/test_parser.py"),
        _result("t4", "3 passed in 0.12s"),
        _use("t5", "Bash", command="OPENAI_API_KEY=sk-abcdef1234567890abcdef1234567890 "
                                   "uv run python scripts/smoke.py"),
        _result("t5", "Exit code 2\nModuleNotFoundError: No module named 'httpx'", error=True),
        _use("t6", "Bash", command="git commit -m \"Parser: return None on empty input\""),
        _result("t6", "[fix-parser 1a2b3c4] Parser: return None on empty input"),
    ]
    path.write_text("".join(rows))
    return str(path)


def _recs(tmp_path):
    return C.session_records(_transcript(tmp_path / "t.jsonl"), H._classify)


def test_a_fixed_failure_is_one_episode_with_its_error_files_and_reason(tmp_path):
    fixed = [r["text"] for r in _recs(tmp_path) if r["kind"] == "fixed"]
    assert len(fixed) == 1
    t = fixed[0]
    assert "uv run pytest tests/test_parser.py -q" in t
    assert "KeyError: 'tokens'" in t and "src/parser.py" in t
    assert "reads tokens before checking for empty input" in t
    assert "early return" in t           # what the user said meanwhile


def test_tool_output_beyond_the_error_line_is_not_kept(tmp_path):
    assert "Narnia" not in json.dumps(_recs(tmp_path))


def test_exploration_is_not_recorded_and_working_commands_are(tmp_path):
    recs = _recs(tmp_path)
    assert not any("ls src" in r["text"] for r in recs)
    cmds = [r["text"] for r in recs if r["kind"] == "command"]
    assert any("uv run pytest tests/test_parser.py" in c for c in cmds)


def test_a_failure_not_fixed_by_the_end_is_unresolved_and_secrets_are_removed(tmp_path):
    un = [r["text"] for r in _recs(tmp_path) if r["kind"] == "unresolved"]
    assert len(un) == 1 and "No module named 'httpx'" in un[0]
    assert "sk-abcdef" not in json.dumps(_recs(tmp_path))
    assert "`python scripts/smoke.py`" in un[0] or "`uv run python scripts/smoke.py`" in un[0]


def test_a_secret_in_a_command_is_removed():
    assert C._clean_command("curl -H 'Authorization: Bearer abc.def' https://x") == \
        "curl -H 'Authorization: [removed]' https://x"
    assert "hunter2" not in C._clean_command("PGPASSWORD=hunter2 psql -h db")


def test_a_heredoc_commit_message():
    cmd = "git add -A && git commit -m \"$(cat <<'EOF'\nFix the parser\n\nBody\nEOF\n)\""
    assert C._commit_message(cmd) == "Fix the parser"


def test_commits_decisions_and_the_session_are_recorded(tmp_path):
    recs = _recs(tmp_path)
    kinds = {r["kind"] for r in recs}
    assert {"commit", "decision", "session"} <= kinds
    assert any(r["text"] == "committed: Parser: return None on empty input" for r in recs)
    assert any(r["kind"] == "decision" and r["text"].startswith("the user said: Let's use an early return")
               for r in recs)
    s = next(r["text"] for r in recs if r["kind"] == "session")
    assert "fix-parser" in s and "src/parser.py" in s and "parser tests fail" in s


@pytest.mark.parametrize("out,want", [
    ("Traceback (most recent call last):\n  x\nValueError: bad", "ValueError: bad"),
    ("error[E0308]: mismatched types\n --> src/main.rs", "error[E0308]: mismatched types"),
    ("npm ERR! missing script: test", "npm ERR! missing script: test"),
    ("Exit code 1\nsomething odd happened", "something odd happened"),
])
def test_the_error_line(out, want):
    assert C.error_line(out) == want


def test_the_core_of_a_compound_command():
    assert C._core("cd /x && source .venv/bin/activate && FOO=1 pytest -q 2>&1 | tail -5") == "pytest -q"
    assert C.kind_of("cd /x && make test") == "test"
    assert C.kind_of("grep -rn foo .") is None


@pytest.fixture
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("SOURCEDRECALL_STATE", str(tmp_path / "state"))
    monkeypatch.delenv("RG_MEMORY_DIR", raising=False)
    monkeypatch.setenv("RG_NLI", "0")
    import sourcedrecall.profile_memory as pm

    def reset():
        pm._state.update({"mem": None, "audit_pass": None, "needs_reload": False,
                          "uncached_turns": None, "transcripts": None,
                          "episodes_index": None})
        pm._ingest_state.update({"extractor": None, "owner": None})
    reset()
    yield tmp_path
    reset()




def test_stored_at_session_end_searchable_in_its_project_and_forgettable(home):
    pytest.importorskip("stanza", reason="ingest needs the rgx parser (stanza)")
    t = _transcript(home / "t.jsonl")
    out = H.session_end({"transcript_path": t, "session_id": "s1", "cwd": str(home)},
                        owner="Dana Cole", sync=True)
    assert out["coding_records"] >= 5, out
    import sourcedrecall.profile_memory as pm
    r = pm.profile_history("KeyError tokens in the parser test", scope=str(home))
    top = r["results"][0]
    assert top["kind"] == "fixed" and top["date"] == "2026-10-01"
    assert top["session"] == "claude-code:s1"
    assert pm.profile_history("parser", scope=str(home / "elsewhere"))["results"] == []
    # stored again (a resumed session): replaced, not doubled
    H.session_end({"transcript_path": t, "session_id": "s1", "cwd": str(home)},
                  owner="Dana Cole", sync=True)
    assert len(pm._load_episodes()) == out["coding_records"]
    assert pm.profile_forget(top["id"])["forgotten"]
    assert all(x["id"] != top["id"] for x in
               pm.profile_history("KeyError", all_projects=True)["results"])
