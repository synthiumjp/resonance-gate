"""The MCP wiring: the four substrate tools plus the nine profile_* (p2
memory bridge) tools registered, and a call through the registered tool
round-trips to the substrate."""

import asyncio


PROFILE_TOOLS = {"profile_dynamics", "profile_quarantine", "profile_conflicts",
        "profile_recall", "profile_context", "profile_correct",
        "profile_status", "profile_rehydrate", "profile_ingest", "profile_forget", "profile_confirm", "profile_export",
        "profile_check"}


def _server(monkeypatch, tmp_path, legacy):
    import importlib
    monkeypatch.setenv("SOURCEDRECALL_STATE", str(tmp_path / "state"))
    monkeypatch.setenv("SOURCEDRECALL_BROWSER_PORT", "0")
    if legacy:
        monkeypatch.setenv("SOURCEDRECALL_LEGACY_TOOLS", "1")
    else:
        monkeypatch.delenv("SOURCEDRECALL_LEGACY_TOOLS", raising=False)
    import sourcedrecall.mcp_server as srv
    return importlib.reload(srv)


def test_a_new_user_sees_only_the_profile_tools(tmp_path, monkeypatch):
    srv = _server(monkeypatch, tmp_path, legacy=False)
    tools = asyncio.run(srv.mcp.list_tools())
    assert {t.name for t in tools} == PROFILE_TOOLS
    assert srv.service is None


def test_all_tools_registered_and_callable(tmp_path, monkeypatch):
    srv = _server(monkeypatch, tmp_path, legacy=True)
    tools = asyncio.run(srv.mcp.list_tools())
    assert {t.name for t in tools} == {"remember", "recall", "update", "forget"} | PROFILE_TOOLS

    # each tool advertises a description (shown to the calling model)
    assert all(t.description for t in tools)

    # the decorated tool functions are the real implementations
    r = srv.remember("Ada Byron", "works at", "Analytical Engine Co")
    assert r["stored"] is True
    out = srv.recall("Ada Byron")
    assert out["facts"][0]["object"] == "Analytical Engine Co"

    # the MCP call path serializes without error and yields content
    called = asyncio.run(srv.mcp.call_tool("recall", {"query": "Ada Byron"}))
    assert called  # non-empty content (list of blocks or (content, structured))
