"""sourcedrecall: local memory for AI agents. It stores the user's own dated
messages; a grammar parser (not a language model) decides what is stored,
whose words they are, and what has gone out of date. MCP server, hooks for
Claude Code, Codex, Gemini CLI and Cursor, and a command line."""

# 2026-10-12 (review 4.5): was a fixed "0.1.0" while the package said 0.5.2
try:
    from importlib.metadata import version as _v
    __version__ = _v("sourcedrecall")
except Exception:
    __version__ = "unknown"
