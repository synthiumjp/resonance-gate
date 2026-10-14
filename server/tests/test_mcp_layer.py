"""The MCP wiring: the nine profile_* tools registered, the diagnostics only
when asked for."""

import asyncio


# 2026-10-12 (review 3.11): the diagnostics are hidden by default
EXTRA_TOOLS = {"profile_dynamics", "profile_quarantine", "profile_status", "profile_export"}
PROFILE_TOOLS = {"profile_conflicts", "profile_recall", "profile_context", "profile_correct",
                 "profile_rehydrate", "profile_ingest", "profile_forget", "profile_confirm",
                 "profile_check"}


def _server(monkeypatch, tmp_path, all_tools=False):
    import importlib
    monkeypatch.setenv("SOURCEDRECALL_STATE", str(tmp_path / "state"))
    monkeypatch.setenv("SOURCEDRECALL_BROWSER_PORT", "0")
    if all_tools:
        monkeypatch.setenv("SOURCEDRECALL_ALL_TOOLS", "1")
    else:
        monkeypatch.delenv("SOURCEDRECALL_ALL_TOOLS", raising=False)
    import sourcedrecall.mcp_server as srv
    return importlib.reload(srv)


def test_a_new_user_sees_only_the_profile_tools(tmp_path, monkeypatch):
    srv = _server(monkeypatch, tmp_path)
    tools = asyncio.run(srv.mcp.list_tools())
    assert {t.name for t in tools} == PROFILE_TOOLS


def test_the_diagnostics_only_when_asked_for(tmp_path, monkeypatch):
    srv = _server(monkeypatch, tmp_path, all_tools=True)
    tools = asyncio.run(srv.mcp.list_tools())
    assert {t.name for t in tools} == PROFILE_TOOLS | EXTRA_TOOLS
    assert all(t.description for t in tools)


def test_tool_descriptions_are_short(tmp_path, monkeypatch):
    srv = _server(monkeypatch, tmp_path)
    for t in asyncio.run(srv.mcp.list_tools()):
        assert len(t.description) < 450, t.name
