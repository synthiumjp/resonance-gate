"""Review 2026-10-12 (3.2): what an agent can do through the MCP write and
read tools. A future date would make an agent's message newer than all the
user said; rehydrate returned any number of turns from any project."""
import datetime

import pytest


@pytest.fixture
def pm(tmp_path, monkeypatch):
    monkeypatch.setenv("RG_MEMORY_DIR", str(tmp_path))
    monkeypatch.setenv("RG_NLI", "0")
    monkeypatch.delenv("CLAUDE_PROJECT_DIR", raising=False)
    monkeypatch.delenv("SOURCEDRECALL_SCOPE", raising=False)
    import sourcedrecall.profile_memory as mod
    mod._state.update({"mem": None, "audit_pass": None, "needs_reload": False,
                       "uncached_turns": None, "transcripts": None, "msg_index": None})
    return mod


def test_a_future_date_is_refused_through_mcp(pm):
    import sourcedrecall.mcp_server as m
    later = (datetime.date.today() + datetime.timedelta(days=30)).isoformat()
    with pytest.raises(ValueError, match="future"):
        m.profile_ingest([{"role": "user", "content": "I live in Leeds."}], date=later)


def test_today_and_the_past_are_accepted(pm):
    pm._not_future(None)
    pm._not_future(datetime.date.today().isoformat())
    pm._not_future("2024-01-05")


def _index(pm, monkeypatch, scope):
    turns = [{"role": "human", "text": f"turn {i}"} for i in range(500)]
    idx = {"c1": {"title": "t", "date": "2026-01-01", "scope": scope, "turns": turns}}
    monkeypatch.setattr(pm, "_ensure_transcripts_locked", lambda: idx)


def test_rehydrate_returns_at_most_200_turns(pm, monkeypatch):
    _index(pm, monkeypatch, None)
    out = pm.rehydrate("c1", max_turns=100000)
    assert out["found"] and len(out["turns"]) == 200 and out["truncated"]
    assert len(pm.rehydrate("c1", max_turns=-5)["turns"]) == 1


def test_rehydrate_stays_in_the_project(pm, monkeypatch):
    from sourcedrecall.paths import project_scope
    _index(pm, monkeypatch, project_scope("/work/alpha"))
    assert pm.rehydrate("c1", scope="/work/alpha")["found"]
    assert not pm.rehydrate("c1", scope="/work/beta")["found"]
    assert pm.rehydrate("c1")["found"]          # no project: everything visible
