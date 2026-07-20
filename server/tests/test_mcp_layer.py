"""The MCP wiring: exactly four tools registered, and a call through the
registered tool round-trips to the substrate."""

import asyncio


def test_four_tools_registered_and_callable(tmp_path, monkeypatch):
    monkeypatch.setenv("RG_MEMORY_STATE", str(tmp_path / "state"))
    monkeypatch.setenv("RG_MEMORY_BROWSER_PORT", "0")
    import rg_memory.mcp_server as srv

    tools = asyncio.run(srv.mcp.list_tools())
    assert {t.name for t in tools} == {"remember", "recall", "update", "forget"}

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
